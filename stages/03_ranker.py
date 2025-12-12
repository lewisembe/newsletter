#!/usr/bin/env python3
"""
Stage 03: Ranker - Deduplication and Relevance Ranking

This script performs recursive ranking with semantic deduplication on classified URLs
from Stage 02, producing a final ordered list of the most relevant headlines.

Process:
1. Query database for classified URLs within specified date/time range
2. Group URLs by thematic category
3. Apply recursive ranking with deduplication per category (Top N per category)
4. Consolidate category tops and apply global recursive ranking
5. Output ranked list as JSON and CSV files
6. Return list of ranked URL IDs for Stage 04

Key Features:
- Recursive batch processing to handle large URL sets without JSON errors
- Integrated deduplication (LLM identifies and removes semantic duplicates)
- Hybrid ranking (category-level + global) for thematic diversity
- Configurable batch sizes and output limits

Author: Newsletter Utils Team
Created: 2025-11-12
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse
import yaml
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from common.postgres_db import PostgreSQLURLDatabase
from common.llm import LLMClient
from common.logging_utils import setup_rotating_file_logger

# Load environment variables
load_dotenv()
MODEL_RANKER = os.getenv('MODEL_RANKER', 'gpt-4o-mini')
BATCH_SIZE = int(os.getenv('STAGE03_BATCH_SIZE', '30'))
RANKER_TEMPERATURE = float(os.getenv('RANKER_TEMPERATURE', '0.3'))
MAX_HEADLINES = int(os.getenv('MAX_HEADLINES', '25'))

# Level Scoring configuration (alternative ranking method)
RANKER_METHOD = os.getenv('RANKER_METHOD', 'level_scoring')  # 'dual_subset' or 'level_scoring' (recursive deprecated)
RANKER_SCORING_MODE = os.getenv('RANKER_SCORING_MODE', 'top_x_absolute')
RANKER_TOP_X = int(os.getenv('RANKER_TOP_X', str(MAX_HEADLINES)))
RANKER_SCORING_LEVELS = int(os.getenv('RANKER_SCORING_LEVELS', '5'))
RANKER_SCORING_BATCH_SIZE = int(os.getenv('RANKER_SCORING_BATCH_SIZE', '60'))
RANKER_TIEBREAK_BY_RECENCY = os.getenv('RANKER_TIEBREAK_BY_RECENCY', 'true').lower() == 'true'
RANKER_TIEBREAK_BY_SOURCE = os.getenv('RANKER_TIEBREAK_BY_SOURCE', 'true').lower() == 'true'

# Clustering configuration (DEPRECATED - removed 2025-11-15)
# Deduplication now handled in Stage 05 through LLM prompting
# RANKER_ENABLE_CLUSTERING = False
# RANKER_CLUSTERING_MULTIPLIER = 2
# CLUSTERING_BATCH_SIZE = 30
# CLUSTERING_MAX_ITERATIONS = 10
# CLUSTERING_MODEL = 'gpt-4o-mini'

# Dual Subset configuration (new method)
RANKER_NUM_HEADLINES = int(os.getenv('RANKER_NUM_HEADLINES', '20'))
RANKER_NUM_FEATURED = int(os.getenv('RANKER_NUM_FEATURED', '10'))

# Cluster integration configuration (v3.2)
RANKER_ENABLE_CLUSTER_BOOST = os.getenv('RANKER_ENABLE_CLUSTER_BOOST', 'true').lower() == 'true'
RANKER_CLUSTER_BOOST_MAX = float(os.getenv('RANKER_CLUSTER_BOOST_MAX', '1.0'))
RANKER_ENABLE_CLUSTER_DEDUP = os.getenv('RANKER_ENABLE_CLUSTER_DEDUP', 'true').lower() == 'true'

# Sources configuration
SOURCES_CONFIG_PATH = os.getenv('SOURCES_CONFIG_PATH', 'config/sources.yml')

# Setup logging
logger = logging.getLogger(__name__)


def setup_logging(run_date: str, verbose: bool = False) -> str:
    """
    Setup logging for Stage 03.

    Args:
        run_date: Date string in YYYY-MM-DD format
        verbose: Enable verbose logging

    Returns:
        Path to log file
    """
    log_file = setup_rotating_file_logger(
        run_date,
        "03_ranker.log",
        log_level=logging.INFO,
        verbose=verbose,
    )

    logger.info(f"Stage 03 logging initialized: {log_file}")
    return str(log_file)


def load_source_order() -> List[str]:
    """
    Load source domains in order from sources.yml configuration.

    Returns:
        List of source domains in order (e.g., ['ft.com', 'bbc.com', ...])
    """
    sources_file = project_root / SOURCES_CONFIG_PATH

    try:
        with open(sources_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        sources = config.get('sources', [])

        # Extract domains from URLs in the order they appear
        source_domains = []
        for source in sources:
            if source.get('enabled', True):  # Only include enabled sources
                url = source.get('url', '')
                # Extract domain from URL (e.g., https://www.ft.com/ -> ft.com)
                if url:
                    parsed = urlparse(url)
                    domain = parsed.netloc
                    # Remove 'www.' prefix if present
                    if domain.startswith('www.'):
                        domain = domain[4:]
                    source_domains.append(domain)

        logger.info(f"Loaded {len(source_domains)} source domains from {sources_file}")
        return source_domains

    except FileNotFoundError:
        logger.warning(f"Sources config not found: {sources_file}. Using empty source order.")
        return []
    except Exception as e:
        logger.warning(f"Failed to load source order from {sources_file}: {e}")
        return []


def load_categories(db: PostgreSQLURLDatabase) -> List[Dict[str, Any]]:
    """
    Load thematic categories from database.

    Args:
        db: Database instance to query categories from

    Returns:
        List of category dictionaries with id, name, description, examples
    """
    try:
        # Load from database instead of file
        db_categories = db.get_all_categories()

        if not db_categories:
            raise ValueError("No categories found in database")

        # Convert to expected format
        categories = []
        for cat in db_categories:
            categories.append({
                'id': cat['id'],
                'name': cat['name'],
                'description': cat.get('description'),
                'examples': []  # DB doesn't store examples, but stage doesn't use them
            })

        logger.info(f"Loaded {len(categories)} thematic categories from database")
        return categories

    except Exception as e:
        logger.error(f"Failed to load categories: {e}")
        raise


def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split list into chunks of specified size.

    Args:
        items: List to split
        chunk_size: Size of each chunk

    Returns:
        List of chunks
    """
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


# ============================================================================
# CLUSTER INTEGRATION (v3.2)
# ============================================================================

import math


def compute_cluster_boost(cluster_size: int, max_boost: float = 1.0) -> float:
    """
    Compute relevance boost based on cluster size with logarithmic saturation.

    The boost follows a logarithmic curve that saturates:
    - 1 article: 0 boost
    - 2 articles: ~0.30 boost
    - 5 articles: ~0.70 boost
    - 10+ articles: ~1.0 (saturates at max_boost)

    Args:
        cluster_size: Number of articles in the cluster
        max_boost: Maximum boost value (default: 1.0)

    Returns:
        Boost value between 0 and max_boost
    """
    if cluster_size <= 1:
        return 0.0
    # log(cluster_size) / log(10) gives ~1 at size 10
    raw_boost = math.log(cluster_size) / math.log(10)
    return min(max_boost, raw_boost)


def deduplicate_by_cluster(
    urls: List[Dict[str, Any]],
    db: 'PostgreSQLURLDatabase'
) -> tuple[List[Dict[str, Any]], Dict[int, List[int]]]:
    """
    Deduplicate URLs by cluster, keeping the representative with most content.

    For each cluster, selects the URL with the highest word_count as the
    representative, and records the IDs of related URLs.

    Args:
        urls: List of URL dictionaries (must have 'id' and optionally 'cluster_id')
        db: Database instance for querying cluster info

    Returns:
        Tuple of:
        - List of deduplicated URLs (representatives only)
        - Dict mapping representative_id -> [related_url_ids]
    """
    if not urls:
        return [], {}

    # Group URLs by cluster_id
    clusters: Dict[Optional[str], List[Dict[str, Any]]] = {}
    for url in urls:
        cluster_id = url.get('cluster_id')
        if cluster_id not in clusters:
            clusters[cluster_id] = []
        clusters[cluster_id].append(url)

    representatives = []
    related_map: Dict[int, List[int]] = {}

    for cluster_id, cluster_urls in clusters.items():
        if cluster_id is None or len(cluster_urls) == 1:
            # No cluster or single URL - keep as-is
            for url in cluster_urls:
                representatives.append(url)
                related_map[url['id']] = []
        else:
            # Multiple URLs in cluster - select representative by word_count
            sorted_urls = sorted(
                cluster_urls,
                key=lambda u: (u.get('word_count') or 0, u.get('extracted_at', '')),
                reverse=True
            )
            representative = sorted_urls[0]
            related_ids = [u['id'] for u in sorted_urls[1:]]

            representatives.append(representative)
            related_map[representative['id']] = related_ids

            logger.info(
                f"Cluster {cluster_id}: selected representative {representative['id']} "
                f"(word_count={representative.get('word_count', 0)}), "
                f"{len(related_ids)} related URLs"
            )

    logger.info(f"Deduplication: {len(urls)} URLs → {len(representatives)} representatives")
    return representatives, related_map


def apply_cluster_boost_to_urls(
    urls: List[Dict[str, Any]],
    db: 'PostgreSQLURLDatabase',
    max_boost: float = 1.0
) -> List[Dict[str, Any]]:
    """
    Apply cluster boost to URLs based on their cluster size.

    Adds 'cluster_boost' field to each URL dict.

    Args:
        urls: List of URL dictionaries
        db: Database instance
        max_boost: Maximum boost value

    Returns:
        URLs with 'cluster_boost' field added
    """
    boosted_urls = []

    for url in urls:
        url_copy = url.copy()
        cluster_id = url.get('cluster_id')

        if cluster_id:
            cluster_size = db.get_cluster_article_count(cluster_id)
            boost = compute_cluster_boost(cluster_size, max_boost)
            url_copy['cluster_boost'] = boost
            url_copy['cluster_size'] = cluster_size
        else:
            url_copy['cluster_boost'] = 0.0
            url_copy['cluster_size'] = 1

        boosted_urls.append(url_copy)

    # Log boost distribution
    boosted_count = sum(1 for u in boosted_urls if u.get('cluster_boost', 0) > 0)
    if boosted_count > 0:
        avg_boost = sum(u.get('cluster_boost', 0) for u in boosted_urls) / len(boosted_urls)
        max_actual_boost = max(u.get('cluster_boost', 0) for u in boosted_urls)
        logger.info(
            f"Cluster boost applied: {boosted_count}/{len(boosted_urls)} URLs boosted, "
            f"avg={avg_boost:.2f}, max={max_actual_boost:.2f}"
        )

    return boosted_urls


def calculate_majority_category(categories: List[str]) -> str:
    """
    Calculate the majority category from a list of categories.

    Args:
        categories: List of category strings

    Returns:
        Most frequent category, or 'otros' if empty
    """
    if not categories:
        return 'otros'

    from collections import Counter
    category_counts = Counter(categories)
    return category_counts.most_common(1)[0][0]


# DEPRECATED: Clustering functions removed (cluster_batch, cluster_recursive)
# Deduplication is now handled in Stage 05 through LLM prompting
# Removal date: 2025-11-15
# Reason: High cost (~$0.006/run), low benefit (6-15% URL reduction)
#         Stage 05 LLM handles narrative deduplication more effectively


def rank_batch(
    urls: List[Dict[str, Any]],
    llm_client: LLMClient,
    run_date: str,
    depth: int = 0
) -> List[Dict[str, Any]]:
    """
    Rank ALL URLs in a batch using LLM (no size limit).

    Returns complete ranking of all input URLs, not just top N.
    This enables transitive ordering across recursive calls.

    Args:
        urls: List of URL dictionaries
        llm_client: LLM client instance
        run_date: Run date for tracking
        depth: Recursion depth (for logging)

    Returns:
        Ranked list of ALL URLs in order of relevance
    """
    if not urls:
        return []

    # Prepare data for LLM (only essential fields)
    url_data = [
        {
            "id": i,
            "db_id": url['id'],  # Original database ID for tracking
            "title": url['title'],
            "category": url.get('categoria_tematica', 'otros'),
            "source": url['source']
        }
        for i, url in enumerate(urls)
    ]

    # Create prompt
    system_prompt = "Eres un editor de noticias experto que ordena historias por relevancia editorial."

    user_prompt = f"""Analiza estos {len(url_data)} titulares y devuelve TODOS ordenados por importancia (del más al menos relevante).

CRITERIO DE RELEVANCIA:
Prioriza lo que un lector DEBE saber si solo lee estas noticias. Un lector que consulta únicamente estas URLs y no lee otros medios.

Valora especialmente:
- Urgencia y actualidad (breaking news, eventos en desarrollo)
- Impacto social, político o económico significativo
- Novedad y sorpresa (anuncios importantes, giros inesperados)
- Relevancia temática (continuación de historias importantes)

CONSIDERA (como señal adicional, no exclusiva):
- Si múltiples fuentes cubren el mismo tema, PUEDE ser señal de relevancia
- Pero también puede ser ruido mediático sin valor
- Usa tu criterio editorial

TITULARES:
{json.dumps(url_data, ensure_ascii=False, indent=2)}

OUTPUT (JSON estricto):
{{
  "ranked": [
    {{"id": <int>, "score": <int 0-100>}}
  ]
}}

IMPORTANTE:
- Devuelve EXACTAMENTE {len(urls)} resultados
- Ordenados por score descendente
- JSON sin razones (solo id y score)"""

    try:
        logger.debug(f"Ranking batch of {len(urls)} URLs (depth={depth})")

        response = llm_client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=MODEL_RANKER,
            temperature=RANKER_TEMPERATURE,
            max_tokens=2000,  # Reduced from 3000 (no reasons)
            response_format={"type": "json_object"},
            stage="03",
            operation=f"rank_batch_d{depth}",
            run_date=run_date
        )

        # Parse response
        result = json.loads(response)
        ranked = result.get('ranked', [])

        if not ranked:
            logger.warning(f"Empty ranking result for batch (depth={depth})")
            return urls  # Fallback: return all in original order

        # Validate and map back to original URLs
        ranked_urls = []
        for item in ranked:
            url_id = item.get('id')
            score = item.get('score', 0)
            reason = item.get('reason', '')

            if url_id is None or url_id >= len(urls):
                logger.warning(f"Invalid ID in ranking result: {url_id}")
                continue

            url_dict = urls[url_id].copy()
            url_dict['rank_score'] = score
            url_dict['rank_reason'] = reason
            ranked_urls.append(url_dict)

        logger.info(f"Batch ranked: {len(urls)} URLs → {len(ranked_urls)} ranked (depth={depth})")
        return ranked_urls

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response (depth={depth}): {e}")
        logger.error(f"Response was: {response[:500]}")
        # Fallback: return all URLs without ranking
        return urls

    except Exception as e:
        logger.error(f"Ranking batch failed (depth={depth}): {e}")
        return urls


def rank_recursive(
    urls: List[Dict[str, Any]],
    llm_client: LLMClient,
    run_date: str,
    depth: int = 0
) -> List[Dict[str, Any]]:
    """
    Recursively rank ALL URLs to achieve transitive ordering.

    No size reduction during recursion - only at the final step.
    This ensures complete ordering of all input URLs.

    Args:
        urls: List of URL dictionaries to rank
        llm_client: LLM client instance
        run_date: Run date for tracking
        depth: Current recursion depth (for logging)

    Returns:
        Complete ranked list of ALL URLs (ordered 1 → N)
    """
    if not urls:
        return []

    logger.info(f"Recursive ranking: {len(urls)} URLs at depth {depth}")

    # Base case: small enough to rank directly
    if len(urls) <= BATCH_SIZE:
        ranked = rank_batch(urls, llm_client, run_date, depth)
        logger.info(f"Base case: ranked {len(ranked)} URLs (depth={depth})")
        return ranked

    # Recursive case: split into batches, rank each, consolidate, and recurse
    batches = chunk_list(urls, BATCH_SIZE)
    logger.info(f"Split into {len(batches)} batches for ranking (depth={depth})")

    # Rank each batch independently (ALL URLs, no limit)
    ranked_batches = []
    for i, batch in enumerate(batches):
        logger.info(f"Ranking batch {i+1}/{len(batches)} ({len(batch)} URLs) at depth {depth}")
        ranked_batch = rank_batch(batch, llm_client, run_date, depth)
        ranked_batches.append(ranked_batch)

    # Consolidate results (merge all ranked batches)
    consolidated = []
    for batch in ranked_batches:
        consolidated.extend(batch)

    logger.info(f"Consolidated {len(consolidated)} URLs from {len(batches)} batches (depth={depth})")

    # Recurse on consolidated results to achieve global ordering
    return rank_recursive(consolidated, llm_client, run_date, depth + 1)


def classify_batch_by_level(
    urls: List[Dict[str, Any]],
    llm_client: LLMClient,
    run_date: str,
    depth: int = 0
) -> List[Dict[str, Any]]:
    """
    Classify URLs by relevance level (1-5) using LLM with absolute criteria.

    Level 5: Maximum relevance - Reader MUST NOT miss this
    Level 4: High relevance - Should read for complete context
    Level 3: Medium relevance - Interesting but not essential
    Level 2: Low relevance - Optional
    Level 1: Minimum relevance - Dispensable

    Args:
        urls: List of URL dictionaries to classify
        llm_client: LLM client instance
        run_date: Run date for tracking
        depth: Batch number (for logging)

    Returns:
        List of URL dictionaries with 'relevance_level' field added
    """
    if not urls:
        return []

    # Prepare data for LLM (minimal fields)
    url_data = [
        {
            "id": i,
            "db_id": url['id'],
            "title": url['title']
        }
        for i, url in enumerate(urls)
    ]

    system_prompt = """Eres un editor de noticias experto. Tu trabajo es clasificar artículos pensando en un lector que SOLO leerá las noticias que tú selecciones como más relevantes.

CRITERIO FUNDAMENTAL:
"Si el lector solo lee las noticias que clasifiques como Nivel 5, ¿se escapará algo importante del día?"

Clasifica en 5 niveles de relevancia:

Nivel 5: Máxima relevancia - DEBE LEER
  - Si el lector NO lee esto, se perderá algo crucial del día
  - Breaking news crítica (guerra, crisis, atentados)
  - Eventos con alto impacto inmediato (político, económico, social)
  - Desarrollos urgentes que cambian el contexto actual

Nivel 4: Alta relevancia - DEBERÍA LEER
  - Noticias importantes que completan el panorama del día
  - Análisis profundo de temas relevantes
  - Eventos significativos pero no urgentes

Nivel 3: Relevancia media - PUEDE LEER
  - Noticias interesantes pero no esenciales
  - Cobertura de eventos secundarios
  - Contexto adicional útil

Nivel 2: Relevancia baja - OPCIONAL
  - Noticias de nicho o seguimiento
  - No afecta comprensión del día

Nivel 1: Mínima relevancia - PRESCINDIBLE
  - Contenido de relleno
  - El lector no perdería nada si lo omite

IMPORTANTE:
- Clasifica según criterio ABSOLUTO (no fuerces distribución)
- Piensa: "¿Qué NECESITA saber el lector sobre el mundo HOY?"
- Sé exigente con Nivel 5: solo lo verdaderamente imprescindible"""

    user_prompt = f"""Clasifica estos {len(url_data)} artículos según el criterio editorial:

"El lector solo leerá lo que tú marques como más relevante. No puede escapársele nada importante del día."

Artículos:
{json.dumps(url_data, ensure_ascii=False, indent=2)}

Responde SOLO JSON (sin explicaciones):
{{
  "classifications": [
    {{"id": 0, "level": 5}},
    {{"id": 1, "level": 3}},
    ...
  ]
}}

IMPORTANTE: Devuelve EXACTAMENTE {len(url_data)} clasificaciones."""

    try:
        logger.debug(f"Classifying batch of {len(urls)} URLs by level (batch={depth})")

        response = llm_client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=MODEL_RANKER,
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"},
            stage="03",
            operation=f"classify_level_b{depth}",
            run_date=run_date
        )

        result = json.loads(response)
        classifications = result.get('classifications', [])

        if len(classifications) != len(urls):
            logger.warning(
                f"Classification count mismatch: expected {len(urls)}, got {len(classifications)} (batch={depth})"
            )

        # Map classifications back to URLs
        classified_urls = []
        for item in classifications:
            url_id = item.get('id')
            level = item.get('level', 3)  # Default to medium if missing

            if url_id is None or url_id >= len(urls):
                logger.warning(f"Invalid ID in classification: {url_id} (batch={depth})")
                continue

            url_dict = urls[url_id].copy()
            url_dict['relevance_level'] = level
            classified_urls.append(url_dict)

        # Add URLs that weren't classified (fallback)
        classified_ids = {item.get('id') for item in classifications if item.get('id') is not None}
        for i, url in enumerate(urls):
            if i not in classified_ids:
                logger.warning(f"URL {i} (db_id={url['id']}) not classified, defaulting to level 3")
                url_dict = url.copy()
                url_dict['relevance_level'] = 3
                classified_urls.append(url_dict)

        logger.info(
            f"Batch classified (batch={depth}): {len(urls)} URLs → "
            f"{len(classified_urls)} with relevance levels"
        )

        return classified_urls

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse classification JSON (batch={depth}): {e}")
        logger.error(f"Response was: {response[:500]}")
        # Fallback: assign level 3 to all
        return [
            {**url, 'relevance_level': 3}
            for url in urls
        ]

    except Exception as e:
        logger.error(f"Classification batch failed (batch={depth}): {e}")
        # Fallback: assign level 3 to all
        return [
            {**url, 'relevance_level': 3}
            for url in urls
        ]


def rerank_top_tier(
    candidates: List[Dict[str, Any]],
    top_x: int,
    llm_client: LLMClient,
    run_date: str
) -> List[Dict[str, Any]]:
    """
    Re-rank top tier candidates to select exactly top_x most imprescindible articles.

    Used when more than top_x URLs are classified as Level 5.

    Args:
        candidates: List of Level 5 URL dictionaries
        top_x: Number of URLs to select
        llm_client: LLM client instance
        run_date: Run date for tracking

    Returns:
        List of exactly top_x URLs, ordered by importance
    """
    if len(candidates) <= top_x:
        return candidates

    logger.info(f"Re-ranking {len(candidates)} Level 5 candidates to select top {top_x}")

    # Prepare data
    url_data = [
        {
            "id": i,
            "db_id": url['id'],
            "title": url['title']
        }
        for i, url in enumerate(candidates)
    ]

    system_prompt = f"""Eres un editor de noticias que debe seleccionar exactamente {top_x} artículos para un lector ocupado.

CRITERIO:
"El lector SOLO leerá estos {top_x} artículos. Con solo estos, debe entender lo esencial del día sin perderse nada crítico."

Ordena por:
1. IMPRESCINDIBILIDAD: ¿Qué le faltaría al lector si no lee esto?
2. URGENCIA: ¿Está sucediendo ahora? ¿Requiere atención inmediata?
3. IMPACTO: ¿Afecta a muchas personas? ¿Cambia el contexto actual?
4. NOVEDAD: ¿Es sorpresivo? ¿Inesperado?

Asegura DIVERSIDAD temática: mejor cubrir 5 temas importantes que {top_x} variaciones del mismo tema."""

    user_prompt = f"""Tienes {len(candidates)} artículos marcados como máxima relevancia.

Selecciona los {top_x} MÁS imprescindibles para un lector que SOLO leerá esos.

Criterio: "Con estos {top_x}, el lector debe captar lo esencial del día."

Candidatos:
{json.dumps(url_data, ensure_ascii=False, indent=2)}

Responde JSON ordenado (más imprescindible primero):
{{
  "top_{top_x}": [123, 456, 789, ...]
}}

IMPORTANTE: Devuelve EXACTAMENTE {top_x} db_ids (no el índice id)."""

    try:
        response = llm_client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=MODEL_RANKER,
            temperature=0.3,
            max_tokens=1000,
            response_format={"type": "json_object"},
            stage="03",
            operation="rerank_top_tier",
            run_date=run_date
        )

        result = json.loads(response)
        selected_db_ids = result.get(f'top_{top_x}', [])

        if len(selected_db_ids) != top_x:
            logger.warning(
                f"Re-ranking returned {len(selected_db_ids)} IDs, expected {top_x}. "
                f"Using what we got or truncating."
            )

        # Map db_ids back to URLs
        db_id_to_url = {url['id']: url for url in candidates}
        selected_urls = []

        for db_id in selected_db_ids[:top_x]:
            if db_id in db_id_to_url:
                selected_urls.append(db_id_to_url[db_id])
            else:
                logger.warning(f"db_id {db_id} from re-ranking not found in candidates")

        # If we didn't get enough, fill with remaining candidates sorted by original order
        if len(selected_urls) < top_x:
            selected_db_ids_set = set(selected_db_ids)
            remaining = [url for url in candidates if url['id'] not in selected_db_ids_set]
            selected_urls.extend(remaining[:top_x - len(selected_urls)])

        logger.info(f"Re-ranking complete: selected {len(selected_urls)} top tier URLs")
        return selected_urls

    except Exception as e:
        logger.error(f"Re-ranking failed: {e}. Returning first {top_x} candidates.")
        return candidates[:top_x]


# ============================================================================
# DUAL SUBSET SELECTION (New ranking method)
# ============================================================================

def classify_batch_with_3_levels(
    urls: List[Dict[str, Any]],
    batch_idx: int,
    llm_client: LLMClient,
    run_date: str
) -> List[Dict[str, Any]]:
    """
    Classify a batch of URLs into 3 relevance levels.

    Level 3 (Alto): Critical news - must not miss
    Level 2 (Medio): Important news - should read
    Level 1 (Bajo): Relevant news - nice to know

    Args:
        urls: List of URL dicts (max 20 recommended)
        batch_idx: Batch index for logging
        llm_client: LLM client
        run_date: Run date

    Returns:
        List of URLs with 'relevance_level' field (1-3)
    """
    url_data = [
        {
            "id": i,
            "db_id": url['id'],
            "title": url['title'],
            "category": url.get('categoria_tematica', 'otros'),
            "source": url['source']
        }
        for i, url in enumerate(urls)
    ]

    system_prompt = """Eres un editor de noticias que clasifica artículos por relevancia editorial.

CRITERIO DE CLASIFICACIÓN (3 niveles):

Nivel 3 (Alto - CRÍTICO):
  - Breaking news de impacto inmediato
  - Eventos que cambian el contexto actual
  - Información imprescindible para entender el día
  - El lector NO puede perdérselo

Nivel 2 (Medio - IMPORTANTE):
  - Noticias relevantes con impacto significativo
  - Desarrollos importantes pero no urgentes
  - Contexto valioso para el lector informado
  - Debería leerlo si tiene tiempo

Nivel 1 (Bajo - RELEVANTE):
  - Noticias de interés general
  - Seguimiento de temas conocidos
  - Información complementaria
  - Puede leerlo si le interesa el tema

IMPORTANTE:
- Clasifica según criterio ABSOLUTO (no distribuyas niveles uniformemente)
- Piensa: "¿Qué tan crítico es que el lector sepa esto HOY?"
- Sé exigente con Nivel 3: solo lo verdaderamente imprescindible
- La mayoría de noticias suelen ser Nivel 2 o Nivel 1"""

    user_prompt = f"""Clasifica estos {len(url_data)} artículos en 3 niveles de relevancia editorial.

ARTÍCULOS:
{json.dumps(url_data, ensure_ascii=False, indent=2)}

Responde SOLO JSON (sin explicaciones):
{{
  "classifications": [
    {{"id": 0, "level": 3}},
    {{"id": 1, "level": 2}},
    ...
  ]
}}

IMPORTANTE: Devuelve EXACTAMENTE {len(url_data)} clasificaciones con levels 1, 2, o 3."""

    try:
        logger.info(f"Classifying batch {batch_idx}: {len(urls)} URLs into 3 relevance levels")

        response = llm_client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=MODEL_RANKER,
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"},
            stage="03",
            operation=f"classify_3levels_b{batch_idx}",
            run_date=run_date
        )

        result = json.loads(response)
        classifications = result.get('classifications', [])

        if len(classifications) != len(urls):
            logger.warning(
                f"Batch {batch_idx}: Classification count mismatch - "
                f"expected {len(urls)}, got {len(classifications)}"
            )

        # Map classifications back to URLs
        classified_urls = []
        for item in classifications:
            url_id = item.get('id')
            level = item.get('level', 2)  # Default to medio

            if url_id is None or url_id >= len(urls):
                logger.warning(f"Batch {batch_idx}: Invalid ID {url_id}")
                continue

            url_dict = urls[url_id].copy()
            url_dict['relevance_level'] = level
            classified_urls.append(url_dict)

        # Add unclassified URLs with default level
        classified_ids = {item.get('id') for item in classifications if item.get('id') is not None}
        for i, url in enumerate(urls):
            if i not in classified_ids:
                logger.warning(f"Batch {batch_idx}: URL {i} not classified, defaulting to level 2")
                url_dict = url.copy()
                url_dict['relevance_level'] = 2
                classified_urls.append(url_dict)

        # Count distribution
        level_counts = {}
        for url in classified_urls:
            level = url.get('relevance_level', 2)
            level_counts[level] = level_counts.get(level, 0) + 1

        logger.info(
            f"Batch {batch_idx} classified: {len(classified_urls)} URLs - "
            f"L3:{level_counts.get(3,0)}, L2:{level_counts.get(2,0)}, L1:{level_counts.get(1,0)}"
        )

        return classified_urls

    except Exception as e:
        logger.error(f"Batch {batch_idx} classification failed: {e}")
        # Fallback: assign level 2 to all
        return [
            {**url, 'relevance_level': 2}
            for url in urls
        ]


def select_final_subsets_single_round(
    candidates: List[Dict[str, Any]],
    num_headlines: int,
    num_featured: int,
    llm_client: LLMClient,
    run_date: str
) -> Dict[str, Any]:
    """
    Single-round selection of N headlines and M featured from candidates.
    Used when candidates <= batch_size (~20).

    Args:
        candidates: Pre-filtered candidate URLs with relevance_level
        num_headlines: Number of headlines to select
        num_featured: Number of featured to select
        llm_client: LLM client
        run_date: Run date

    Returns:
        Dict with 'headlines' (URL dicts) and 'featured' (ID list)
    """
    url_data = [
        {
            "db_id": url['id'],
            "title": url['title'],
            "category": url.get('categoria_tematica', 'otros'),
            "source": url['source'],
            "relevance_level": url.get('relevance_level', 2)
        }
        for url in candidates
    ]

    system_prompt = f"""Eres un editor de noticias que selecciona artículos para un newsletter diario.

TAREA: Seleccionar {num_headlines} HEADLINES y {num_featured} FEATURED para hoy.

DEFINICIONES:
1. HEADLINES ({num_headlines}): Artículos que el lector debe conocer del día
   - Se mostrarán como lista con títulos y links
   - Cubren panorama completo del día

2. FEATURED ({num_featured}): Subset de HEADLINES con comentario editorial
   - Los {num_featured} MÁS importantes de los {num_headlines}
   - Recibirán análisis en profundidad
   - DEBEN estar incluidos en HEADLINES

CRITERIOS:
- Prioriza artículos con relevance_level más alto (3 > 2 > 1)
- FEATURED debe ser subset de HEADLINES
- Asegura diversidad temática en FEATURED
- Con FEATURED el lector capta lo esencial del día"""

    user_prompt = f"""Selecciona artículos para el newsletter de hoy.

Candidatos ({len(candidates)} artículos pre-filtrados):
{json.dumps(url_data, ensure_ascii=False, indent=2)}

TAREA:
1. Selecciona {num_headlines} HEADLINES (IDs de artículos a mostrar)
2. De esos {num_headlines}, selecciona {num_featured} FEATURED (IDs para análisis profundo)

Responde SOLO JSON:
{{
  "headlines": [db_id1, db_id2, ..., db_id{num_headlines}],
  "featured": [db_id1, db_id3, ..., db_id{num_featured}]
}}

IMPORTANTE:
- headlines: EXACTAMENTE {num_headlines} db_ids
- featured: EXACTAMENTE {num_featured} db_ids
- Todos los featured DEBEN estar en headlines
- Sin duplicados"""

    try:
        response = llm_client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=MODEL_RANKER,
            temperature=0.3,
            max_tokens=1000,
            response_format={"type": "json_object"},
            stage="03",
            operation="select_subsets_single",
            run_date=run_date
        )

        result = json.loads(response)
        headlines_ids = result.get('headlines', [])
        featured_ids = result.get('featured', [])

        # CRITICAL: Deduplicate IDs (LLM may return duplicates)
        headlines_ids_unique = []
        seen_headlines = set()
        for hid in headlines_ids:
            if hid not in seen_headlines:
                headlines_ids_unique.append(hid)
                seen_headlines.add(hid)
        if len(headlines_ids) != len(headlines_ids_unique):
            logger.warning(f"LLM returned {len(headlines_ids) - len(headlines_ids_unique)} duplicate headlines, removed")
        headlines_ids = headlines_ids_unique

        featured_ids_unique = []
        seen_featured = set()
        for fid in featured_ids:
            if fid not in seen_featured:
                featured_ids_unique.append(fid)
                seen_featured.add(fid)
        if len(featured_ids) != len(featured_ids_unique):
            logger.warning(f"LLM returned {len(featured_ids) - len(featured_ids_unique)} duplicate featured, removed")
        featured_ids = featured_ids_unique

        # Validation
        if len(headlines_ids) != num_headlines:
            logger.warning(f"Expected {num_headlines} headlines, got {len(headlines_ids)}")
        if len(featured_ids) != num_featured:
            logger.warning(f"Expected {num_featured} featured, got {len(featured_ids)}")

        # Validate subset relationship
        featured_set = set(featured_ids)
        headlines_set = set(headlines_ids)
        if not featured_set.issubset(headlines_set):
            logger.warning("Featured not subset of headlines, filtering...")
            featured_ids = [fid for fid in featured_ids if fid in headlines_set]

        # Map IDs to URL objects
        id_to_url = {url['id']: url for url in candidates}
        headlines_urls = [id_to_url[db_id] for db_id in headlines_ids if db_id in id_to_url]

        logger.info(f"Single-round selection: {len(headlines_urls)} headlines, {len(featured_ids)} featured")

        return {
            'headlines': headlines_urls,
            'featured': featured_ids
        }

    except Exception as e:
        logger.error(f"Single-round selection failed: {e}")
        # Fallback: take top N by relevance
        headlines_urls = candidates[:num_headlines]
        featured_ids = [url['id'] for url in headlines_urls[:num_featured]]
        return {
            'headlines': headlines_urls,
            'featured': featured_ids
        }


def select_final_subsets_multi_round(
    candidates: List[Dict[str, Any]],
    num_headlines: int,
    num_featured: int,
    batch_size: int,
    llm_client: LLMClient,
    run_date: str
) -> Dict[str, Any]:
    """
    Multi-round tournament selection for large candidate pools.
    Processes in batches to maintain LLM focus.

    Args:
        candidates: All candidate URLs with relevance_level
        num_headlines: Final number of headlines
        num_featured: Final number of featured
        batch_size: URLs per batch
        llm_client: LLM client
        run_date: Run date

    Returns:
        Dict with 'headlines' (URL dicts) and 'featured' (ID list)
    """
    logger.info(f"Multi-round selection: {len(candidates)} candidates → {num_headlines} headlines")

    # Round 1: Process in batches, select top 50% from each batch
    round1_survivors = []
    num_batches = (len(candidates) + batch_size - 1) // batch_size

    for batch_idx in range(num_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(candidates))
        batch = candidates[start_idx:end_idx]

        # Select top 50% from this batch
        batch_select_count = max(1, len(batch) // 2)

        logger.info(f"Round 1, Batch {batch_idx+1}/{num_batches}: selecting {batch_select_count}/{len(batch)}")

        # Simple relevance-based selection for intermediate rounds
        batch_sorted = sorted(
            batch,
            key=lambda x: (-x.get('relevance_level', 2), x.get('extracted_at', '')),
            reverse=True
        )
        round1_survivors.extend(batch_sorted[:batch_select_count])

    logger.info(f"Round 1 complete: {len(round1_survivors)} survivors")

    # If still too many for single round, do another round
    if len(round1_survivors) > batch_size:
        logger.info(f"Round 2: Further reducing {len(round1_survivors)} → ~{num_headlines*2}")
        round1_survivors.sort(
            key=lambda x: (-x.get('relevance_level', 2), x.get('extracted_at', '')),
            reverse=True
        )
        round1_survivors = round1_survivors[:num_headlines * 2]

    # Final round: Use LLM to select exact N headlines and M featured
    logger.info(f"Final round: Selecting {num_headlines} headlines + {num_featured} featured from {len(round1_survivors)}")

    return select_final_subsets_single_round(
        candidates=round1_survivors,
        num_headlines=num_headlines,
        num_featured=num_featured,
        llm_client=llm_client,
        run_date=run_date
    )


def select_dual_subsets(
    clusters: List[Dict[str, Any]],
    num_headlines: int,
    num_featured: int,
    llm_client: LLMClient,
    run_date: str,
    batch_size: int = 20
) -> Dict[str, Any]:
    """
    Select two subsets from clusters with 3-level relevance scoring:
    - headlines: N URLs to show reader
    - featured: M URLs to extract full content (M ⊂ N)
    Each URL gets relevance_level: 3 (alto), 2 (medio), 1 (bajo)

    Args:
        clusters: List of cluster dicts with representatives
        num_headlines: Number of headlines to select (N)
        num_featured: Number of featured articles to select (M)
        llm_client: LLM client instance
        run_date: Run date for tracking
        batch_size: Maximum URLs per LLM call (default: 20)

    Returns:
        Dict with 'headlines' (with relevance_level) and 'featured' ID arrays
    """
    representatives = [cluster['representative'] for cluster in clusters]

    logger.info(f"Starting dual subset selection with 3-level relevance")
    logger.info(f"Input: {len(representatives)} URLs, batch_size: {batch_size}")
    logger.info(f"Target: {num_headlines} headlines, {num_featured} featured")

    # PASO 1: Classify all URLs in batches with 3 relevance levels
    all_classified = []
    num_batches = (len(representatives) + batch_size - 1) // batch_size

    for batch_idx in range(num_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(representatives))
        batch = representatives[start_idx:end_idx]

        logger.info(f"Processing batch {batch_idx+1}/{num_batches} ({len(batch)} URLs)")

        classified_batch = classify_batch_with_3_levels(
            urls=batch,
            batch_idx=batch_idx + 1,
            llm_client=llm_client,
            run_date=run_date
        )

        all_classified.extend(classified_batch)

    logger.info(f"All batches classified: {len(all_classified)} URLs total")

    # PASO 2: Sort by relevance level (Level 3 first, then 2, then 1)
    # Within same level, sort by recency
    all_classified.sort(
        key=lambda x: (
            -x.get('relevance_level', 2),  # Higher level first
            x.get('extracted_at', '')  # Most recent first within level
        ),
        reverse=True
    )

    # PASO 3: Pre-filter candidates for selection
    # Take top candidates (2x headlines) to give LLM good pool without overwhelming context
    max_candidates = min(len(all_classified), num_headlines * 2)
    candidates = all_classified[:max_candidates]

    logger.info(f"PASO 2: Pre-filtered to {len(candidates)} candidates for final selection")

    # PASO 3: Select N headlines and M featured using LLM with focused context
    # If candidates > batch_size, we need to do multi-round selection
    if len(candidates) <= batch_size:
        # Single round selection
        logger.info(f"PASO 3: Single-round selection ({len(candidates)} candidates)")
        selection_result = select_final_subsets_single_round(
            candidates=candidates,
            num_headlines=num_headlines,
            num_featured=num_featured,
            llm_client=llm_client,
            run_date=run_date
        )
        headlines_urls = selection_result['headlines']
        featured_ids = selection_result['featured']
    else:
        # Multi-round selection in batches
        logger.info(f"PASO 3: Multi-round selection ({len(candidates)} candidates, batch_size={batch_size})")
        selection_result = select_final_subsets_multi_round(
            candidates=candidates,
            num_headlines=num_headlines,
            num_featured=num_featured,
            batch_size=batch_size,
            llm_client=llm_client,
            run_date=run_date
        )
        headlines_urls = selection_result['headlines']
        featured_ids = selection_result['featured']

    headlines_ids = [url['id'] for url in headlines_urls]

    # Log distribution
    level_dist_headlines = {}
    for url in headlines_urls:
        level = url.get('relevance_level', 2)
        level_dist_headlines[level] = level_dist_headlines.get(level, 0) + 1

    level_dist_featured = {}
    for url in headlines_urls:
        if url['id'] in featured_ids:
            level = url.get('relevance_level', 2)
            level_dist_featured[level] = level_dist_featured.get(level, 0) + 1

    logger.info(
        f"Headlines distribution ({num_headlines}): "
        f"L3:{level_dist_headlines.get(3,0)}, "
        f"L2:{level_dist_headlines.get(2,0)}, "
        f"L1:{level_dist_headlines.get(1,0)}"
    )
    logger.info(
        f"Featured distribution ({num_featured}): "
        f"L3:{level_dist_featured.get(3,0)}, "
        f"L2:{level_dist_featured.get(2,0)}, "
        f"L1:{level_dist_featured.get(1,0)}"
    )

    # Return with classified URLs (includes relevance_level)
    return {
        'headlines': headlines_ids,
        'featured': featured_ids,
        'classified_urls': all_classified  # Include all classified for build_dual_output
    }


def build_dual_output(
    clusters: List[Dict[str, Any]],
    selection: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build dual subset output from clusters and LLM selection with relevance levels.

    Args:
        clusters: List of cluster dicts
        selection: Dict with 'headlines', 'featured' ID arrays, and 'classified_urls'

    Returns:
        Output dict with headlines array (with relevance_level) and featured ID array
    """
    headlines_ids = selection['headlines']
    featured_ids_set = set(selection['featured'])
    classified_urls = selection.get('classified_urls', [])

    # Build cluster lookup
    cluster_lookup = {
        cluster['representative']['id']: cluster
        for cluster in clusters
    }

    # Build URL lookup with relevance levels
    url_relevance_lookup = {
        url['id']: url.get('relevance_level', 2)
        for url in classified_urls
    }

    # Build headlines output
    headlines = []
    for db_id in headlines_ids:
        if db_id not in cluster_lookup:
            logger.warning(f"ID {db_id} from selection not found in clusters")
            continue

        cluster = cluster_lookup[db_id]
        representative = cluster['representative']

        # Build entry with related articles and relevance level
        entry = representative.copy()
        entry['is_featured'] = db_id in featured_ids_set
        entry['relevance_level'] = url_relevance_lookup.get(db_id, 2)  # Add relevance level
        entry['related_articles'] = [
            {
                'id': rel['id'],
                'url': rel['url'],
                'title': rel['title'],
                'source': rel['source'],
                'relation_reason': f"Covers same event: {cluster.get('event_description', 'related')}"
            }
            for rel in cluster.get('related_articles', [])
        ]

        headlines.append(entry)

    # Count relevance distribution
    level_counts = {}
    for h in headlines:
        level = h.get('relevance_level', 2)
        level_counts[level] = level_counts.get(level, 0) + 1

    logger.info(
        f"Built output: {len(headlines)} headlines, {len(featured_ids_set)} featured - "
        f"L3:{level_counts.get(3,0)}, L2:{level_counts.get(2,0)}, L1:{level_counts.get(1,0)}"
    )

    return {
        'headlines': headlines,
        'featured': list(selection['featured'])  # Simple ID array
    }


def rank_with_dual_subset(
    urls: List[Dict[str, Any]],
    llm_client: LLMClient,
    run_date: str,
    db: PostgreSQLURLDatabase,
    num_headlines: int = None,
    num_featured: int = None
) -> Dict[str, Any]:
    """
    Rank URLs using dual subset selection (headlines + featured).

    This is a simpler, faster alternative to level_scoring that:
    1. Performs clustering for deduplication
    2. Selects two subsets: M headlines (to show) + N featured (to analyze)

    Args:
        urls: List of URL dicts to rank
        llm_client: LLM client instance
        run_date: Run date for tracking
        db: Database instance
        num_headlines: Number of headlines to select (M)
        num_featured: Number of featured articles to select (N)

    Returns:
        Dict with 'headlines' array and 'featured' ID array
    """
    num_headlines = num_headlines or RANKER_NUM_HEADLINES
    num_featured = num_featured or RANKER_NUM_FEATURED

    logger.info(f"Starting dual subset selection: {len(urls)} input URLs")
    logger.info(f"Target: {num_headlines} headlines, {num_featured} featured")

    # PASO 0: Safety limit - if too many URLs, pre-filter to avoid JSON errors
    MAX_URLS_FOR_LLM = 250  # Safety limit to avoid overwhelming LLM context
    if len(urls) > MAX_URLS_FOR_LLM:
        logger.warning(f"Too many URLs ({len(urls)}) for single LLM call")
        logger.info(f"Pre-filtering to top {MAX_URLS_FOR_LLM} by recency and source authority...")
        # Sort by: 1) categoria_tematica priority, 2) extracted_at (most recent first)
        urls_sorted = sorted(
            urls,
            key=lambda x: (
                -1 if x.get('categoria_tematica') in ['economia', 'finanzas', 'politica'] else 0,
                x.get('extracted_at', ''),
            ),
            reverse=True
        )
        urls = urls_sorted[:MAX_URLS_FOR_LLM]
        logger.info(f"Pre-filtered to {len(urls)} URLs for LLM selection")

    # PASO 1: Prepare URLs as standalone clusters (clustering removed)
    logger.info("PASO 1: Preparing URLs as standalone items (clustering disabled)")
    # Convert URLs to single-member clusters
    # Deduplication is now handled in Stage 05 through LLM prompting
    clusters = [
        {
            'representative': url,
            'related_articles': [],
            'cluster_size': 1,
            'event_description': url.get('title', ''),
            'categoria_tematica': url.get('categoria_tematica', 'otros')
        }
        for url in urls
    ]

    # PASO 2: Selección dual con LLM
    logger.info("PASO 2: Selección de headlines + featured...")
    selection = select_dual_subsets(
        clusters=clusters,
        num_headlines=num_headlines,
        num_featured=num_featured,
        llm_client=llm_client,
        run_date=run_date
    )

    # PASO 3: Construir output
    logger.info("PASO 3: Construyendo output final...")
    output = build_dual_output(clusters, selection)

    # Count related articles
    total_related = sum(len(h.get('related_articles', [])) for h in output['headlines'])

    logger.info(f"Dual subset selection complete:")
    logger.info(f"  Headlines: {len(output['headlines'])}")
    logger.info(f"  Featured: {len(output['featured'])}")
    logger.info(f"  Related articles: {total_related}")

    return output


def sort_within_level(
    urls: List[Dict[str, Any]],
    level: int,
    db: PostgreSQLURLDatabase,
    source_domains: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Sort URLs within a relevance level using heuristics.

    Sorting criteria (in order):
    1. Recency (extracted_at DESC) - more recent first
    2. Source authority (premium sources first)
    3. Original relevance_level (for ties)

    Args:
        urls: List of URL dictionaries in this level
        level: Relevance level number (for logging)
        db: Database instance for querying timestamps
        source_domains: Optional list of source domains in order of authority

    Returns:
        Sorted list of URLs
    """
    if not urls:
        return []

    # Query extracted_at timestamps
    url_ids = [url['id'] for url in urls]
    timestamps = {}

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(url_ids))
            query = f"SELECT id, extracted_at FROM urls WHERE id IN ({placeholders})"
            cursor.execute(query, url_ids)
            for row in cursor.fetchall():
                timestamps[row['id']] = row['extracted_at']
    except Exception as e:
        logger.warning(f"Failed to query timestamps for level {level}: {e}")

    # Build source authority lookup from provided domains (or empty if not provided)
    source_order = {}
    if source_domains:
        source_order = {domain.strip(): i for i, domain in enumerate(source_domains)}

    def sort_key(url):
        # Primary: cluster boost (higher boost = higher priority)
        cluster_boost = url.get('cluster_boost', 0.0)

        # Secondary: recency (newer first)
        timestamp = timestamps.get(url['id'], '')
        recency_score = timestamp if RANKER_TIEBREAK_BY_RECENCY else ''

        # Tertiary: source authority (lower index = higher authority)
        source = url.get('source', '')
        source_score = source_order.get(source, 999) if RANKER_TIEBREAK_BY_SOURCE else 999

        # Quaternary: original relevance level (preserve if available)
        original_level = url.get('relevance_level', level)

        return (
            -cluster_boost,  # Descending (higher boost = better)
            -1 if recency_score else 0,  # Empty timestamps last
            recency_score,  # Descending (ISO format sorts correctly)
            source_score,  # Ascending (lower = better)
            -original_level  # Descending (higher level = better)
        )

    sorted_urls = sorted(urls, key=sort_key, reverse=True)
    return sorted_urls


def rank_with_level_scoring(
    urls: List[Dict[str, Any]],
    llm_client: LLMClient,
    run_date: str,
    db: PostgreSQLURLDatabase,
    top_x: int = None,
    use_cached_scores: bool = True,
    score_ttl_days: int = 7
) -> List[Dict[str, Any]]:
    """
    Rank URLs using level scoring system (1-5) with top-X absolute selection.

    Process (v3.1 with incremental mode):
    0. Separate URLs into cached (with valid relevance_level) vs new (need scoring)
    1. Classify only new URLs into 5 relevance levels (absolute criteria)
    2. Persist new scores to database
    3. Combine cached + new URLs
    4. Extract Level 5 URLs, re-rank if > top_x to select exactly top_x
    5. Redistribute remaining URLs into 4 balanced levels (4,3,2,1)
    6. Sort within each level using heuristics (recency, source authority)
    7. Return ordered list: Level 5 → Level 4 → Level 3 → Level 2 → Level 1

    Args:
        urls: List of URL dictionaries to rank
        llm_client: LLM client instance
        run_date: Run date for tracking
        db: Database instance for tie-breaking queries
        top_x: Number of top relevance URLs to select (default: RANKER_TOP_X)
        use_cached_scores: Use cached relevance_level (incremental mode, default: True)
        score_ttl_days: Days before cached score expires (default: 7)

    Returns:
        Ranked list of URLs with relevance_level field
    """
    from datetime import datetime, timezone, timedelta

    if not urls:
        return []

    if top_x is None:
        top_x = RANKER_TOP_X

    logger.info("="*80)
    logger.info("LEVEL SCORING RANKING METHOD (v3.2 with cluster integration)")
    logger.info("="*80)
    logger.info(f"Input URLs: {len(urls)}")
    logger.info(f"Top-X target: {top_x}")
    logger.info(f"Scoring levels: {RANKER_SCORING_LEVELS}")
    logger.info(f"Batch size: {RANKER_SCORING_BATCH_SIZE}")
    logger.info(f"Incremental mode: {use_cached_scores}")
    logger.info(f"Cluster boost enabled: {RANKER_ENABLE_CLUSTER_BOOST}")
    logger.info(f"Cluster dedup enabled: {RANKER_ENABLE_CLUSTER_DEDUP}")
    if use_cached_scores:
        logger.info(f"Score TTL: {score_ttl_days} days")

    # Track related URLs for later storage
    related_url_map: Dict[int, List[int]] = {}

    # PASO -1: Cluster deduplication (v3.2)
    if RANKER_ENABLE_CLUSTER_DEDUP:
        logger.info("-"*80)
        logger.info("PASO -1: Deduplicación por cluster semántico")
        logger.info("-"*80)

        urls_with_cluster = [u for u in urls if u.get('cluster_id')]
        urls_without_cluster = [u for u in urls if not u.get('cluster_id')]

        logger.info(f"URLs with cluster_id: {len(urls_with_cluster)}")
        logger.info(f"URLs without cluster_id: {len(urls_without_cluster)}")

        if urls_with_cluster:
            deduped_urls, related_url_map = deduplicate_by_cluster(urls_with_cluster, db)
            urls = deduped_urls + urls_without_cluster
            logger.info(f"After deduplication: {len(urls)} URLs")

            # Count clusters with multiple articles
            multi_article_clusters = sum(1 for related in related_url_map.values() if related)
            total_related = sum(len(related) for related in related_url_map.values())
            if multi_article_clusters > 0:
                logger.info(f"Clusters with multiple articles: {multi_article_clusters}")
                logger.info(f"Total related articles (will be linked): {total_related}")
        else:
            logger.info("No URLs with cluster_id, skipping deduplication")

    # PASO -0.5: Apply cluster boost (v3.2)
    if RANKER_ENABLE_CLUSTER_BOOST:
        logger.info("-"*80)
        logger.info("PASO -0.5: Aplicar boost por tamaño de cluster")
        logger.info("-"*80)

        urls = apply_cluster_boost_to_urls(urls, db, RANKER_CLUSTER_BOOST_MAX)

    # PASO 0: Separate cached vs new URLs (v3.1 incremental mode)
    if use_cached_scores:
        logger.info("-"*80)
        logger.info("PASO 0: Modo Incremental - Separar cached vs new URLs")
        logger.info("-"*80)

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=score_ttl_days)

        cached_urls = []
        new_urls = []

        for url in urls:
            has_level = url.get('relevance_level') is not None
            scored_at = url.get('scored_at')

            # Normalize scored_at to aware datetime for safe comparison
            scored_at_dt = None
            if isinstance(scored_at, str):
                try:
                    scored_at_dt = datetime.fromisoformat(scored_at.replace("Z", "+00:00"))
                except ValueError:
                    logger.warning(f"Invalid scored_at format for URL {url.get('id')}: {scored_at}")
            elif isinstance(scored_at, datetime):
                scored_at_dt = scored_at

            if scored_at_dt and scored_at_dt.tzinfo is None:
                scored_at_dt = scored_at_dt.replace(tzinfo=timezone.utc)

            is_valid = scored_at_dt is not None and scored_at_dt > cutoff_date

            if has_level and is_valid:
                cached_urls.append(url)
            else:
                new_urls.append(url)

        logger.info(f"Cached URLs (with valid score): {len(cached_urls)}")
        logger.info(f"New URLs (need scoring): {len(new_urls)}")

        if cached_urls:
            logger.info("Cached URLs distribution:")
            cached_level_counts = {}
            for url in cached_urls:
                level = url.get('relevance_level', 3)
                cached_level_counts[level] = cached_level_counts.get(level, 0) + 1
            for level in sorted(cached_level_counts.keys(), reverse=True):
                logger.info(f"  Level {level}: {cached_level_counts[level]} URLs")

        # Only classify new URLs
        urls_to_classify = new_urls
    else:
        logger.info("Incremental mode disabled, classifying all URLs")
        cached_urls = []
        urls_to_classify = urls

    # PASO 1: Classify URLs by level (absolute criteria)
    logger.info("-"*80)
    logger.info("PASO 1: Clasificación por niveles de relevancia")
    logger.info("-"*80)

    if urls_to_classify:
        batches = chunk_list(urls_to_classify, RANKER_SCORING_BATCH_SIZE)
        logger.info(f"Split into {len(batches)} batches for classification")

        newly_classified = []
        for i, batch in enumerate(batches):
            logger.info(f"Classifying batch {i+1}/{len(batches)} ({len(batch)} URLs)")
            classified_batch = classify_batch_by_level(batch, llm_client, run_date, depth=i)
            newly_classified.extend(classified_batch)

        logger.info(f"Classification complete: {len(newly_classified)} URLs newly classified")

        # PASO 1.5: Persist new scores to database (v3.1)
        if use_cached_scores and newly_classified:
            logger.info("-"*80)
            logger.info("PASO 1.5: Persistir nuevos scores en base de datos")
            logger.info("-"*80)

            scoring_updates = []
            for url in newly_classified:
                scoring_updates.append({
                    'id': url['id'],
                    'relevance_level': url.get('relevance_level', 3),
                    'scored_by_method': 'level_scoring'
                })

            result = db.batch_update_url_scoring(scoring_updates)
            logger.info(f"Persisted {result['updated']} new scores to database")

        # Combine cached + newly classified
        all_classified = cached_urls + newly_classified
        logger.info(f"Total URLs after combining cached + new: {len(all_classified)}")
    else:
        logger.info("No new URLs to classify, using only cached scores")
        all_classified = cached_urls

    # Count distribution
    level_counts = {}
    for url in all_classified:
        level = url.get('relevance_level', 3)
        level_counts[level] = level_counts.get(level, 0) + 1

    logger.info("Initial distribution:")
    for level in sorted(level_counts.keys(), reverse=True):
        logger.info(f"  Level {level}: {level_counts[level]} URLs")

    # PASO 2: Extract Top-X from Level 5
    logger.info("-"*80)
    logger.info("PASO 2: Extracción Top-X (Nivel 5)")
    logger.info("-"*80)

    level_5_candidates = [url for url in all_classified if url.get('relevance_level') == 5]
    logger.info(f"Level 5 candidates: {len(level_5_candidates)}")

    if len(level_5_candidates) > top_x:
        logger.info(f"More than {top_x} Level 5 candidates, re-ranking to select top {top_x}...")
        top_x_urls = rerank_top_tier(level_5_candidates, top_x, llm_client, run_date)
    else:
        logger.info(f"Level 5 candidates ({len(level_5_candidates)}) <= top_x ({top_x}), using all")
        top_x_urls = level_5_candidates

    # Mark as final level 5
    for url in top_x_urls:
        url['relevance_level'] = 5

    logger.info(f"Top-X selection: {len(top_x_urls)} URLs at Level 5")

    # PASO 3: Redistribute remaining URLs into 4 balanced levels
    logger.info("-"*80)
    logger.info("PASO 3: Redistribución equilibrada del resto")
    logger.info("-"*80)

    top_x_ids = {url['id'] for url in top_x_urls}
    remaining_urls = [url for url in all_classified if url['id'] not in top_x_ids]

    logger.info(f"Remaining URLs to redistribute: {len(remaining_urls)}")

    if remaining_urls:
        # Sort remaining by original level (descending)
        remaining_sorted = sorted(
            remaining_urls,
            key=lambda u: u.get('relevance_level', 3),
            reverse=True
        )

        # Split into 4 equal parts for levels 4, 3, 2, 1
        n = len(remaining_sorted)
        tier_size = n // 4
        remainder = n % 4

        # Distribute remainder to higher tiers
        level_4_urls = remaining_sorted[0:tier_size + (1 if remainder > 0 else 0)]
        start_3 = len(level_4_urls)
        level_3_urls = remaining_sorted[start_3:start_3 + tier_size + (1 if remainder > 1 else 0)]
        start_2 = start_3 + len(level_3_urls)
        level_2_urls = remaining_sorted[start_2:start_2 + tier_size + (1 if remainder > 2 else 0)]
        level_1_urls = remaining_sorted[start_2 + len(level_2_urls):]

        # Reassign levels
        for url in level_4_urls:
            url['relevance_level'] = 4
        for url in level_3_urls:
            url['relevance_level'] = 3
        for url in level_2_urls:
            url['relevance_level'] = 2
        for url in level_1_urls:
            url['relevance_level'] = 1

        logger.info("Redistribution complete:")
        logger.info(f"  Level 4: {len(level_4_urls)} URLs")
        logger.info(f"  Level 3: {len(level_3_urls)} URLs")
        logger.info(f"  Level 2: {len(level_2_urls)} URLs")
        logger.info(f"  Level 1: {len(level_1_urls)} URLs")

        # Combine all
        all_redistributed = top_x_urls + level_4_urls + level_3_urls + level_2_urls + level_1_urls
    else:
        all_redistributed = top_x_urls

    # PASO 4: Sort within each level
    logger.info("-"*80)
    logger.info("PASO 4: Ordenamiento heurístico dentro de niveles")
    logger.info("-"*80)

    # Load source domains for tiebreaking (if enabled)
    source_domains = None
    if RANKER_TIEBREAK_BY_SOURCE:
        source_domains = load_source_order()
        logger.info(f"Loaded {len(source_domains)} source domains for tiebreaking")

    # Group by level
    urls_by_level = {5: [], 4: [], 3: [], 2: [], 1: []}
    for url in all_redistributed:
        level = url.get('relevance_level', 3)
        if level in urls_by_level:
            urls_by_level[level].append(url)

    # Sort each level
    final_ranked = []
    for level in [5, 4, 3, 2, 1]:
        level_urls = urls_by_level[level]
        if level_urls:
            logger.info(f"Sorting Level {level}: {len(level_urls)} URLs")
            sorted_level = sort_within_level(level_urls, level, db, source_domains)
            final_ranked.extend(sorted_level)

    # PASO 5: Final output with cluster-related URLs (v3.2)
    logger.info("="*80)
    logger.info("LEVEL SCORING COMPLETE (v3.2 with cluster integration)")
    logger.info("="*80)
    logger.info(f"Total ranked: {len(final_ranked)} URLs")
    logger.info("Final distribution:")
    for level in [5, 4, 3, 2, 1]:
        count = len(urls_by_level[level])
        logger.info(f"  Level {level}: {count} URLs")

    # Build final output with related_url_ids from cluster deduplication
    final_output = []
    for url in final_ranked[:top_x]:
        output_entry = url.copy()
        # Add related_url_ids from cluster deduplication (v3.2)
        output_entry['related_url_ids'] = related_url_map.get(url['id'], [])
        # Keep related_articles for backward compatibility (empty list)
        output_entry['related_articles'] = []
        final_output.append(output_entry)

    # Log cluster integration stats
    urls_with_related = sum(1 for u in final_output if u.get('related_url_ids'))
    total_related_urls = sum(len(u.get('related_url_ids', [])) for u in final_output)
    if urls_with_related > 0:
        logger.info(f"Cluster integration: {urls_with_related} URLs have related articles")
        logger.info(f"Total related URLs linked: {total_related_urls}")

    return final_output


def find_existing_ranking(
    run_date: str,
    execution_params: Dict[str, Any]
) -> Optional[str]:
    """
    Find existing ranking file with matching parameters.

    Searches for ranked JSON files that match the execution parameters
    to avoid regenerating identical rankings.

    Args:
        run_date: Date string (YYYY-MM-DD)
        execution_params: Execution parameters (method, max_headlines, categories, etc.)

    Returns:
        Path to existing ranking file, or None if not found
    """
    output_dir = Path("data") / "processed"
    if not output_dir.exists():
        return None

    # Build expected filename pattern
    method = execution_params.get('ranking_method', 'unknown')
    max_headlines = execution_params.get('max_headlines', 0)

    # Handle categories filter
    categories_filter = execution_params.get('categories_filter')
    if categories_filter and isinstance(categories_filter, list):
        categories_str = '-'.join(sorted(categories_filter))
    else:
        categories_str = 'all'

    # Clustering parameter (always 'nocluster' since clustering removed)
    clustering_str = 'nocluster'

    # Pattern: ranked_{date}_*_{method}_top{N}_{categories}_{clustering}.json
    # We ignore timestamp to find any file from the same date with matching params
    pattern = f"ranked_{run_date}_*_{method}_top{max_headlines}_{categories_str}_{clustering_str}.json"

    matching_files = list(output_dir.glob(pattern))

    if matching_files:
        # Return most recent (sorted by filename timestamp)
        most_recent = sorted(matching_files, reverse=True)[0]
        logger.info(f"Found existing ranking file: {most_recent}")
        return str(most_recent)

    return None


def save_to_database(
    ranked_urls: List[Dict[str, Any]],
    newsletter_name: str,
    run_date: str,
    db: PostgreSQLURLDatabase,
    ranker_method: str,
    categories_filter: List[str],
    articles_count: int,
    execution_time_seconds: float
) -> int:
    """
    Save ranked URLs to database instead of JSON file.

    Args:
        ranked_urls: List of ranked URL dictionaries
        newsletter_name: Name of the newsletter
        run_date: Run date string (YYYY-MM-DD)
        db: Database instance
        ranker_method: Ranking method used
        categories_filter: List of categories included
        articles_count: Number of articles ranked
        execution_time_seconds: Time taken to complete ranking

    Returns:
        ID of the created ranking run
    """
    # CRITICAL: Deduplicate ranked_urls by ID (safety net to prevent duplicates in output)
    seen_ids = set()
    deduplicated_urls = []
    duplicates_removed = 0
    for url in ranked_urls:
        url_id = url.get('id')
        if url_id not in seen_ids:
            seen_ids.add(url_id)
            deduplicated_urls.append(url)
        else:
            duplicates_removed += 1
            logger.warning(f"Duplicate URL ID {url_id} found in ranked_urls, skipping: {url.get('title', 'N/A')}")

    if duplicates_removed > 0:
        logger.warning(f"⚠️  Removed {duplicates_removed} duplicate URLs from output")

    ranked_urls = deduplicated_urls

    # Create ranking run record
    logger.info(f"Creating ranking run for {newsletter_name} on {run_date}...")
    ranking_run_id = db.create_ranking_run(
        newsletter_name=newsletter_name,
        run_date=run_date,
        ranker_method=ranker_method,
        categories_filter=categories_filter,
        articles_count=articles_count,
        execution_time_seconds=execution_time_seconds
    )

    # Prepare ranked URLs for insertion (v3.2: includes related_url_ids)
    ranked_urls_data = []
    for rank, url in enumerate(ranked_urls, start=1):
        entry = {
            'url_id': url['id'],
            'rank': rank
        }
        # Add related_url_ids if present (v3.2 cluster integration)
        related_ids = url.get('related_url_ids', [])
        if related_ids:
            entry['related_url_ids'] = json.dumps(related_ids)
        ranked_urls_data.append(entry)

    # Insert ranked URLs
    num_inserted = db.insert_ranked_urls(ranking_run_id, ranked_urls_data)

    # Log cluster integration stats
    urls_with_related = sum(1 for u in ranked_urls_data if u.get('related_url_ids'))
    if urls_with_related > 0:
        logger.info(f"  URLs with related articles: {urls_with_related}")
    db.update_ranking_total(ranking_run_id, num_inserted)

    logger.info(f"✓ Saved ranking to database:")
    logger.info(f"  Ranking run ID: {ranking_run_id}")
    logger.info(f"  URLs ranked: {num_inserted}")

    return ranking_run_id


def parse_datetime_arg(date_str: str) -> datetime:
    """
    Parse datetime string from CLI argument.

    Supports formats:
    - YYYY-MM-DD (assumes 00:00:00 UTC)
    - YYYY-MM-DDTHH:MM:SS (assumes UTC)

    Args:
        date_str: Date/datetime string

    Returns:
        datetime object with UTC timezone
    """
    if 'T' in date_str:
        # Full datetime
        dt = datetime.fromisoformat(date_str)
    else:
        # Date only - assume 00:00:00
        dt = datetime.strptime(date_str, '%Y-%m-%d')

    # Ensure UTC timezone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def main():
    """Main execution function for Stage 03."""
    parser = argparse.ArgumentParser(
        description="Stage 03: Rank URLs for newsletter generation (writes to database)"
    )

    # Newsletter identification (required)
    parser.add_argument(
        '--newsletter-name',
        type=str,
        required=True,
        help='Name of the newsletter (e.g., noticias_diarias, tech_brief)'
    )

    # Date/time range arguments
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument(
        '--date',
        type=str,
        help='Date to process (YYYY-MM-DD, processes full day 00:00-23:59 UTC)'
    )
    date_group.add_argument(
        '--start',
        type=str,
        help='Start datetime (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)'
    )

    parser.add_argument(
        '--end',
        type=str,
        help='End datetime (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS), required with --start'
    )

    # Filtering arguments
    parser.add_argument(
        '--categories',
        nargs='+',
        help='Filter by specific categories (e.g., politica economia tecnologia)'
    )

    parser.add_argument(
        '--sources',
        nargs='+',
        help='Filter by specific source IDs (e.g., ft nyt bbc) or ["all"] for all sources'
    )

    # Output arguments
    parser.add_argument(
        '--articles-count',
        type=int,
        default=MAX_HEADLINES,
        help=f'Number of articles to rank (top N) (default: {MAX_HEADLINES})'
    )

    parser.add_argument(
        '--top-per-category',
        type=int,
        default=None,
        help='Optional: Take top N from each category (ensures diversity). If not set, uses global ranking only.'
    )

    # Ranking method
    parser.add_argument(
        '--ranker-method',
        type=str,
        default=None,
        choices=['dual_subset', 'level_scoring'],
        help=f'Ranking method to use (default: from RANKER_METHOD env var = {RANKER_METHOD})'
    )

    # Incremental scoring (v3.1)
    parser.add_argument(
        '--use-cached-scores',
        action='store_true',
        default=True,
        help='Use cached relevance_level scores (incremental mode, default: True)'
    )
    parser.add_argument(
        '--no-cached-scores',
        dest='use_cached_scores',
        action='store_false',
        help='Disable cached scores, re-score all URLs from scratch'
    )
    parser.add_argument(
        '--score-ttl-days',
        type=int,
        default=7,
        help='Days before cached score expires (default: 7)'
    )

    # Logging
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    # Force regeneration
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force regeneration of ranking even if file with same parameters exists'
    )

    args = parser.parse_args()

    # Parse date range
    if args.date:
        # Full day
        start_dt = datetime.strptime(args.date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        end_dt = start_dt + timedelta(days=1) - timedelta(microseconds=1)
        run_date = args.date
    else:
        # Custom range
        if not args.end:
            parser.error("--end is required when using --start")

        start_dt = parse_datetime_arg(args.start)
        end_dt = parse_datetime_arg(args.end)
        run_date = start_dt.strftime('%Y-%m-%d')

    # Setup logging
    setup_logging(run_date, args.verbose)

    logger.info("="*80)
    logger.info("STAGE 03: RANKER")
    logger.info("="*80)
    logger.info(f"Newsletter: {args.newsletter_name}")
    logger.info(f"Date range: {start_dt.isoformat()} to {end_dt.isoformat()}")
    logger.info(f"Articles to rank: {args.articles_count}")
    if args.categories:
        logger.info(f"Category filter: {args.categories}")

    # Start timing
    import time
    stage_start_time = time.time()

    # Initialize database and LLM client
    db = PostgreSQLURLDatabase(os.getenv('DATABASE_URL'))
    llm_client = LLMClient()

    # Load categories config
    categories = load_categories(db)
    category_ids = [cat['id'] for cat in categories]
    category_name_to_id = {cat['name']: cat['id'] for cat in categories}

    # Validate and convert category filter (support both names and IDs)
    if args.categories:
        converted_categories = []
        for cat in args.categories:
            if cat in category_ids:
                # Already an ID
                converted_categories.append(cat)
            elif cat in category_name_to_id:
                # It's a name, convert to ID
                converted_categories.append(category_name_to_id[cat])
            else:
                logger.error(f"Invalid category: {cat}")
                logger.error(f"Valid category names: {list(category_name_to_id.keys())}")
                logger.error(f"Valid category IDs: {category_ids}")
                return {"status": "failed", "error": f"Invalid category: {cat}"}
        args.categories = converted_categories
        logger.info(f"Category filter (converted to IDs): {args.categories}")

    # Convert source IDs to URLs if provided
    source_urls = None
    if hasattr(args, 'sources') and args.sources:
        # Handle "all" keyword
        if args.sources == ["all"] or "all" in args.sources:
            logger.info("Source filter: 'all' - using all available sources")
            source_urls = None
        else:
            # Load sources from config
            import yaml
            sources_file = project_root / "config" / "sources.yml"
            try:
                with open(sources_file, 'r', encoding='utf-8') as f:
                    sources_config = yaml.safe_load(f)
                all_sources = sources_config.get('sources', [])
                source_map = {s['id']: s['url'] for s in all_sources}
                source_urls = [source_map[sid] for sid in args.sources if sid in source_map]

                if len(source_urls) != len(args.sources):
                    missing = set(args.sources) - set(source_map.keys())
                    logger.warning(f"Some source IDs not found in config: {missing}")

                logger.info(f"Source filter: {', '.join(args.sources)} ({len(source_urls)} URLs)")
            except Exception as e:
                logger.error(f"Failed to load sources: {e}")
                source_urls = None

    # Query URLs from database
    logger.info("Querying database for classified URLs...")
    urls = db.get_urls_for_newsletter(
        start_datetime=start_dt.isoformat(),
        end_datetime=end_dt.isoformat(),
        sources=source_urls,
        categories=args.categories
    )

    logger.info(f"Retrieved {len(urls)} URLs from database")

    if not urls:
        logger.warning("No URLs found for specified criteria")
        execution_time = time.time() - stage_start_time
        return {
            "status": "success",
            "ranking_run_id": None,
            "total_ranked": 0,
            "execution_time": execution_time
        }

    # Check for existing ranking in database (unless --force specified)
    if not args.force:
        existing_ranking = db.get_ranking_run(args.newsletter_name, run_date)
        if existing_ranking:
            logger.info("="*80)
            logger.info("EXISTING RANKING FOUND IN DATABASE")
            logger.info("="*80)
            logger.info(f"Ranking already exists for {args.newsletter_name} on {run_date}")
            logger.info(f"  Ranking run ID: {existing_ranking['id']}")
            logger.info(f"  Use --force to regenerate")
            logger.info("="*80)
            print(f"\nExisting ranking run ID: {existing_ranking['id']}")
            print("Use --force to regenerate ranking")
            execution_time = time.time() - stage_start_time
            return {
                "status": "success",
                "ranking_run_id": existing_ranking['id'],
                "total_ranked": existing_ranking.get('total_ranked', 0),
                "execution_time": execution_time,
                "skipped": True
            }

    logger.info("No existing ranking found or --force specified, proceeding with ranking...")

    # Choose ranking method (CLI argument overrides .env)
    ranking_method = args.ranker_method.lower() if args.ranker_method else RANKER_METHOD.lower()
    logger.info(f"Ranking method: {ranking_method}")

    if ranking_method == 'level_scoring':
        # ============================================================
        # LEVEL SCORING METHOD (new)
        # ============================================================
        logger.info("Using LEVEL SCORING ranking method")

        # Rank URLs using level scoring system (v3.1 with incremental mode)
        ranked_urls = rank_with_level_scoring(
            urls=urls,
            llm_client=llm_client,
            run_date=run_date,
            db=db,
            top_x=args.articles_count,
            use_cached_scores=args.use_cached_scores,
            score_ttl_days=args.score_ttl_days
        )

        # rank_with_level_scoring() already returns URLs with related_articles
        # (if clustering enabled) and limited to top_x
        final_output = ranked_urls

        # v3.1: No longer need rank_score (not stored in DB)
        # relevance_level is the source of truth

        # Stats for summary (clustering removed - no related articles)
        clusters_by_category = {}
        total_multi_member = 0
        total_related = 0
        clusters = []  # Empty for level scoring (not used in summary)

    elif ranking_method == 'recursive':
        # ============================================================
        # RECURSIVE METHOD (DEPRECATED)
        # ============================================================
        logger.error("RECURSIVE method is deprecated and has been removed")
        logger.error("Clustering functions (cluster_batch, cluster_recursive) removed on 2025-11-15")
        logger.error("Please use 'dual_subset' or 'level_scoring' methods instead")
        logger.error("Deduplication is now handled in Stage 05 through LLM prompting")
        raise ValueError(
            "RANKER_METHOD='recursive' is deprecated. "
            "Use 'dual_subset' or 'level_scoring' instead. "
            "Update your .env or newsletters.yml configuration."
        )

    elif ranking_method == 'dual_subset':
        # ============================================================
        # DUAL SUBSET METHOD (simplified - now just ranks top N)
        # ============================================================
        logger.info("Using DUAL SUBSET selection method")
        logger.info(f"Target: {args.articles_count} articles")

        # Rank URLs using dual subset selection (now simplified to top N)
        output_data = rank_with_dual_subset(
            urls=urls,
            llm_client=llm_client,
            run_date=run_date,
            db=db,
            num_headlines=args.articles_count,
            num_featured=args.articles_count  # Same value - we'll extract content from all
        )

        # output_data has format: {'headlines': [...], 'featured': [...]}
        final_output = output_data['headlines']

        # Add compatibility fields
        for url in final_output:
            if 'rank_score' not in url:
                url['rank_score'] = 50
            if 'rank_reason' not in url:
                url['rank_reason'] = "Ranked article"

    else:
        logger.error(f"Unknown ranking method: {ranking_method}")
        logger.error("Valid methods: 'level_scoring', 'dual_subset'")
        return {"status": "failed", "error": f"Unknown ranking method: {ranking_method}"}

    # Common logging after ranking
    logger.info(f"Final output prepared: {len(final_output)} primary articles")

    # Save to database
    logger.info("-"*80)
    logger.info("Saving ranking to database...")
    logger.info("-"*80)

    execution_time = time.time() - stage_start_time

    ranking_run_id = save_to_database(
        ranked_urls=final_output,
        newsletter_name=args.newsletter_name,
        run_date=run_date,
        db=db,
        ranker_method=ranking_method,
        categories_filter=args.categories or [],
        articles_count=args.articles_count,
        execution_time_seconds=execution_time
    )

    # Print summary
    logger.info("="*80)
    logger.info("STAGE 03 SUMMARY")
    logger.info("="*80)
    logger.info(f"Newsletter: {args.newsletter_name}")
    logger.info(f"Total input URLs: {len(urls)}")
    logger.info(f"URLs ranked: {len(final_output)}")
    logger.info(f"Ranking run ID: {ranking_run_id}")
    logger.info(f"Execution time: {execution_time:.2f}s")
    logger.info("="*80)

    # Print top 10 for quick review
    logger.info("\nTop 10 headlines:")
    for i, url in enumerate(final_output[:10], start=1):
        logger.info(f"{i}. [{url.get('rank_score', 0)}] {url['title']}")
        logger.info(f"   Category: {url.get('categoria_tematica', 'N/A')} | Source: {url['source']}")
        if url.get('rank_reason'):
            logger.info(f"   Reason: {url['rank_reason']}")

    logger.info("\nStage 03 completed successfully")

    # Return metadata for orchestrator
    return {
        "status": "success",
        "ranking_run_id": ranking_run_id,
        "total_ranked": len(final_output),
        "execution_time": execution_time
    }


if __name__ == "__main__":
    result = main()
    if isinstance(result, dict):
        # Called from orchestrator or programmatically
        sys.exit(0 if result["status"] == "success" else 1)
    else:
        # Legacy CLI usage
        sys.exit(result)
