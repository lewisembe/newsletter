#!/usr/bin/env python3
"""
Migration script to add ranking and debug report tables to the database.

This script:
1. Creates new tables: ranking_runs, ranked_urls, debug_reports
2. Fixes the content_extraction_method constraint
3. Creates indices for efficient queries
4. Is idempotent (safe to run multiple times)
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import common modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.postgres_db import PostgreSQLURLDatabase


def migrate_database():
    """Apply database migrations."""
    db = PostgreSQLURLDatabase()

    print("Starting database migration...")

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # 1. Create ranking_runs table
        print("Creating ranking_runs table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ranking_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                newsletter_name TEXT NOT NULL,
                run_date TEXT NOT NULL,
                generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ranker_method TEXT NOT NULL,
                categories_filter TEXT,
                articles_count INTEGER,
                total_ranked INTEGER,
                status TEXT CHECK(status IN ('completed', 'failed')) DEFAULT 'completed',
                execution_time_seconds REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(newsletter_name, run_date)
            )
        """)

        # 2. Create ranked_urls table
        print("Creating ranked_urls table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ranked_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ranking_run_id INTEGER NOT NULL,
                url_id INTEGER NOT NULL,
                rank INTEGER NOT NULL,
                score INTEGER,
                ranking_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ranking_run_id) REFERENCES ranking_runs(id) ON DELETE CASCADE,
                FOREIGN KEY (url_id) REFERENCES urls(id) ON DELETE CASCADE,
                UNIQUE(ranking_run_id, url_id)
            )
        """)

        # 3. Create indices for ranked_urls
        print("Creating indices for ranked_urls...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ranked_urls_run
            ON ranked_urls(ranking_run_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ranked_urls_url
            ON ranked_urls(url_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ranked_urls_rank
            ON ranked_urls(ranking_run_id, rank)
        """)

        # 4. Create debug_reports table
        print("Creating debug_reports table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS debug_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                newsletter_name TEXT NOT NULL,
                run_date TEXT NOT NULL,
                stage_01_duration REAL,
                stage_02_duration REAL,
                stage_03_duration REAL,
                stage_04_duration REAL,
                stage_05_duration REAL,
                total_duration REAL,
                tokens_used_stage_02 INTEGER,
                tokens_used_stage_03 INTEGER,
                tokens_used_stage_05 INTEGER,
                total_tokens INTEGER,
                report_json TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(newsletter_name, run_date)
            )
        """)

        # 5. Fix content_extraction_method constraint (if needed)
        print("Checking content_extraction_method constraint...")

        # Check if urls table exists and has the old constraint
        cursor.execute("""
            SELECT sql FROM sqlite_master
            WHERE type='table' AND name='urls'
        """)
        result = cursor.fetchone()

        if result:
            table_sql = result[0]
            # If table has the old constraint values, we need to recreate it
            if "CHECK(content_extraction_method IN ('libre', 'archiver', 'fallo'))" in table_sql:
                print("Found outdated constraint on content_extraction_method, recreating table...")

                # Create new table with updated constraint
                cursor.execute("""
                    CREATE TABLE urls_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT UNIQUE NOT NULL,
                        title TEXT,
                        source TEXT,
                        content_type TEXT CHECK(content_type IN ('contenido', 'no_contenido')),
                        content_subtype TEXT CHECK(content_subtype IN ('temporal', 'atemporal')),
                        categoria_tematica TEXT,
                        extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_extracted_at TIMESTAMP,
                        categorized_at TIMESTAMP,
                        full_content TEXT,
                        extraction_status TEXT CHECK(extraction_status IN ('success', 'failed', 'pending')),
                        extraction_error TEXT,
                        word_count INTEGER,
                        content_extraction_method TEXT CHECK(
                            content_extraction_method IN (
                                'xpath_cache', 'newspaper', 'readability',
                                'llm_xpath', 'json_ld', 'libre', 'archiver', 'fallo'
                            )
                        ),
                        archive_url TEXT,
                        content_extracted_at TIMESTAMP,
                        classification_method TEXT,
                        rule_name TEXT,
                        ai_summary TEXT
                    )
                """)

                # Copy data from old table
                cursor.execute("""
                    INSERT INTO urls_new
                    SELECT * FROM urls
                """)

                # Drop old table and rename new one
                cursor.execute("DROP TABLE urls")
                cursor.execute("ALTER TABLE urls_new RENAME TO urls")

                print("✓ Updated content_extraction_method constraint")
            else:
                print("✓ content_extraction_method constraint is up to date")

        # 6. Create indices on urls table if they don't exist
        print("Creating indices on urls table...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_urls_date
            ON urls(last_extracted_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_urls_category
            ON urls(categoria_tematica)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_urls_content_type
            ON urls(content_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_urls_extraction_status
            ON urls(extraction_status)
        """)

        # Commit all changes
        conn.commit()

    print("\n✅ Migration completed successfully!")
    print("\nNew tables created:")
    print("  - ranking_runs")
    print("  - ranked_urls")
    print("  - debug_reports")
    print("\nIndices created for better query performance")


if __name__ == "__main__":
    try:
        migrate_database()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}", file=sys.stderr)
        sys.exit(1)
