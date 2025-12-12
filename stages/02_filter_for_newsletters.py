#!/usr/bin/env python3
"""
Stage 02: Filter URLs for Newsletter Generation

This script performs thematic categorization and temporality classification
on content URLs extracted in Stage 01, preparing them for newsletter generation.

Process:
1. Query database for content URLs within specified date/time range
2. Filter by specified sources (optional)
3. Classify URLs into thematic categories using LLM
4. Classify content temporality (temporal vs atemporal) using LLM
5. Update database with classifications
6. Return list of classified URL IDs ready for Stage 03

Author: Newsletter Utils Team
Created: 2025-11-12
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any
import yaml
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from common.postgres_db import PostgreSQLURLDatabase
from common.llm import (
    LLMClient,
    classify_thematic_categories_batch,
    classify_content_temporality_batch
)
from common.logging_utils import setup_rotating_file_logger

# Load environment variables
load_dotenv()
MODEL_CLASSIFIER = os.getenv('MODEL_CLASSIFIER', 'gpt-4o-mini')
BATCH_SIZE = int(os.getenv('STAGE02_BATCH_SIZE', '30'))

# Setup logging
logger = logging.getLogger(__name__)


def setup_logging(run_date: str) -> str:
    """
    Setup logging for Stage 02.

    Args:
        run_date: Date string in YYYY-MM-DD format

    Returns:
        Path to log file
    """
    log_file = setup_rotating_file_logger(
        run_date,
        "02_filter_for_newsletters.log",
        log_level=logging.INFO,
        verbose=False,
    )

    logger.info(f"Stage 02 logging initialized: {log_file}")
    return str(log_file)


def load_categories(db: PostgreSQLURLDatabase) -> List[Dict[str, Any]]:
    """
    Load thematic categories from PostgreSQL database.

    Args:
        db: PostgreSQLURLDatabase instance

    Returns:
        List of category dictionaries with id, name, description, examples
    """
    try:
        categories = db.get_all_categories()

        if not categories:
            raise ValueError("No categories found in database")

        logger.info(f"Loaded {len(categories)} categories from database")
        return categories

    except Exception as e:
        logger.error(f"Failed to load categories from database: {e}")
        raise


def load_sources() -> List[Dict[str, Any]]:
    """
    Load sources from config file.

    Returns:
        List of source dictionaries
    """
    sources_file = project_root / "config" / "sources.yml"

    try:
        with open(sources_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        sources = config.get('sources', [])

        if not sources:
            raise ValueError("No sources found in configuration")

        logger.info(f"Loaded {len(sources)} sources from {sources_file}")
        return sources

    except Exception as e:
        logger.error(f"Failed to load sources from {sources_file}: {e}")
        raise


def parse_datetime(dt_string: str) -> datetime:
    """
    Parse datetime string in multiple formats.

    Supports:
    - ISO format: 2025-11-10T08:00:00
    - Date only: 2025-11-10 (assumes 00:00:00)

    Args:
        dt_string: Datetime string

    Returns:
        datetime object in UTC
    """
    try:
        # Try ISO format first
        if 'T' in dt_string:
            dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        else:
            # Date only, assume 00:00:00
            dt = datetime.fromisoformat(dt_string + 'T00:00:00')

        # Ensure UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    except Exception as e:
        raise ValueError(f"Invalid datetime format '{dt_string}': {e}")


def filter_and_classify(
    db: PostgreSQLURLDatabase,
    start_datetime: str,
    end_datetime: str,
    source_ids: Optional[List[str]] = None,
    target_categories: Optional[List[str]] = None,
    classify_temporality: bool = True,
    llm_client: Optional[LLMClient] = None,
    run_date: Optional[str] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Filter and classify URLs for newsletter generation.

    Args:
        db: Database instance
        start_datetime: Start datetime (ISO format)
        end_datetime: End datetime (ISO format)
        source_ids: Optional list of source IDs to filter by
        target_categories: Optional list of categories to keep (filtering happens AFTER classification)
        classify_temporality: Whether to classify temporality
        llm_client: LLM client instance
        run_date: Run date for logging
        force: If True, reclassify even URLs that already have categoria_tematica

    Returns:
        Dictionary with statistics and results
    """
    logger.info(f"Starting Stage 02: Filter and classify URLs")
    logger.info(f"Time range: {start_datetime} to {end_datetime}")
    logger.info(f"Force reclassification: {force}")
    if source_ids:
        logger.info(f"Source filter: {', '.join(source_ids)}")
    if target_categories:
        logger.info(f"Target categories (post-classification filter): {', '.join(target_categories)}")

    # Convert source IDs to URLs
    source_urls = None
    if source_ids:
        # Handle "all" keyword - means no filter (all sources)
        if source_ids == ["all"] or "all" in source_ids:
            logger.info("Source filter: 'all' - using all available sources")
            source_urls = None  # None means no filter
        else:
            all_sources = load_sources()
            source_map = {s['id']: s['url'] for s in all_sources}
            source_urls = [source_map[sid] for sid in source_ids if sid in source_map]

            if len(source_urls) != len(source_ids):
                missing = set(source_ids) - set(source_map.keys())
                logger.warning(f"Some source IDs not found in config: {missing}")

    # Query database for content URLs (NO category filter yet)
    # If force=False, only get URLs without categoria_tematica (idempotency)
    urls = db.get_urls_for_newsletter(
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        sources=source_urls,
        categories=None,  # Don't filter by category yet
        only_uncategorized=(not force)  # Only uncategorized if not forcing
    )

    if force:
        logger.info(f"Retrieved {len(urls)} content URLs from database (including already categorized)")
    else:
        logger.info(f"Retrieved {len(urls)} uncategorized content URLs from database (idempotent mode)")

    if not urls:
        logger.warning("No URLs found matching criteria")
        return {
            'total_urls': 0,
            'classified_urls': 0,
            'filtered_urls': 0,
            'categories_breakdown': {},
            'temporality_breakdown': {},
            'url_ids': []
        }

    # Load available categories from database
    all_categories = load_categories(db)

    # Initialize LLM client if not provided
    if llm_client is None:
        llm_client = LLMClient()

    # Prepare URLs for classification (convert to list of dicts with id, url, title)
    urls_for_classification = []
    for url_data in urls:
        urls_for_classification.append({
            'id': url_data['id'],
            'url': url_data['url'],
            'title': url_data.get('title', '')
        })

    # Step 1: Classify thematic categories
    logger.info(f"Classifying {len(urls_for_classification)} URLs into thematic categories...")
    classified_urls = classify_thematic_categories_batch(
        urls=urls_for_classification,
        categories=all_categories,
        llm_client=llm_client,
        model=MODEL_CLASSIFIER,
        stage="02",
        run_date=run_date,
        batch_size=BATCH_SIZE
    )

    # Step 2: Classify temporality (if enabled)
    temporality_breakdown = {}
    if classify_temporality:
        logger.info(f"Classifying temporality for {len(classified_urls)} URLs...")
        classified_urls = classify_content_temporality_batch(
            urls=classified_urls,
            llm_client=llm_client,
            model=MODEL_CLASSIFIER,
            stage="02",
            run_date=run_date,
            batch_size=BATCH_SIZE
        )

        # Count temporality breakdown
        for url_data in classified_urls:
            temp = url_data.get('content_subtype', 'unknown')
            temporality_breakdown[temp] = temporality_breakdown.get(temp, 0) + 1

    # Step 3: Update database with classifications
    logger.info("Updating database with classifications...")
    updates = []
    for url_data in classified_urls:
        update = {
            'id': url_data['id'],
            'categoria_tematica': url_data['categoria_tematica']
        }
        if classify_temporality and 'content_subtype' in url_data:
            update['content_subtype'] = url_data['content_subtype']
        updates.append(update)

    update_stats = db.batch_update_categorization(updates)
    logger.info(f"Database update complete: {update_stats['updated']} updated, {update_stats['errors']} errors")

    # Step 4: Filter by target categories (if specified)
    if target_categories:
        # Convert category names to IDs for filtering
        # target_categories might contain names like "Economía" but DB stores IDs like "economia"
        category_name_to_id = {cat['name']: cat['id'] for cat in all_categories}
        target_category_ids = []
        for cat in target_categories:
            if cat in category_name_to_id:
                target_category_ids.append(category_name_to_id[cat])
            else:
                # Assume it's already an ID
                target_category_ids.append(cat)

        logger.info(f"Filtering URLs by target categories: {target_categories} (IDs: {target_category_ids})")
        filtered_urls = [
            url_data for url_data in classified_urls
            if url_data['categoria_tematica'] in target_category_ids
        ]
        logger.info(f"Filtered to {len(filtered_urls)} URLs matching target categories")
    else:
        filtered_urls = classified_urls

    # Count categories breakdown
    categories_breakdown = {}
    for url_data in classified_urls:
        cat = url_data.get('categoria_tematica', 'unknown')
        categories_breakdown[cat] = categories_breakdown.get(cat, 0) + 1

    # Extract URL IDs for output
    url_ids = [url_data['id'] for url_data in filtered_urls]

    results = {
        'total_urls': len(urls),
        'classified_urls': len(classified_urls),
        'filtered_urls': len(filtered_urls),
        'categories_breakdown': categories_breakdown,
        'temporality_breakdown': temporality_breakdown,
        'url_ids': url_ids
    }

    logger.info(f"Stage 02 complete: {results['filtered_urls']} URLs ready for Stage 03")
    logger.info(f"Categories breakdown: {', '.join(f'{k}={v}' for k, v in sorted(categories_breakdown.items()))}")
    if temporality_breakdown:
        logger.info(f"Temporality breakdown: {', '.join(f'{k}={v}' for k, v in sorted(temporality_breakdown.items()))}")

    return results


def main():
    """Main entry point for Stage 02."""
    parser = argparse.ArgumentParser(
        description='Stage 02: Filter and classify URLs for newsletter generation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Classify all content URLs from today (00:00 to 23:59)
  %(prog)s --date 2025-11-10

  # Classify URLs from specific time range
  %(prog)s --start "2025-11-10T08:00:00" --end "2025-11-10T20:00:00"

  # Filter by specific sources
  %(prog)s --date 2025-11-10 --sources ft bbc elconfidencial

  # Filter by target categories (applied AFTER classification)
  %(prog)s --date 2025-11-10 --categories politica economia tecnologia

  # Skip temporality classification (faster)
  %(prog)s --date 2025-11-10 --no-temporality

  # Custom database path
  %(prog)s --date 2025-11-10 --db data/custom.db
        """
    )

    # Date/time arguments
    parser.add_argument(
        '--date',
        type=str,
        help='Date to process (YYYY-MM-DD). Uses 00:00:00 to 23:59:59 if --start/--end not provided.'
    )
    parser.add_argument(
        '--start',
        type=str,
        help='Start datetime (ISO format: YYYY-MM-DDTHH:MM:SS). Required if --date not provided.'
    )
    parser.add_argument(
        '--end',
        type=str,
        help='End datetime (ISO format: YYYY-MM-DDTHH:MM:SS). Required if --date not provided.'
    )

    # Filtering arguments
    parser.add_argument(
        '--sources',
        nargs='+',
        help='Source IDs to filter by (space-separated). Example: ft bbc elconfidencial'
    )
    parser.add_argument(
        '--categories',
        nargs='+',
        help='Target categories to keep (space-separated). Filtering happens AFTER classification. '
             'Example: politica economia tecnologia'
    )

    # Classification options
    parser.add_argument(
        '--no-temporality',
        action='store_true',
        help='Skip temporality classification (faster, only classify thematic categories)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force reclassification of URLs that already have categoria_tematica'
    )

    # Database options
    parser.add_argument(
        '--db',
        type=str,
        default=os.getenv('DATABASE_URL'),
        help='PostgreSQL connection string (default: from DATABASE_URL env var)'
    )

    # Output options
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Validate date/time arguments
    if args.date:
        # Use date with full day range
        start_datetime = args.date + 'T00:00:00'
        end_datetime = args.date + 'T23:59:59'
        run_date = args.date
    elif args.start and args.end:
        # Use explicit start/end
        start_datetime = args.start
        end_datetime = args.end
        # Extract date from start for logging
        run_date = args.start.split('T')[0]
    else:
        parser.error("Either --date or both --start and --end must be provided")

    # Validate datetime formats
    try:
        parse_datetime(start_datetime)
        parse_datetime(end_datetime)
    except ValueError as e:
        parser.error(str(e))

    # Setup logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    log_file = setup_logging(run_date)

    logger.info("="*80)
    logger.info("STAGE 02: FILTER FOR NEWSLETTERS")
    logger.info("="*80)
    logger.info(f"Start datetime: {start_datetime}")
    logger.info(f"End datetime: {end_datetime}")
    logger.info(f"Database: {args.db}")
    logger.info(f"Classify temporality: {not args.no_temporality}")
    logger.info(f"Force reclassification: {args.force}")
    logger.info(f"Log file: {log_file}")

    try:
        # Initialize database (PostgreSQL)
        db = PostgreSQLURLDatabase(args.db)

        # Initialize LLM client
        llm_client = LLMClient()

        # Run filtering and classification
        results = filter_and_classify(
            db=db,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            source_ids=args.sources,
            target_categories=args.categories,
            classify_temporality=not args.no_temporality,
            llm_client=llm_client,
            run_date=run_date,
            force=args.force
        )

        # Print summary
        logger.info("="*80)
        logger.info("STAGE 02 SUMMARY")
        logger.info("="*80)
        logger.info(f"Total content URLs retrieved: {results['total_urls']}")
        logger.info(f"URLs classified: {results['classified_urls']}")
        logger.info(f"URLs after category filter: {results['filtered_urls']}")
        logger.info("")
        logger.info("Categories breakdown:")
        for cat, count in sorted(results['categories_breakdown'].items()):
            logger.info(f"  {cat}: {count}")

        if results['temporality_breakdown']:
            logger.info("")
            logger.info("Temporality breakdown:")
            for temp, count in sorted(results['temporality_breakdown'].items()):
                logger.info(f"  {temp}: {count}")

        logger.info("")
        logger.info(f"Ready for Stage 03: {len(results['url_ids'])} URL IDs")
        logger.info("="*80)

        return 0

    except Exception as e:
        logger.error(f"Stage 02 failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
