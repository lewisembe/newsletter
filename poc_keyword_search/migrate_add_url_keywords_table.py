#!/usr/bin/env python3
"""
Migration: Add url_keywords table for N:N relationship.

This allows a single URL to be associated with multiple keywords,
solving the problem of URLs that appear in multiple keyword searches.
"""

import sqlite3
import sys
from pathlib import Path

def migrate_add_url_keywords_table():
    """Add url_keywords table and migrate existing data."""

    poc_dir = Path(__file__).parent
    db_path = poc_dir / "data" / "poc_news.db"

    if not db_path.exists():
        print(f"✗ POC database not found: {db_path}")
        print("  Run: python poc_keyword_search/init_poc_db.py")
        return False

    print(f"Migrating POC database: {db_path}")

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='url_keywords'
        """)
        if cursor.fetchone():
            print("✓ Table 'url_keywords' already exists.")
            return True

        print("\n1. Creating url_keywords table...")
        cursor.execute("""
            CREATE TABLE url_keywords (
                url_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                found_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (url_id, keyword),
                FOREIGN KEY (url_id) REFERENCES urls(id) ON DELETE CASCADE
            )
        """)

        print("✓ Table created successfully!")

        # Create index for faster queries
        print("\n2. Creating indices...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_url_keywords_url_id
            ON url_keywords(url_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_url_keywords_keyword
            ON url_keywords(keyword)
        """)
        print("✓ Indices created!")

        # Migrate existing data from search_keyword column
        print("\n3. Migrating existing data from urls.search_keyword...")
        cursor.execute("""
            SELECT id, search_keyword
            FROM urls
            WHERE search_keyword IS NOT NULL
        """)
        existing_data = cursor.fetchall()

        migrated = 0
        for url_id, keyword in existing_data:
            if keyword:
                cursor.execute("""
                    INSERT OR IGNORE INTO url_keywords (url_id, keyword)
                    VALUES (?, ?)
                """, (url_id, keyword))
                migrated += 1

        print(f"✓ Migrated {migrated} existing keyword associations!")

        conn.commit()

        # Verify
        cursor.execute("SELECT COUNT(*) FROM url_keywords")
        total = cursor.fetchone()[0]

        print(f"\n{'='*60}")
        print("✓ Migration completed successfully!")
        print(f"{'='*60}")
        print(f"Total keyword associations: {total}")
        print(f"\nNow URLs can have multiple keywords:")
        print(f"  - Same URL found by 'inflación España' → saved")
        print(f"  - Same URL found by 'BCE tipos' → added as 2nd keyword")
        print(f"\nQuery examples:")
        print(f"  # Get all keywords for a URL:")
        print(f"  SELECT keyword FROM url_keywords WHERE url_id = 1;")
        print(f"  ")
        print(f"  # Get all URLs for a keyword:")
        print(f"  SELECT u.url, u.title FROM urls u")
        print(f"  JOIN url_keywords uk ON u.id = uk.url_id")
        print(f"  WHERE uk.keyword = 'inflación España';")
        print(f"{'='*60}")

        return True

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = migrate_add_url_keywords_table()
    sys.exit(0 if success else 1)
