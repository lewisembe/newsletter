#!/usr/bin/env python3
"""
Migration script to add cluster_id tracking to urls table and supporting data.

This enables Stage 01 to persist the semantic cluster identifier for every URL
directly in news.db, to store per-cluster statistics, and to cache embeddings
(`url_embeddings`) for the incremental FAISS index used by the persistent
clusterer.

Usage:
    python scripts/migrate_add_cluster_id.py [--db-path path/to/news.db]
"""

import argparse
import logging
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add cluster_id columns to urls table")
    parser.add_argument(
        "--db-path",
        dest="db_path",
        default=Path(__file__).parent.parent / "data" / "news.db",
        help="Path to news.db (default: data/news.db)",
    )
    return parser.parse_args()


def backup_database(db_path: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}.db"
    shutil.copy2(db_path, backup_path)
    logger.info(f"Backup created at {backup_path}")
    return backup_path


def migration_needed(conn: sqlite3.Connection) -> bool:
    cursor = conn.cursor()

    # Check urls table
    cursor.execute("PRAGMA table_info(urls)")
    columns = {row[1] for row in cursor.fetchall()}
    missing_urls = [col for col in ("cluster_id", "cluster_assigned_at") if col not in columns]

    # Check ranked_urls table for related_url_ids
    missing_ranked = []
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='ranked_urls'
    """)
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(ranked_urls)")
        ranked_columns = {row[1] for row in cursor.fetchall()}
        if "related_url_ids" not in ranked_columns:
            missing_ranked.append("related_url_ids")

    if not missing_urls and not missing_ranked:
        logger.info("All cluster columns already present – no migration needed")
        return False

    if missing_urls:
        logger.info(f"Columns missing from urls table: {missing_urls}")
    if missing_ranked:
        logger.info(f"Columns missing from ranked_urls table: {missing_ranked}")
    return True


def apply_migration(conn: sqlite3.Connection):
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(urls)")
    columns = {row[1] for row in cursor.fetchall()}

    if "cluster_id" not in columns:
        logger.info("Adding cluster_id column...")
        cursor.execute("ALTER TABLE urls ADD COLUMN cluster_id TEXT DEFAULT NULL")

    if "cluster_assigned_at" not in columns:
        logger.info("Adding cluster_assigned_at column...")
        cursor.execute("ALTER TABLE urls ADD COLUMN cluster_assigned_at TIMESTAMP DEFAULT NULL")

    # Add related_url_ids column to ranked_urls for Stage 03 cluster deduplication
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='ranked_urls'
    """)
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(ranked_urls)")
        ranked_columns = {row[1] for row in cursor.fetchall()}
        if "related_url_ids" not in ranked_columns:
            logger.info("Adding related_url_ids column to ranked_urls table...")
            cursor.execute("ALTER TABLE ranked_urls ADD COLUMN related_url_ids TEXT DEFAULT NULL")

    logger.info("Creating cluster_id index (if missing)...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cluster_id ON urls(cluster_id)")

    logger.info("Ensuring clusters table exists...")
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
    additional_cluster_cols = {
        "similarity_mean": "REAL DEFAULT 0",
        "similarity_m2": "REAL DEFAULT 0",
        "similarity_samples": "INTEGER DEFAULT 0",
        "last_assigned_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }
    for column, definition in additional_cluster_cols.items():
        if column not in cluster_columns:
            logger.info(f"Adding {column} column to clusters table...")
            cursor.execute(f"ALTER TABLE clusters ADD COLUMN {column} {definition}")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_clusters_run_date ON clusters(run_date)")

    logger.info("Ensuring url_embeddings table exists...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS url_embeddings (
            url_id INTEGER PRIMARY KEY,
            embedding BLOB NOT NULL,
            dimension INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(url_id) REFERENCES urls(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_url_embeddings_dimension ON url_embeddings(dimension)")

    conn.commit()
    logger.info("Migration applied successfully")


def verify_migration(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(urls)")
    columns = {row[1] for row in cursor.fetchall()}

    for column in ("cluster_id", "cluster_assigned_at"):
        if column not in columns:
            raise RuntimeError(f"{column} not found after migration")

    # Verify related_url_ids in ranked_urls
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='ranked_urls'
    """)
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(ranked_urls)")
        ranked_columns = {row[1] for row in cursor.fetchall()}
        if "related_url_ids" not in ranked_columns:
            logger.warning("related_url_ids column not in ranked_urls (table may be recreated later)")
        else:
            logger.info("related_url_ids column verified in ranked_urls")

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name='idx_cluster_id'
    """)
    if not cursor.fetchone():
        raise RuntimeError("idx_cluster_id index missing after migration")

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='clusters'
    """)
    if not cursor.fetchone():
        raise RuntimeError("clusters table missing after migration")

    cursor.execute("PRAGMA table_info(clusters)")
    cluster_columns = {row[1] for row in cursor.fetchall()}
    for column in ("similarity_mean", "similarity_m2", "similarity_samples", "last_assigned_at"):
        if column not in cluster_columns:
            raise RuntimeError(f"{column} column missing in clusters table")

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name='idx_clusters_run_date'
    """)
    if not cursor.fetchone():
        raise RuntimeError("idx_clusters_run_date index missing after migration")

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='url_embeddings'
    """)
    if not cursor.fetchone():
        raise RuntimeError("url_embeddings table missing after migration")

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name='idx_url_embeddings_dimension'
    """)
    if not cursor.fetchone():
        raise RuntimeError("idx_url_embeddings_dimension index missing after migration")

    logger.info("Verification succeeded")


def main():
    args = parse_args()
    db_path = Path(args.db_path)

    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        raise SystemExit(1)

    backup_path = backup_database(db_path)

    conn = sqlite3.connect(db_path)
    try:
        if not migration_needed(conn):
            return

        apply_migration(conn)
        verify_migration(conn)
        logger.info("Cluster-id migration completed successfully")
        logger.info(f"Backup stored at {backup_path}")
    except Exception as exc:
        logger.error(f"Migration failed: {exc}")
        logger.error(f"You can restore the backup with: cp {backup_path} {db_path}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
