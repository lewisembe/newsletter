"""
SQLite Database Manager for Newsletter Utils

Provides a robust interface for URL storage and retrieval using SQLite.
Replaces CSV-based persistence with proper database functionality.

Author: Newsletter Utils Team
Created: 2025-11-10
"""

import sqlite3
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
import os

logger = logging.getLogger(__name__)


class SQLiteURLDatabase:
    """
    SQLite database manager for URL storage and retrieval.

    Features:
    - UNIQUE constraint on URL (enforces integrity)
    - Dual timestamp tracking (extracted_at + last_extracted_at)
    - Indexed queries for performance
    - Connection pooling
    - Transaction support with rollback
    - Comprehensive error handling

    Usage:
        db = SQLiteURLDatabase("data/news.db")
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

    def __init__(self, db_path: str = "data/news.db"):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_directory()
        logger.info(f"SQLiteURLDatabase initialized with path: {db_path}")

    def _ensure_directory(self):
        """Ensure database directory exists"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")

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
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def init_db(self, drop_existing: bool = False):
        """
        Initialize database schema with tables and indices.

        Args:
            drop_existing: If True, drops existing tables before creating

        Creates:
            - urls table with UNIQUE constraint
            - Indices for performance (extracted_at, content_type, source)
            - Composite index (extracted_at, content_type) for Stage 02 queries
            - Auto-update trigger for updated_at timestamp
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Drop existing tables if requested
            if drop_existing:
                cursor.execute("DROP TABLE IF EXISTS urls")
                logger.warning("Dropped existing tables")

            # Create urls table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS urls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    title TEXT,

                    -- Classification (Nivel 1)
                    content_type TEXT NOT NULL CHECK(content_type IN ('contenido', 'no_contenido')),

                    -- Classification (Nivel 2, opcional) - Temporalidad del contenido
                    content_subtype TEXT CHECK(content_subtype IN ('temporal', 'atemporal', NULL)),

                    -- Classification metadata
                    classification_method TEXT NOT NULL CHECK(classification_method IN ('cached_url', 'regex_rule', 'heuristic', 'llm_api')),
                    rule_name TEXT DEFAULT NULL,

                    -- Source
                    source TEXT NOT NULL,

                    -- Timestamps (ISO 8601 UTC)
                    extracted_at TIMESTAMP NOT NULL,
                    last_extracted_at TIMESTAMP NOT NULL,

                    -- Stage 02: Thematic categorization (for newsletter filtering)
                    categoria_tematica TEXT DEFAULT NULL,
                    categorized_at TIMESTAMP DEFAULT NULL,

                    -- Stage 01.5: Semantic clustering metadata
                    cluster_id TEXT DEFAULT NULL,
                    cluster_assigned_at TIMESTAMP DEFAULT NULL,

                    -- Content extraction tracking (Stage 04)
                    content_extracted_at TIMESTAMP DEFAULT NULL,
                    content_extraction_method TEXT CHECK(content_extraction_method IN ('xpath_cache', 'newspaper', 'readability', 'llm_xpath', 'archive', 'failed', NULL)),

                    -- Metadata
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Ensure clustering columns exist for pre-existing databases
            cursor.execute("PRAGMA table_info(urls)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            if 'cluster_id' not in existing_columns:
                cursor.execute("ALTER TABLE urls ADD COLUMN cluster_id TEXT DEFAULT NULL")
                logger.info("Added cluster_id column to urls table")
            if 'cluster_assigned_at' not in existing_columns:
                cursor.execute("ALTER TABLE urls ADD COLUMN cluster_assigned_at TIMESTAMP DEFAULT NULL")
                logger.info("Added cluster_assigned_at column to urls table")

            # Clusters table keeps aggregated metadata per semantic cluster
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clusters (
                    id TEXT PRIMARY KEY,
                    run_date TEXT NOT NULL,
                    centroid_url_id INTEGER,
                    article_count INTEGER NOT NULL,
                    avg_similarity REAL,
                    similarity_mean REAL DEFAULT 0,
                    similarity_m2 REAL DEFAULT 0,
                    similarity_samples INTEGER DEFAULT 0,
                    last_assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (centroid_url_id) REFERENCES urls(id)
                )
            """)

            cursor.execute("PRAGMA table_info(clusters)")
            cluster_columns = {row[1] for row in cursor.fetchall()}
            if 'similarity_mean' not in cluster_columns:
                cursor.execute("ALTER TABLE clusters ADD COLUMN similarity_mean REAL DEFAULT 0")
                logger.info("Added similarity_mean column to clusters table")
            if 'similarity_m2' not in cluster_columns:
                cursor.execute("ALTER TABLE clusters ADD COLUMN similarity_m2 REAL DEFAULT 0")
                logger.info("Added similarity_m2 column to clusters table")
            if 'similarity_samples' not in cluster_columns:
                cursor.execute("ALTER TABLE clusters ADD COLUMN similarity_samples INTEGER DEFAULT 0")
                logger.info("Added similarity_samples column to clusters table")
            if 'last_assigned_at' not in cluster_columns:
                cursor.execute("ALTER TABLE clusters ADD COLUMN last_assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                logger.info("Added last_assigned_at column to clusters table")

            # Embedding storage for incremental clustering
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS url_embeddings (
                    url_id INTEGER PRIMARY KEY,
                    embedding BLOB NOT NULL,
                    dimension INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(url_id) REFERENCES urls(id) ON DELETE CASCADE
                )
            """)

            # Create indices
            # UNIQUE index on url (enforced by UNIQUE constraint, but explicit for clarity)
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_url ON urls(url)")

            # Critical indices for queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_extracted_at ON urls(extracted_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_last_extracted_at ON urls(last_extracted_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_type ON urls(content_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON urls(source)")

            # Composite index for Stage 02 filtering (date + content_type)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_extracted_content ON urls(extracted_at, content_type)")

            # Index for title search (optional, for future FTS)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_title ON urls(title)")

            # Indices for Stage 02 thematic categorization
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_categoria_tematica ON urls(categoria_tematica)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_categorized_at ON urls(categorized_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cluster_id ON urls(cluster_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_clusters_run_date ON clusters(run_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_url_embeddings_dimension ON url_embeddings(dimension)")

            # Create trigger for auto-updating updated_at
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS update_urls_timestamp
                AFTER UPDATE ON urls
                FOR EACH ROW
                BEGIN
                    UPDATE urls SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS update_clusters_timestamp
                AFTER UPDATE ON clusters
                FOR EACH ROW
                BEGIN
                    UPDATE clusters SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END
            """)

            # Create pipeline_runs table for orchestrator tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    newsletter_name TEXT NOT NULL,
                    run_date TEXT NOT NULL,
                    stage INTEGER NOT NULL CHECK(stage IN (1, 2, 3, 4, 5)),
                    status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed')),
                    output_file TEXT DEFAULT NULL,
                    error_message TEXT DEFAULT NULL,
                    started_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP DEFAULT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indices for pipeline_runs
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_newsletter ON pipeline_runs(newsletter_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_date ON pipeline_runs(run_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_stage ON pipeline_runs(stage)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_status ON pipeline_runs(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_newsletter_date_stage ON pipeline_runs(newsletter_name, run_date, stage)")

            # Create site_cookies table for authenticated scraping (Stage 04)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS site_cookies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL,
                    cookie_name TEXT NOT NULL,
                    cookie_value TEXT NOT NULL,
                    path TEXT DEFAULT '/',
                    secure BOOLEAN DEFAULT 1,
                    http_only BOOLEAN DEFAULT 0,
                    same_site TEXT CHECK(same_site IN ('Strict', 'Lax', 'None', NULL)),
                    expiry INTEGER DEFAULT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(domain, cookie_name)
                )
            """)

            # Create indices for site_cookies
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cookies_domain ON site_cookies(domain)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cookies_expiry ON site_cookies(expiry)")

            # Create trigger for auto-updating site_cookies.updated_at
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS update_site_cookies_timestamp
                AFTER UPDATE ON site_cookies
                FOR EACH ROW
                BEGIN
                    UPDATE site_cookies SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END
            """)

            conn.commit()
            logger.info("Database schema initialized successfully (urls, pipeline_runs, site_cookies)")

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

        Returns:
            Row ID of inserted URL, or None if URL already exists

        Raises:
            sqlite3.IntegrityError: If URL already exists
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
                        classification_method, rule_name, extracted_at, last_extracted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    url_data['url'],
                    url_data.get('title'),
                    url_data['source'],
                    url_data['content_type'],
                    url_data.get('content_subtype'),
                    url_data['classification_method'],
                    url_data.get('rule_name'),
                    url_data['extracted_at'],
                    url_data['last_extracted_at']
                ))

                conn.commit()
                row_id = cursor.lastrowid
                logger.debug(f"Added URL: {url_data['url']} (id: {row_id})")
                return row_id

            except sqlite3.IntegrityError as e:
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
            set_clauses.append(f"{key} = ?")
            values.append(value)

        values.append(url)  # For WHERE clause

        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = f"""
                UPDATE urls
                SET {', '.join(set_clauses)}
                WHERE url = ?
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
            cursor.execute("SELECT * FROM urls WHERE url = ?", (url,))
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
            placeholders = ','.join('?' * len(url_list))
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

            query = "SELECT * FROM urls WHERE date(extracted_at) = ?"
            params = [date]

            if content_type:
                query += " AND content_type = ?"
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
                    cursor.execute("SELECT id, extracted_at FROM urls WHERE url = ?", (url_data['url'],))
                    existing = cursor.fetchone()

                    if existing:
                        # Update: preserve extracted_at, update last_extracted_at
                        cursor.execute("""
                            UPDATE urls
                            SET title = ?,
                                content_type = ?,
                                content_subtype = ?,
                                classification_method = ?,
                                rule_name = ?,
                                last_extracted_at = ?
                            WHERE url = ?
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
                                classification_method, rule_name, extracted_at, last_extracted_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            url_data['url'],
                            url_data.get('title'),
                            url_data['source'],
                            url_data['content_type'],
                            url_data.get('content_subtype'),
                            url_data['classification_method'],
                            url_data.get('rule_name'),
                            extracted_at,
                            now
                        ))
                        stats['inserted'] += 1

                except sqlite3.Error as e:
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
                WHERE date(extracted_at) = ?
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
                SET cluster_id = ?,
                    cluster_assigned_at = ?
                WHERE id = ?
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
            cursor.execute("DELETE FROM clusters WHERE run_date = ?", (date,))
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
                VALUES (?, ?, ?, ?, ?)
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
                SET cluster_id = ?,
                    cluster_assigned_at = ?
                WHERE id = ?
                """,
                (cluster_id, assigned_at, url_id),
            )
            conn.commit()

    def get_cluster_id_map(self) -> Dict[int, str]:
        """Return mapping of url_id -> cluster_id for assigned URLs."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cluster_id FROM urls WHERE cluster_id IS NOT NULL")
            return {row[0]: row[1] for row in cursor.fetchall() if row[1]}

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
                result[row[0]] = {
                    "run_date": row[1],
                    "article_count": row[2],
                    "avg_similarity": row[3],
                    "similarity_mean": row[4] or 0.0,
                    "similarity_m2": row[5] or 0.0,
                    "similarity_samples": row[6] or 0,
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
                ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, CURRENT_TIMESTAMP, ?)
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
            fields.append("article_count = ?")
            values.append(article_count)
        if avg_similarity is not None:
            fields.append("avg_similarity = ?")
            values.append(avg_similarity)
        if similarity_mean is not None:
            fields.append("similarity_mean = ?")
            values.append(similarity_mean)
        if similarity_m2 is not None:
            fields.append("similarity_m2 = ?")
            values.append(similarity_m2)
        if similarity_samples is not None:
            fields.append("similarity_samples = ?")
            values.append(similarity_samples)
        if centroid_url_id is not None:
            fields.append("centroid_url_id = ?")
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
                WHERE id = ?
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
                VALUES (?, ?, ?)
                """,
                (url_id, sqlite3.Binary(embedding), dimension),
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
                    'url_id': row[0],
                    'embedding': row[1],
                    'dimension': row[2],
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            cursor.execute("SELECT COUNT(*) FROM clusters")
            clusters_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM url_embeddings")
            embeddings_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM urls WHERE cluster_id IS NOT NULL")
            assigned_urls_count = cursor.fetchone()[0]

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
                LIMIT ?
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
                WHERE extracted_at >= ?
                  AND extracted_at <= ?
                  AND content_type = 'contenido'
            """
            params = [start_datetime, end_datetime]

            # Add source filter
            if sources:
                placeholders = ','.join('?' * len(sources))
                query += f" AND source IN ({placeholders})"
                params.extend(sources)

            # Add category filter (only if categories specified AND URL has category)
            if categories:
                placeholders = ','.join('?' * len(categories))
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
                set_clauses.append(f"{key} = ?")
                values.append(value)

            values.append(url_id)  # For WHERE clause

            query = f"""
                UPDATE urls
                SET {', '.join(set_clauses)}
                WHERE id = ?
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
                            SET categoria_tematica = ?,
                                content_subtype = ?,
                                categorized_at = ?
                            WHERE id = ?
                        """, (categoria_tematica, content_subtype, now, url_id))
                    else:
                        cursor.execute("""
                            UPDATE urls
                            SET categoria_tematica = ?,
                                categorized_at = ?
                            WHERE id = ?
                        """, (categoria_tematica, now, url_id))

                    if cursor.rowcount > 0:
                        stats['updated'] += 1

                except sqlite3.Error as e:
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
            cursor.execute("SELECT COUNT(*) FROM urls")
            total = cursor.fetchone()[0]

            # Content type breakdown
            cursor.execute("SELECT content_type, COUNT(*) FROM urls GROUP BY content_type")
            content_breakdown = dict(cursor.fetchall())

            # Unique sources
            cursor.execute("SELECT COUNT(DISTINCT source) FROM urls")
            sources = cursor.fetchone()[0]

            # Date range
            cursor.execute("SELECT MIN(extracted_at), MAX(extracted_at) FROM urls")
            date_range = cursor.fetchone()

            return {
                'total_urls': total,
                'contenido_count': content_breakdown.get('contenido', 0),
                'no_contenido_count': content_breakdown.get('no_contenido', 0),
                'sources_count': sources,
                'date_range': {
                    'earliest': date_range[0],
                    'latest': date_range[1]
                } if date_range[0] else None
            }

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
            cursor.execute("SELECT * FROM urls WHERE id = ?", (url_id,))
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
                set_clauses.append(f"{key} = ?")
                values.append(value)

            values.append(url_id)  # For WHERE clause

            query = f"""
                UPDATE urls
                SET {', '.join(set_clauses)}
                WHERE id = ?
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

            placeholders = ','.join('?' * len(ranked_url_ids))

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
                ) VALUES (?, ?, ?, 'running', ?)
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
                SET status = ?,
                    output_file = ?,
                    error_message = ?,
                    completed_at = ?
                WHERE id = ?
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
                WHERE newsletter_name = ?
                  AND run_date = ?
                  AND stage = ?
                ORDER BY created_at DESC
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
                ) VALUES (?, ?, ?, 'running', ?)
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
                    SET status = ?,
                        last_successful_stage = ?,
                        completed_at = ?
                    WHERE id = ?
                """, (status, last_successful_stage, now, execution_id))
            else:
                cursor.execute("""
                    UPDATE pipeline_executions
                    SET status = ?,
                        last_successful_stage = ?
                    WHERE id = ?
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
                SELECT * FROM pipeline_executions WHERE id = ?
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
                WHERE newsletter_name = ? AND run_date = ?
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
                    WHERE newsletter_name = ?
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
                WHERE execution_id = ?
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
                SET execution_id = ?
                WHERE id = ?
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
                WHERE execution_id = ?
                  AND stage >= ?
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
            cursor.execute("SELECT * FROM urls WHERE id = ?", (url_id,))
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
                ) VALUES (?, ?, ?, ?, ?, ?, 'completed')
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
                WHERE newsletter_name = ? AND run_date = ?
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
            cursor.execute("DELETE FROM ranked_urls WHERE ranking_run_id = ?", (ranking_run_id,))

            # Insert new ranked URLs (v3.2: includes related_url_ids for cluster context)
            for ranked_url in ranked_urls:
                related_url_ids = ranked_url.get('related_url_ids')  # JSON string or None
                cursor.execute("""
                    INSERT INTO ranked_urls (
                        ranking_run_id, url_id, rank, related_url_ids
                    ) VALUES (?, ?, ?, ?)
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
                SET total_ranked = ?
                WHERE id = ?
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
                WHERE newsletter_name = ? AND run_date = ?
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
                WHERE ru.ranking_run_id = ?
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
                WHERE ru.ranking_run_id = ?
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                WHERE newsletter_name = ? AND run_date = ?
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
                WHERE domain = ? OR domain = ?
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
                WHERE domain = ? OR domain = ?
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
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                WHERE domain = ? OR domain = ?
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
                WHERE (domain = ? OR domain = ?)
                  AND expiry IS NOT NULL
                  AND expiry < ?
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
            cursor.execute("SELECT ai_summary FROM urls WHERE id = ?", (url_id,))
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
            cursor.execute("UPDATE urls SET ai_summary = ? WHERE id = ?", (summary, url_id))
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
                INSERT OR REPLACE INTO newsletters (
                    newsletter_name, run_date, template_name, output_format,
                    categories, content_markdown, content_html,
                    articles_count, articles_with_content, ranking_run_id,
                    generation_method, model_summarizer, model_writer,
                    total_tokens_used, generation_duration_seconds,
                    output_file_md, output_file_html, context_report_file
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                newsletter_name, run_date, template_name, output_format,
                categories_json, content_markdown, content_html,
                articles_count, articles_with_content, ranking_run_id,
                generation_method, model_summarizer, model_writer,
                total_tokens_used, generation_duration_seconds,
                output_file_md, output_file_html, context_report_file
            ))

            conn.commit()
            newsletter_id = cursor.lastrowid
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
                WHERE newsletter_name = ? AND run_date = ?
            """, (newsletter_name, run_date))

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
                    WHERE run_date BETWEEN ? AND ?
                      AND newsletter_name = ?
                    ORDER BY run_date DESC, generated_at DESC
                """, (start_date, end_date, newsletter_name))
            else:
                cursor.execute("""
                    SELECT * FROM newsletters
                    WHERE run_date BETWEEN ? AND ?
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

    def get_latest_newsletters(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get latest newsletters generated.

        Args:
            limit: Maximum number to return

        Returns:
            List of newsletter dicts
        """
        import json

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM newsletters
                ORDER BY generated_at DESC
                LIMIT ?
            """, (limit,))

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
                    WHERE newsletter_name = ?
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
                SET relevance_level = ?,
                    scored_at = ?,
                    scored_by_method = ?
                WHERE id = ?
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
                    SET relevance_level = ?,
                        scored_at = ?,
                        scored_by_method = ?
                    WHERE id = ?
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
                WHERE cluster_id = ?
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
                WHERE cluster_id = ?
                  AND id != ?
                  AND content_type = 'contenido'
                ORDER BY
                    CASE WHEN word_count IS NOT NULL THEN word_count ELSE 0 END DESC,
                    extracted_at DESC
                LIMIT ?
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
                WHERE cluster_id = ?
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
                WHERE cluster_id = ?
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
                WHERE cluster_id = ?
                  AND id != ?
                  AND DATE(extracted_at) >= DATE(?, '-' || ? || ' days')
                  AND DATE(extracted_at) <= DATE(?)
                ORDER BY
                    extracted_at DESC,
                    CASE WHEN word_count IS NOT NULL THEN word_count ELSE 0 END DESC
                LIMIT ?
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
                SET cluster_name = ?
                WHERE id = ?
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
                  AND c.article_count >= ?
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
                WHERE cluster_id = ?
                  AND title IS NOT NULL
                  AND title != ''
                ORDER BY extracted_at DESC
                LIMIT ?
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
                WHERE id = ?
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
                WHERE extracted_at >= ? AND extracted_at < ?
                  AND content_type = 'contenido'
            """
            params = [start_datetime, end_datetime]

            # Filter by sources
            if sources:
                placeholders = ','.join(['?'] * len(sources))
                query += f" AND source IN ({placeholders})"
                params.extend(sources)

            # Filter by categories
            if categories:
                placeholders = ','.join(['?'] * len(categories))
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


# Convenience functions for backwards compatibility
def init_database(db_path: str = "data/news.db", drop_existing: bool = False):
    """Initialize database schema"""
    db = SQLiteURLDatabase(db_path)
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
