#!/usr/bin/env python3
"""
Migration script to add pipeline_executions table and execution_id column to pipeline_runs.

This migration enables:
- Tracking complete pipeline executions with their original parameters
- Resuming failed pipelines from last successful stage
- Replaying historical newsletters with exact same configuration

Usage:
    python scripts/migrate_add_executions.py [--db-path path/to/news.db]
"""

import sqlite3
import sys
import os
import logging
from pathlib import Path
from datetime import datetime, timezone

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_path():
    """Get database path from command line or use default."""
    if len(sys.argv) > 1 and sys.argv[1] == '--db-path' and len(sys.argv) > 2:
        return sys.argv[2]

    # Default path
    project_root = Path(__file__).parent.parent
    return project_root / 'data' / 'news.db'


def backup_database(db_path: Path) -> Path:
    """Create backup of database before migration."""
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}.db"

    logger.info(f"Creating backup: {backup_path}")

    # Copy database file
    import shutil
    shutil.copy2(db_path, backup_path)

    logger.info(f"Backup created successfully")
    return backup_path


def check_migration_needed(conn: sqlite3.Connection) -> bool:
    """Check if migration is needed."""
    cursor = conn.cursor()

    # Check if pipeline_executions table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='pipeline_executions'
    """)

    if cursor.fetchone():
        logger.info("Migration already applied (pipeline_executions table exists)")
        return False

    return True


def apply_migration(conn: sqlite3.Connection):
    """Apply the migration."""
    cursor = conn.cursor()

    logger.info("Creating pipeline_executions table...")

    # Create pipeline_executions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            newsletter_name TEXT NOT NULL,
            run_date TEXT NOT NULL,
            config_snapshot TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'partial', 'failed')),
            last_successful_stage INTEGER CHECK(last_successful_stage IN (1, 2, 3, 4, 5)),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP DEFAULT NULL,
            UNIQUE(newsletter_name, run_date, created_at)
        )
    """)

    logger.info("Creating index on pipeline_executions...")

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pipeline_executions_lookup
        ON pipeline_executions(newsletter_name, run_date, status)
    """)

    logger.info("Adding execution_id column to pipeline_runs...")

    # Add execution_id column to pipeline_runs
    # Note: SQLite doesn't support ALTER COLUMN, so we check if column exists first
    cursor.execute("PRAGMA table_info(pipeline_runs)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'execution_id' not in columns:
        cursor.execute("""
            ALTER TABLE pipeline_runs
            ADD COLUMN execution_id INTEGER REFERENCES pipeline_executions(id)
        """)
        logger.info("Added execution_id column to pipeline_runs")
    else:
        logger.info("execution_id column already exists in pipeline_runs")

    conn.commit()
    logger.info("Migration completed successfully!")


def verify_migration(conn: sqlite3.Connection):
    """Verify migration was applied correctly."""
    cursor = conn.cursor()

    # Check pipeline_executions table
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='pipeline_executions'
    """)
    if not cursor.fetchone():
        raise Exception("pipeline_executions table not found after migration")

    # Check execution_id column
    cursor.execute("PRAGMA table_info(pipeline_runs)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'execution_id' not in columns:
        raise Exception("execution_id column not found in pipeline_runs after migration")

    # Check index
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name='idx_pipeline_executions_lookup'
    """)
    if not cursor.fetchone():
        raise Exception("Index idx_pipeline_executions_lookup not found after migration")

    logger.info("Migration verification passed!")


def main():
    db_path = Path(get_db_path())

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        logger.error("Please run the pipeline at least once to create the database")
        sys.exit(1)

    logger.info(f"Using database: {db_path}")

    # Create backup
    backup_path = backup_database(db_path)

    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Check if migration needed
        if not check_migration_needed(conn):
            logger.info("No migration needed")
            conn.close()
            return

        # Apply migration
        logger.info("Applying migration...")
        apply_migration(conn)

        # Verify migration
        verify_migration(conn)

        conn.close()

        logger.info("="*80)
        logger.info("MIGRATION COMPLETED SUCCESSFULLY")
        logger.info(f"Backup saved to: {backup_path}")
        logger.info("="*80)

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        logger.error(f"Database backup is available at: {backup_path}")
        logger.error("You can restore it with: cp {} {}".format(backup_path, db_path))
        sys.exit(1)


if __name__ == '__main__':
    main()
