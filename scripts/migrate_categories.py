#!/usr/bin/env python3
"""
Category Migration Script

Migrates URLs from old 19-category system to new 7-category consolidated system.

Usage:
    python scripts/migrate_categories.py [--dry-run] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]

Arguments:
    --dry-run: Show what would be migrated without actually updating the database
    --start-date: Only migrate URLs extracted after this date (inclusive)
    --end-date: Only migrate URLs extracted before this date (inclusive)
    --verbose: Enable verbose logging

Examples:
    # Migrate all URLs (dry run first to see changes)
    python scripts/migrate_categories.py --dry-run

    # Actually perform migration
    python scripts/migrate_categories.py

    # Migrate only URLs from a specific date range
    python scripts/migrate_categories.py --start-date 2025-11-10 --end-date 2025-11-12

Author: Newsletter Utils Team
Created: 2025-11-12
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import yaml
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from common.postgres_db import PostgreSQLURLDatabase

# Load environment variables
load_dotenv()

# Configuration
DB_PATH = os.getenv('DB_PATH', 'data/news.db')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Category mapping: old -> new
CATEGORY_MAPPING = {
    # politica consolidates: politica, nacional, justicia, educacion
    'politica': 'politica',
    'nacional': 'politica',
    'justicia': 'politica',
    'educacion': 'politica',

    # economia consolidates: economia, empresas, mercados, energia
    'economia': 'economia',
    'empresas': 'economia',
    'mercados': 'economia',
    'energia': 'economia',

    # tecnologia consolidates: tecnologia, ciencia, salud, medioambiente
    'tecnologia': 'tecnologia',
    'ciencia': 'tecnologia',
    'salud': 'tecnologia',
    'medioambiente': 'tecnologia',

    # geopolitica consolidates: internacional
    'internacional': 'geopolitica',
    'geopolitica': 'geopolitica',

    # sociedad consolidates: sociedad, cultura, entretenimiento, opinion
    'sociedad': 'sociedad',
    'cultura': 'sociedad',
    'entretenimiento': 'sociedad',
    'opinion': 'sociedad',

    # deportes stays the same
    'deportes': 'deportes',

    # otros is new (for anything unmapped)
    'otros': 'otros',
}


def load_new_categories() -> List[str]:
    """
    Load new category IDs from config file.

    Returns:
        List of new category IDs
    """
    categories_file = project_root / "config" / "categories.yml"

    try:
        with open(categories_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        categories = config.get('categories', [])
        category_ids = [cat['id'] for cat in categories]

        logger.info(f"Loaded {len(category_ids)} new categories: {', '.join(category_ids)}")
        return category_ids

    except Exception as e:
        logger.error(f"Failed to load categories from {categories_file}: {e}")
        raise


def migrate_categories(
    db_path: str,
    dry_run: bool = True,
    start_date: str = None,
    end_date: str = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Migrate URL categories from old to new system.

    Args:
        db_path: Path to SQLite database
        dry_run: If True, don't actually update database
        start_date: Only migrate URLs extracted after this date (YYYY-MM-DD)
        end_date: Only migrate URLs extracted before this date (YYYY-MM-DD)
        verbose: Enable verbose logging

    Returns:
        Dictionary with migration statistics
    """
    if verbose:
        logger.setLevel(logging.DEBUG)

    # Load new categories to validate
    new_categories = load_new_categories()

    # Connect to database
    db = PostgreSQLURLDatabase(db_path)

    # Build query
    query = "SELECT id, url, title, categoria_tematica FROM urls WHERE categoria_tematica IS NOT NULL"
    params = []

    if start_date:
        query += " AND extracted_at >= ?"
        params.append(f"{start_date} 00:00:00")

    if end_date:
        query += " AND extracted_at <= ?"
        params.append(f"{end_date} 23:59:59")

    query += " ORDER BY extracted_at DESC"

    # Get URLs to migrate
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        urls = cursor.fetchall()

    if not urls:
        logger.info("No URLs found to migrate")
        return {
            'total_urls': 0,
            'migrated': 0,
            'unchanged': 0,
            'unmapped': 0,
            'by_old_category': {},
            'by_new_category': {}
        }

    logger.info(f"Found {len(urls)} URLs to analyze")

    # Statistics
    stats = {
        'total_urls': len(urls),
        'migrated': 0,
        'unchanged': 0,
        'unmapped': 0,
        'by_old_category': {},
        'by_new_category': {}
    }

    # Process each URL
    updates = []
    for row in urls:
        url_id, url, title, old_category = row

        if not old_category:
            continue

        # Count old category
        stats['by_old_category'][old_category] = stats['by_old_category'].get(old_category, 0) + 1

        # Map to new category
        new_category = CATEGORY_MAPPING.get(old_category, 'otros')

        # Validate new category exists
        if new_category not in new_categories:
            logger.warning(f"Mapped category '{new_category}' not in new categories list, using 'otros'")
            new_category = 'otros'

        # Count new category
        stats['by_new_category'][new_category] = stats['by_new_category'].get(new_category, 0) + 1

        if old_category == new_category:
            stats['unchanged'] += 1
            if verbose:
                logger.debug(f"  UNCHANGED: {url_id} | {old_category} -> {new_category} | {title[:50]}...")
        elif old_category not in CATEGORY_MAPPING:
            stats['unmapped'] += 1
            logger.warning(f"  UNMAPPED: {url_id} | {old_category} -> {new_category} (fallback) | {title[:50]}...")
            updates.append((new_category, url_id))
        else:
            stats['migrated'] += 1
            if verbose:
                logger.debug(f"  MIGRATE: {url_id} | {old_category} -> {new_category} | {title[:50]}...")
            updates.append((new_category, url_id))

    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("MIGRATION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total URLs analyzed: {stats['total_urls']}")
    logger.info(f"  - To be migrated: {stats['migrated']}")
    logger.info(f"  - Unchanged: {stats['unchanged']}")
    logger.info(f"  - Unmapped (fallback to 'otros'): {stats['unmapped']}")

    logger.info("\nOld category breakdown:")
    for cat, count in sorted(stats['by_old_category'].items(), key=lambda x: x[1], reverse=True):
        new_cat = CATEGORY_MAPPING.get(cat, 'otros')
        arrow = " -> " + new_cat if cat != new_cat else " (unchanged)"
        logger.info(f"  {cat:20s} {count:5d} URLs{arrow}")

    logger.info("\nNew category breakdown:")
    for cat, count in sorted(stats['by_new_category'].items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {cat:20s} {count:5d} URLs")

    # Perform updates
    if not dry_run and updates:
        logger.info("\n" + "=" * 80)
        logger.info(f"Updating {len(updates)} URLs in database...")
        logger.info("=" * 80)

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            try:
                cursor.executemany(
                    "UPDATE urls SET categoria_tematica = ?, categorized_at = CURRENT_TIMESTAMP WHERE id = ?",
                    updates
                )
                conn.commit()
                logger.info(f"✓ Successfully updated {len(updates)} URLs")
            except Exception as e:
                conn.rollback()
                logger.error(f"✗ Failed to update database: {e}")
                raise
    elif dry_run:
        logger.info("\n" + "=" * 80)
        logger.info("DRY RUN - No changes made to database")
        logger.info("=" * 80)
        logger.info("Run without --dry-run to apply changes")

    return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Migrate URL categories from 19-category to 7-category system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would change
  python scripts/migrate_categories.py --dry-run

  # Actually perform migration
  python scripts/migrate_categories.py

  # Migrate specific date range
  python scripts/migrate_categories.py --start-date 2025-11-10 --end-date 2025-11-12

  # Verbose output
  python scripts/migrate_categories.py --dry-run --verbose
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without updating database'
    )

    parser.add_argument(
        '--start-date',
        type=str,
        help='Only migrate URLs extracted after this date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        help='Only migrate URLs extracted before this date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging (shows each URL migration)'
    )

    parser.add_argument(
        '--db-path',
        type=str,
        default=DB_PATH,
        help=f'Path to SQLite database (default: {DB_PATH})'
    )

    args = parser.parse_args()

    # Validate date formats
    for date_arg, date_val in [('start-date', args.start_date), ('end-date', args.end_date)]:
        if date_val:
            try:
                datetime.strptime(date_val, '%Y-%m-%d')
            except ValueError:
                logger.error(f"Invalid --{date_arg} format: {date_val}. Expected YYYY-MM-DD")
                sys.exit(1)

    logger.info("Category Migration Script")
    logger.info("=" * 80)
    logger.info(f"Database: {args.db_path}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE UPDATE'}")
    if args.start_date:
        logger.info(f"Start date: {args.start_date}")
    if args.end_date:
        logger.info(f"End date: {args.end_date}")
    logger.info("=" * 80 + "\n")

    try:
        stats = migrate_categories(
            db_path=args.db_path,
            dry_run=args.dry_run,
            start_date=args.start_date,
            end_date=args.end_date,
            verbose=args.verbose
        )

        logger.info("\nMigration completed successfully")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
