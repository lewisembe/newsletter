#!/usr/bin/env python3
"""
Migration script to normalize keywords in POC database.

Changes:
1. Creates new 'keywords' table with unique keyword entities
2. Modifies 'url_keywords' to use keyword_id instead of keyword TEXT
3. Migrates existing data preserving all relationships
4. Creates appropriate indexes and foreign keys

Author: Luis Martinez
Date: 2025-11-24
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

DB_PATH = Path(__file__).parent / "data" / "poc_news.db"


def create_backup():
    """Create timestamped backup of database."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH.parent / f"poc_news_backup_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)
    print(f"✅ Backup created: {backup_path}")
    return backup_path


def migrate_to_normalized_keywords():
    """Main migration function."""

    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        sys.exit(1)

    # Create backup first
    backup_path = create_backup()

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        print("\n🔄 Starting migration to normalized keywords schema...")

        # ===================================================================
        # STEP 1: Create keywords table
        # ===================================================================
        print("\n[1/8] Creating 'keywords' table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL UNIQUE,
                category TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                CONSTRAINT check_keyword_not_empty CHECK (length(trim(keyword)) > 0)
            )
        ''')
        print("    ✅ Table 'keywords' created")

        # ===================================================================
        # STEP 2: Extract unique keywords from url_keywords
        # ===================================================================
        print("\n[2/8] Extracting unique keywords from url_keywords...")
        cursor.execute('SELECT DISTINCT keyword FROM url_keywords ORDER BY keyword')
        unique_keywords = cursor.fetchall()
        print(f"    Found {len(unique_keywords)} unique keywords")

        # ===================================================================
        # STEP 3: Insert keywords into keywords table
        # ===================================================================
        print("\n[3/8] Populating 'keywords' table...")
        for (keyword_text,) in unique_keywords:
            # Get the earliest found_at timestamp for this keyword
            cursor.execute(
                'SELECT MIN(found_at) FROM url_keywords WHERE keyword = ?',
                (keyword_text,)
            )
            earliest_date = cursor.fetchone()[0]

            cursor.execute('''
                INSERT OR IGNORE INTO keywords (keyword, created_at, last_used_at)
                VALUES (?, ?, ?)
            ''', (keyword_text, earliest_date, earliest_date))

        rows_inserted = cursor.execute('SELECT COUNT(*) FROM keywords').fetchone()[0]
        print(f"    ✅ Inserted {rows_inserted} keywords")

        # ===================================================================
        # STEP 4: Create indexes on keywords table
        # ===================================================================
        print("\n[4/8] Creating indexes on 'keywords' table...")
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_keywords_keyword ON keywords(keyword)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_keywords_active ON keywords(is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_keywords_category ON keywords(category)')
        print("    ✅ Indexes created")

        # ===================================================================
        # STEP 5: Create new url_keywords table with normalized schema
        # ===================================================================
        print("\n[5/8] Creating normalized 'url_keywords_new' table...")
        cursor.execute('''
            CREATE TABLE url_keywords_new (
                url_id INTEGER NOT NULL,
                keyword_id INTEGER NOT NULL,
                found_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (url_id, keyword_id),
                FOREIGN KEY (url_id) REFERENCES urls(id) ON DELETE CASCADE,
                FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
            )
        ''')
        print("    ✅ Table 'url_keywords_new' created")

        # ===================================================================
        # STEP 6: Migrate data from old to new url_keywords
        # ===================================================================
        print("\n[6/8] Migrating data to normalized schema...")
        cursor.execute('''
            INSERT INTO url_keywords_new (url_id, keyword_id, found_at)
            SELECT uk.url_id, k.id, uk.found_at
            FROM url_keywords uk
            INNER JOIN keywords k ON uk.keyword = k.keyword
        ''')
        rows_migrated = cursor.rowcount
        print(f"    ✅ Migrated {rows_migrated} url-keyword relationships")

        # ===================================================================
        # STEP 7: Replace old table with new table
        # ===================================================================
        print("\n[7/8] Replacing old url_keywords table...")
        cursor.execute('DROP TABLE url_keywords')
        cursor.execute('ALTER TABLE url_keywords_new RENAME TO url_keywords')
        print("    ✅ Table replaced")

        # ===================================================================
        # STEP 8: Create indexes on new url_keywords table
        # ===================================================================
        print("\n[8/8] Creating indexes on normalized 'url_keywords' table...")
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_url_keywords_url_id ON url_keywords(url_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_url_keywords_keyword_id ON url_keywords(keyword_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_url_keywords_found_at ON url_keywords(found_at)')
        print("    ✅ Indexes created")

        # ===================================================================
        # VALIDATION
        # ===================================================================
        print("\n🔍 Validating migration...")

        # Check row counts
        keywords_count = cursor.execute('SELECT COUNT(*) FROM keywords').fetchone()[0]
        url_keywords_count = cursor.execute('SELECT COUNT(*) FROM url_keywords').fetchone()[0]

        print(f"    - Keywords table: {keywords_count} rows")
        print(f"    - url_keywords table: {url_keywords_count} rows")

        # Verify foreign keys
        cursor.execute('''
            SELECT COUNT(*) FROM url_keywords uk
            LEFT JOIN keywords k ON uk.keyword_id = k.id
            WHERE k.id IS NULL
        ''')
        orphaned_keywords = cursor.fetchone()[0]

        cursor.execute('''
            SELECT COUNT(*) FROM url_keywords uk
            LEFT JOIN urls u ON uk.url_id = u.id
            WHERE u.id IS NULL
        ''')
        orphaned_urls = cursor.fetchone()[0]

        if orphaned_keywords > 0 or orphaned_urls > 0:
            raise Exception(f"Validation failed: {orphaned_keywords} orphaned keywords, {orphaned_urls} orphaned urls")

        print("    ✅ All foreign keys valid")

        # Commit changes
        conn.commit()
        print("\n✅ Migration completed successfully!")
        print(f"\n📊 Summary:")
        print(f"    - Unique keywords: {keywords_count}")
        print(f"    - URL-keyword relationships: {url_keywords_count}")
        print(f"    - Backup saved at: {backup_path}")

        # Show sample data
        print("\n📋 Sample keywords:")
        cursor.execute('''
            SELECT k.id, k.keyword, COUNT(uk.url_id) as url_count
            FROM keywords k
            LEFT JOIN url_keywords uk ON k.id = uk.keyword_id
            GROUP BY k.id
            ORDER BY url_count DESC
            LIMIT 5
        ''')
        for kid, kw, count in cursor.fetchall():
            print(f"    [{kid}] {kw}: {count} URLs")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print(f"Database restored from backup: {backup_path}")
        # Restore from backup
        shutil.copy2(backup_path, DB_PATH)
        sys.exit(1)

    finally:
        if conn:
            conn.close()


def show_schema_diff():
    """Show before/after schema comparison."""
    print("\n" + "="*70)
    print("SCHEMA CHANGES")
    print("="*70)

    print("\n❌ OLD SCHEMA:")
    print("""
    url_keywords (
        url_id INTEGER,
        keyword TEXT,              ← String repeated for each URL
        found_at TIMESTAMP,
        PRIMARY KEY (url_id, keyword)
    )
    """)

    print("\n✅ NEW SCHEMA:")
    print("""
    keywords (
        id INTEGER PRIMARY KEY,
        keyword TEXT UNIQUE,       ← Keyword stored once
        category TEXT,
        is_active BOOLEAN,
        created_at TIMESTAMP,
        last_used_at TIMESTAMP
    )

    url_keywords (
        url_id INTEGER,
        keyword_id INTEGER,        ← Foreign key to keywords
        found_at TIMESTAMP,
        PRIMARY KEY (url_id, keyword_id),
        FOREIGN KEY (url_id) REFERENCES urls(id),
        FOREIGN KEY (keyword_id) REFERENCES keywords(id)
    )
    """)
    print("="*70 + "\n")


if __name__ == '__main__':
    print("="*70)
    print("POC KEYWORD SEARCH - DATABASE NORMALIZATION MIGRATION")
    print("="*70)

    show_schema_diff()

    response = input("Proceed with migration? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Migration cancelled.")
        sys.exit(0)

    migrate_to_normalized_keywords()
