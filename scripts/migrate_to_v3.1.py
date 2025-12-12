#!/usr/bin/env python3
"""
Migration script: v3.0 → v3.1

Changes:
1. Create table `newsletters` for storing complete newsletters
2. Add scoring columns to `urls` table (relevance_level, scored_at, scored_by_method)
3. Clean up `ranked_urls` table (remove score and level columns, keep only rank)
4. Create optimized indexes
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "news.db"


def backup_database(db_path: Path) -> Path:
    """Create backup before migration"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"news_backup_v3.0_{timestamp}.db"

    print(f"Creating backup: {backup_path}")

    # Use SQLite backup API
    source_conn = sqlite3.connect(db_path)
    backup_conn = sqlite3.connect(backup_path)

    source_conn.backup(backup_conn)

    source_conn.close()
    backup_conn.close()

    print(f"✓ Backup created: {backup_path}")
    return backup_path


def verify_database(conn: sqlite3.Connection) -> bool:
    """Verify database integrity"""
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check;")
    result = cursor.fetchone()

    if result[0] != "ok":
        print(f"✗ Database integrity check failed: {result[0]}")
        return False

    print("✓ Database integrity verified")
    return True


def create_newsletters_table(conn: sqlite3.Connection):
    """Create newsletters table"""
    print("\n[1/4] Creating newsletters table...")

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS newsletters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Identificación
            newsletter_name TEXT NOT NULL,
            run_date TEXT NOT NULL,

            -- Configuración
            template_name TEXT NOT NULL,
            output_format TEXT NOT NULL,
            categories TEXT,

            -- Contenido
            content_markdown TEXT NOT NULL,
            content_html TEXT,

            -- Metadata de generación
            articles_count INTEGER NOT NULL,
            articles_with_content INTEGER NOT NULL,

            -- Execution tracking
            ranking_run_id INTEGER,
            generation_method TEXT DEFAULT '4-step',
            model_summarizer TEXT DEFAULT 'gpt-4o-mini',
            model_writer TEXT DEFAULT 'gpt-4o',

            -- Performance
            total_tokens_used INTEGER,
            generation_duration_seconds REAL,

            -- Files
            output_file_md TEXT,
            output_file_html TEXT,
            context_report_file TEXT,

            -- Timestamps
            generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

            -- Constraints
            UNIQUE(newsletter_name, run_date),
            FOREIGN KEY (ranking_run_id) REFERENCES ranking_runs(id) ON DELETE SET NULL
        );
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_newsletters_name ON newsletters(newsletter_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_newsletters_date ON newsletters(run_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_newsletters_ranking ON newsletters(ranking_run_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_newsletters_generated_at ON newsletters(generated_at);")

    conn.commit()
    print("✓ newsletters table created with indexes")


def add_scoring_columns_to_urls(conn: sqlite3.Connection):
    """Add scoring columns to urls table"""
    print("\n[2/4] Adding scoring columns to urls table...")

    cursor = conn.cursor()

    # Check if columns already exist
    cursor.execute("PRAGMA table_info(urls);")
    existing_columns = [row[1] for row in cursor.fetchall()]

    columns_to_add = [
        ("relevance_level", "ALTER TABLE urls ADD COLUMN relevance_level INTEGER DEFAULT NULL CHECK(relevance_level BETWEEN 1 AND 5);"),
        ("scored_at", "ALTER TABLE urls ADD COLUMN scored_at TIMESTAMP DEFAULT NULL;"),
        ("scored_by_method", "ALTER TABLE urls ADD COLUMN scored_by_method TEXT DEFAULT NULL CHECK(scored_by_method IN ('level_scoring', 'dual_subset', NULL));")
    ]

    for col_name, sql in columns_to_add:
        if col_name not in existing_columns:
            cursor.execute(sql)
            print(f"  ✓ Added column: {col_name}")
        else:
            print(f"  → Column already exists: {col_name}")

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_urls_relevance_level ON urls(relevance_level);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_urls_scored_at ON urls(scored_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_urls_scoring_method ON urls(scored_by_method);")

    conn.commit()
    print("✓ Scoring columns and indexes added to urls table")


def cleanup_ranked_urls_table(conn: sqlite3.Connection):
    """Remove score and level columns from ranked_urls table"""
    print("\n[3/4] Cleaning up ranked_urls table...")

    cursor = conn.cursor()

    # Check current schema
    cursor.execute("PRAGMA table_info(ranked_urls);")
    existing_columns = {row[1]: row for row in cursor.fetchall()}

    print(f"  Current columns: {list(existing_columns.keys())}")

    # Check if we need to migrate
    needs_migration = 'score' in existing_columns or 'level' in existing_columns

    if not needs_migration:
        print("  → ranked_urls already clean (no score/level columns)")
        return

    print("  Migrating ranked_urls to clean schema...")

    # Create new table with clean schema
    cursor.execute("""
        CREATE TABLE ranked_urls_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ranking_run_id INTEGER NOT NULL,
            url_id INTEGER NOT NULL,
            rank INTEGER NOT NULL,
            FOREIGN KEY(ranking_run_id) REFERENCES ranking_runs(id),
            FOREIGN KEY(url_id) REFERENCES urls(id)
        );
    """)

    # Copy data (only id, ranking_run_id, url_id, rank)
    cursor.execute("""
        INSERT INTO ranked_urls_new (id, ranking_run_id, url_id, rank)
        SELECT id, ranking_run_id, url_id, rank
        FROM ranked_urls;
    """)

    rows_copied = cursor.rowcount
    print(f"  ✓ Copied {rows_copied} rows to new table")

    # Drop old table and rename new one
    cursor.execute("DROP TABLE ranked_urls;")
    cursor.execute("ALTER TABLE ranked_urls_new RENAME TO ranked_urls;")

    # Recreate indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ranked_urls_ranking ON ranked_urls(ranking_run_id, rank);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ranked_urls_url ON ranked_urls(url_id, ranking_run_id);")

    conn.commit()
    print("✓ ranked_urls table cleaned (removed score and level columns)")


def verify_migration(conn: sqlite3.Connection):
    """Verify migration was successful"""
    print("\n[4/4] Verifying migration...")

    cursor = conn.cursor()

    # Check newsletters table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='newsletters';")
    if not cursor.fetchone():
        raise Exception("newsletters table not found")
    print("  ✓ newsletters table exists")

    # Check urls has scoring columns
    cursor.execute("PRAGMA table_info(urls);")
    urls_columns = [row[1] for row in cursor.fetchall()]
    required_cols = ['relevance_level', 'scored_at', 'scored_by_method']
    for col in required_cols:
        if col not in urls_columns:
            raise Exception(f"urls.{col} column not found")
    print(f"  ✓ urls table has scoring columns: {required_cols}")

    # Check ranked_urls is clean
    cursor.execute("PRAGMA table_info(ranked_urls);")
    ranked_urls_columns = [row[1] for row in cursor.fetchall()]
    expected_cols = ['id', 'ranking_run_id', 'url_id', 'rank']
    if set(ranked_urls_columns) != set(expected_cols):
        raise Exception(f"ranked_urls has unexpected columns: {ranked_urls_columns}")
    print(f"  ✓ ranked_urls table is clean: {expected_cols}")

    # Check indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='newsletters';")
    newsletters_indexes = [row[0] for row in cursor.fetchall()]
    if len(newsletters_indexes) < 4:
        raise Exception(f"Missing newsletters indexes, found: {newsletters_indexes}")
    print(f"  ✓ newsletters has {len(newsletters_indexes)} indexes")

    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='urls' AND (name LIKE '%relevance%' OR name LIKE '%scored%' OR name LIKE '%scoring%');")
    urls_indexes = [row[0] for row in cursor.fetchall()]
    if len(urls_indexes) < 3:
        raise Exception(f"Missing urls scoring indexes, found: {urls_indexes}")
    print(f"  ✓ urls has {len(urls_indexes)} scoring indexes")

    print("\n✓ Migration verification successful")


def main():
    print("=" * 60)
    print("Migration: v3.0 → v3.1")
    print("=" * 60)

    if not DB_PATH.exists():
        print(f"✗ Database not found: {DB_PATH}")
        sys.exit(1)

    try:
        # Backup
        backup_path = backup_database(DB_PATH)

        # Connect
        conn = sqlite3.connect(DB_PATH)

        # Verify before migration
        if not verify_database(conn):
            print("\n✗ Database integrity check failed, aborting migration")
            conn.close()
            sys.exit(1)

        # Run migrations
        create_newsletters_table(conn)
        add_scoring_columns_to_urls(conn)
        cleanup_ranked_urls_table(conn)

        # Verify migration
        verify_migration(conn)

        # Final integrity check
        if not verify_database(conn):
            print("\n✗ Post-migration integrity check failed")
            conn.close()
            sys.exit(1)

        conn.close()

        print("\n" + "=" * 60)
        print("✓ Migration completed successfully")
        print("=" * 60)
        print(f"\nBackup saved at: {backup_path}")
        print("\nNext steps:")
        print("  1. Update common/db.py with new methods")
        print("  2. Update stages/03_ranker.py for incremental mode")
        print("  3. Update stages/05_generate_newsletters.py to persist newsletters")
        print("  4. Update DATABASE.md and CLAUDE.md documentation")

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        print(f"Database backup available at: {backup_path}")
        print("To restore: cp {backup_path} {DB_PATH}")
        sys.exit(1)


if __name__ == "__main__":
    main()
