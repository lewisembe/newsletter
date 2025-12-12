#!/usr/bin/env python3
"""
Clear all AI summaries from the database.

This script removes all cached article summaries, forcing them to be regenerated
with the new JSON structured format when Stage 05 runs again.

Usage:
    python scripts/clear_summaries.py [--db-path path/to/news.db] [--dry-run]

Author: Newsletter Utils Team
Created: 2025-11-20
"""

import sys
import argparse
import sqlite3
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from common.postgres_db import PostgreSQLURLDatabase


def clear_summaries(db_path: str, dry_run: bool = False):
    """
    Clear all AI summaries from the database.

    Args:
        db_path: Path to SQLite database
        dry_run: If True, only count summaries without deleting
    """
    db = PostgreSQLURLDatabase(db_path)

    # Count existing summaries
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM urls WHERE ai_summary IS NOT NULL")
        count = cursor.fetchone()[0]

    print(f"Found {count} articles with cached summaries")

    if count == 0:
        print("✓ No summaries to clear")
        return

    if dry_run:
        print("\n[DRY RUN] Would clear all summaries, but --dry-run flag is set")
        return

    # Confirm deletion
    confirm = input(f"\nAre you sure you want to clear {count} summaries? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Aborted.")
        return

    # Clear summaries
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE urls SET ai_summary = NULL WHERE ai_summary IS NOT NULL")
        conn.commit()

    print(f"✓ Cleared {count} summaries successfully")
    print("\nSummaries will be regenerated with JSON format when Stage 05 runs again.")


def main():
    parser = argparse.ArgumentParser(
        description="Clear all AI summaries from the database"
    )

    parser.add_argument(
        '--db-path',
        default='data/news.db',
        help='Path to SQLite database (default: data/news.db)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Count summaries without deleting'
    )

    args = parser.parse_args()

    # Verify database exists
    if not Path(args.db_path).exists():
        print(f"Error: Database not found at {args.db_path}")
        return 1

    clear_summaries(args.db_path, args.dry_run)
    return 0


if __name__ == '__main__':
    sys.exit(main())
