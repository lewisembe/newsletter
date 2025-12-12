#!/usr/bin/env python3
"""
Database Migration Script for Stage 04

Adds new columns to the urls table for content extraction:
- full_content: Full extracted article text
- extraction_status: Status of extraction ('success', 'failed', 'pending')
- extraction_error: Error message if extraction failed
- word_count: Word count of extracted content
- archive_url: Archive.today URL if fetched from archive

Author: Newsletter Utils Team
Created: 2025-11-13
"""

import sqlite3
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from common.postgres_db import PostgreSQLURLDatabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate_schema(db_path: str = "data/news.db"):
    """
    Apply Stage 04 schema migrations.

    Args:
        db_path: Path to SQLite database
    """
    logger.info("="*80)
    logger.info("STAGE 04 DATABASE MIGRATION")
    logger.info("="*80)
    logger.info(f"Database: {db_path}")

    db = PostgreSQLURLDatabase(db_path)

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Check existing schema
        logger.info("\nChecking existing schema...")
        cursor.execute("PRAGMA table_info(urls)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        logger.info(f"Existing columns: {len(existing_columns)} found")

        # Define new columns to add
        new_columns = [
            ("full_content", "TEXT DEFAULT NULL", "Full extracted article content"),
            ("extraction_status", "TEXT CHECK(extraction_status IN ('success', 'failed', 'pending', NULL))", "Extraction status"),
            ("extraction_error", "TEXT DEFAULT NULL", "Error message if extraction failed"),
            ("word_count", "INTEGER DEFAULT NULL", "Word count of extracted content"),
            ("archive_url", "TEXT DEFAULT NULL", "Archive.today URL if used"),
        ]

        logger.info("\nApplying migrations...")
        migrations_applied = 0

        for column_name, column_def, description in new_columns:
            if column_name not in existing_columns:
                try:
                    sql = f"ALTER TABLE urls ADD COLUMN {column_name} {column_def}"
                    cursor.execute(sql)
                    logger.info(f"✓ Added column: {column_name} ({description})")
                    migrations_applied += 1
                except sqlite3.Error as e:
                    logger.error(f"✗ Failed to add column {column_name}: {e}")
                    raise
            else:
                logger.info(f"  Column already exists: {column_name}")

        # Update content_extraction_method CHECK constraint to include new methods
        logger.info("\nUpdating content_extraction_method constraint...")

        # SQLite doesn't support ALTER CHECK constraint directly
        # We'll document the new valid values:
        # 'xpath_cache', 'newspaper', 'readability', 'llm_xpath', 'archive', 'failed'
        logger.info("  Note: New extraction methods added:")
        logger.info("    - xpath_cache: Extracted using cached XPath")
        logger.info("    - newspaper: Extracted using newspaper3k")
        logger.info("    - readability: Extracted using readability-lxml")
        logger.info("    - llm_xpath: Extracted using LLM-discovered XPath")
        logger.info("    - archive: Fetched from archive.today")
        logger.info("    - failed: All extraction methods failed")

        # Create index for extraction_status for faster queries
        logger.info("\nCreating indices...")
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_extraction_status ON urls(extraction_status)")
            logger.info("✓ Created index: idx_extraction_status")
        except sqlite3.Error as e:
            logger.warning(f"Index creation warning: {e}")

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_word_count ON urls(word_count)")
            logger.info("✓ Created index: idx_word_count")
        except sqlite3.Error as e:
            logger.warning(f"Index creation warning: {e}")

        conn.commit()

        # Verify migration
        logger.info("\nVerifying migration...")
        cursor.execute("PRAGMA table_info(urls)")
        final_columns = {row[1] for row in cursor.fetchall()}

        all_expected_columns = existing_columns | {col[0] for col in new_columns}
        missing = all_expected_columns - final_columns

        if missing:
            logger.error(f"✗ Migration incomplete. Missing columns: {missing}")
            return False

        logger.info("="*80)
        logger.info("MIGRATION SUMMARY")
        logger.info("="*80)
        logger.info(f"Migrations applied: {migrations_applied}")
        logger.info(f"Total columns: {len(final_columns)}")
        logger.info(f"Status: {'✓ SUCCESS' if migrations_applied > 0 else '✓ UP TO DATE'}")
        logger.info("="*80)

        return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Apply Stage 04 database schema migrations"
    )
    parser.add_argument(
        '--db-path',
        default='data/news.db',
        help='Path to SQLite database (default: data/news.db)'
    )

    args = parser.parse_args()

    try:
        success = migrate_schema(args.db_path)
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
