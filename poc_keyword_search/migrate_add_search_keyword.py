#!/usr/bin/env python3
"""
Migration script to add search_keyword column to urls table.

This column allows differentiation between:
- URLs from Stage 01 (sources): search_keyword=NULL
- URLs from POC (keyword search): search_keyword='inflación España'
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import common modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.postgres_db import PostgreSQLURLDatabase

def migrate_add_search_keyword():
    """Add search_keyword column to urls table if it doesn't exist."""

    db = PostgreSQLURLDatabase()

    try:
        # Check if column already exists
        cursor = db.conn.cursor()
        cursor.execute("PRAGMA table_info(urls)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'search_keyword' in columns:
            print("✓ Column 'search_keyword' already exists in urls table.")
            return True

        # Add column
        print("Adding 'search_keyword' column to urls table...")
        cursor.execute("""
            ALTER TABLE urls
            ADD COLUMN search_keyword TEXT
        """)

        db.conn.commit()
        print("✓ Column 'search_keyword' added successfully!")

        # Create index for faster queries
        print("Creating index on search_keyword column...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_search_keyword
            ON urls(search_keyword)
        """)

        db.conn.commit()
        print("✓ Index created successfully!")

        # Verify
        cursor.execute("PRAGMA table_info(urls)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'search_keyword' in columns:
            print(f"\n✓ Migration completed successfully!")
            print(f"  - URLs from sources will have: search_keyword=NULL")
            print(f"  - URLs from keywords will have: search_keyword='topic name'")
            return True
        else:
            print("\n✗ Migration verification failed!")
            return False

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        db.conn.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = migrate_add_search_keyword()
    sys.exit(0 if success else 1)
