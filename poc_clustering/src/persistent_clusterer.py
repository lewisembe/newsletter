"""Persistent clustering service for incremental Stage 01 integration."""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

import faiss  # type: ignore
import numpy as np

from .embedder import Embedder
from .hashtag_generator import HashtagGenerator

logger = logging.getLogger(__name__)


@dataclass
class ArticleRecord:
    id: int
    title: str
    url: str
    extracted_at: str


class PersistentClusterer:
    """Incremental semantic clustering that persists FAISS index and stats."""

    def __init__(self, config: dict, db, run_date: str):
        self.config = config
        self.db = db
        self.run_date = run_date
        model_cfg = config["model"]
        self.embedder = Embedder(
            model_name=model_cfg["name"],
            cache_dir=model_cfg["cache_dir"],
            device=model_cfg.get("device", "cpu"),
            batch_size=model_cfg.get("batch_size", 100),
        )
        self.embedding_dim = self.embedder.get_embedding_dim()

        state_cfg = config.get("state", {})
        base_dir = Path(config.get("_base_dir", ".")).resolve()
        state_dir = Path(state_cfg.get("directory", "./state"))
        if not state_dir.is_absolute():
            state_dir = (base_dir / state_dir).resolve()
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.state_dir / "faiss_index.bin"

        self.index = None
        self.article_clusters: Dict[int, str] = {}
        self.cluster_stats: Dict[str, Dict[str, float]] = {}

        # Initialize hashtag generator for cluster naming
        hashtag_cfg = config.get("hashtag", {})
        self.hashtag_generator = HashtagGenerator(
            model=hashtag_cfg.get("llm_model", "gpt-4o-mini"),
            temperature=hashtag_cfg.get("temperature", 0.3),
            max_tokens=hashtag_cfg.get("max_tokens", 50),
        )
        self.max_titles_for_context = hashtag_cfg.get("max_titles_for_context", 5)
        self.min_cluster_size_for_name = config.get("clustering", {}).get("min_cluster_size", 2)

    def run(self) -> Dict[str, int]:
        new_articles = self._fetch_new_articles()
        if not new_articles:
            return {}

        self._load_state()
        embeddings = self._embed_articles(new_articles)

        assigned = 0
        new_clusters = 0

        for article, embedding in zip(new_articles, embeddings):
            cluster_id, similarity = self._match_cluster(embedding)
            if cluster_id is None:
                cluster_id = self._create_cluster(article.id)
                new_clusters += 1
            else:
                self._update_cluster_statistics(cluster_id, similarity)

            self.db.assign_cluster_to_url(article.id, cluster_id)
            self.article_clusters[article.id] = cluster_id
            self.db.save_embedding(article.id, embedding.astype(np.float32).tobytes(), self.embedding_dim)
            self._add_vector_to_index(article.id, embedding)
            assigned += 1

        self._persist_index()

        # Generate names for clusters that need them (2+ articles, no name yet)
        clusters_named = self._generate_cluster_names()

        # Save clustering run parameters for traceability
        total_clusters = len(self.cluster_stats)
        config_with_dim = {**self.config, "_embedding_dim": self.embedding_dim}
        self.db.save_clustering_run(
            run_date=self.run_date,
            config=config_with_dim,
            urls_processed=assigned,
            clusters_created=new_clusters,
            total_clusters=total_clusters,
        )

        return {
            "assigned": assigned,
            "new_clusters": new_clusters,
            "total_clusters": total_clusters,
            "index_vectors": int(self.index.ntotal) if self.index else 0,
            "clusters_named": clusters_named,
        }

    def _fetch_new_articles(self) -> List[ArticleRecord]:
        rows = self.db.get_unclustered_content_urls()
        articles = []
        for row in rows:
            articles.append(
                ArticleRecord(
                    id=row["id"],
                    title=row.get("title") or row.get("url") or "",
                    url=row.get("url", ""),
                    extracted_at=row.get("extracted_at", ""),
                )
            )
        return articles

    def _embed_articles(self, articles: List[ArticleRecord]) -> np.ndarray:
        titles = [a.title.strip() or a.url for a in articles]
        return self.embedder.embed(titles, show_progress=False)

    def _load_state(self) -> None:
        if self.index_path.exists():
            self.index = faiss.read_index(str(self.index_path))
        else:
            self.index = faiss.IndexIDMap(faiss.IndexFlatIP(self.embedding_dim))
            self._bootstrap_from_embeddings()

        self.article_clusters = self.db.get_cluster_id_map()
        self.cluster_stats = self.db.get_cluster_stats_map()

    def _bootstrap_from_embeddings(self) -> None:
        records = self.db.load_all_embeddings()
        if not records:
            return
        vectors = []
        ids = []
        for row in records:
            emb = np.frombuffer(row["embedding"], dtype=np.float32)
            if row["dimension"] != self.embedding_dim:
                continue
            vectors.append(emb)
            ids.append(row["url_id"])
        if vectors:
            mat = np.stack(vectors)
            ids_arr = np.array(ids, dtype="int64")
            self.index.add_with_ids(mat, ids_arr)

    def _match_cluster(self, embedding: np.ndarray) -> Tuple[Optional[str], Optional[float]]:
        if self.index is None or self.index.ntotal == 0:
            return None, None

        max_neighbors = self.config["clustering"].get("max_neighbors", 3)
        k = min(max_neighbors, self.index.ntotal)
        if k == 0:
            return None, None

        sims, ids = self.index.search(embedding[np.newaxis, :].astype(np.float32), k)
        best_sim = float(sims[0][0])
        neighbor_id = int(ids[0][0])
        if neighbor_id == -1:
            return None, None

        cluster_id = self.article_clusters.get(neighbor_id)
        if not cluster_id:
            return None, None

        threshold = self._compute_threshold(cluster_id)
        if best_sim >= threshold:
            return cluster_id, best_sim
        return None, None

    def _compute_threshold(self, cluster_id: str) -> float:
        cfg = self.config["clustering"]
        base = cfg.get("similarity_threshold", 0.93)
        if not cfg.get("adaptive_threshold", True):
            return base
        stats = self.cluster_stats.get(cluster_id, {})
        samples = stats.get("similarity_samples", 0)
        if samples < 2:
            return base
        mean = stats.get("similarity_mean", base)
        m2 = stats.get("similarity_m2", 0.0)
        variance = m2 / (samples - 1) if samples > 1 else 0.0
        std = math.sqrt(max(variance, 0.0))
        adaptive_k = cfg.get("adaptive_k", 1.0)
        threshold = mean - adaptive_k * std
        return max(0.5, min(0.99, threshold))

    def _create_cluster(self, centroid_url_id: int) -> str:
        cluster_id = f"{self.run_date.replace('-', '')}_{uuid4().hex[:8]}"
        self.db.create_cluster_record(cluster_id, self.run_date, centroid_url_id, article_count=1, avg_similarity=1.0)
        self.cluster_stats[cluster_id] = {
            "run_date": self.run_date,
            "article_count": 1,
            "avg_similarity": 1.0,
            "similarity_mean": 0.0,
            "similarity_m2": 0.0,
            "similarity_samples": 0,
        }
        return cluster_id

    def _update_cluster_statistics(self, cluster_id: str, similarity: Optional[float]) -> None:
        stats = self.cluster_stats.setdefault(
            cluster_id,
            {
                "run_date": self.run_date,
                "article_count": 0,
                "avg_similarity": 0.0,
                "similarity_mean": 0.0,
                "similarity_m2": 0.0,
                "similarity_samples": 0,
            },
        )
        stats["article_count"] = stats.get("article_count", 0) + 1
        avg_similarity = stats.get("avg_similarity", 0.0)
        if similarity is not None:
            samples = stats.get("similarity_samples", 0) + 1
            mean = stats.get("similarity_mean", 0.0)
            delta = similarity - mean
            new_mean = mean + delta / samples
            delta2 = similarity - new_mean
            m2 = stats.get("similarity_m2", 0.0) + delta * delta2
            stats.update(
                {
                    "similarity_mean": new_mean,
                    "similarity_m2": m2,
                    "similarity_samples": samples,
                }
            )
            avg_similarity = new_mean

        stats["avg_similarity"] = avg_similarity
        self.db.update_cluster_stats(
            cluster_id,
            article_count=stats["article_count"],
            avg_similarity=avg_similarity,
            similarity_mean=stats.get("similarity_mean"),
            similarity_m2=stats.get("similarity_m2"),
            similarity_samples=stats.get("similarity_samples"),
        )

    def _add_vector_to_index(self, article_id: int, embedding: np.ndarray) -> None:
        if self.index is None:
            self.index = faiss.IndexIDMap(faiss.IndexFlatIP(self.embedding_dim))
        vector = embedding.reshape(1, -1).astype(np.float32)
        ids = np.array([article_id], dtype="int64")
        self.index.add_with_ids(vector, ids)

    def _persist_index(self) -> None:
        if self.index is None:
            return
        faiss.write_index(self.index, str(self.index_path))

    def _generate_cluster_names(self) -> int:
        """
        Generate names/hashtags for clusters that don't have one yet.

        Only generates names for clusters with >= min_cluster_size articles.

        Returns:
            Number of clusters that were named
        """
        clusters_without_name = self.db.get_clusters_without_name(
            min_article_count=self.min_cluster_size_for_name
        )

        if not clusters_without_name:
            return 0

        named_count = 0
        for cluster in clusters_without_name:
            cluster_id = cluster["id"]
            titles = self.db.get_cluster_titles(cluster_id, limit=self.max_titles_for_context)

            if not titles:
                continue

            try:
                hashtag = self.hashtag_generator.generate(titles, max_titles=self.max_titles_for_context)
                self.db.update_cluster_name(cluster_id, hashtag)
                logger.info(f"Named cluster {cluster_id} ({cluster['article_count']} articles): {hashtag}")
                named_count += 1
            except Exception as e:
                logger.warning(f"Failed to generate name for cluster {cluster_id}: {e}")

        return named_count
