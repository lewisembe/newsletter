#!/usr/bin/env python3
"""
Migration script to add cluster_name column to clusters table and create VIEW.

This enables:
1. Storing descriptive names/hashtags for clusters
2. Easy querying of URLs with their cluster names via VIEW

Usage:
    python scripts/migrate_add_cluster_name.py [--db-path path/to/news.db]
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
    parser = argparse.ArgumentParser(description="Add cluster_name column and VIEW")
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
    cursor.execute("PRAGMA table_info(clusters)")
    columns = {row[1] for row in cursor.fetchall()}

    if "cluster_name" in columns:
        logger.info("cluster_name column already present – checking VIEW...")
        # Check if VIEW exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='view' AND name='urls_with_cluster'
        """)
        if cursor.fetchone():
            logger.info("VIEW urls_with_cluster already exists – no migration needed")
            return False
        logger.info("VIEW urls_with_cluster missing – will create")
        return True

    logger.info("cluster_name column missing from clusters table")
    return True


def apply_migration(conn: sqlite3.Connection):
    cursor = conn.cursor()

    # Check if cluster_name column exists
    cursor.execute("PRAGMA table_info(clusters)")
    columns = {row[1] for row in cursor.fetchall()}

    if "cluster_name" not in columns:
        logger.info("Adding cluster_name column to clusters table...")
        cursor.execute("ALTER TABLE clusters ADD COLUMN cluster_name TEXT DEFAULT NULL")

    # Drop existing VIEW if it exists (to recreate with updated schema)
    logger.info("Creating/updating VIEW urls_with_cluster...")
    cursor.execute("DROP VIEW IF EXISTS urls_with_cluster")

    # Create VIEW for easy querying of URLs with cluster info
    cursor.execute("""
        CREATE VIEW urls_with_cluster AS
        SELECT
            u.id,
            u.url,
            u.title,
            u.source,
            u.content_type,
            u.content_subtype,
            u.categoria_tematica,
            u.extracted_at,
            u.last_extracted_at,
            u.cluster_id,
            u.cluster_assigned_at,
            c.cluster_name,
            c.article_count as cluster_size,
            c.avg_similarity as cluster_similarity
        FROM urls u
        LEFT JOIN clusters c ON u.cluster_id = c.id
    """)

    # Create index on cluster_name for faster lookups
    logger.info("Creating index on cluster_name...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cluster_name ON clusters(cluster_name)")

    conn.commit()
    logger.info("Migration applied successfully")


def verify_migration(conn: sqlite3.Connection):
    cursor = conn.cursor()

    # Check cluster_name column
    cursor.execute("PRAGMA table_info(clusters)")
    columns = {row[1] for row in cursor.fetchall()}
    if "cluster_name" not in columns:
        raise RuntimeError("cluster_name column not found after migration")

    # Check VIEW exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='view' AND name='urls_with_cluster'
    """)
    if not cursor.fetchone():
        raise RuntimeError("VIEW urls_with_cluster not found after migration")

    # Check index exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name='idx_cluster_name'
    """)
    if not cursor.fetchone():
        raise RuntimeError("idx_cluster_name index not found after migration")

    # Test the VIEW works
    cursor.execute("SELECT COUNT(*) FROM urls_with_cluster LIMIT 1")

    logger.info("Verification succeeded")


def main():
    args = parse_args()
    db_path = Path(args.db_path)

    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        raise SystemExit(1)

    backup_path = backup_database(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        if not migration_needed(conn):
            return

        apply_migration(conn)
        verify_migration(conn)
        logger.info("Cluster-name migration completed successfully")
        logger.info(f"Backup stored at {backup_path}")
    except Exception as exc:
        logger.error(f"Migration failed: {exc}")
        logger.error(f"You can restore the backup with: cp {backup_path} {db_path}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
