"""
Cluster Manager - Gestión de clustering con FAISS y threshold adaptativo
"""

import numpy as np
import faiss
from typing import Dict, List, Tuple
from collections import defaultdict


class UnionFind:
    """Disjoint Set Union (DSU) para fusionar clusters"""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        """Find con path compression"""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: int, y: int):
        """Union por rank"""
        px, py = self.find(x), self.find(y)
        if px == py:
            return

        if self.rank[px] < self.rank[py]:
            px, py = py, px
        self.parent[py] = px
        if self.rank[px] == self.rank[py]:
            self.rank[px] += 1


class ClusterManager:
    """Gestiona clustering usando FAISS para búsqueda eficiente"""

    def __init__(
        self,
        embedding_dim: int,
        similarity_threshold: float = 0.75,
        adaptive_threshold: bool = True,
        adaptive_k: float = 0.8,
        max_neighbors: int = 5,
    ):
        """
        Args:
            embedding_dim: Dimensión de los embeddings
            similarity_threshold: Threshold base de similitud (0-1)
            adaptive_threshold: Usar threshold adaptativo μ - k*σ
            adaptive_k: Factor para threshold adaptativo
            max_neighbors: Máximo de vecinos a considerar
        """
        self.embedding_dim = embedding_dim
        self.base_threshold = similarity_threshold
        self.adaptive_threshold = adaptive_threshold
        self.adaptive_k = adaptive_k
        self.max_neighbors = max_neighbors

        # FAISS index (Inner Product para cosine similarity con vectores normalizados)
        self.index = faiss.IndexFlatIP(embedding_dim)

        # Almacenamiento
        self.embeddings = []  # Lista de embeddings
        self.article_ids = []  # IDs de artículos correspondientes
        self.dsu = None  # Se inicializa cuando se conoce N

        # Estadísticas por cluster
        self.cluster_stats = defaultdict(lambda: {"similarities": []})

    def add_articles(
        self, embeddings: np.ndarray, article_ids: List[int]
    ) -> Dict[int, int]:
        """
        Añade artículos y realiza clustering incremental.

        Args:
            embeddings: Array (N, embedding_dim) de embeddings normalizados
            article_ids: Lista de IDs de artículos

        Returns:
            Dict mapping article_id -> cluster_id
        """
        if len(embeddings) != len(article_ids):
            raise ValueError("Mismatch between embeddings and article_ids")

        n = len(article_ids)
        start_idx = len(self.embeddings)

        # Inicializar DSU si es la primera vez
        if self.dsu is None:
            self.dsu = UnionFind(len(article_ids))

        # Añadir nuevos artículos
        for i, (emb, aid) in enumerate(zip(embeddings, article_ids)):
            current_idx = start_idx + i

            if self.index.ntotal == 0:
                # Primer artículo -> crear cluster 0
                self.index.add(np.array([emb], dtype=np.float32))
                self.embeddings.append(emb)
                self.article_ids.append(aid)
                continue

            # Buscar vecinos más cercanos
            k = min(self.max_neighbors, self.index.ntotal)
            similarities, indices = self.index.search(
                np.array([emb], dtype=np.float32), k
            )

            # similarities[0] contiene las similitudes (ya son inner product = cosine sim)
            # indices[0] contiene los índices de los vecinos

            best_similarity = similarities[0][0]
            best_neighbor_idx = indices[0][0]

            # Determinar threshold para el cluster del vecino
            neighbor_cluster = self.dsu.find(best_neighbor_idx)
            threshold = self._get_threshold(neighbor_cluster)

            # Decidir si añadir al cluster o crear uno nuevo
            if best_similarity >= threshold:
                # Añadir al cluster existente
                self.dsu.union(current_idx, best_neighbor_idx)

                # Registrar similitud para estadísticas
                cluster_id = self.dsu.find(current_idx)
                self.cluster_stats[cluster_id]["similarities"].append(
                    best_similarity
                )

            # Añadir al índice FAISS
            self.index.add(np.array([emb], dtype=np.float32))
            self.embeddings.append(emb)
            self.article_ids.append(aid)

        # Extender DSU si es necesario
        if len(self.article_ids) > len(self.dsu.parent):
            old_size = len(self.dsu.parent)
            new_size = len(self.article_ids)
            self.dsu.parent.extend(range(old_size, new_size))
            self.dsu.rank.extend([0] * (new_size - old_size))

        # Construir mapping article_id -> cluster_id
        cluster_map = {}
        for idx, aid in enumerate(self.article_ids):
            cluster_id = self.dsu.find(idx)
            cluster_map[aid] = cluster_id

        return cluster_map

    def _get_threshold(self, cluster_id: int) -> float:
        """
        Calcula threshold para un cluster.

        Args:
            cluster_id: ID del cluster

        Returns:
            Threshold de similitud
        """
        if not self.adaptive_threshold:
            return self.base_threshold

        similarities = self.cluster_stats[cluster_id]["similarities"]

        if len(similarities) < 2:
            # Cluster muy pequeño -> usar threshold base
            return self.base_threshold

        # Calcular μ - k*σ
        mean_sim = np.mean(similarities)
        std_sim = np.std(similarities)
        adaptive_threshold = mean_sim - self.adaptive_k * std_sim

        # Limitar a rango razonable [0.5, 0.95]
        adaptive_threshold = max(0.5, min(0.95, adaptive_threshold))

        return adaptive_threshold

    def get_clusters(self) -> Dict[int, List[int]]:
        """
        Obtiene clusters como dict cluster_id -> [article_ids]

        Returns:
            Dict mapping cluster_id -> lista de article_ids
        """
        clusters = defaultdict(list)
        for idx, aid in enumerate(self.article_ids):
            cluster_id = self.dsu.find(idx)
            clusters[cluster_id].append(aid)
        return dict(clusters)

    def get_cluster_stats(self, cluster_id: int) -> Dict:
        """
        Obtiene estadísticas de un cluster.

        Args:
            cluster_id: ID del cluster

        Returns:
            Dict con size, avg_similarity, std_similarity, threshold
        """
        # Obtener miembros del cluster
        members = []
        for idx in range(len(self.article_ids)):
            if self.dsu.find(idx) == cluster_id:
                members.append(idx)

        if not members:
            return {}

        # Calcular similitudes internas
        similarities = []
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                emb_i = self.embeddings[members[i]]
                emb_j = self.embeddings[members[j]]
                sim = np.dot(emb_i, emb_j)  # Ya normalizados
                similarities.append(sim)

        if not similarities:
            # Solo 1 miembro
            return {
                "size": 1,
                "avg_similarity": 1.0,
                "std_similarity": 0.0,
                "threshold": self.base_threshold,
            }

        return {
            "size": len(members),
            "avg_similarity": float(np.mean(similarities)),
            "std_similarity": float(np.std(similarities)),
            "threshold": self._get_threshold(cluster_id),
        }

    def get_centroid_article(self, cluster_id: int) -> int:
        """
        Obtiene el artículo más cercano al centroide del cluster.

        Args:
            cluster_id: ID del cluster

        Returns:
            article_id del centroide
        """
        # Obtener miembros del cluster
        members = []
        for idx in range(len(self.article_ids)):
            if self.dsu.find(idx) == cluster_id:
                members.append(idx)

        if not members:
            return None

        if len(members) == 1:
            return self.article_ids[members[0]]

        # Calcular centroide
        member_embeddings = [self.embeddings[idx] for idx in members]
        centroid = np.mean(member_embeddings, axis=0)
        centroid = centroid / np.linalg.norm(centroid)  # Normalizar

        # Encontrar miembro más cercano al centroide
        max_sim = -1
        centroid_idx = members[0]
        for idx in members:
            sim = np.dot(self.embeddings[idx], centroid)
            if sim > max_sim:
                max_sim = sim
                centroid_idx = idx

        return self.article_ids[centroid_idx]


if __name__ == "__main__":
    # Test
    print("Testing ClusterManager...")

    # Crear embeddings de prueba (5 artículos, 384 dims)
    np.random.seed(42)
    embedding_dim = 384

    # 2 clusters: artículos 0,1 similares, artículos 2,3 similares, artículo 4 único
    emb0 = np.random.randn(embedding_dim)
    emb1 = emb0 + np.random.randn(embedding_dim) * 0.1  # Muy similar a 0
    emb2 = np.random.randn(embedding_dim)
    emb3 = emb2 + np.random.randn(embedding_dim) * 0.1  # Muy similar a 2
    emb4 = np.random.randn(embedding_dim)  # Diferente

    # Normalizar
    embeddings = np.array([emb0, emb1, emb2, emb3, emb4])
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

    article_ids = [100, 101, 102, 103, 104]

    # Crear cluster manager
    cm = ClusterManager(
        embedding_dim=embedding_dim,
        similarity_threshold=0.75,
        adaptive_threshold=True,
    )

    # Añadir artículos
    cluster_map = cm.add_articles(embeddings, article_ids)

    print("\nCluster assignments:")
    for aid, cid in cluster_map.items():
        print(f"  Article {aid} -> Cluster {cid}")

    # Obtener clusters
    clusters = cm.get_clusters()
    print(f"\nTotal clusters: {len(clusters)}")
    for cid, members in clusters.items():
        print(f"  Cluster {cid}: {members}")
        stats = cm.get_cluster_stats(cid)
        print(f"    Stats: {stats}")

    # Centroide
    for cid in clusters.keys():
        centroid_aid = cm.get_centroid_article(cid)
        print(f"  Cluster {cid} centroid: Article {centroid_aid}")
