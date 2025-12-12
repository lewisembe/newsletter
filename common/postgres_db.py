"""
PostgreSQL Database Manager for Newsletter Utils

Provides a robust interface for URL storage and retrieval using PostgreSQL.
Replaces CSV-based persistence with proper database functionality.

Author: Newsletter Utils Team
Created: 2025-11-10
"""

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
import logging
from datetime import datetime, timezone, date
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
import os
import json

logger = logging.getLogger(__name__)


class PostgreSQLURLDatabase:
    """
    PostgreSQL database manager for URL storage and retrieval.

    Features:
    - UNIQUE constraint on URL (enforces integrity)
    - Dual timestamp tracking (extracted_at + last_extracted_at)
    - Indexed queries for performance
    - Connection pooling
    - Transaction support with rollback
    - Comprehensive error handling

    Usage:
        db = PostgreSQLURLDatabase("data/news.db")
        db.init_db()

        # Add new URL
        db.add_url({
            'url': 'https://example.com/article',
            'title': 'Example Article',
            'source': 'https://example.com',
            'content_type': 'contenido',
            'content_subtype': None,
            'classification_method': 'regex_rule',
            'rule_name': 'example_articles'
        })

        # Batch upsert
        urls = [...]  # List of URL dicts
        db.batch_upsert(urls)

        # Query by date
        urls = db.get_urls_by_date('2025-11-10')
    """

    def __init__(self, connection_string: str):
        """
        Initialize database connection.

        Args:
            connection_string: PostgreSQL connection string (e.g., postgresql://user:pass@host/db)
        """
        self.connection_string = connection_string
        self._token_usage_table_initialized = False
        logger.info(f"PostgreSQLURLDatabase initialized")


    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.

        Ensures proper connection cleanup and error handling.

        Usage:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ...")
        """
        conn = None
        try:
            conn = psycopg.connect(self.connection_string, row_factory=dict_row)
            conn.autocommit = False
            yield conn
        except psycopg.Error as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def init_db(self, drop_existing: bool = False):
        """
        Schema initialization skipped - use PostgreSQL schema file instead.
        """
        logger.info("PostgreSQL schema managed externally (docker/schemas/schema_manual.sql)")
        pass

    def add_url(self, url_data: Dict[str, Any]) -> Optional[int]:
        """
        Add a single URL to the database.

        Args:
            url_data: Dictionary with URL information:
                - url (required): URL string
                - title: Article title
                - source (required): Source URL
                - content_type (required): 'contenido' | 'no_contenido'
                - content_subtype: 'noticia' | 'otros' | None
                - classification_method (required): Method used
                - rule_name: Regex rule name or None
                - extracted_at: ISO timestamp (defaults to now)
                - execution_id: Execution ID that extracted this URL (optional)

        Returns:
            Row ID of inserted URL, or None if URL already exists

        Raises:
            psycopg.errors.UniqueViolation: If URL already exists
        """
        # Set defaults
        if 'extracted_at' not in url_data:
            url_data['extracted_at'] = datetime.now(timezone.utc).isoformat()
        if 'last_extracted_at' not in url_data:
            url_data['last_extracted_at'] = url_data['extracted_at']

        with self.get_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    INSERT INTO urls (
                        url, title, source, content_type, content_subtype,
                        classification_method, rule_name, extracted_at, last_extracted_at,
                        execution_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    url_data['url'],
                    url_data.get('title'),
                    url_data['source'],
                    url_data['content_type'],
                    url_data.get('content_subtype'),
                    url_data['classification_method'],
                    url_data.get('rule_name'),
                    url_data['extracted_at'],
                    url_data['last_extracted_at'],
                    url_data.get('execution_id')
                ))

                conn.commit()
                row_id = cursor.lastrowid
                logger.debug(f"Added URL: {url_data['url']} (id: {row_id})")
                return row_id

            except psycopg.errors.UniqueViolation as e:
                if "UNIQUE constraint failed" in str(e):
                    logger.debug(f"URL already exists: {url_data['url']}")
                    return None
                raise

    def update_url(self, url: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing URL record.

        Args:
            url: URL to update
            updates: Dictionary with fields to update

        Returns:
            True if URL was updated, False if not found
        """
        if not updates:
            return False

        # Build SET clause
        set_clauses = []
        values = []
        for key, value in updates.items():
            set_clauses.append(f"{key} = %s")
            values.append(value)

        values.append(url)  # For WHERE clause

        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = f"""
                UPDATE urls
                SET {', '.join(set_clauses)}
                WHERE url = %s
            """

            cursor.execute(query, values)
            conn.commit()

            updated = cursor.rowcount > 0
            if updated:
                logger.debug(f"Updated URL: {url}")
            else:
                logger.debug(f"URL not found for update: {url}")

            return updated

    def get_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single URL by its URL string.

        Args:
            url: URL to retrieve

        Returns:
            Dictionary with URL data, or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM urls WHERE url = %s", (url,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    def get_existing_urls(self, url_list: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Retrieve existing URLs from database for deduplication check.

        Optimized bulk lookup to avoid re-classifying URLs that already exist.
        Used by Stage 01 to separate new URLs from existing ones.

        Args:
            url_list: List of URL strings to check

        Returns:
            Dictionary mapping URL -> URL data for URLs that exist in DB
            Empty dict if none found
        """
        if not url_list:
            return {}

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Build parameterized query for bulk lookup
            placeholders = ','.join(['%s'] * len(url_list))
            query = f"SELECT * FROM urls WHERE url IN ({placeholders})"

            cursor.execute(query, url_list)
            rows = cursor.fetchall()

            # Return as dict mapping URL -> data
            result = {row['url']: dict(row) for row in rows}

            logger.debug(f"Bulk lookup: {len(result)} of {len(url_list)} URLs exist in database")
            return result

    def get_all_urls(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve all URLs from database.

        Args:
            limit: Optional limit on number of results

        Returns:
            List of URL dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM urls ORDER BY last_extracted_at DESC"
            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def get_urls_by_date(self, date: str, content_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve URLs by extraction date (first time extracted).

        This is the primary query for Stage 02 filtering.
        Uses extracted_at (not last_extracted_at) to get "news of the day".

        Args:
            date: Date string in YYYY-MM-DD format
            content_type: Optional filter ('contenido' | 'no_contenido')

        Returns:
            List of URL dictionaries matching criteria
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM urls WHERE date(extracted_at) = %s"
            params = [date]

            if content_type:
                query += " AND content_type = %s"
                params.append(content_type)

            query += " ORDER BY extracted_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            logger.info(f"Retrieved {len(rows)} URLs for date {date}" +
                       (f" with content_type={content_type}" if content_type else ""))

            return [dict(row) for row in rows]

    def batch_upsert(self, urls: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Batch upsert URLs with deduplication logic.

        Mimics CSV deduplication behavior:
        - New URLs: extracted_at = last_extracted_at = NOW
        - Existing URLs: preserve extracted_at, update last_extracted_at = NOW

        Args:
            urls: List of URL dictionaries

        Returns:
            Dictionary with statistics:
                - inserted: Number of new URLs added
                - updated: Number of existing URLs updated
                - errors: Number of errors
        """
        stats = {'inserted': 0, 'updated': 0, 'errors': 0}
        now = datetime.now(timezone.utc).isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()

            for url_data in urls:
                try:
                    # Check if URL exists
                    cursor.execute("SELECT id, extracted_at FROM urls WHERE url = %s", (url_data['url'],))
                    existing = cursor.fetchone()

                    if existing:
                        # Update: preserve extracted_at, update last_extracted_at
                        cursor.execute("""
                            UPDATE urls
                            SET title = %s,
                                content_type = %s,
                                content_subtype = %s,
                                classification_method = %s,
                                rule_name = %s,
                                last_extracted_at = %s
                            WHERE url = %s
                        """, (
                            url_data.get('title'),
                            url_data['content_type'],
                            url_data.get('content_subtype'),
                            url_data['classification_method'],
                            url_data.get('rule_name'),
                            now,
                            url_data['url']
                        ))
                        stats['updated'] += 1

                    else:
                        # Insert: both timestamps = NOW (or provided)
                        extracted_at = url_data.get('extracted_at', now)
                        cursor.execute("""
                            INSERT INTO urls (
                                url, title, source, content_type, content_subtype,
                                classification_method, rule_name, extracted_at, last_extracted_at,
                                execution_id
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            url_data['url'],
                            url_data.get('title'),
                            url_data['source'],
                            url_data['content_type'],
                            url_data.get('content_subtype'),
                            url_data['classification_method'],
                            url_data.get('rule_name'),
                            extracted_at,
                            now,
                            url_data.get('execution_id')
                        ))
                        stats['inserted'] += 1

                except psycopg.Error as e:
                    logger.error(f"Error upserting URL {url_data.get('url')}: {e}")
                    stats['errors'] += 1

            conn.commit()

        logger.info(f"Batch upsert complete: {stats['inserted']} inserted, " +
                   f"{stats['updated']} updated, {stats['errors']} errors")

        return stats

    def reset_clusters_for_date(self, date: str) -> int:
        """
        Clear cluster assignments for contenido URLs on a specific date.

        Args:
            date: Date string in YYYY-MM-DD format

        Returns:
            Number of rows reset
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE urls
                SET cluster_id = NULL,
                    cluster_assigned_at = NULL
                WHERE date(extracted_at) = %s
                  AND content_type = 'contenido'
            """, (date,))
            conn.commit()

            reset_rows = cursor.rowcount
            logger.info(f"Cleared cluster assignments for {reset_rows} URLs on {date}")
            return reset_rows

    def batch_update_clusters(self, assignments: Dict[int, str]) -> int:
        """
        Batch-assign cluster IDs to URLs identified by ID.

        Args:
            assignments: Mapping of url_id -> cluster identifier

        Returns:
            Number of rows updated
        """
        if not assignments:
            return 0

        now = datetime.now(timezone.utc).isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            before_changes = conn.total_changes

            rows = [
                (cluster_id, now, url_id)
                for url_id, cluster_id in assignments.items()
            ]

            cursor.executemany("""
                UPDATE urls
                SET cluster_id = %s,
                    cluster_assigned_at = %s
                WHERE id = %s
            """, rows)

            conn.commit()
            updated = conn.total_changes - before_changes
            logger.info(f"Cluster assignments updated for {updated} URLs")
            return updated

    def clear_clusters_for_date(self, date: str) -> int:
        """
        Delete cluster metadata for a specific extraction date.

        Args:
            date: Date string in YYYY-MM-DD format

        Returns:
            Number of cluster rows deleted
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM clusters WHERE run_date = %s", (date,))
            conn.commit()
            deleted = cursor.rowcount
            logger.info(f"Deleted {deleted} cluster records for {date}")
            return deleted

    def upsert_clusters(self, clusters: List[Dict[str, Any]]) -> int:
        """
        Insert or update semantic cluster metadata rows.

        Args:
            clusters: List of dicts with keys:
                - id: cluster identifier
                - run_date: YYYY-MM-DD date string
                - centroid_url_id: representative URL ID
                - article_count: number of URLs in cluster
                - avg_similarity: optional float

        Returns:
            Number of clusters upserted
        """
        if not clusters:
            return 0

        with self.get_connection() as conn:
            cursor = conn.cursor()
            rows = [
                (
                    cluster["id"],
                    cluster["run_date"],
                    cluster.get("centroid_url_id"),
                    cluster.get("article_count", 0),
                    cluster.get("avg_similarity"),
                )
                for cluster in clusters
            ]

            cursor.executemany("""
                INSERT INTO clusters (id, run_date, centroid_url_id, article_count, avg_similarity)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(id) DO UPDATE SET
                    run_date = excluded.run_date,
                    centroid_url_id = excluded.centroid_url_id,
                    article_count = excluded.article_count,
                    avg_similarity = excluded.avg_similarity
            """, rows)

            conn.commit()
            logger.info(f"Upserted {len(rows)} cluster records")
            return len(rows)

    def get_content_urls(self, date: str) -> List[Dict[str, Any]]:
        """
        Get content URLs for a specific date.

        Optimized query for Stage 02 filtering.
        Filters by extracted_at (first extraction) and content_type='contenido'.

        Args:
            date: Date string in YYYY-MM-DD format

        Returns:
            List of content URL dictionaries
        """
        return self.get_urls_by_date(date, content_type='contenido')

    def get_unclustered_content_urls(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve content URLs without cluster assignment."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT id, url, title, source, extracted_at
                FROM urls
                WHERE content_type = 'contenido'
                  AND (cluster_id IS NULL OR cluster_id = '')
                ORDER BY extracted_at ASC
            """
            if limit:
                query += f" LIMIT {int(limit)}"
            cursor.execute(query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def assign_cluster_to_url(self, url_id: int, cluster_id: str, assigned_at: Optional[str] = None) -> None:
        """Update a URL with its cluster assignment."""
        assigned_at = assigned_at or datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE urls
                SET cluster_id = %s,
                    cluster_assigned_at = %s
                WHERE id = %s
                """,
                (cluster_id, assigned_at, url_id),
            )
            conn.commit()

    def get_cluster_id_map(self) -> Dict[int, str]:
        """Return mapping of url_id -> cluster_id for assigned URLs."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cluster_id FROM urls WHERE cluster_id IS NOT NULL")
            return {row['id']: row['cluster_id'] for row in cursor.fetchall() if row['cluster_id']}

    def get_cluster_stats_map(self) -> Dict[str, Dict[str, Any]]:
        """Return mapping of cluster_id -> stats payload."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, run_date, article_count, avg_similarity,
                       similarity_mean, similarity_m2, similarity_samples
                FROM clusters
            """
            )
            result = {}
            for row in cursor.fetchall():
                result[row['id']] = {
                    "run_date": row['run_date'],
                    "article_count": row['article_count'],
                    "avg_similarity": row['avg_similarity'],
                    "similarity_mean": row['similarity_mean'] or 0.0,
                    "similarity_m2": row['similarity_m2'] or 0.0,
                    "similarity_samples": row['similarity_samples'] or 0,
                }
            return result

    def create_cluster_record(
        self,
        cluster_id: str,
        run_date: str,
        centroid_url_id: int,
        article_count: int = 1,
        avg_similarity: Optional[float] = None,
        cluster_name: Optional[str] = None,
    ) -> None:
        """Insert a new cluster metadata row."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO clusters (
                    id, run_date, centroid_url_id, article_count, avg_similarity,
                    similarity_mean, similarity_m2, similarity_samples, last_assigned_at,
                    cluster_name
                ) VALUES (%s, %s, %s, %s, %s, 0, 0, 0, CURRENT_TIMESTAMP, %s)
                """,
                (cluster_id, run_date, centroid_url_id, article_count, avg_similarity, cluster_name),
            )
            conn.commit()

    def update_cluster_stats(
        self,
        cluster_id: str,
        *,
        article_count: Optional[int] = None,
        avg_similarity: Optional[float] = None,
        similarity_mean: Optional[float] = None,
        similarity_m2: Optional[float] = None,
        similarity_samples: Optional[int] = None,
        centroid_url_id: Optional[int] = None,
    ) -> None:
        """Update cluster statistics incrementally."""
        fields = []
        values = []
        if article_count is not None:
            fields.append("article_count = %s")
            values.append(article_count)
        if avg_similarity is not None:
            fields.append("avg_similarity = %s")
            values.append(avg_similarity)
        if similarity_mean is not None:
            fields.append("similarity_mean = %s")
            values.append(similarity_mean)
        if similarity_m2 is not None:
            fields.append("similarity_m2 = %s")
            values.append(similarity_m2)
        if similarity_samples is not None:
            fields.append("similarity_samples = %s")
            values.append(similarity_samples)
        if centroid_url_id is not None:
            fields.append("centroid_url_id = %s")
            values.append(centroid_url_id)
        fields.append("last_assigned_at = CURRENT_TIMESTAMP")

        if not fields:
            return

        values.append(cluster_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                UPDATE clusters
                SET {', '.join(fields)}
                WHERE id = %s
                """,
                values,
            )
            conn.commit()

    def save_embedding(self, url_id: int, embedding: bytes, dimension: int) -> None:
        """Persist an embedding blob for a URL."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO url_embeddings (url_id, embedding, dimension)
                VALUES (%s, %s, %s)
                """,
                (url_id, embedding, dimension),
            )
            conn.commit()

    def load_all_embeddings(self) -> List[Dict[str, Any]]:
        """Return all stored embeddings (for index bootstrap)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT url_id, embedding, dimension FROM url_embeddings")
            rows = cursor.fetchall()
            return [
                {
                    'url_id': row['url_id'],
                    'embedding': row['embedding'],
                    'dimension': row['dimension'],
                }
                for row in rows
            ]

    def save_clustering_run(
        self,
        run_date: str,
        config: Dict[str, Any],
        urls_processed: int,
        clusters_created: int,
        total_clusters: int,
    ) -> int:
        """
        Save clustering run parameters and results for traceability.

        Args:
            run_date: Date of the clustering run (YYYY-MM-DD)
            config: Full clustering configuration dict
            urls_processed: Number of URLs processed in this run
            clusters_created: Number of new clusters created
            total_clusters: Total clusters after this run

        Returns:
            ID of the inserted clustering_runs record
        """
        import json
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Ensure table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clustering_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_date TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    embedding_dim INTEGER NOT NULL,
                    similarity_threshold REAL NOT NULL,
                    adaptive_threshold INTEGER NOT NULL,
                    adaptive_k REAL,
                    max_neighbors INTEGER,
                    min_cluster_size INTEGER,
                    config_json TEXT NOT NULL,
                    urls_processed INTEGER NOT NULL,
                    clusters_created INTEGER NOT NULL,
                    total_clusters INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute(
                """
                INSERT INTO clustering_runs (
                    run_date, model_name, embedding_dim, similarity_threshold,
                    adaptive_threshold, adaptive_k, max_neighbors, min_cluster_size,
                    config_json, urls_processed, clusters_created, total_clusters
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_date,
                    config.get("model", {}).get("name", "unknown"),
                    config.get("_embedding_dim", 384),
                    config.get("clustering", {}).get("similarity_threshold", 0.94),
                    1 if config.get("clustering", {}).get("adaptive_threshold", True) else 0,
                    config.get("clustering", {}).get("adaptive_k"),
                    config.get("clustering", {}).get("max_neighbors"),
                    config.get("clustering", {}).get("min_cluster_size"),
                    json.dumps(config, indent=2, default=str),
                    urls_processed,
                    clusters_created,
                    total_clusters,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def clear_all_clusters(self) -> Dict[str, int]:
        """
        Clear all clustering data to allow fresh re-clustering.

        Returns:
            Dict with counts of deleted records
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Count before deletion
            cursor.execute("SELECT COUNT(*) as count FROM clusters")
            clusters_count = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(*) as count FROM url_embeddings")
            embeddings_count = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(*) as count FROM urls WHERE cluster_id IS NOT NULL")
            assigned_urls_count = cursor.fetchone()['count']

            # Clear cluster assignments from urls
            cursor.execute("""
                UPDATE urls
                SET cluster_id = NULL, cluster_assigned_at = NULL
                WHERE cluster_id IS NOT NULL
            """)

            # Clear clusters table
            cursor.execute("DELETE FROM clusters")

            # Clear embeddings table
            cursor.execute("DELETE FROM url_embeddings")

            conn.commit()

            return {
                "clusters_deleted": clusters_count,
                "embeddings_deleted": embeddings_count,
                "urls_unassigned": assigned_urls_count,
            }

    def get_clustering_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent clustering runs for review."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM clustering_runs
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_urls_for_newsletter(
        self,
        start_datetime: str,
        end_datetime: str,
        sources: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        only_uncategorized: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get content URLs for newsletter generation (Stage 02).

        Filters by:
        - Date range (extracted_at between start and end)
        - content_type = 'contenido'
        - Optionally by sources
        - Optionally by thematic categories (if already categorized)
        - Optionally only uncategorized URLs

        Args:
            start_datetime: Start datetime in ISO format (e.g., '2025-11-10T00:00:00')
            end_datetime: End datetime in ISO format (e.g., '2025-11-10T23:59:59')
            sources: Optional list of source URLs to filter by
            categories: Optional list of categoria_tematica to filter by
            only_uncategorized: If True, only return URLs without categoria_tematica

        Returns:
            List of URL dictionaries matching criteria
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Build query
            query = """
                SELECT * FROM urls
                WHERE extracted_at >= %s
                  AND extracted_at <= %s
                  AND content_type = 'contenido'
            """
            params = [start_datetime, end_datetime]

            # Add source filter
            if sources:
                placeholders = ','.join(['%s'] * len(sources))
                query += f" AND source IN ({placeholders})"
                params.extend(sources)

            # Add category filter (only if categories specified AND URL has category)
            if categories:
                placeholders = ','.join(['%s'] * len(categories))
                query += f" AND categoria_tematica IN ({placeholders})"
                params.extend(categories)

            # Add uncategorized filter (for idempotent Stage 02)
            if only_uncategorized:
                query += " AND categoria_tematica IS NULL"

            query += " ORDER BY extracted_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            logger.info(f"Retrieved {len(rows)} URLs for newsletter "
                       f"(date range: {start_datetime} to {end_datetime}, "
                       f"sources: {len(sources) if sources else 'all'}, "
                       f"categories: {len(categories) if categories else 'all'})")

            return [dict(row) for row in rows]

    def update_categorization(
        self,
        url_id: int,
        categoria_tematica: str,
        content_subtype: Optional[str] = None
    ) -> bool:
        """
        Update thematic categorization for a URL (Stage 02).

        Args:
            url_id: ID of the URL to update
            categoria_tematica: Thematic category
            content_subtype: Content temporality ('temporal' or 'atemporal')

        Returns:
            True if updated successfully, False otherwise
        """
        now = datetime.now(timezone.utc).isoformat()

        updates = {
            'categoria_tematica': categoria_tematica,
            'categorized_at': now
        }

        if content_subtype is not None:
            updates['content_subtype'] = content_subtype

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Build SET clause
            set_clauses = []
            values = []
            for key, value in updates.items():
                set_clauses.append(f"{key} = %s")
                values.append(value)

            values.append(url_id)  # For WHERE clause

            query = f"""
                UPDATE urls
                SET {', '.join(set_clauses)}
                WHERE id = %s
            """

            cursor.execute(query, values)
            conn.commit()

            updated = cursor.rowcount > 0
            if updated:
                logger.debug(f"Updated categorization for URL ID {url_id}: {categoria_tematica}")
            else:
                logger.debug(f"URL ID {url_id} not found for categorization update")

            return updated

    def batch_update_categorization(
        self,
        updates: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Batch update categorizations for multiple URLs.

        Args:
            updates: List of dicts with:
                - id: URL ID
                - categoria_tematica: Thematic category
                - content_subtype: Optional content temporality

        Returns:
            Dictionary with statistics:
                - updated: Number of URLs updated
                - errors: Number of errors
        """
        stats = {'updated': 0, 'errors': 0}
        now = datetime.now(timezone.utc).isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()

            for update_data in updates:
                try:
                    url_id = update_data['id']
                    categoria_tematica = update_data['categoria_tematica']
                    content_subtype = update_data.get('content_subtype')

                    if content_subtype:
                        cursor.execute("""
                            UPDATE urls
                            SET categoria_tematica = %s,
                                content_subtype = %s,
                                categorized_at = %s
                            WHERE id = %s
                        """, (categoria_tematica, content_subtype, now, url_id))
                    else:
                        cursor.execute("""
                            UPDATE urls
                            SET categoria_tematica = %s,
                                categorized_at = %s
                            WHERE id = %s
                        """, (categoria_tematica, now, url_id))

                    if cursor.rowcount > 0:
                        stats['updated'] += 1

                except psycopg.Error as e:
                    logger.error(f"Error updating categorization for URL ID {update_data.get('id')}: {e}")
                    stats['errors'] += 1

            conn.commit()

        logger.info(f"Batch categorization update complete: {stats['updated']} updated, "
                   f"{stats['errors']} errors")

        return stats

    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with statistics:
                - total_urls: Total number of URLs
                - contenido_count: Number of content URLs
                - no_contenido_count: Number of non-content URLs
                - sources_count: Number of unique sources
                - date_range: Earliest and latest extracted_at
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total URLs
            cursor.execute("SELECT COUNT(*) as count FROM urls")
            total = cursor.fetchone()['count']

            # Content type breakdown
            cursor.execute("SELECT content_type, COUNT(*) FROM urls GROUP BY content_type")
            content_breakdown = dict(cursor.fetchall())

            # Unique sources
            cursor.execute("SELECT COUNT(DISTINCT source) as count FROM urls")
            sources = cursor.fetchone()['count']

            # Date range
            cursor.execute("SELECT MIN(extracted_at) as earliest, MAX(extracted_at) as latest FROM urls")
            date_range = cursor.fetchone()

            return {
                'total_urls': total,
                'contenido_count': content_breakdown.get('contenido', 0),
                'no_contenido_count': content_breakdown.get('no_contenido', 0),
                'sources_count': sources,
                'date_range': {
                    'earliest': date_range['earliest'],
                    'latest': date_range['latest']
                } if date_range['earliest'] else None
            }

    def get_url_count_by_source_names(self, source_names: List[str]) -> int:
        """
        Get total count of URLs in database for specific sources.

        Args:
            source_names: List of source names (e.g., ['elconfidencial', 'abc'])

        Returns:
            Total count of URLs for those sources
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if not source_names:
                return 0

            # Get base_urls for the source names
            placeholders = ','.join(['%s'] * len(source_names))
            query = f"SELECT base_url FROM sources WHERE name IN ({placeholders})"
            cursor.execute(query, source_names)

            base_urls = [row['base_url'] for row in cursor.fetchall()]

            if not base_urls:
                return 0

            # Count URLs matching those base_urls
            placeholders = ','.join(['%s'] * len(base_urls))
            query = f"SELECT COUNT(*) as count FROM urls WHERE source IN ({placeholders})"
            cursor.execute(query, base_urls)
            result = cursor.fetchone()

            return result['count'] if result else 0

    def get_url_by_id(self, url_id: int) -> Optional[Dict[str, Any]]:
        """
        Get URL data by ID.

        Args:
            url_id: URL ID to retrieve

        Returns:
            URL data as dictionary, or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM urls WHERE id = %s", (url_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    def update_content_extraction(
        self,
        url_id: int,
        full_content: Optional[str] = None,
        extraction_method: Optional[str] = None,
        extraction_status: Optional[str] = None,
        extraction_error: Optional[str] = None,
        word_count: Optional[int] = None,
        archive_url: Optional[str] = None,
        title: Optional[str] = None
    ) -> bool:
        """
        Update content extraction results for a URL (Stage 04).

        Args:
            url_id: ID of the URL to update
            full_content: Full extracted article content
            extraction_method: Method used ('xpath_cache', 'newspaper', 'readability', 'llm_xpath', 'failed')
            extraction_status: Status ('success', 'failed', 'pending')
            extraction_error: Error message if extraction failed
            word_count: Word count of extracted content
            archive_url: Archive.today URL if fetched from archive
            title: Updated article title (from HTML extraction)

        Returns:
            True if updated successfully, False otherwise
        """
        now = datetime.now(timezone.utc).isoformat()

        updates = {}

        # Add provided fields to updates
        if full_content is not None:
            updates['full_content'] = full_content

        if extraction_method is not None:
            updates['content_extraction_method'] = extraction_method

        if extraction_status is not None:
            updates['extraction_status'] = extraction_status

        if extraction_error is not None:
            updates['extraction_error'] = extraction_error

        if word_count is not None:
            updates['word_count'] = word_count

        if archive_url is not None:
            updates['archive_url'] = archive_url

        if title is not None:
            updates['title'] = title

        # Always update timestamp if extraction was attempted
        if extraction_method or extraction_status:
            updates['content_extracted_at'] = now

        if not updates:
            logger.warning(f"No fields to update for URL ID {url_id}")
            return False

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Build SET clause
            set_clauses = []
            values = []
            for key, value in updates.items():
                set_clauses.append(f"{key} = %s")
                values.append(value)

            values.append(url_id)  # For WHERE clause

            query = f"""
                UPDATE urls
                SET {', '.join(set_clauses)}
                WHERE id = %s
            """

            cursor.execute(query, values)
            conn.commit()

            updated = cursor.rowcount > 0
            if updated:
                logger.debug(
                    f"Updated content extraction for URL ID {url_id}: "
                    f"method={extraction_method}, status={extraction_status}, "
                    f"word_count={word_count}"
                )
            else:
                logger.warning(f"URL ID {url_id} not found for content extraction update")

            return updated

    def get_urls_needing_extraction(
        self,
        ranked_url_ids: List[int],
        force: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get URLs that need content extraction.

        Args:
            ranked_url_ids: List of URL IDs from ranking
            force: If True, return all URLs even if already extracted

        Returns:
            List of URL data dictionaries that need extraction
        """
        if not ranked_url_ids:
            return []

        with self.get_connection() as conn:
            cursor = conn.cursor()

            placeholders = ','.join(['%s'] * len(ranked_url_ids))

            if force:
                # Return all requested URLs
                query = f"SELECT * FROM urls WHERE id IN ({placeholders})"
                cursor.execute(query, ranked_url_ids)
            else:
                # Return only URLs without content
                query = f"""
                    SELECT * FROM urls
                    WHERE id IN ({placeholders})
                    AND (full_content IS NULL OR full_content = '')
                """
                cursor.execute(query, ranked_url_ids)

            rows = cursor.fetchall()

            logger.info(
                f"URLs needing extraction: {len(rows)} out of {len(ranked_url_ids)} "
                f"(force={force})"
            )

            return [dict(row) for row in rows]

    def vacuum(self):
        """
        Vacuum database to reclaim space and optimize performance.

        Should be run periodically (e.g., monthly).
        """
        with self.get_connection() as conn:
            conn.execute("VACUUM")
            logger.info("Database vacuumed successfully")

    # Pipeline orchestrator methods

    def start_pipeline_run(
        self,
        newsletter_name: str,
        run_date: str,
        stage: int
    ) -> int:
        """
        Start a new pipeline run for a newsletter stage.

        Args:
            newsletter_name: Name of the newsletter
            run_date: Date string (YYYY-MM-DD)
            stage: Stage number (1-5)

        Returns:
            ID of the created pipeline run
        """
        now = datetime.now(timezone.utc).isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pipeline_runs (
                    newsletter_name, run_date, stage, status, started_at
                ) VALUES (%s, %s, %s, 'running', %s)
            """, (newsletter_name, run_date, stage, now))
            conn.commit()
            run_id = cursor.lastrowid
            logger.info(f"Started pipeline run: {newsletter_name} / stage {stage} / run_id={run_id}")
            return run_id

    def complete_pipeline_run(
        self,
        run_id: int,
        status: str,
        output_file: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Complete a pipeline run with status and output.

        Args:
            run_id: Pipeline run ID
            status: Status ('completed' or 'failed')
            output_file: Path to output file (if successful)
            error_message: Error message (if failed)

        Returns:
            True if updated successfully
        """
        now = datetime.now(timezone.utc).isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE pipeline_runs
                SET status = %s,
                    output_file = %s,
                    error_message = %s,
                    completed_at = %s
                WHERE id = %s
            """, (status, output_file, error_message, now, run_id))
            conn.commit()

            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"Completed pipeline run {run_id}: status={status}")
            return updated

    def get_pipeline_run_status(
        self,
        newsletter_name: str,
        run_date: str,
        stage: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent pipeline run status for a newsletter stage.

        Args:
            newsletter_name: Name of the newsletter
            run_date: Date string (YYYY-MM-DD)
            stage: Stage number (1-5)

        Returns:
            Pipeline run dictionary, or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pipeline_runs
                WHERE newsletter_name = %s
                  AND run_date = %s
                  AND stage = %s
                -- pipeline_runs does not store created_at; use started_at/id as recency proxy
                ORDER BY started_at DESC NULLS LAST, id DESC
                LIMIT 1
            """, (newsletter_name, run_date, stage))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    # === Pipeline Execution Methods (for replay/resume) ===

    def create_pipeline_execution(
        self,
        newsletter_name: str,
        run_date: str,
        config_snapshot: Dict[str, Any]
    ) -> int:
        """
        Create a new pipeline execution record with config snapshot.

        Args:
            newsletter_name: Name of the newsletter
            run_date: Date string (YYYY-MM-DD)
            config_snapshot: Full newsletter configuration from YAML

        Returns:
            ID of the created pipeline execution
        """
        import json
        now = datetime.now(timezone.utc).isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pipeline_executions (
                    newsletter_name, run_date, config_snapshot, status, created_at
                ) VALUES (%s, %s, %s, 'running', %s)
            """, (newsletter_name, run_date, json.dumps(config_snapshot), now))
            conn.commit()
            execution_id = cursor.lastrowid
            logger.info(f"Created pipeline execution: {newsletter_name} / {run_date} / execution_id={execution_id}")
            return execution_id

    def update_pipeline_execution_status(
        self,
        execution_id: int,
        status: str,
        last_successful_stage: Optional[int] = None
    ) -> bool:
        """
        Update pipeline execution status and last successful stage.

        Args:
            execution_id: Pipeline execution ID
            status: Status ('running', 'completed', 'partial', 'failed')
            last_successful_stage: Last stage that completed successfully (1-5)

        Returns:
            True if updated successfully
        """
        now = datetime.now(timezone.utc).isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()

            if status in ('completed', 'partial', 'failed'):
                cursor.execute("""
                    UPDATE pipeline_executions
                    SET status = %s,
                        last_successful_stage = %s,
                        completed_at = %s
                    WHERE id = %s
                """, (status, last_successful_stage, now, execution_id))
            else:
                cursor.execute("""
                    UPDATE pipeline_executions
                    SET status = %s,
                        last_successful_stage = %s
                    WHERE id = %s
                """, (status, last_successful_stage, execution_id))

            conn.commit()
            updated = cursor.rowcount > 0

            if updated:
                logger.info(f"Updated pipeline execution {execution_id}: status={status}, last_stage={last_successful_stage}")

            return updated

    def get_pipeline_execution_by_id(self, execution_id: int) -> Optional[Dict[str, Any]]:
        """
        Get pipeline execution by ID.

        Args:
            execution_id: Pipeline execution ID

        Returns:
            Pipeline execution dictionary, or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pipeline_executions WHERE id = %s
            """, (execution_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    def get_pipeline_execution_by_date(
        self,
        newsletter_name: str,
        run_date: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get most recent pipeline execution for a newsletter and date.

        Args:
            newsletter_name: Name of the newsletter
            run_date: Date string (YYYY-MM-DD)

        Returns:
            Pipeline execution dictionary, or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pipeline_executions
                WHERE newsletter_name = %s AND run_date = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (newsletter_name, run_date))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    def get_last_failed_execution(
        self,
        newsletter_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent failed or partial pipeline execution.

        Args:
            newsletter_name: Optional filter by newsletter name

        Returns:
            Pipeline execution dictionary, or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if newsletter_name:
                cursor.execute("""
                    SELECT * FROM pipeline_executions
                    WHERE newsletter_name = %s
                      AND status IN ('failed', 'partial')
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (newsletter_name,))
            else:
                cursor.execute("""
                    SELECT * FROM pipeline_executions
                    WHERE status IN ('failed', 'partial')
                    ORDER BY created_at DESC
                    LIMIT 1
                """)

            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    def get_pipeline_runs_by_execution(
        self,
        execution_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get all pipeline runs (stages) for a specific execution.

        Args:
            execution_id: Pipeline execution ID

        Returns:
            List of pipeline run dictionaries, ordered by stage
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pipeline_runs
                WHERE execution_id = %s
                ORDER BY stage ASC
            """, (execution_id,))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def link_pipeline_run_to_execution(
        self,
        run_id: int,
        execution_id: int
    ) -> bool:
        """
        Link a pipeline run to a pipeline execution.

        Args:
            run_id: Pipeline run ID
            execution_id: Pipeline execution ID

        Returns:
            True if updated successfully
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE pipeline_runs
                SET execution_id = %s
                WHERE id = %s
            """, (execution_id, run_id))
            conn.commit()

            return cursor.rowcount > 0

    def invalidate_subsequent_stages(
        self,
        execution_id: int,
        from_stage: int
    ) -> int:
        """
        Mark stages >= from_stage as 'pending' to force re-execution.

        This is used when resuming from a failed stage - all subsequent
        stages need to be re-run to ensure data consistency.

        Args:
            execution_id: Pipeline execution ID
            from_stage: Stage number to start invalidation from (inclusive)

        Returns:
            Number of stages invalidated
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE pipeline_runs
                SET status = 'pending',
                    completed_at = NULL,
                    error_message = NULL
                WHERE execution_id = %s
                  AND stage >= %s
            """, (execution_id, from_stage))
            conn.commit()

            invalidated = cursor.rowcount

            if invalidated > 0:
                logger.info(f"Invalidated {invalidated} stages >= {from_stage} for execution {execution_id}")

            return invalidated

    def get_url_by_id(self, url_id: int) -> Optional[Dict[str, Any]]:
        """
        Get URL record by ID.

        Args:
            url_id: URL ID to retrieve

        Returns:
            URL dictionary with all fields, or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM urls WHERE id = %s", (url_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    # === Ranking Methods (Stage 03) ===

    def create_ranking_run(
        self,
        newsletter_name: str,
        run_date: str,
        ranker_method: str,
        categories_filter: List[str],
        articles_count: int,
        execution_time_seconds: float
    ) -> int:
        """
        Create a new ranking run record.

        Args:
            newsletter_name: Name of the newsletter
            run_date: Date of execution (YYYY-MM-DD)
            ranker_method: Ranking method used (dual_subset, level_scoring, etc.)
            categories_filter: List of categories included
            articles_count: Number of articles to rank (top N)
            execution_time_seconds: Time taken to complete ranking

        Returns:
            ID of the created ranking run
        """
        import json

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ranking_runs (
                    newsletter_name, run_date, ranker_method,
                    categories_filter, articles_count, execution_time_seconds, status
                ) VALUES (%s, %s, %s, %s, %s, %s, 'completed')
                ON CONFLICT(newsletter_name, run_date) DO UPDATE SET
                    ranker_method = excluded.ranker_method,
                    categories_filter = excluded.categories_filter,
                    articles_count = excluded.articles_count,
                    execution_time_seconds = excluded.execution_time_seconds,
                    generated_at = CURRENT_TIMESTAMP,
                    status = 'completed'
            """, (
                newsletter_name,
                run_date,
                ranker_method,
                json.dumps(categories_filter),
                articles_count,
                execution_time_seconds
            ))
            conn.commit()

            # Get the ID of the inserted/updated row
            cursor.execute("""
                SELECT id FROM ranking_runs
                WHERE newsletter_name = %s AND run_date = %s
            """, (newsletter_name, run_date))
            row = cursor.fetchone()

            ranking_run_id = row['id']
            logger.info(f"Created ranking run ID {ranking_run_id} for {newsletter_name} on {run_date}")
            return ranking_run_id

    def insert_ranked_urls(
        self,
        ranking_run_id: int,
        ranked_urls: List[Dict[str, Any]]
    ) -> int:
        """
        Insert ranked URLs for a ranking run.

        Args:
            ranking_run_id: ID of the ranking run
            ranked_urls: List of dicts with keys:
                - url_id: ID of the URL
                - rank: Rank position (1 = best)
                - related_url_ids: Optional JSON string of related URL IDs (v3.2)

        Returns:
            Number of URLs inserted
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Delete existing ranked URLs for this run (if re-running)
            cursor.execute("DELETE FROM ranked_urls WHERE ranking_run_id = %s", (ranking_run_id,))

            # Insert new ranked URLs (v3.2: includes related_url_ids for cluster context)
            for ranked_url in ranked_urls:
                related_url_ids = ranked_url.get('related_url_ids')  # JSON string or None
                cursor.execute("""
                    INSERT INTO ranked_urls (
                        ranking_run_id, url_id, rank, related_url_ids
                    ) VALUES (%s, %s, %s, %s)
                """, (
                    ranking_run_id,
                    ranked_url['url_id'],
                    ranked_url['rank'],
                    related_url_ids
                ))

            conn.commit()
            logger.info(f"Inserted {len(ranked_urls)} ranked URLs for ranking run {ranking_run_id}")
            return len(ranked_urls)

    def update_ranking_total(self, ranking_run_id: int, total_ranked: int):
        """
        Update the total_ranked count for a ranking run.

        Args:
            ranking_run_id: ID of the ranking run
            total_ranked: Total number of URLs ranked
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ranking_runs
                SET total_ranked = %s
                WHERE id = %s
            """, (total_ranked, ranking_run_id))
            conn.commit()

    def get_ranking_run(self, newsletter_name: str, run_date: str) -> Optional[Dict[str, Any]]:
        """
        Get ranking run by newsletter name and date.

        Args:
            newsletter_name: Name of the newsletter
            run_date: Date of execution (YYYY-MM-DD)

        Returns:
            Ranking run dictionary or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM ranking_runs
                WHERE newsletter_name = %s AND run_date = %s
            """, (newsletter_name, run_date))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    def get_ranked_urls(
        self,
        ranking_run_id: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get ranked URLs for a ranking run with full URL data.

        Args:
            ranking_run_id: ID of the ranking run
            limit: Optional limit on number of results

        Returns:
            List of ranked URL dictionaries with joined data from urls table,
            including related_url_ids from cluster deduplication (v3.2)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT
                    ru.id as ranked_url_id,
                    ru.rank,
                    ru.related_url_ids,
                    u.*
                FROM ranked_urls ru
                JOIN urls u ON ru.url_id = u.id
                WHERE ru.ranking_run_id = %s
                ORDER BY ru.rank ASC
            """

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query, (ranking_run_id,))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def get_ranked_urls_with_content(
        self,
        ranking_run_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get ranked URLs that have successfully extracted content.

        Args:
            ranking_run_id: ID of the ranking run

        Returns:
            List of ranked URL dictionaries with content
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    ru.rank,
                    u.*
                FROM ranked_urls ru
                JOIN urls u ON ru.url_id = u.id
                WHERE ru.ranking_run_id = %s
                  AND u.extraction_status = 'success'
                  AND u.full_content IS NOT NULL
                ORDER BY ru.rank ASC
            """, (ranking_run_id,))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    # === Debug Report Methods ===

    def save_debug_report(
        self,
        newsletter_name: str,
        run_date: str,
        debug_data: Dict[str, Any]
    ) -> bool:
        """
        Save debug report to database.

        Args:
            newsletter_name: Name of the newsletter
            run_date: Date of execution (YYYY-MM-DD)
            debug_data: Dictionary containing all debug information

        Returns:
            True if saved successfully
        """
        import json

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Extract stage durations and token counts from debug_data
            stages = debug_data.get('stages', {})

            cursor.execute("""
                INSERT INTO debug_reports (
                    newsletter_name, run_date,
                    stage_01_duration, stage_02_duration, stage_03_duration,
                    stage_04_duration, stage_05_duration, total_duration,
                    tokens_used_stage_02, tokens_used_stage_03, tokens_used_stage_05,
                    total_tokens, report_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(newsletter_name, run_date) DO UPDATE SET
                    stage_01_duration = excluded.stage_01_duration,
                    stage_02_duration = excluded.stage_02_duration,
                    stage_03_duration = excluded.stage_03_duration,
                    stage_04_duration = excluded.stage_04_duration,
                    stage_05_duration = excluded.stage_05_duration,
                    total_duration = excluded.total_duration,
                    tokens_used_stage_02 = excluded.tokens_used_stage_02,
                    tokens_used_stage_03 = excluded.tokens_used_stage_03,
                    tokens_used_stage_05 = excluded.tokens_used_stage_05,
                    total_tokens = excluded.total_tokens,
                    report_json = excluded.report_json,
                    generated_at = CURRENT_TIMESTAMP
            """, (
                newsletter_name,
                run_date,
                stages.get('stage_01', {}).get('duration'),
                stages.get('stage_02', {}).get('duration'),
                stages.get('stage_03', {}).get('duration'),
                stages.get('stage_04', {}).get('duration'),
                stages.get('stage_05', {}).get('duration'),
                debug_data.get('total_duration'),
                stages.get('stage_02', {}).get('tokens_used'),
                stages.get('stage_03', {}).get('tokens_used'),
                stages.get('stage_05', {}).get('tokens_used'),
                debug_data.get('summary', {}).get('total_tokens'),
                json.dumps(debug_data, indent=2)
            ))
            conn.commit()

            logger.info(f"Saved debug report for {newsletter_name} on {run_date}")
            return True

    def get_debug_report(self, newsletter_name: str, run_date: str) -> Optional[Dict[str, Any]]:
        """
        Get debug report from database.

        Args:
            newsletter_name: Name of the newsletter
            run_date: Date of execution (YYYY-MM-DD)

        Returns:
            Debug report dictionary or None if not found
        """
        import json

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM debug_reports
                WHERE newsletter_name = %s AND run_date = %s
            """, (newsletter_name, run_date))
            row = cursor.fetchone()

            if row:
                report = dict(row)
                # Parse JSON back to dict
                if report.get('report_json'):
                    report['report_data'] = json.loads(report['report_json'])
                return report
            return None

    # === Cookie Management Methods (Stage 04 - Authenticated Scraping) ===

    def get_cookies_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        """
        Get all cookies for a specific domain.

        Args:
            domain: Domain to retrieve cookies for (e.g., 'ft.com')

        Returns:
            List of cookie dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM site_cookies
                WHERE domain = %s OR domain = %s
                ORDER BY cookie_name
            """, (domain, f".{domain}"))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def has_cookies_for_domain(self, domain: str) -> bool:
        """
        Check if cookies exist for a domain.

        Args:
            domain: Domain to check

        Returns:
            True if cookies exist for this domain
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count FROM site_cookies
                WHERE domain = %s OR domain = %s
            """, (domain, f".{domain}"))

            row = cursor.fetchone()
            return row['count'] > 0

    def save_cookies(self, domain: str, cookies: List[Dict[str, Any]]) -> int:
        """
        Save or update cookies for a domain.

        Uses UPSERT (INSERT OR REPLACE) to handle both new and existing cookies.

        Args:
            domain: Domain these cookies belong to
            cookies: List of cookie dictionaries with keys:
                - name (required)
                - value (required)
                - path (optional, default '/')
                - secure (optional, default True)
                - httpOnly (optional, default False)
                - sameSite (optional)
                - expiry or expirationDate (optional, Unix timestamp)

        Returns:
            Number of cookies saved
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            saved_count = 0

            for cookie in cookies:
                try:
                    # Normalize cookie data
                    cookie_name = cookie.get('name') or cookie.get('cookie_name')
                    cookie_value = cookie.get('value') or cookie.get('cookie_value')

                    if not cookie_name or not cookie_value:
                        logger.warning(f"Skipping invalid cookie (missing name or value)")
                        continue

                    # Handle expiry field (could be 'expiry' or 'expirationDate')
                    expiry = cookie.get('expiry') or cookie.get('expirationDate')
                    if expiry:
                        expiry = int(expiry)

                    # Handle sameSite (could be null, convert to None)
                    same_site = cookie.get('sameSite') or cookie.get('same_site')
                    if same_site and same_site not in ['Strict', 'Lax', 'None']:
                        same_site = None

                    cursor.execute("""
                        INSERT INTO site_cookies (
                            domain, cookie_name, cookie_value, path,
                            secure, http_only, same_site, expiry
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(domain, cookie_name) DO UPDATE SET
                            cookie_value = excluded.cookie_value,
                            path = excluded.path,
                            secure = excluded.secure,
                            http_only = excluded.http_only,
                            same_site = excluded.same_site,
                            expiry = excluded.expiry,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        cookie.get('domain', domain),
                        cookie_name,
                        cookie_value,
                        cookie.get('path', '/'),
                        int(cookie.get('secure', True)),
                        int(cookie.get('httpOnly') or cookie.get('http_only', False)),
                        same_site,
                        expiry
                    ))
                    saved_count += 1

                except Exception as e:
                    logger.error(f"Failed to save cookie {cookie.get('name')}: {e}")
                    continue

            conn.commit()
            logger.info(f"Saved {saved_count} cookies for domain {domain}")
            return saved_count

    def delete_cookies_for_domain(self, domain: str) -> int:
        """
        Delete all cookies for a domain.

        Args:
            domain: Domain to delete cookies for

        Returns:
            Number of cookies deleted
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM site_cookies
                WHERE domain = %s OR domain = %s
            """, (domain, f".{domain}"))
            conn.commit()

            deleted = cursor.rowcount
            logger.info(f"Deleted {deleted} cookies for domain {domain}")
            return deleted

    def get_all_cookie_domains(self) -> List[str]:
        """
        Get list of all domains that have cookies stored.

        Returns:
            List of unique domain names
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT domain FROM site_cookies
                ORDER BY domain
            """)

            rows = cursor.fetchall()
            return [row['domain'] for row in rows]

    def check_cookie_expiry(self, domain: str, threshold_days: int = 7) -> Dict[str, Any]:
        """
        Check if cookies for a domain need renewal.

        Args:
            domain: Domain to check
            threshold_days: Consider renewal needed if any cookie expires within this many days

        Returns:
            Dictionary with:
                - needs_renewal: bool
                - expiring_soon: list of cookie names expiring soon
                - expired: list of cookie names already expired
        """
        import time

        now = int(time.time())
        threshold = now + (threshold_days * 24 * 60 * 60)

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Find expiring cookies
            cursor.execute("""
                SELECT cookie_name, expiry FROM site_cookies
                WHERE (domain = %s OR domain = %s)
                  AND expiry IS NOT NULL
                  AND expiry < %s
            """, (domain, f".{domain}", threshold))

            expiring = cursor.fetchall()

            result = {
                'needs_renewal': len(expiring) > 0,
                'expiring_soon': [],
                'expired': []
            }

            for row in expiring:
                if row['expiry'] < now:
                    result['expired'].append(row['cookie_name'])
                else:
                    result['expiring_soon'].append(row['cookie_name'])

            return result

    def get_article_summary(self, url_id: int) -> Optional[str]:
        """
        Get cached AI summary for an article.

        Args:
            url_id: URL ID

        Returns:
            Summary text if exists, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ai_summary FROM urls WHERE id = %s", (url_id,))
            row = cursor.fetchone()
            return row['ai_summary'] if row and row['ai_summary'] else None

    def save_article_summary(self, url_id: int, summary: str) -> bool:
        """
        Save AI-generated summary for an article.

        Args:
            url_id: URL ID
            summary: Summary text

        Returns:
            True if saved successfully
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE urls SET ai_summary = %s WHERE id = %s", (summary, url_id))
            conn.commit()
            return True

    # ===== Newsletter Methods (v3.1) =====

    def save_newsletter(
        self,
        newsletter_name: str,
        run_date: str,
        content_markdown: str,
        template_name: str,
        output_format: str,
        articles_count: int,
        articles_with_content: int,
        ranking_run_id: Optional[int] = None,
        total_tokens_used: Optional[int] = None,
        generation_duration_seconds: Optional[float] = None,
        output_file_md: Optional[str] = None,
        context_report_file: Optional[str] = None,
        content_html: Optional[str] = None,
        output_file_html: Optional[str] = None,
        categories: Optional[List[str]] = None,
        generation_method: str = '4-step',
        model_summarizer: str = 'gpt-4o-mini',
        model_writer: str = 'gpt-4o'
    ) -> int:
        """
        Save complete newsletter to database.

        Args:
            newsletter_name: Newsletter identifier
            run_date: Date (YYYY-MM-DD)
            content_markdown: Complete newsletter content in Markdown
            template_name: Template used (e.g., 'default', 'chief_economist')
            output_format: Format ('markdown', 'html', 'both')
            articles_count: Total articles in newsletter
            articles_with_content: Articles with full content
            ranking_run_id: FK to ranking_runs table
            total_tokens_used: Total LLM tokens consumed
            generation_duration_seconds: Generation time
            output_file_md: Path to .md file
            context_report_file: Path to context_report.json
            content_html: Newsletter in HTML (optional)
            output_file_html: Path to .html file (optional)
            categories: List of categories (optional)
            generation_method: Generation method (default: '4-step')
            model_summarizer: Model for summarization
            model_writer: Model for writing

        Returns:
            Newsletter ID
        """
        import json

        with self.get_connection() as conn:
            cursor = conn.cursor()

            categories_json = json.dumps(categories) if categories else None

            cursor.execute("""
                INSERT INTO newsletters (
                    newsletter_name, run_date, template_name, output_format,
                    categories, content_markdown, content_html,
                    articles_count, articles_with_content, ranking_run_id,
                    generation_method, model_summarizer, model_writer,
                    total_tokens_used, generation_duration_seconds,
                    output_file_md, output_file_html, context_report_file
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (newsletter_name, run_date) DO UPDATE SET
                    template_name = EXCLUDED.template_name,
                    output_format = EXCLUDED.output_format,
                    categories = EXCLUDED.categories,
                    content_markdown = EXCLUDED.content_markdown,
                    content_html = EXCLUDED.content_html,
                    articles_count = EXCLUDED.articles_count,
                    articles_with_content = EXCLUDED.articles_with_content,
                    ranking_run_id = EXCLUDED.ranking_run_id,
                    generation_method = EXCLUDED.generation_method,
                    model_summarizer = EXCLUDED.model_summarizer,
                    model_writer = EXCLUDED.model_writer,
                    total_tokens_used = EXCLUDED.total_tokens_used,
                    generation_duration_seconds = EXCLUDED.generation_duration_seconds,
                    output_file_md = EXCLUDED.output_file_md,
                    output_file_html = EXCLUDED.output_file_html,
                    context_report_file = EXCLUDED.context_report_file,
                    generated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                newsletter_name, run_date, template_name, output_format,
                categories_json, content_markdown, content_html,
                articles_count, articles_with_content, ranking_run_id,
                generation_method, model_summarizer, model_writer,
                total_tokens_used, generation_duration_seconds,
                output_file_md, output_file_html, context_report_file
            ))

            conn.commit()
            row = cursor.fetchone()
            newsletter_id = row['id'] if row else None
            logger.info(f"Saved newsletter '{newsletter_name}' for {run_date} (ID: {newsletter_id})")
            return newsletter_id

    def get_newsletter(
        self,
        newsletter_name: str,
        run_date: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get newsletter by name and date.

        Args:
            newsletter_name: Newsletter identifier
            run_date: Date (YYYY-MM-DD)

        Returns:
            Newsletter dict or None if not found
        """
        import json

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM newsletters
                WHERE newsletter_name = %s AND run_date = %s
            """, (newsletter_name, run_date))

            row = cursor.fetchone()
            if not row:
                return None

            newsletter = dict(row)
            # Parse categories JSON
            if newsletter.get('categories'):
                newsletter['categories'] = json.loads(newsletter['categories'])
            return newsletter

    def get_newsletter_by_id(self, newsletter_id: int) -> Optional[Dict[str, Any]]:
        """
        Get newsletter by ID.

        Args:
            newsletter_id: Newsletter database ID

        Returns:
            Newsletter dict or None if not found
        """
        import json

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM newsletters
                WHERE id = %s
            """, (newsletter_id,))

            row = cursor.fetchone()
            if not row:
                return None

            newsletter = dict(row)
            # Parse categories JSON
            if newsletter.get('categories'):
                newsletter['categories'] = json.loads(newsletter['categories'])
            return newsletter

    def get_newsletters_by_date_range(
        self,
        start_date: str,
        end_date: str,
        newsletter_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get newsletters in date range.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            newsletter_name: Optional filter by name

        Returns:
            List of newsletter dicts
        """
        import json

        with self.get_connection() as conn:
            cursor = conn.cursor()

            if newsletter_name:
                cursor.execute("""
                    SELECT * FROM newsletters
                    WHERE run_date BETWEEN %s AND %s
                      AND newsletter_name = %s
                    ORDER BY run_date DESC, generated_at DESC
                """, (start_date, end_date, newsletter_name))
            else:
                cursor.execute("""
                    SELECT * FROM newsletters
                    WHERE run_date BETWEEN %s AND %s
                    ORDER BY run_date DESC, generated_at DESC
                """, (start_date, end_date))

            rows = cursor.fetchall()
            newsletters = []
            for row in rows:
                newsletter = dict(row)
                if newsletter.get('categories'):
                    newsletter['categories'] = json.loads(newsletter['categories'])
                newsletters.append(newsletter)

            return newsletters

    def get_latest_newsletters(self, limit: int = 10, user_id: int | None = None) -> List[Dict[str, Any]]:
        """
        Get latest newsletters generated.

        Args:
            limit: Maximum number to return
            user_id: If provided, include private newsletters owned by this user

        Returns:
            List of newsletter dicts
        """
        import json

        with self.get_connection() as conn:
            cursor = conn.cursor()
            params = [limit]
            visibility_filter = "nc.visibility = 'public'"
            query = None

            if user_id is not None:
                visibility_filter = "(nc.visibility = 'public' OR nc.created_by_user_id = %s)"
                params.insert(0, user_id)

            try:
                query = f"""
                    SELECT n.*
                    FROM newsletters n
                    JOIN newsletter_configs nc ON nc.name = n.newsletter_name
                    WHERE {visibility_filter}
                    ORDER BY n.generated_at DESC
                    LIMIT %s
                """
                cursor.execute(query, tuple(params))
            except psycopg.errors.UndefinedColumn:
                conn.rollback()
                # Backward compatibility if visibility column has not been migrated yet
                fallback_params = (limit,)
                cursor.execute("""
                    SELECT *
                    FROM newsletters
                    ORDER BY generated_at DESC
                    LIMIT %s
                """, fallback_params)
            rows = cursor.fetchall()
            newsletters = []
            for row in rows:
                newsletter = dict(row)
                if newsletter.get('categories'):
                    newsletter['categories'] = json.loads(newsletter['categories'])
                newsletters.append(newsletter)

            return newsletters

    def get_newsletter_stats(
        self,
        newsletter_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get newsletter statistics.

        Args:
            newsletter_name: Optional filter by name

        Returns:
            Dict with statistics
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if newsletter_name:
                cursor.execute("""
                    SELECT
                        COUNT(*) as total,
                        AVG(articles_count) as avg_articles,
                        AVG(articles_with_content) as avg_with_content,
                        AVG(total_tokens_used) as avg_tokens,
                        AVG(generation_duration_seconds) as avg_duration,
                        MIN(run_date) as first_date,
                        MAX(run_date) as last_date
                    FROM newsletters
                    WHERE newsletter_name = %s
                """, (newsletter_name,))
            else:
                cursor.execute("""
                    SELECT
                        COUNT(*) as total,
                        AVG(articles_count) as avg_articles,
                        AVG(articles_with_content) as avg_with_content,
                        AVG(total_tokens_used) as avg_tokens,
                        AVG(generation_duration_seconds) as avg_duration,
                        MIN(run_date) as first_date,
                        MAX(run_date) as last_date
                    FROM newsletters
                """)

            row = cursor.fetchone()
            return dict(row) if row else {}

    # ===== Scoring Methods (v3.1) =====

    def update_url_scoring(
        self,
        url_id: int,
        relevance_level: int,
        scored_by_method: str
    ) -> bool:
        """
        Update scoring for a single URL.

        Args:
            url_id: URL ID
            relevance_level: Level 1-5
            scored_by_method: 'level_scoring' or 'dual_subset'

        Returns:
            True if updated successfully
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()

            cursor.execute("""
                UPDATE urls
                SET relevance_level = %s,
                    scored_at = %s,
                    scored_by_method = %s
                WHERE id = %s
            """, (relevance_level, now, scored_by_method, url_id))

            conn.commit()
            return cursor.rowcount > 0

    def batch_update_url_scoring(
        self,
        updates: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Batch update scoring for multiple URLs.

        Args:
            updates: List of dicts with keys:
                - id: URL ID
                - relevance_level: Level 1-5
                - scored_by_method: 'level_scoring' or 'dual_subset'

        Returns:
            Dict with 'updated' count
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()

            updated_count = 0
            for update in updates:
                cursor.execute("""
                    UPDATE urls
                    SET relevance_level = %s,
                        scored_at = %s,
                        scored_by_method = %s
                    WHERE id = %s
                """, (
                    update['relevance_level'],
                    now,
                    update['scored_by_method'],
                    update['id']
                ))
                updated_count += cursor.rowcount

            conn.commit()
            logger.info(f"Batch updated {updated_count} URL scores")
            return {'updated': updated_count}

    # ===== Cluster Context Methods (for Stage 03/05 integration) =====

    def get_cluster_article_count(self, cluster_id: str) -> int:
        """
        Get the number of articles in a cluster.

        Args:
            cluster_id: Cluster identifier

        Returns:
            Number of articles in the cluster
        """
        if not cluster_id:
            return 0

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM urls
                WHERE cluster_id = %s
                  AND content_type = 'contenido'
            """, (cluster_id,))
            row = cursor.fetchone()
            return row['count'] if row else 0

    def get_cluster_articles_for_context(
        self,
        cluster_id: str,
        exclude_url_id: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get related articles from a cluster for 360° context in Stage 05.

        Returns articles sorted by word_count (most content first), excluding
        the main article.

        Args:
            cluster_id: Cluster identifier
            exclude_url_id: URL ID to exclude (the main/representative article)
            limit: Maximum number of related articles to return

        Returns:
            List of article dicts with: id, title, source, url, full_content, word_count, extracted_at
        """
        if not cluster_id:
            return []

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    id, title, source, url, full_content, word_count, extracted_at
                FROM urls
                WHERE cluster_id = %s
                  AND id != %s
                  AND content_type = 'contenido'
                ORDER BY
                    CASE WHEN word_count IS NOT NULL THEN word_count ELSE 0 END DESC,
                    extracted_at DESC
                LIMIT %s
            """, (cluster_id, exclude_url_id, limit))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_representative_url_from_cluster(
        self,
        cluster_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the representative article from a cluster (highest word_count).

        Used in Stage 03 to select which article represents a cluster
        when deduplicating.

        Args:
            cluster_id: Cluster identifier

        Returns:
            URL dict of the representative article, or None if cluster is empty
        """
        if not cluster_id:
            return None

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM urls
                WHERE cluster_id = %s
                  AND content_type = 'contenido'
                ORDER BY
                    CASE WHEN word_count IS NOT NULL THEN word_count ELSE 0 END DESC,
                    extracted_at DESC
                LIMIT 1
            """, (cluster_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_urls_by_cluster_id(self, cluster_id: str) -> List[Dict[str, Any]]:
        """
        Get all URLs belonging to a cluster.

        Args:
            cluster_id: Cluster identifier

        Returns:
            List of URL dicts in the cluster
        """
        if not cluster_id:
            return []

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM urls
                WHERE cluster_id = %s
                ORDER BY
                    CASE WHEN word_count IS NOT NULL THEN word_count ELSE 0 END DESC,
                    extracted_at DESC
            """, (cluster_id,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_cluster_related_articles(
        self,
        cluster_id: str,
        exclude_url_id: int,
        reference_date: str,
        max_days_back: int = 0,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get related articles from the same cluster within a time window.

        Used by Stage 05 to provide historical context for news summaries.

        Args:
            cluster_id: Cluster identifier
            exclude_url_id: URL ID to exclude (the main article)
            reference_date: Reference date (YYYY-MM-DD) for the time window
            max_days_back: Maximum days back from reference_date (0 = same day only)
            limit: Maximum number of related articles to return

        Returns:
            List of URL dicts for related articles within the time window
        """
        if not cluster_id or max_days_back < 0:
            return []

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM urls
                WHERE cluster_id = %s
                  AND id != %s
                  AND DATE(extracted_at) >= (DATE(%s) - INTERVAL '%s days')
                  AND DATE(extracted_at) <= DATE(%s)
                ORDER BY
                    extracted_at DESC,
                    CASE WHEN word_count IS NOT NULL THEN word_count ELSE 0 END DESC
                LIMIT %s
            """, (cluster_id, exclude_url_id, reference_date, max_days_back, reference_date, limit))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # ===== Cluster Name Methods (v3.2) =====

    def update_cluster_name(self, cluster_id: str, cluster_name: str) -> bool:
        """
        Update the name/hashtag for a cluster.

        Args:
            cluster_id: Cluster identifier
            cluster_name: Descriptive name or hashtag for the cluster

        Returns:
            True if updated successfully
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE clusters
                SET cluster_name = %s
                WHERE id = %s
            """, (cluster_name, cluster_id))
            conn.commit()

            updated = cursor.rowcount > 0
            if updated:
                logger.debug(f"Updated cluster name: {cluster_id} -> {cluster_name}")
            return updated

    def get_clusters_without_name(self, min_article_count: int = 2) -> List[Dict[str, Any]]:
        """
        Get clusters that don't have a name yet.

        Used to identify clusters that need hashtag generation.

        Args:
            min_article_count: Minimum articles to be considered (default: 2)

        Returns:
            List of cluster dicts with id, article_count, and sample titles
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.id, c.article_count, c.run_date, c.avg_similarity
                FROM clusters c
                WHERE (c.cluster_name IS NULL OR c.cluster_name = '')
                  AND c.article_count >= %s
                ORDER BY c.article_count DESC
            """, (min_article_count,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_cluster_titles(self, cluster_id: str, limit: int = 5) -> List[str]:
        """
        Get sample titles from a cluster for hashtag generation.

        Args:
            cluster_id: Cluster identifier
            limit: Maximum number of titles to return

        Returns:
            List of article titles
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT title
                FROM urls
                WHERE cluster_id = %s
                  AND title IS NOT NULL
                  AND title != ''
                ORDER BY extracted_at DESC
                LIMIT %s
            """, (cluster_id, limit))

            rows = cursor.fetchall()
            return [row['title'] for row in rows]

    def get_cluster_info(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full cluster information including name.

        Args:
            cluster_id: Cluster identifier

        Returns:
            Cluster dict or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM clusters
                WHERE id = %s
            """, (cluster_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_urls_for_newsletter_with_scoring(
        self,
        start_datetime: str,
        end_datetime: str,
        sources: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        skip_already_scored: bool = False,
        scored_within_days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get URLs with scoring filter (for incremental mode).

        Args:
            start_datetime: Start datetime (ISO format)
            end_datetime: End datetime (ISO format)
            sources: Optional list of sources to filter
            categories: Optional list of categories to filter
            skip_already_scored: If True, exclude URLs with relevance_level != NULL
            scored_within_days: If set, only URLs scored within N days ago

        Returns:
            List of URL dicts
        """
        from datetime import timedelta

        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT * FROM urls
                WHERE extracted_at >= %s AND extracted_at < %s
                  AND content_type = 'contenido'
            """
            params = [start_datetime, end_datetime]

            # Filter by sources
            if sources:
                placeholders = ','.join(['%s'] * len(sources))
                query += f" AND source IN ({placeholders})"
                params.extend(sources)

            # Filter by categories
            if categories:
                placeholders = ','.join(['%s'] * len(categories))
                query += f" AND categoria_tematica IN ({placeholders})"
                params.extend(categories)

            # Skip already scored
            if skip_already_scored:
                query += " AND relevance_level IS NULL"

            # Scored within days
            if scored_within_days is not None:
                cutoff = (datetime.now(timezone.utc) - timedelta(days=scored_within_days)).isoformat()
                query += " AND (scored_at IS NULL OR scored_at < ?)"
                params.append(cutoff)

            query += " ORDER BY extracted_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def save_newsletter(
        self,
        newsletter_name: str,
        run_date: str,
        content_markdown: str,
        content_html: Optional[str],
        template_name: str,
        output_format: str,
        articles_count: int,
        articles_with_content: int,
        ranking_run_id: Optional[int],
        total_tokens_used: int,
        generation_duration_seconds: float,
        output_file_md: Optional[str],
        output_file_html: Optional[str],
        context_report_file: Optional[str],
        categories: Optional[List[str]],
        generation_method: str,
        model_summarizer: str,
        model_writer: str
    ) -> int:
        """
        Save newsletter to database.

        Args:
            newsletter_name: Name of the newsletter
            run_date: Run date (YYYY-MM-DD)
            content_markdown: Newsletter content in Markdown format
            content_html: Newsletter content in HTML format (optional)
            template_name: Name of the prompt template used
            output_format: Output format ('markdown', 'html', 'both')
            articles_count: Total number of articles
            articles_with_content: Number of articles with full content
            ranking_run_id: ID of the ranking run (foreign key)
            total_tokens_used: Total tokens used in generation
            generation_duration_seconds: Generation duration in seconds
            output_file_md: Path to the markdown output file
            output_file_html: Path to the HTML output file
            context_report_file: Path to the context report file
            categories: List of categories
            generation_method: Generation method used
            model_summarizer: Summarizer model name
            model_writer: Writer model name

        Returns:
            Newsletter ID
        """
        import json

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Convert categories list to JSON string
            categories_json = json.dumps(categories) if categories else None

            # Check if newsletter already exists (ON CONFLICT UPDATE)
            cursor.execute("""
                INSERT INTO newsletters (
                    newsletter_name,
                    run_date,
                    content_markdown,
                    content_html,
                    template_name,
                    output_format,
                    articles_count,
                    articles_with_content,
                    ranking_run_id,
                    total_tokens_used,
                    generation_duration_seconds,
                    output_file_md,
                    output_file_html,
                    context_report_file,
                    categories,
                    generation_method,
                    model_summarizer,
                    model_writer,
                    generated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                )
                ON CONFLICT (newsletter_name, run_date)
                DO UPDATE SET
                    content_markdown = EXCLUDED.content_markdown,
                    content_html = EXCLUDED.content_html,
                    template_name = EXCLUDED.template_name,
                    output_format = EXCLUDED.output_format,
                    articles_count = EXCLUDED.articles_count,
                    articles_with_content = EXCLUDED.articles_with_content,
                    ranking_run_id = EXCLUDED.ranking_run_id,
                    total_tokens_used = EXCLUDED.total_tokens_used,
                    generation_duration_seconds = EXCLUDED.generation_duration_seconds,
                    output_file_md = EXCLUDED.output_file_md,
                    output_file_html = EXCLUDED.output_file_html,
                    context_report_file = EXCLUDED.context_report_file,
                    categories = EXCLUDED.categories,
                    generation_method = EXCLUDED.generation_method,
                    model_summarizer = EXCLUDED.model_summarizer,
                    model_writer = EXCLUDED.model_writer,
                    generated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                newsletter_name,
                run_date,
                content_markdown,
                content_html,
                template_name,
                output_format,
                articles_count,
                articles_with_content,
                ranking_run_id,
                total_tokens_used,
                generation_duration_seconds,
                output_file_md,
                output_file_html,
                context_report_file,
                categories_json,
                generation_method,
                model_summarizer,
                model_writer
            ))

            result = cursor.fetchone()
            newsletter_id = result['id']
            conn.commit()

            logger.info(f"Newsletter saved to database: {newsletter_name} (ID: {newsletter_id})")
            return newsletter_id

    # ============================================
    # USER MANAGEMENT METHODS (Authentication)
    # ============================================

    def create_user(self, nombre: str, email: str, hashed_password: str, role: str = "user") -> Optional[Dict]:
        """
        Create new user.

        Args:
            nombre: User's name
            email: User's email (must be unique)
            hashed_password: Bcrypt hashed password
            role: User role (admin, user, enterprise)

        Returns:
            User dict if successful, None if email already exists
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO users (nombre, email, hashed_password, role)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, nombre, email, role, is_active, created_at, updated_at, last_login
                """, (nombre, email, hashed_password, role))

                user = cursor.fetchone()
                conn.commit()

                logger.info(f"User created: {email} (role: {role})")
                return user

        except psycopg.errors.UniqueViolation:
            logger.warning(f"User creation failed: email already exists ({email})")
            return None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """
        Fetch user by email (for login).

        Args:
            email: User's email

        Returns:
            User dict with all fields including hashed_password, or None if not found
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT id, nombre, email, hashed_password, role, is_active,
                           created_at, updated_at, last_login
                    FROM users
                    WHERE email = %s
                """, (email,))

                user = cursor.fetchone()
                return user

        except Exception as e:
            logger.error(f"Error fetching user by email: {e}")
            return None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """
        Fetch user by ID (for token validation).

        Args:
            user_id: User's ID

        Returns:
            User dict without hashed_password, or None if not found
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT id, nombre, email, role, is_active,
                           created_at, updated_at, last_login
                    FROM users
                    WHERE id = %s
                """, (user_id,))

                user = cursor.fetchone()
                return user

        except Exception as e:
            logger.error(f"Error fetching user by ID: {e}")
            return None

    def update_user_profile(self, user_id: int, nombre: Optional[str] = None,
                           new_password_hash: Optional[str] = None) -> bool:
        """
        Update user's name and/or password.

        Args:
            user_id: User's ID
            nombre: New name (optional)
            new_password_hash: New hashed password (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Build dynamic update query
                update_fields = []
                params = []

                if nombre is not None:
                    update_fields.append("nombre = %s")
                    params.append(nombre)

                if new_password_hash is not None:
                    update_fields.append("hashed_password = %s")
                    params.append(new_password_hash)

                if not update_fields:
                    return True  # Nothing to update

                params.append(user_id)

                query = f"""
                    UPDATE users
                    SET {', '.join(update_fields)}
                    WHERE id = %s
                """

                cursor.execute(query, params)
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"User profile updated: ID {user_id}")
                    return True
                else:
                    logger.warning(f"User not found for update: ID {user_id}")
                    return False

        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            return False

    def update_user_role(self, user_id: int, new_role: str) -> bool:
        """
        Update user role (admin operation).

        Args:
            user_id: User's ID
            new_role: New role (user or enterprise)

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE users
                    SET role = %s
                    WHERE id = %s AND role != 'admin'
                """, (new_role, user_id))

                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"User role updated: ID {user_id} -> {new_role}")
                    return True
                else:
                    logger.warning(f"User not found or is admin (cannot change role): ID {user_id}")
                    return False

        except Exception as e:
            logger.error(f"Error updating user role: {e}")
            return False

    def get_all_users(self, include_inactive: bool = False) -> List[Dict]:
        """
        Fetch all users (admin operation).

        Args:
            include_inactive: Include deactivated users

        Returns:
            List of user dicts (without hashed_password)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, nombre, email, role, is_active,
                           created_at, updated_at, last_login
                    FROM users
                """

                if not include_inactive:
                    query += " WHERE is_active = TRUE"

                query += " ORDER BY created_at DESC"

                cursor.execute(query)
                users = cursor.fetchall()

                return users

        except Exception as e:
            logger.error(f"Error fetching all users: {e}")
            return []

    def update_last_login(self, user_id: int) -> bool:
        """
        Update last_login timestamp.

        Args:
            user_id: User's ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE users
                    SET last_login = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))

                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error updating last_login: {e}")
            return False

    def deactivate_user(self, user_id: int) -> bool:
        """
        Soft delete user (set is_active=False).

        Args:
            user_id: User's ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE users
                    SET is_active = FALSE
                    WHERE id = %s AND role != 'admin'
                """, (user_id,))

                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"User deactivated: ID {user_id}")
                    return True
                else:
                    logger.warning(f"User not found or is admin (cannot deactivate): ID {user_id}")
                    return False

        except Exception as e:
            logger.error(f"Error deactivating user: {e}")
            return False

    def reactivate_user(self, user_id: int) -> bool:
        """
        Reactivate user (set is_active=True).

        Args:
            user_id: User's ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE users
                    SET is_active = TRUE
                    WHERE id = %s
                """, (user_id,))

                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"User reactivated: ID {user_id}")
                    return True
                else:
                    logger.warning(f"User not found: ID {user_id}")
                    return False

        except Exception as e:
            logger.error(f"Error reactivating user: {e}")
            return False

    # ============================================
    # CATEGORIES MANAGEMENT
    # ============================================

    def get_all_categories(self) -> List[Dict[str, Any]]:
        """
        Get all categories from the database.

        Returns:
            List[Dict]: List of category dictionaries with fields:
                - id (str): Category identifier
                - name (str): Display name
                - description (str): Category description
                - consolidates (list): List of predecessor category IDs
                - examples (list): List of example strings
                - created_at (datetime)
                - updated_at (datetime)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, name, description, consolidates, examples,
                           created_at, updated_at
                    FROM categories
                    ORDER BY name
                """)
                categories = cursor.fetchall()
                return categories

        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []

    def get_category_by_id(self, category_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific category by ID.

        Args:
            category_id: Category identifier

        Returns:
            Dict or None: Category data if found, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, name, description, consolidates, examples,
                           created_at, updated_at
                    FROM categories
                    WHERE id = %s
                """, (category_id,))
                return cursor.fetchone()

        except Exception as e:
            logger.error(f"Error fetching category {category_id}: {e}")
            return None

    def create_category(
        self,
        category_id: str,
        name: str,
        description: str,
        consolidates: List[str] = None,
        examples: List[str] = None
    ) -> bool:
        """
        Create a new category.

        Args:
            category_id: Unique category identifier
            name: Display name
            description: Category description
            consolidates: List of predecessor category IDs (optional)
            examples: List of example strings (optional)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            import json

            consolidates_json = json.dumps(consolidates or [])
            examples_json = json.dumps(examples or [])

            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO categories (id, name, description, consolidates, examples)
                    VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)
                """, (category_id, name, description, consolidates_json, examples_json))
                conn.commit()
                logger.info(f"Category created: {category_id}")
                return True

        except Exception as e:
            logger.error(f"Error creating category {category_id}: {e}")
            return False

    def update_category(
        self,
        category_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        consolidates: Optional[List[str]] = None,
        examples: Optional[List[str]] = None
    ) -> bool:
        """
        Update an existing category.

        Args:
            category_id: Category identifier
            name: New display name (optional)
            description: New description (optional)
            consolidates: New list of predecessor categories (optional)
            examples: New list of examples (optional)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            import json

            # Build dynamic UPDATE query based on provided fields
            updates = []
            params = []

            if name is not None:
                updates.append("name = %s")
                params.append(name)

            if description is not None:
                updates.append("description = %s")
                params.append(description)

            if consolidates is not None:
                updates.append("consolidates = %s::jsonb")
                params.append(json.dumps(consolidates))

            if examples is not None:
                updates.append("examples = %s::jsonb")
                params.append(json.dumps(examples))

            if not updates:
                logger.warning("No fields to update")
                return False

            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(category_id)

            query = f"""
                UPDATE categories
                SET {', '.join(updates)}
                WHERE id = %s
            """

            with self.get_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Category updated: {category_id}")
                    return True
                else:
                    logger.warning(f"Category not found: {category_id}")
                    return False

        except Exception as e:
            logger.error(f"Error updating category {category_id}: {e}")
            return False

    def delete_category(self, category_id: str) -> bool:
        """
        Delete a category. Sets categoria_tematica to NULL for affected URLs.

        Args:
            category_id: Category identifier

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                # Foreign key constraint ON DELETE SET NULL handles URL updates
                cursor = conn.execute("""
                    DELETE FROM categories
                    WHERE id = %s
                """, (category_id,))
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Category deleted: {category_id}")
                    return True
                else:
                    logger.warning(f"Category not found: {category_id}")
                    return False

        except Exception as e:
            logger.error(f"Error deleting category {category_id}: {e}")
            return False

    def log_category_change(
        self,
        category_id: str,
        changed_by: int,
        change_type: str,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None
    ) -> bool:
        """
        Log a category change for audit purposes.

        Args:
            category_id: Category identifier
            changed_by: User ID who made the change
            change_type: Type of change ('created', 'updated', 'deleted')
            old_values: Previous values (optional)
            new_values: New values (optional)

        Returns:
            bool: True if logged successfully
        """
        try:
            import json

            old_json = json.dumps(old_values) if old_values else None
            new_json = json.dumps(new_values) if new_values else None

            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO category_changes
                    (category_id, changed_by, change_type, old_values, new_values)
                    VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)
                """, (category_id, changed_by, change_type, old_json, new_json))
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error logging category change: {e}")
            return False

    def get_urls_by_category(
        self,
        category_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all URLs assigned to a specific category.

        Args:
            category_id: Category identifier
            limit: Optional limit on number of results

        Returns:
            List[Dict]: List of URL records
        """
        try:
            query = """
                SELECT id, url, title, categoria_tematica, categorized_at
                FROM urls
                WHERE categoria_tematica = %s
                ORDER BY categorized_at DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            with self.get_connection() as conn:
                cursor = conn.execute(query, (category_id,))
                return cursor.fetchall()

        except Exception as e:
            logger.error(f"Error fetching URLs for category {category_id}: {e}")
            return []

    def count_urls_by_category(self) -> Dict[str, int]:
        """
        Get count of URLs per category.

        Returns:
            Dict[str, int]: Mapping of category_id -> count
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT categoria_tematica, COUNT(*) as count
                    FROM urls
                    WHERE categoria_tematica IS NOT NULL
                    GROUP BY categoria_tematica
                """)
                results = cursor.fetchall()
                return {row['categoria_tematica']: row['count'] for row in results}

        except Exception as e:
            logger.error(f"Error counting URLs by category: {e}")
            return {}

    # ============================================
    # RECLASSIFICATION JOBS
    # ============================================

    def create_reclassification_job(
        self,
        triggered_by: int,
        category_ids: List[str]
    ) -> Optional[int]:
        """
        Create a new reclassification job.

        Args:
            triggered_by: User ID who triggered the job
            category_ids: List of category IDs that were modified

        Returns:
            int: Job ID if created, None on error
        """
        try:
            import json

            category_ids_json = json.dumps(category_ids)

            with self.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO reclassification_jobs
                    (triggered_by, category_ids, status, total_urls)
                    VALUES (%s, %s::jsonb, 'pending',
                        (SELECT COUNT(*) FROM urls WHERE categoria_tematica IS NOT NULL))
                    RETURNING id
                """, (triggered_by, category_ids_json))
                job_id = cursor.fetchone()['id']
                conn.commit()
                logger.info(f"Reclassification job created: {job_id}")
                return job_id

        except Exception as e:
            logger.error(f"Error creating reclassification job: {e}")
            return None

    def update_reclassification_job(
        self,
        job_id: int,
        status: Optional[str] = None,
        processed_urls: Optional[int] = None,
        failed_urls: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update reclassification job status.

        Args:
            job_id: Job identifier
            status: New status ('pending', 'running', 'completed', 'failed')
            processed_urls: Number of URLs processed
            failed_urls: Number of URLs that failed
            error_message: Error message if job failed

        Returns:
            bool: True if updated successfully
        """
        try:
            updates = []
            params = []

            if status is not None:
                updates.append("status = %s")
                params.append(status)

                # Set timestamps based on status
                if status == 'running':
                    updates.append("started_at = CURRENT_TIMESTAMP")
                elif status in ('completed', 'failed'):
                    updates.append("completed_at = CURRENT_TIMESTAMP")

            if processed_urls is not None:
                updates.append("processed_urls = %s")
                params.append(processed_urls)

            if failed_urls is not None:
                updates.append("failed_urls = %s")
                params.append(failed_urls)

            if error_message is not None:
                updates.append("error_message = %s")
                params.append(error_message)

            if not updates:
                return False

            params.append(job_id)
            query = f"""
                UPDATE reclassification_jobs
                SET {', '.join(updates)}
                WHERE id = %s
            """

            with self.get_connection() as conn:
                conn.execute(query, params)
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error updating reclassification job {job_id}: {e}")
            return False

    def get_reclassification_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        """
        Get reclassification job details.

        Args:
            job_id: Job identifier

        Returns:
            Dict or None: Job details if found
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM reclassification_jobs
                    WHERE id = %s
                """, (job_id,))
                return cursor.fetchone()

        except Exception as e:
            logger.error(f"Error fetching reclassification job {job_id}: {e}")
            return None

    def get_recent_reclassification_jobs(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent reclassification jobs.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List[Dict]: List of recent jobs
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM reclassification_jobs
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))
                return cursor.fetchall()

        except Exception as e:
            logger.error(f"Error fetching recent reclassification jobs: {e}")
            return []

    # ============================================
    # API KEYS MANAGEMENT (Encrypted OpenAI Keys)
    # ============================================

    def create_api_key(
        self,
        alias: str,
        encrypted_key: str,
        user_id: Optional[int] = None,
        notes: Optional[str] = None,
        use_as_fallback: bool = True
    ) -> Optional[int]:
        """
        Create a new API key.

        Args:
            alias: Human-readable identifier
            encrypted_key: Encrypted API key
            user_id: User ID for enterprise users (NULL for admin keys)
            notes: Optional notes
            use_as_fallback: Whether this API key can be used as fallback (default: True)

        Returns:
            API key ID if successful, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO api_keys (alias, encrypted_key, user_id, notes, use_as_fallback)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (alias, encrypted_key, user_id, notes, use_as_fallback))

                api_key_id = cursor.fetchone()['id']
                conn.commit()

                logger.info(f"API key created: {alias} (ID: {api_key_id}, fallback: {use_as_fallback})")
                return api_key_id

        except psycopg.errors.UniqueViolation:
            logger.warning(f"API key creation failed: alias already exists ({alias})")
            return None
        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            return None

    def get_api_key_by_id(self, api_key_id: int) -> Optional[Dict[str, Any]]:
        """
        Get API key by ID (includes encrypted key).

        Args:
            api_key_id: API key ID

        Returns:
            API key dict or None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT * FROM api_keys
                    WHERE id = %s
                """, (api_key_id,))

                return cursor.fetchone()

        except Exception as e:
            logger.error(f"Error fetching API key by ID: {e}")
            return None

    def get_api_key_by_alias(self, alias: str) -> Optional[Dict[str, Any]]:
        """
        Get API key by alias (includes encrypted key).

        Args:
            alias: API key alias

        Returns:
            API key dict or None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT * FROM api_keys
                    WHERE alias = %s
                """, (alias,))

                return cursor.fetchone()

        except Exception as e:
            logger.error(f"Error fetching API key by alias: {e}")
            return None

    def get_all_api_keys(
        self,
        user_id: Optional[int] = None,
        include_inactive: bool = False,
        admin_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all API keys (without encrypted key for security).

        Args:
            user_id: Filter by user ID. If provided, only that user's keys are returned.
            include_inactive: Include inactive keys
            admin_only: When user_id is None, True limits results to admin-level keys
                (user_id IS NULL). Set to False to return every key regardless of owner.

        Returns:
            List of API key dicts (encrypted_key excluded)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, alias, user_id, is_active, created_at, updated_at,
                           last_used_at, usage_count, notes, use_as_fallback
                    FROM api_keys
                    WHERE 1=1
                """

                params = []

                if user_id is not None:
                    query += " AND user_id = %s"
                    params.append(user_id)
                elif admin_only:
                    query += " AND user_id IS NULL"

                if not include_inactive:
                    query += " AND is_active = TRUE"

                query += " ORDER BY created_at DESC"

                cursor.execute(query, params)
                return cursor.fetchall()

        except Exception as e:
            logger.error(f"Error fetching API keys: {e}")
            return []

    def update_api_key(
        self,
        api_key_id: int,
        alias: Optional[str] = None,
        encrypted_key: Optional[str] = None,
        is_active: Optional[bool] = None,
        notes: Optional[str] = None,
        use_as_fallback: Optional[bool] = None
    ) -> bool:
        """
        Update API key.

        Args:
            api_key_id: API key ID
            alias: New alias (optional)
            encrypted_key: New encrypted key (optional)
            is_active: New active status (optional)
            notes: New notes (optional)
            use_as_fallback: Whether to use as fallback (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                updates = []
                params = []

                if alias is not None:
                    updates.append("alias = %s")
                    params.append(alias)

                if encrypted_key is not None:
                    updates.append("encrypted_key = %s")
                    params.append(encrypted_key)

                if is_active is not None:
                    updates.append("is_active = %s")
                    params.append(is_active)

                if notes is not None:
                    updates.append("notes = %s")
                    params.append(notes)

                if use_as_fallback is not None:
                    updates.append("use_as_fallback = %s")
                    params.append(use_as_fallback)

                if not updates:
                    return True

                params.append(api_key_id)

                query = f"""
                    UPDATE api_keys
                    SET {', '.join(updates)}
                    WHERE id = %s
                """

                cursor.execute(query, params)
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"API key updated: ID {api_key_id}")
                    return True
                else:
                    logger.warning(f"API key not found: ID {api_key_id}")
                    return False

        except psycopg.errors.UniqueViolation:
            logger.warning(f"API key update failed: alias already exists")
            return False
        except Exception as e:
            logger.error(f"Error updating API key: {e}")
            return False

    def delete_api_key(self, api_key_id: int) -> bool:
        """
        Delete API key (hard delete).

        Args:
            api_key_id: API key ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    DELETE FROM api_keys
                    WHERE id = %s
                """, (api_key_id,))

                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"API key deleted: ID {api_key_id}")
                    return True
                else:
                    logger.warning(f"API key not found: ID {api_key_id}")
                    return False

        except Exception as e:
            logger.error(f"Error deleting API key: {e}")
            return False

    def get_api_keys_with_fallback(
        self,
        primary_api_key_id: int,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get API keys in priority order: primary key first, then fallback keys.

        Args:
            primary_api_key_id: Primary API key ID to use first
            user_id: User ID filter (None = admin keys only)

        Returns:
            List of API key dicts with encrypted keys, ordered by priority
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Query: Primary key first, then fallback keys (active only)
                query = """
                    SELECT * FROM api_keys
                    WHERE is_active = TRUE
                      AND (id = %s OR (use_as_fallback = TRUE AND id != %s))
                """

                params = [primary_api_key_id, primary_api_key_id]

                if user_id is not None:
                    query += " AND user_id = %s"
                    params.append(user_id)
                else:
                    query += " AND user_id IS NULL"

                # Order: Primary first, then fallback keys by usage_count (least used first)
                query += """
                    ORDER BY
                        CASE WHEN id = %s THEN 0 ELSE 1 END,
                        usage_count ASC,
                        created_at ASC
                """
                params.append(primary_api_key_id)

                cursor.execute(query, params)
                keys = cursor.fetchall()

                logger.debug(f"Found {len(keys)} API keys (1 primary + {len(keys)-1} fallback)")
                return keys

        except Exception as e:
            logger.error(f"Error fetching API keys with fallback: {e}")
            return []

    def update_api_key_usage(self, api_key_id: int) -> bool:
        """
        Update API key usage stats (increment counter and timestamp).

        Args:
            api_key_id: API key ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE api_keys
                    SET usage_count = usage_count + 1,
                        last_used_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (api_key_id,))

                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error updating API key usage: {e}")
            return False

    # ===== SOURCES MANAGEMENT =====

    def get_all_sources(self, include_inactive=False):
        """Get all sources from database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            where_clause = "" if include_inactive else "WHERE is_active = true"
            cursor.execute(f"""
                SELECT * FROM sources
                {where_clause}
                ORDER BY priority DESC, display_name ASC
            """)
            return cursor.fetchall()

    def get_source_by_id(self, source_id):
        """Get source by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sources WHERE id = %s", (source_id,))
            return cursor.fetchone()

    def get_source_by_name(self, name):
        """Get source by name."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sources WHERE name = %s", (name,))
            return cursor.fetchone()

    def get_source_by_base_url(self, base_url: str):
        """
        Get source by base URL.

        Args:
            base_url: Base URL to search for (e.g., 'https://ft.com' or 'https://www.ft.com')

        Returns:
            Source record or None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Try exact match first
            cursor.execute("SELECT * FROM sources WHERE base_url = %s", (base_url,))
            result = cursor.fetchone()

            if result:
                return result

            # Try with/without www prefix
            if base_url.startswith('https://www.'):
                alt_url = base_url.replace('https://www.', 'https://')
            elif base_url.startswith('https://'):
                alt_url = base_url.replace('https://', 'https://www.')
            else:
                return None

            cursor.execute("SELECT * FROM sources WHERE base_url = %s", (alt_url,))
            return cursor.fetchone()

    def create_source(self, name, display_name, base_url,
                     language='es', description=None, is_active=True,
                     priority=1, notes=None):
        """Create new source."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sources
                (name, display_name, base_url, language, description, is_active, priority, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (name, display_name, base_url, language, description, is_active, priority, notes))
            source_id = cursor.fetchone()['id']
            conn.commit()
            return source_id

    def update_source(self, source_id, **kwargs):
        """Update source fields."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            allowed_fields = ['name', 'display_name', 'base_url', 'language',
                            'description', 'is_active', 'priority', 'notes']
            updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}

            if not updates:
                return False

            set_clause = ', '.join([f"{k} = %s" for k in updates.keys()])
            values = list(updates.values()) + [source_id]

            cursor.execute(f"""
                UPDATE sources
                SET {set_clause}
                WHERE id = %s
            """, values)

            success = cursor.rowcount > 0
            conn.commit()
            return success

    def delete_source(self, source_id):
        """Delete source (soft delete: set is_active=false)."""
        return self.update_source(source_id, is_active=False)

    # DEPRECATED: count_urls_by_date() - Removed due to incorrect accumulation across executions
    # URL metrics are now tracked directly by Stage 01 script via execution_id parameter

    # ===== STAGE EXECUTION MANAGEMENT =====

    def create_execution(self, schedule_id=None, execution_type='manual',
                        api_key_id=None, stage_name='01_extract_urls',
                        parameters=None):
        """Create execution record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get API key alias snapshot
            api_key_alias = None
            if api_key_id:
                key_data = self.get_api_key_by_id(api_key_id)
                api_key_alias = key_data['alias'] if key_data else None

            cursor.execute("""
                INSERT INTO execution_history
                (schedule_id, execution_type, stage_name, api_key_id,
                 api_key_alias, parameters, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'pending')
                RETURNING id
            """, (schedule_id, execution_type, stage_name, api_key_id,
                  api_key_alias, parameters))

            execution_id = cursor.fetchone()['id']
            conn.commit()
            return execution_id

    def update_execution_status(self, execution_id, status, **kwargs):
        """Update execution status and optional fields."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            fields = {'status': status}
            fields.update(kwargs)

            set_clause = ', '.join([f"{k} = %s" for k in fields.keys()])
            values = list(fields.values()) + [execution_id]

            cursor.execute(f"""
                UPDATE execution_history
                SET {set_clause}
                WHERE id = %s
            """, values)

            conn.commit()

    def get_execution_history(self, limit=50, offset=0, stage_name=None, status=None):
        """Get execution history with filters."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            where_clauses = []
            params = []

            if stage_name:
                where_clauses.append("eh.stage_name = %s")
                params.append(stage_name)

            if status:
                where_clauses.append("eh.status = %s")
                params.append(status)

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            # Add LIMIT and OFFSET to params
            params.extend([limit, offset])

            cursor.execute(f"""
                SELECT eh.*, se.name as schedule_name
                FROM execution_history eh
                LEFT JOIN scheduled_executions se ON eh.schedule_id = se.id
                {where_sql}
                ORDER BY eh.created_at DESC
                LIMIT %s OFFSET %s
            """, params)

            return cursor.fetchall()

    def get_execution_by_id(self, execution_id):
        """Get execution by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT eh.*, se.name as schedule_name
                FROM execution_history eh
                LEFT JOIN scheduled_executions se ON eh.schedule_id = se.id
                WHERE eh.id = %s
            """, (execution_id,))
            return cursor.fetchone()

    def create_schedule(self, name, cron_expression, api_key_id=None,
                       parameters=None, created_by_user_id=None,
                       execution_target='01_extract_urls', newsletter_config_id=None):
        """Create schedule."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scheduled_executions
                (name, cron_expression, api_key_id, parameters, created_by_user_id, execution_target, newsletter_config_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (name, cron_expression, api_key_id, parameters, created_by_user_id, execution_target, newsletter_config_id))

            schedule_id = cursor.fetchone()['id']
            conn.commit()
            return schedule_id

    def get_active_schedules(self):
        """Get active schedules."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM scheduled_executions
                WHERE is_enabled = true
                ORDER BY created_at DESC
            """)
            return cursor.fetchall()

    def get_schedule_by_id(self, schedule_id):
        """Get schedule by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scheduled_executions WHERE id = %s", (schedule_id,))
            return cursor.fetchone()

    def get_all_schedules(self, include_disabled=False, execution_target=None):
        """Get all schedules, optionally filtered by execution_target."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            where_clauses = []
            params = []

            if not include_disabled:
                where_clauses.append("is_enabled = true")

            if execution_target:
                where_clauses.append("execution_target = %s")
                params.append(execution_target)

            where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            cursor.execute(f"""
                SELECT * FROM scheduled_executions
                {where_clause}
                ORDER BY created_at DESC
            """, params)
            return cursor.fetchall()

    def update_schedule(self, schedule_id, updates):
        """Update schedule."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if not updates:
                return False

            set_clause = ', '.join([f"{k} = %s" for k in updates.keys()])
            values = list(updates.values()) + [schedule_id]

            cursor.execute(f"""
                UPDATE scheduled_executions
                SET {set_clause}
                WHERE id = %s
            """, values)

            success = cursor.rowcount > 0
            conn.commit()
            return success

    def update_schedule_last_run(self, schedule_id, last_run_at):
        """Update schedule last run timestamp."""
        return self.update_schedule(schedule_id, {'last_run_at': last_run_at})

    def delete_schedule(self, schedule_id):
        """Delete schedule."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM scheduled_executions WHERE id = %s", (schedule_id,))
            success = cursor.rowcount > 0
            conn.commit()
            return success

    def has_running_execution(self, schedule_id=None):
        """Check if there are running or pending executions (optionally filtered by schedule_id)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if schedule_id is not None:
                cursor.execute("""
                    SELECT COUNT(*) as count FROM execution_history
                    WHERE schedule_id = %s AND status IN ('running', 'pending')
                """, (schedule_id,))
            else:
                cursor.execute("""
                    SELECT COUNT(*) as count FROM execution_history
                    WHERE status IN ('running', 'pending')
                """)
            return cursor.fetchone()['count'] > 0

    def create_scheduled_execution(self, schedule_data: dict):
        """Create scheduled execution (wrapper with schema mapping)."""
        import json
        is_enabled = schedule_data.get('is_active', True)
        source_filter = schedule_data.get('source_filter')
        parameters_dict = {}
        if source_filter is not None:
            parameters_dict['source_filter'] = source_filter
        if 'trigger_on_stage1_ready' in schedule_data:
            parameters_dict['trigger_on_stage1_ready'] = schedule_data.get('trigger_on_stage1_ready', False)
        parameters = json.dumps(parameters_dict) if parameters_dict else None

        schedule_id = self.create_schedule(
            name=schedule_data['name'],
            cron_expression=schedule_data['cron_expression'],
            api_key_id=schedule_data['api_key_id'],
            parameters=parameters,
            created_by_user_id=schedule_data.get('created_by_user_id'),
            execution_target=schedule_data.get('execution_target', '01_extract_urls'),
            newsletter_config_id=schedule_data.get('newsletter_config_id')
        )
        if not is_enabled:
            self.update_schedule(schedule_id, {'is_enabled': is_enabled})
        return self.get_scheduled_execution_by_id(schedule_id)

    def get_scheduled_executions(self, execution_target=None):
        """Get all scheduled executions with schema mapping, optionally filtered by execution_target."""
        import json
        schedules = self.get_all_schedules(include_disabled=True, execution_target=execution_target)
        result = []
        for schedule in schedules:
            mapped = dict(schedule)
            mapped['is_active'] = mapped.pop('is_enabled', True)
            mapped['next_run_at'] = None  # TODO: Calculate based on cron_expression + last_run_at
            parameters = mapped.get('parameters')
            if parameters:
                try:
                    params_dict = json.loads(parameters) if isinstance(parameters, str) else parameters
                    mapped['source_filter'] = params_dict.get('source_filter')
                    mapped['trigger_on_stage1_ready'] = bool(params_dict.get('trigger_on_stage1_ready', False))
                except:
                    mapped['source_filter'] = None
                    mapped['trigger_on_stage1_ready'] = False
            else:
                mapped['source_filter'] = None
                mapped['trigger_on_stage1_ready'] = False
            result.append(mapped)
        return result

    def get_scheduled_execution_by_id(self, schedule_id: int):
        """Get scheduled execution by ID with schema mapping."""
        import json
        schedule = self.get_schedule_by_id(schedule_id)
        if not schedule:
            return None
        mapped = dict(schedule)
        mapped['is_active'] = mapped.pop('is_enabled', True)
        mapped['next_run_at'] = None  # TODO: Calculate based on cron_expression + last_run_at
        parameters = mapped.get('parameters')
        if parameters:
            try:
                params_dict = json.loads(parameters) if isinstance(parameters, str) else parameters
                mapped['source_filter'] = params_dict.get('source_filter')
                mapped['trigger_on_stage1_ready'] = bool(params_dict.get('trigger_on_stage1_ready', False))
            except:
                mapped['source_filter'] = None
                mapped['trigger_on_stage1_ready'] = False
        else:
            mapped['source_filter'] = None
            mapped['trigger_on_stage1_ready'] = False
        return mapped

    def update_scheduled_execution(self, schedule_id: int, update_data: dict):
        """Update scheduled execution with schema mapping."""
        import json
        existing_schedule = self.get_schedule_by_id(schedule_id)
        db_updates = {}
        if 'is_active' in update_data:
            db_updates['is_enabled'] = update_data['is_active']
        for field in ['name', 'cron_expression', 'api_key_id', 'execution_target', 'newsletter_config_id']:
            if field in update_data:
                db_updates[field] = update_data[field]

        # If parameters dict is provided directly, use it (from API endpoint)
        if 'parameters' in update_data:
            db_updates['parameters'] = json.dumps(update_data['parameters']) if update_data['parameters'] else None
        else:
            # Otherwise, handle individual parameter fields (legacy support)
            existing_params = {}
            if existing_schedule and existing_schedule.get('parameters'):
                try:
                    existing_params = json.loads(existing_schedule['parameters']) if isinstance(existing_schedule['parameters'], str) else existing_schedule['parameters']
                    if not isinstance(existing_params, dict):
                        existing_params = {}
                except:
                    existing_params = {}
            if 'source_filter' in update_data:
                source_filter = update_data['source_filter']
                existing_params.pop('source_filter', None)
                if source_filter is not None:
                    existing_params['source_filter'] = source_filter
            if 'trigger_on_stage1_ready' in update_data:
                trigger_flag = update_data['trigger_on_stage1_ready']
                existing_params.pop('trigger_on_stage1_ready', None)
                if trigger_flag is not None:
                    existing_params['trigger_on_stage1_ready'] = trigger_flag
            if 'source_filter' in update_data or 'trigger_on_stage1_ready' in update_data:
                db_updates['parameters'] = json.dumps(existing_params) if existing_params else None

        success = self.update_schedule(schedule_id, db_updates)
        if not success:
            return None
        return self.get_scheduled_execution_by_id(schedule_id)

    def delete_scheduled_execution(self, schedule_id: int):
        """Delete scheduled execution."""
        return self.delete_schedule(schedule_id)

    def get_execution_details(self, execution_id: int):
        """
        Get detailed information about an execution including URLs and statistics.

        Args:
            execution_id: Execution ID

        Returns:
            Dictionary with:
                - execution: Basic execution info
                - urls: List of URLs extracted (limited to 1000)
                - stats_by_source: Statistics grouped by source
                - stats_by_category: Statistics grouped by category
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get execution info
            cursor.execute("""
                SELECT
                    eh.*,
                    ak.alias as api_key_alias,
                    se.name as schedule_name
                FROM execution_history eh
                LEFT JOIN api_keys ak ON eh.api_key_id = ak.id
                LEFT JOIN scheduled_executions se ON eh.schedule_id = se.id
                WHERE eh.id = %s
            """, (execution_id,))
            execution = cursor.fetchone()

            if not execution:
                return None

            # Extract date from execution timestamps for filtering URLs
            # Use started_at if available, otherwise created_at
            if execution['started_at']:
                exec_date = execution['started_at'].date()
            else:
                exec_date = execution['created_at'].date()

            # Get URLs extracted by this execution
            # Try execution_id first, fallback to date if no execution_id
            cursor.execute("""
                SELECT
                    id,
                    url,
                    title,
                    source,
                    content_type,
                    content_subtype,
                    categoria_tematica,
                    classification_method,
                    rule_name,
                    extracted_at,
                    last_extracted_at
                FROM urls
                WHERE execution_id = %s
                ORDER BY extracted_at DESC
                LIMIT 1000
            """, (execution_id,))
            urls = cursor.fetchall()

            # Get ACTUAL total count of URLs for this execution (not limited to 1000)
            cursor.execute("""
                SELECT COUNT(*) as total_count
                FROM urls
                WHERE execution_id = %s
            """, (execution_id,))
            total_count_result = cursor.fetchone()
            total_urls_count = total_count_result['total_count'] if total_count_result else 0

            # Get stats by source for this execution
            cursor.execute("""
                SELECT
                    source,
                    COUNT(*) as total_urls,
                    COUNT(CASE WHEN content_type = 'contenido' THEN 1 END) as content_urls,
                    COUNT(CASE WHEN content_type = 'no_contenido' THEN 1 END) as non_content_urls,
                    COUNT(CASE WHEN categoria_tematica IS NOT NULL THEN 1 END) as categorized_urls
                FROM urls
                WHERE execution_id = %s
                GROUP BY source
                ORDER BY total_urls DESC
            """, (execution_id,))
            stats_by_source = cursor.fetchall()

            # Get stats by category for this execution
            cursor.execute("""
                SELECT
                    categoria_tematica,
                    COUNT(*) as url_count
                FROM urls
                WHERE execution_id = %s
                  AND categoria_tematica IS NOT NULL
                  AND content_type = 'contenido'
                GROUP BY categoria_tematica
                ORDER BY url_count DESC
            """, (execution_id,))
            stats_by_category = cursor.fetchall()

            return {
                'execution': dict(execution),
                'urls': [dict(url) for url in urls],
                'stats_by_source': [dict(stat) for stat in stats_by_source],
                'stats_by_category': [dict(stat) for stat in stats_by_category],
                'total_urls': total_urls_count
            }


    # ==================== NEWSLETTER MANAGEMENT METHODS ====================

    def execute_query(self, query: str, params=None, fetch_one=False):
        """
        Helper method to execute SQL queries with consistent pattern.

        Args:
            query: SQL query string
            params: Query parameters (tuple, dict, or None)
            fetch_one: If True, return single row; if False, return all rows

        Returns:
            Single row dict, list of row dicts, or None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params is not None:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            # Fetch results if SELECT or RETURNING
            if 'RETURNING' in query.upper() or 'SELECT' in query.upper():
                if fetch_one:
                    result = cursor.fetchone()
                else:
                    result = cursor.fetchall()

                # Commit if it's a mutation with RETURNING (INSERT/UPDATE/DELETE)
                if 'RETURNING' in query.upper():
                    conn.commit()

                return result
            else:
                # For other mutations (no RETURNING)
                conn.commit()
                return None

    # Newsletter Configs

    def create_newsletter_config(self, config_data: dict) -> dict:
        """
        Create a new newsletter configuration.

        Args:
            config_data: Dictionary with configuration fields

        Returns:
            Created newsletter config as dict
        """
        query = """
        INSERT INTO newsletter_configs (
            name, display_name, description,
            visibility,
            source_ids, category_ids,
            articles_count, ranker_method,
            output_format, template_name,
            skip_paywall_check, related_window_days,
            is_active, created_by_user_id,
            api_key_id, enable_fallback
        ) VALUES (
            %(name)s, %(display_name)s, %(description)s,
            %(visibility)s,
            %(source_ids)s, %(category_ids)s,
            %(articles_count)s, %(ranker_method)s,
            %(output_format)s, %(template_name)s,
            %(skip_paywall_check)s, %(related_window_days)s,
            %(is_active)s, %(created_by_user_id)s,
            %(api_key_id)s, %(enable_fallback)s
        )
        RETURNING *;
        """
        result = self.execute_query(query, config_data, fetch_one=True)
        return dict(result) if result else None

    def get_newsletter_config_by_id(self, config_id: int) -> dict:
        """Get newsletter configuration by ID."""
        query = "SELECT * FROM newsletter_configs WHERE id = %s;"
        result = self.execute_query(query, (config_id,), fetch_one=True)
        return dict(result) if result else None

    def get_newsletter_config_by_name(self, name: str) -> dict:
        """Get newsletter configuration by name."""
        query = "SELECT * FROM newsletter_configs WHERE name = %s;"
        result = self.execute_query(query, (name,), fetch_one=True)
        return dict(result) if result else None

    def get_all_newsletter_configs(self, only_active: bool = False) -> List[dict]:
        """Get all newsletter configurations."""
        query = "SELECT * FROM newsletter_configs"
        if only_active:
            query += " WHERE is_active = true"
        query += " ORDER BY name;"
        results = self.execute_query(query)
        return [dict(row) for row in results]

    def update_newsletter_config(self, config_id: int, update_data: dict) -> dict:
        """Update newsletter configuration."""
        set_clause = ", ".join(f"{key} = %({key})s" for key in update_data.keys())
        query = f"""
        UPDATE newsletter_configs
        SET {set_clause}
        WHERE id = %(config_id)s
        RETURNING *;
        """
        params = {**update_data, 'config_id': config_id}
        result = self.execute_query(query, params, fetch_one=True)
        return dict(result) if result else None

    def delete_newsletter_config(self, config_id: int) -> bool:
        """Delete newsletter configuration."""
        query = "DELETE FROM newsletter_configs WHERE id = %s;"
        self.execute_query(query, (config_id,))
        return True

    # Newsletter Subscriptions

    def add_user_newsletter_subscription(self, user_id: int, newsletter_name: str) -> Optional[dict]:
        """
        Subscribe a user to a newsletter by config name.

        Returns subscription info joined with config details.
        """
        query = """
        WITH config AS (
            SELECT id FROM newsletter_configs WHERE name = %s
        ), inserted AS (
            INSERT INTO user_newsletter_subscriptions (user_id, newsletter_config_id)
            SELECT %s, id FROM config
            ON CONFLICT (user_id, newsletter_config_id) DO NOTHING
            RETURNING id, user_id, newsletter_config_id, created_at
        )
        SELECT
            s.id,
            s.user_id,
            s.newsletter_config_id,
            s.created_at,
            nc.name AS newsletter_name,
            nc.display_name,
            nc.description,
            nc.is_active,
            nc.visibility,
            nc.created_by_user_id
        FROM inserted s
        JOIN newsletter_configs nc ON nc.id = s.newsletter_config_id;
        """
        try:
            result = self.execute_query(query, (newsletter_name, user_id), fetch_one=True)
        except psycopg.errors.UndefinedColumn:
            # Fallback if visibility column not migrated yet
            legacy_query = """
            WITH config AS (
                SELECT id FROM newsletter_configs WHERE name = %s
            ), inserted AS (
                INSERT INTO user_newsletter_subscriptions (user_id, newsletter_config_id)
                SELECT %s, id FROM config
                ON CONFLICT (user_id, newsletter_config_id) DO NOTHING
                RETURNING id, user_id, newsletter_config_id, created_at
            )
            SELECT
                s.id,
                s.user_id,
                s.newsletter_config_id,
                s.created_at,
                nc.name AS newsletter_name,
                nc.display_name,
                nc.description,
                nc.is_active,
                nc.created_by_user_id
            FROM inserted s
            JOIN newsletter_configs nc ON nc.id = s.newsletter_config_id;
            """
            result = self.execute_query(legacy_query, (newsletter_name, user_id), fetch_one=True)
        return dict(result) if result else None

    def remove_user_newsletter_subscription(self, user_id: int, newsletter_name: str) -> bool:
        """Unsubscribe user from a newsletter by name."""
        query = """
        DELETE FROM user_newsletter_subscriptions
        WHERE user_id = %s
          AND newsletter_config_id = (SELECT id FROM newsletter_configs WHERE name = %s)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id, newsletter_name))
            conn.commit()
            return True

    def get_user_newsletter_subscriptions(self, user_id: int) -> List[dict]:
        """List subscriptions for a user with config details."""
        query = """
        SELECT
            s.id,
            s.user_id,
            s.newsletter_config_id,
            s.created_at,
            nc.name AS newsletter_name,
            nc.display_name,
            nc.description,
            nc.is_active,
            nc.visibility,
            nc.created_by_user_id
        FROM user_newsletter_subscriptions s
        JOIN newsletter_configs nc ON nc.id = s.newsletter_config_id
        WHERE s.user_id = %s
        ORDER BY COALESCE(nc.display_name, nc.name);
        """
        try:
            results = self.execute_query(query, (user_id,))
        except psycopg.errors.UndefinedColumn:
            # Fallback if visibility column not migrated yet
            legacy_query = """
            SELECT
                s.id,
                s.user_id,
                s.newsletter_config_id,
                s.created_at,
                nc.name AS newsletter_name,
                nc.display_name,
                nc.description,
                nc.is_active,
                nc.created_by_user_id
            FROM user_newsletter_subscriptions s
            JOIN newsletter_configs nc ON nc.id = s.newsletter_config_id
            WHERE s.user_id = %s
            ORDER BY COALESCE(nc.display_name, nc.name);
            """
            results = self.execute_query(legacy_query, (user_id,))
        return [dict(row) for row in results]

    # Newsletter Executions

    def create_newsletter_execution(
        self,
        newsletter_config_id: int,
        run_date: date,
        execution_type: str = 'manual',
        schedule_id: int = None,
        api_key_id: int = None,
        sequential_mode: bool = False,
        initial_status: str = 'pending'
    ) -> int:
        """
        Create a new newsletter execution record with optional sequential lock.

        Args:
            sequential_mode: If True, uses advisory lock to prevent concurrent executions

        Returns:
            execution_id or None if lock couldn't be acquired (sequential mode only)
        """
        # Get config snapshot
        config = self.get_newsletter_config_by_id(newsletter_config_id)
        if not config:
            raise ValueError(f"Newsletter config {newsletter_config_id} not found")

        # Convert datetime objects to strings for JSON serialization
        config_snapshot = dict(config)
        if 'created_at' in config_snapshot and config_snapshot['created_at']:
            config_snapshot['created_at'] = config_snapshot['created_at'].isoformat()
        if 'updated_at' in config_snapshot and config_snapshot['updated_at']:
            config_snapshot['updated_at'] = config_snapshot['updated_at'].isoformat()

        # Use transaction-level advisory lock for sequential mode
        # This is an atomic check-and-create operation
        if sequential_mode:
            # Use a CTE with advisory lock and atomic check
            query = """
            WITH lock_check AS (
                SELECT pg_try_advisory_xact_lock(99999) as got_lock
            ), running_check AS (
                SELECT COUNT(*) as running_count
                FROM newsletter_executions
                WHERE status IN ('pending', 'running')
            ), should_create AS (
                SELECT
                    lc.got_lock AND rc.running_count = 0 as can_create
                FROM lock_check lc, running_check rc
            )
            INSERT INTO newsletter_executions (
                newsletter_config_id, run_date, execution_type,
                schedule_id, api_key_id, config_snapshot, status
            )
            SELECT %s, %s, %s, %s, %s, %s, 'pending'
            FROM should_create
            WHERE can_create = true
            RETURNING id;
            """
            result = self.execute_query(
                query,
                (newsletter_config_id, run_date, execution_type, schedule_id, api_key_id, json.dumps(config_snapshot)),
                fetch_one=True
            )
            return result['id'] if result else None

        # Non-sequential mode: create execution directly
        query = """
        INSERT INTO newsletter_executions (
            newsletter_config_id, run_date, execution_type,
            schedule_id, api_key_id, config_snapshot, status
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING id;
        """
        result = self.execute_query(
            query,
            (newsletter_config_id, run_date, execution_type, schedule_id, api_key_id, json.dumps(config_snapshot), initial_status),
            fetch_one=True
        )
        return result['id'] if result else None

    def _enrich_newsletter_execution(self, execution: dict) -> dict:
        """Add derived metrics and aliases to a newsletter execution record."""
        exec_copy = dict(execution)

        # Parse JSON fields
        if exec_copy.get('config_snapshot'):
            exec_copy['config_snapshot'] = json.loads(exec_copy['config_snapshot']) if isinstance(exec_copy['config_snapshot'], str) else exec_copy['config_snapshot']

        # Aggregate stage metrics when totals are missing
        stage_rows = self.execute_query(
            """
            SELECT input_tokens, output_tokens, total_tokens, cost_usd
            FROM newsletter_stage_executions
            WHERE newsletter_execution_id = %s
            """,
            (exec_copy['id'],),
        ) or []
        stage_totals = {'input': 0, 'output': 0, 'tokens': 0, 'cost': 0.0}
        for row in stage_rows:
            input_tokens = int(row['input_tokens'] or 0)
            output_tokens = int(row['output_tokens'] or 0)
            total_tokens = int(row['total_tokens'] or (input_tokens + output_tokens))
            cost = float(row['cost_usd'] or 0.0)
            stage_totals['input'] += input_tokens
            stage_totals['output'] += output_tokens
            stage_totals['tokens'] += total_tokens
            stage_totals['cost'] += cost

        if (exec_copy.get('total_tokens') or 0) == 0:
            exec_copy['total_tokens'] = stage_totals['tokens']
        if (exec_copy.get('total_input_tokens') or 0) == 0:
            exec_copy['total_input_tokens'] = stage_totals['input']
        if (exec_copy.get('total_output_tokens') or 0) == 0:
            exec_copy['total_output_tokens'] = stage_totals['output']
        if (exec_copy.get('total_cost_usd') or 0) == 0:
            exec_copy['total_cost_usd'] = stage_totals['cost']

        # Derive duration if not present
        if exec_copy.get('duration_seconds') is None and exec_copy.get('started_at') and exec_copy.get('completed_at'):
            exec_copy['duration_seconds'] = int((exec_copy['completed_at'] - exec_copy['started_at']).total_seconds())

        return exec_copy

    def get_newsletter_execution_by_id(self, execution_id: int) -> dict:
        """Get newsletter execution by ID with config name and api key alias joined."""
        query = """
        SELECT
            ne.*,
            nc.name as newsletter_config_name,
            ak.alias AS api_key_alias
        FROM newsletter_executions ne
        LEFT JOIN newsletter_configs nc ON ne.newsletter_config_id = nc.id
        LEFT JOIN api_keys ak ON ne.api_key_id = ak.id
        WHERE ne.id = %s;
        """
        result = self.execute_query(query, (execution_id,), fetch_one=True)
        if result:
            return self._enrich_newsletter_execution(dict(result))
        return None

    def get_newsletter_executions(
        self,
        limit: int = 50,
        offset: int = 0,
        newsletter_config_id: int = None,
        status_filter: str = None
    ) -> List[dict]:
        """Get newsletter executions with filters."""
        query = """
        SELECT
            ne.*,
            nc.name as newsletter_config_name,
            ak.alias AS api_key_alias
        FROM newsletter_executions ne
        LEFT JOIN newsletter_configs nc ON ne.newsletter_config_id = nc.id
        LEFT JOIN api_keys ak ON ne.api_key_id = ak.id
        WHERE 1=1
        """
        params = []

        if newsletter_config_id:
            query += " AND ne.newsletter_config_id = %s"
            params.append(newsletter_config_id)

        if status_filter:
            query += " AND ne.status = %s"
            params.append(status_filter)

        query += " ORDER BY ne.created_at DESC LIMIT %s OFFSET %s;"
        params.extend([limit, offset])

        results = self.execute_query(query, tuple(params))
        return [self._enrich_newsletter_execution(dict(row)) for row in results]

    def update_newsletter_execution_status(
        self,
        execution_id: int,
        status: str,
        **kwargs
    ) -> None:
        """
        Update newsletter execution status and related fields.

        kwargs can include: started_at, completed_at, error_message, etc.
        """
        updates = {'status': status}
        updates.update(kwargs)

        # Drop generated columns that cannot be written explicitly
        for field in ('total_tokens', 'duration_seconds'):
            updates.pop(field, None)

        set_clause = ", ".join(f"{key} = %({key})s" for key in updates.keys())
        query = f"""
        UPDATE newsletter_executions
        SET {set_clause}
        WHERE id = %(execution_id)s;
        """
        params = {**updates, 'execution_id': execution_id}
        self.execute_query(query, params)

    def has_running_newsletter_execution(self) -> bool:
        """Check if there are any running newsletter executions."""
        query = """
        SELECT COUNT(*) as count
        FROM newsletter_executions
        WHERE status IN ('pending', 'running');
        """
        result = self.execute_query(query, fetch_one=True)
        return result['count'] > 0 if result else False

    def count_running_newsletter_executions(self, exclude_id: int | None = None) -> int:
        """Count running newsletter executions (pending/running), optionally excluding one id."""
        query = """
        SELECT COUNT(*) as count
        FROM newsletter_executions
        WHERE status IN ('pending', 'running')
        """
        params = []
        if exclude_id is not None:
            query += " AND id != %s"
            params.append(exclude_id)
        result = self.execute_query(query, tuple(params) if params else None, fetch_one=True)
        return result['count'] if result else 0

    def count_running_newsletter_executions_only(self) -> int:
        """Count newsletter executions that are currently running."""
        query = """
        SELECT COUNT(*) as count
        FROM newsletter_executions
        WHERE status = 'running';
        """
        result = self.execute_query(query, fetch_one=True)
        return result['count'] if result else 0

    def try_start_sequential_newsletter_execution(self, execution_id: int, celery_task_id: str | None = None) -> bool:
        """
        Atomically set an execution to running only if no other pending/running exists.

        Returns True if the execution was transitioned to running, False otherwise.
        """
        query = """
        WITH updated AS (
            UPDATE newsletter_executions ne
            SET status = 'running',
                started_at = COALESCE(ne.started_at, NOW()),
                celery_task_id = COALESCE(%s, ne.celery_task_id)
            WHERE ne.id = %s
              AND NOT EXISTS (
                  SELECT 1 FROM newsletter_executions other
                  WHERE other.id != %s
                    AND other.status IN ('pending', 'running')
              )
            RETURNING id
        )
        SELECT COUNT(*) AS updated FROM updated;
        """
        result = self.execute_query(query, (celery_task_id, execution_id, execution_id), fetch_one=True)
        return bool(result and result.get('updated') == 1)

    def try_start_newsletter_execution_with_limit(self, execution_id: int, max_running: int, celery_task_id: str | None = None) -> bool:
        """
        Atomically transition an execution to running if running count is below max_running.

        Returns True if updated, False otherwise.
        """
        if max_running < 1:
            max_running = 1

        query = """
        WITH updated AS (
            UPDATE newsletter_executions ne
            SET status = 'running',
                started_at = COALESCE(ne.started_at, NOW()),
                celery_task_id = COALESCE(%s, ne.celery_task_id)
            WHERE ne.id = %s
              AND ne.status IN ('pending', 'queued')
              AND (
                  SELECT COUNT(*) FROM newsletter_executions other
                  WHERE other.status = 'running'
              ) < %s
            RETURNING id
        )
        SELECT COUNT(*) AS updated FROM updated;
        """
        result = self.execute_query(query, (celery_task_id, execution_id, max_running), fetch_one=True)
        return bool(result and result.get('updated') == 1)

    # Newsletter Stage Executions

    def create_newsletter_stage_execution(
        self,
        newsletter_execution_id: int,
        stage_number: int,
        stage_name: str
    ) -> int:
        """Create a newsletter stage execution record."""
        query = """
        INSERT INTO newsletter_stage_executions (
            newsletter_execution_id, stage_number, stage_name, status
        ) VALUES (%s, %s, %s, 'pending')
        RETURNING id;
        """
        result = self.execute_query(
            query,
            (newsletter_execution_id, stage_number, stage_name),
            fetch_one=True
        )
        return result['id'] if result else None

    def get_newsletter_stage_executions(self, newsletter_execution_id: int) -> List[dict]:
        """Get all stage executions for a newsletter execution."""
        query = """
        SELECT * FROM newsletter_stage_executions
        WHERE newsletter_execution_id = %s
        ORDER BY stage_number;
        """
        results = self.execute_query(query, (newsletter_execution_id,))
        stages = []
        for row in results:
            stage_dict = dict(row)
            if stage_dict.get('stage_metadata'):
                stage_dict['stage_metadata'] = json.loads(stage_dict['stage_metadata']) if isinstance(stage_dict['stage_metadata'], str) else stage_dict['stage_metadata']
            stages.append(stage_dict)
        return stages

    def get_newsletter_stage_execution_id(self, newsletter_execution_id: int, stage_number: int) -> int:
        """Get stage execution ID for a specific newsletter execution and stage number."""
        query = """
        SELECT id FROM newsletter_stage_executions
        WHERE newsletter_execution_id = %s AND stage_number = %s;
        """
        result = self.execute_query(query, (newsletter_execution_id, stage_number), fetch_one=True)
        return result['id'] if result else None

    def update_newsletter_stage_execution_status(
        self,
        stage_execution_id: int,
        status: str,
        **kwargs
    ) -> None:
        """Update newsletter stage execution status and metrics."""
        updates = {'status': status}
        updates.update(kwargs)

        # Generated columns are computed by Postgres; ignore if provided
        for field in ('total_tokens', 'duration_seconds'):
            updates.pop(field, None)

        # Handle JSON serialization for stage_metadata
        if 'stage_metadata' in updates and isinstance(updates['stage_metadata'], dict):
            updates['stage_metadata'] = json.dumps(updates['stage_metadata'])

        set_clause = ", ".join(f"{key} = %({key})s" for key in updates.keys())
        query = f"""
        UPDATE newsletter_stage_executions
        SET {set_clause}
        WHERE id = %(stage_execution_id)s;
        """
        params = {**updates, 'stage_execution_id': stage_execution_id}
        self.execute_query(query, params)

    # URL Classification Lock Management

    def lock_urls_for_classification(self, url_ids: List[int], lock_by: str) -> None:
        """Lock URLs for classification to prevent duplicates."""
        query = """
        UPDATE urls
        SET classification_lock_at = NOW(),
            classification_lock_by = %s
        WHERE id = ANY(%s);
        """
        self.execute_query(query, (lock_by, url_ids))

    def unlock_urls_for_classification(self, url_ids: List[int]) -> None:
        """Unlock URLs after classification."""
        query = """
        UPDATE urls
        SET classification_lock_at = NULL,
            classification_lock_by = NULL
        WHERE id = ANY(%s);
        """
        self.execute_query(query, (url_ids,))

    def get_urls_for_classification(
        self,
        run_date: date,
        source_ids: List[int] = None,
        force: bool = False
    ) -> List[dict]:
        """
        Get URLs that need classification.

        Args:
            run_date: Date to filter URLs
            source_ids: Optional list of source IDs to filter
            force: If True, include already classified URLs
        """
        query = """
        SELECT id, url, title, source, categoria_tematica,
               content_type,
               classification_lock_at, classification_lock_by
        FROM urls
        WHERE DATE(extracted_at) = %s
          AND content_type = 'contenido'
        """
        params = [run_date]

        if source_ids:
            # Convert source IDs to base URLs
            sources = self.get_sources_by_ids(source_ids)
            base_url_list = [s['base_url'] for s in sources]
            query += " AND source = ANY(%s)"
            params.append(base_url_list)

        if not force:
            query += " AND categoria_tematica IS NULL"

        query += " ORDER BY extracted_at;"
        results = self.execute_query(query, tuple(params))
        return [dict(row) for row in results]

    def wait_for_url_classification(self, url_ids: List[int], timeout: int = 300) -> bool:
        """
        Wait for URLs to be classified (polling).

        Args:
            url_ids: List of URL IDs to wait for
            timeout: Timeout in seconds

        Returns:
            True if all classified, False if timeout
        """
        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            query = """
            SELECT COUNT(*) as count
            FROM urls
            WHERE id = ANY(%s)
            AND categoria_tematica IS NOT NULL;
            """
            result = self.execute_query(query, (url_ids,), fetch_one=True)

            if result['count'] == len(url_ids):
                return True

            time.sleep(5)  # Poll every 5 seconds

        return False

    # System Config

    def get_system_config(self, key: str) -> str:
        """Get system configuration value by key."""
        query = "SELECT value FROM system_config WHERE key = %s;"
        result = self.execute_query(query, (key,), fetch_one=True)
        return result['value'] if result else None

    def set_system_config(self, key: str, value: str) -> None:
        """Set system configuration value."""
        query = """
        INSERT INTO system_config (key, value)
        VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value, updated_at = NOW();
        """
        self.execute_query(query, (key, value))

    def get_all_system_config(self) -> dict:
        """Get all system configuration as dict."""
        query = "SELECT key, value, description FROM system_config;"
        results = self.execute_query(query)
        return {row['key']: {'value': row['value'], 'description': row['description']} for row in results}

    # Helper: Check if Stage 1 ran for a date

    def has_stage01_execution_for_date(self, run_date: date) -> bool:
        """Check if Stage 1 has been executed for a given date."""
        query = """
        SELECT COUNT(*) as count
        FROM execution_history
        WHERE stage_name IN ('stage_01', '01_extract_urls')
        AND DATE(COALESCE(started_at, created_at)) = %s
        AND status = 'completed';
        """
        result = self.execute_query(query, (run_date,), fetch_one=True)
        return result['count'] > 0 if result else False

    def has_stage01_executions_for_sources(self, run_date: date, source_ids: List[int]) -> bool:
        """Check if Stage 1 has covered the provided sources on the given date."""
        import json

        if not source_ids:
            return self.has_stage01_execution_for_date(run_date)

        sources = self.get_sources_by_ids(source_ids)
        source_names = {s['name'] for s in sources if s and s.get('name')}
        if not source_names:
            return False

        rows = self.execute_query(
            """
            SELECT parameters
            FROM execution_history
            WHERE stage_name IN ('stage_01', '01_extract_urls')
              AND status = 'completed'
              AND DATE(COALESCE(started_at, created_at)) = %s
            """,
            (run_date,)
        )

        if not rows:
            return False

        covered_names = set()
        for row in rows:
            row_dict = dict(row)
            params = row_dict.get('parameters')
            # Empty parameters means the run processed all active sources
            if not params:
                return True
            try:
                params_dict = json.loads(params) if isinstance(params, str) else params
            except Exception:
                params_dict = {}
            # Handle both legacy and current parameter keys
            names = params_dict.get('source_names') or params_dict.get('source_filter')
            if not names:
                return True
            covered_names.update(names)

        return source_names.issubset(covered_names)

    def get_sources_by_ids(self, source_ids: List[int]) -> List[dict]:
        """Get sources by IDs."""
        query = "SELECT * FROM sources WHERE id = ANY(%s);"
        results = self.execute_query(query, (source_ids,))
        return [dict(row) for row in results]

    def get_categories_by_ids(self, category_ids: List[int]) -> List[dict]:
        """Get categories by IDs."""
        query = "SELECT * FROM categories WHERE id = ANY(%s);"
        results = self.execute_query(query, (category_ids,))
        return [dict(row) for row in results]

    # ==========================================
    # Token Usage (PostgreSQL storage)
    # ==========================================

    def _ensure_token_usage_table(self):
        """Create token_usage table if it does not exist (idempotent)."""
        if self._token_usage_table_initialized:
            return

        create_sql = """
        CREATE TABLE IF NOT EXISTS token_usage (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            date DATE NOT NULL,
            stage VARCHAR(16) NOT NULL,
            model TEXT NOT NULL,
            operation TEXT NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            total_tokens INTEGER NOT NULL,
            cost_usd NUMERIC(12,6) NOT NULL,
            api_key_id INTEGER NULL,
            execution_id INTEGER NULL,
            newsletter_execution_id INTEGER NULL
        );
        CREATE INDEX IF NOT EXISTS idx_token_usage_date ON token_usage(date);
        CREATE INDEX IF NOT EXISTS idx_token_usage_stage ON token_usage(stage);
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(create_sql)
            conn.commit()

        self._token_usage_table_initialized = True

    def log_token_usage(
        self,
        *,
        timestamp: datetime,
        date_value,
        stage: str,
        model: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        api_key_id: int | None = None,
        execution_id: int | None = None,
        newsletter_execution_id: int | None = None,
    ):
        """Persist a token usage row into Postgres."""
        self._ensure_token_usage_table()

        if isinstance(date_value, datetime):
            date_value = date_value.date()

        total_tokens = input_tokens + output_tokens

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO token_usage (
                    timestamp, date, stage, model, operation,
                    input_tokens, output_tokens, total_tokens, cost_usd,
                    api_key_id, execution_id, newsletter_execution_id
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
                """,
                (
                    timestamp,
                    date_value,
                    stage,
                    model,
                    operation,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    round(float(cost_usd), 6),
                    api_key_id,
                    execution_id,
                    newsletter_execution_id,
                ),
            )
            conn.commit()

    def get_token_usage_between(
        self,
        *,
        stage: str | None = None,
        start_ts: datetime | None = None,
        end_ts: datetime | None = None,
        execution_id: int | None = None,
        newsletter_execution_id: int | None = None,
    ) -> dict:
        """Aggregate token usage between two timestamps."""
        self._ensure_token_usage_table()

        conditions = []
        params = []

        if stage:
            conditions.append("stage = %s")
            params.append(stage)
        if start_ts:
            conditions.append("timestamp >= %s")
            params.append(start_ts)
        if end_ts:
            conditions.append("timestamp <= %s")
            params.append(end_ts)
        if execution_id is not None:
            conditions.append("execution_id = %s")
            params.append(execution_id)
        if newsletter_execution_id is not None:
            conditions.append("newsletter_execution_id = %s")
            params.append(newsletter_execution_id)

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
        SELECT
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            COALESCE(SUM(cost_usd), 0) as cost_usd
        FROM token_usage
        {where_clause};
        """

        result = self.execute_query(query, tuple(params) if params else None, fetch_one=True)
        return {
            "input_tokens": int(result["input_tokens"] or 0) if result else 0,
            "output_tokens": int(result["output_tokens"] or 0) if result else 0,
            "cost_usd": float(result["cost_usd"] or 0.0) if result else 0.0,
        }

    def get_token_usage_grouped_by_stage(
        self,
        start_date=None,
        end_date=None
    ) -> List[dict]:
        """Get aggregated token/cost usage grouped by stage."""
        self._ensure_token_usage_table()

        conditions = []
        params = []

        if start_date:
            conditions.append("date >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("date <= %s")
            params.append(end_date)

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
        SELECT
            stage,
            COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
            COALESCE(SUM(input_tokens + output_tokens), 0) AS total_tokens,
            COUNT(*) AS executions,
            COALESCE(AVG(cost_usd), 0) AS avg_cost_per_execution
        FROM token_usage
        {where_clause}
        GROUP BY stage
        ORDER BY total_cost_usd DESC;
        """

        rows = self.execute_query(query, tuple(params) if params else None)
        return [dict(row) for row in rows]

    # ==========================================
    # Source Cookies Management
    # ==========================================

    def save_cookies(
        self,
        domain: str,
        cookies: List[Dict],
        source_id: Optional[int] = None,
        validation_info: Optional[Dict] = None,
        user_email: Optional[str] = None
    ) -> Dict:
        """
        Save or update cookies for a domain.

        Args:
            domain: Domain for cookies (e.g., "ft.com")
            cookies: List of cookie dictionaries
            source_id: Optional source ID to associate cookies with
            validation_info: Optional validation metadata
            user_email: Email of user saving cookies (for audit)

        Returns:
            Dictionary with saved cookie record
        """
        # Check expiry info
        try:
            # Try Docker path first (when running in container)
            from app.utils.cookie_validator import check_cookie_expiry
        except ImportError:
            # Fall back to local dev path
            from webapp.backend.app.utils.cookie_validator import check_cookie_expiry
        expiry_info = check_cookie_expiry(cookies)

        # Prepare validation fields
        validation_status = validation_info.get('status') if validation_info else 'not_tested'
        validation_message = validation_info.get('message') if validation_info else None
        validation_response_size = validation_info.get('response_size') if validation_info else None
        test_url = validation_info.get('test_url') if validation_info else None
        last_validated_at = validation_info.get('tested_at') if validation_info else None

        query = """
        INSERT INTO source_cookies (
            source_id, domain, cookies,
            last_validated_at, validation_status, validation_message,
            last_validation_response_size, test_url,
            has_expired_cookies, expiring_soon, days_until_expiry, earliest_expiry,
            created_by, updated_by
        ) VALUES (
            %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s,
            %s, %s
        )
        ON CONFLICT (source_id, domain)
        DO UPDATE SET
            cookies = EXCLUDED.cookies,
            last_validated_at = EXCLUDED.last_validated_at,
            validation_status = EXCLUDED.validation_status,
            validation_message = EXCLUDED.validation_message,
            last_validation_response_size = EXCLUDED.last_validation_response_size,
            test_url = EXCLUDED.test_url,
            has_expired_cookies = EXCLUDED.has_expired_cookies,
            expiring_soon = EXCLUDED.expiring_soon,
            days_until_expiry = EXCLUDED.days_until_expiry,
            earliest_expiry = EXCLUDED.earliest_expiry,
            updated_by = EXCLUDED.updated_by,
            updated_at = NOW()
        RETURNING *;
        """

        params = (
            source_id, domain, json.dumps(cookies),
            last_validated_at, validation_status, validation_message,
            validation_response_size, test_url,
            expiry_info['has_expired'], expiry_info['expiring_soon'],
            expiry_info['days_until_expiry'], expiry_info['earliest_expiry'],
            user_email, user_email
        )

        result = self.execute_query(query, params, fetch_one=True)
        return dict(result) if result else None

    def get_cookies_by_domain(self, domain: str) -> Optional[Dict]:
        """
        Get cookies for a domain.

        Args:
            domain: Domain to lookup (e.g., "ft.com")

        Returns:
            Cookie record dictionary or None
        """
        query = """
        SELECT * FROM source_cookies
        WHERE domain = %s
        ORDER BY updated_at DESC
        LIMIT 1;
        """
        result = self.execute_query(query, (domain,), fetch_one=True)
        return dict(result) if result else None

    def get_cookies_by_source_id(self, source_id: int) -> Optional[Dict]:
        """
        Get cookies for a source.

        Args:
            source_id: Source ID

        Returns:
            Cookie record dictionary or None
        """
        query = """
        SELECT * FROM source_cookies
        WHERE source_id = %s
        ORDER BY updated_at DESC
        LIMIT 1;
        """
        result = self.execute_query(query, (source_id,), fetch_one=True)
        return dict(result) if result else None

    def list_all_cookies(self) -> List[Dict]:
        """
        List all cookie records.

        Returns:
            List of cookie record dictionaries
        """
        query = """
        SELECT * FROM source_cookies
        ORDER BY domain, updated_at DESC;
        """
        results = self.execute_query(query)
        return [dict(row) for row in results]

    def delete_cookies_by_domain(self, domain: str) -> bool:
        """
        Delete cookies for a domain.

        Args:
            domain: Domain to delete

        Returns:
            True if deleted, False otherwise
        """
        query = "DELETE FROM source_cookies WHERE domain = %s;"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (domain,))
            deleted = cursor.rowcount > 0
            conn.commit()
        return deleted

    def update_cookie_validation(
        self,
        domain: str,
        validation_info: Dict
    ) -> Optional[Dict]:
        """
        Update validation info for cookies.

        Args:
            domain: Domain to update
            validation_info: Validation metadata

        Returns:
            Updated cookie record or None
        """
        query = """
        UPDATE source_cookies
        SET
            last_validated_at = %s,
            validation_status = %s,
            validation_message = %s,
            last_validation_response_size = %s,
            test_url = %s,
            updated_at = NOW()
        WHERE domain = %s
        RETURNING *;
        """

        params = (
            validation_info.get('tested_at'),
            validation_info.get('status'),
            validation_info.get('message'),
            validation_info.get('response_size'),
            validation_info.get('test_url'),
            domain
        )

        result = self.execute_query(query, params, fetch_one=True)
        return dict(result) if result else None


# Convenience functions for backwards compatibility
def init_database(db_path: str = "data/news.db", drop_existing: bool = False):
    """Initialize database schema"""
    db = PostgreSQLURLDatabase(db_path)
    db.init_db(drop_existing=drop_existing)
    return db


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize database
    db = init_database("data/news.db", drop_existing=False)

    # Print stats
    stats = db.get_stats()
    print(f"\nDatabase Statistics:")
    print(f"  Total URLs: {stats['total_urls']}")
    print(f"  Content URLs: {stats['contenido_count']}")
    print(f"  Non-content URLs: {stats['no_contenido_count']}")
    print(f"  Unique sources: {stats['sources_count']}")
    if stats['date_range']:
        print(f"  Date range: {stats['date_range']['earliest']} to {stats['date_range']['latest']}")
