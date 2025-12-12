#!/usr/bin/env python3
"""
Migration script to clean HTML tags from titles in the database.

Some news sources (like Le Monde) have HTML tags embedded as plain text in titles.
This script sanitizes all existing titles by removing HTML tags.

Usage:
    python scripts/clean_html_from_titles.py [--dry-run]
"""

import os
import re
import sys
import sqlite3
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_PATH = os.getenv('DB_PATH', 'data/news.db')


def clean_html_tags(text: str) -> str:
    """
    Remove HTML tags from text string.

    Args:
        text: Original text with potential HTML tags

    Returns:
        Cleaned text without HTML tags
    """
    if not text:
        return text

    # Remove HTML tags
    cleaned = re.sub(r'<[^>]+>', '', text)

    # Clean up extra whitespace
    cleaned = ' '.join(cleaned.split())

    return cleaned.strip()


def main():
    parser = argparse.ArgumentParser(
        description='Clean HTML tags from titles in database'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without actually updating'
    )
    args = parser.parse_args()

    print("=" * 80)
    print("CLEANING HTML TAGS FROM TITLES")
    print("=" * 80)
    print(f"Database: {DB_PATH}")
    print(f"Mode: {'DRY RUN (no changes)' if args.dry_run else 'LIVE (will update DB)'}")
    print()

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Find all URLs with HTML tags in titles
    cursor.execute("SELECT id, url, title FROM urls WHERE title LIKE '%<%'")
    rows = cursor.fetchall()

    if not rows:
        print("✓ No titles with HTML tags found. Database is clean!")
        return 0

    print(f"Found {len(rows)} titles with HTML tags")
    print()

    # Process each title
    updated_count = 0
    for row in rows:
        url_id, url, old_title = row
        new_title = clean_html_tags(old_title)

        if old_title != new_title:
            print(f"ID: {url_id}")
            print(f"URL: {url}")
            print(f"OLD: {old_title[:150]}")
            print(f"NEW: {new_title[:150]}")
            print()

            if not args.dry_run:
                cursor.execute(
                    "UPDATE urls SET title = ? WHERE id = ?",
                    (new_title, url_id)
                )
                updated_count += 1

    if not args.dry_run:
        conn.commit()

    conn.close()

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Titles with HTML tags: {len(rows)}")
    if args.dry_run:
        print(f"Would update: {len(rows)} titles")
        print()
        print("Run without --dry-run to apply changes")
    else:
        print(f"Updated: {updated_count} titles")
        print("✓ Database updated successfully")

    return 0


if __name__ == '__main__':
    sys.exit(main())
