#!/usr/bin/env python3
"""
Migration: Add google_news_url column to urls table

This migration adds a new column to store the original Google News redirect URL,
while the 'url' column contains the resolved final URL.

Usage:
    python poc_keyword_search/migrate_add_google_news_url.py
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Configuration
DB_PATH = "poc_keyword_search/data/poc_news.db"
BACKUP_SUFFIX = f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def main():
    """Run migration."""
    db_path = Path(DB_PATH)

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Run: python poc_keyword_search/init_poc_db.py")
        sys.exit(1)

    # Backup database
    backup_path = Path(str(db_path) + BACKUP_SUFFIX)
    print(f"📦 Creating backup: {backup_path}")

    import shutil
    shutil.copy2(db_path, backup_path)
    print("✅ Backup created")

    # Connect to database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Check if column already exists
        if check_column_exists(cursor, 'urls', 'google_news_url'):
            print("⚠️  Column 'google_news_url' already exists in urls table")
            print("Migration not needed")
            conn.close()
            return

        print("🔧 Adding google_news_url column to urls table...")

        # Add the new column
        cursor.execute("""
            ALTER TABLE urls
            ADD COLUMN google_news_url TEXT
        """)

        conn.commit()
        print("✅ Column added successfully")

        # Verify the migration
        cursor.execute("PRAGMA table_info(urls)")
        columns = cursor.fetchall()

        print("\n📋 Updated table schema:")
        for col in columns:
            col_id, name, type_, notnull, default, pk = col
            nullable = "NOT NULL" if notnull else "NULL"
            pk_marker = " (PRIMARY KEY)" if pk else ""
            print(f"  - {name}: {type_} {nullable}{pk_marker}")

        # Count existing URLs
        cursor.execute("SELECT COUNT(*) FROM urls")
        url_count = cursor.fetchone()[0]

        print(f"\n📊 Statistics:")
        print(f"  - Total URLs in database: {url_count}")
        print(f"  - URLs with google_news_url: 0 (existing URLs will be NULL)")

        print("\n✅ Migration completed successfully!")
        print(f"📦 Backup saved at: {backup_path}")
        print("\nℹ️  Note: Existing URLs will have google_news_url = NULL")
        print("   New URLs from Google News will have both url and google_news_url")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        print(f"\n💡 To restore from backup:")
        print(f"   mv {backup_path} {db_path}")
        sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    print("="*60)
    print("POC Migration: Add google_news_url column")
    print("="*60)
    print()

    main()
