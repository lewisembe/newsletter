#!/usr/bin/env python3
"""
POC Stage 01: Search URLs by Keyword Topics

This is an alternative to the main Stage 01 (which scrapes from fixed sources).
Instead of scraping media websites, this script:
1. Searches Google News by keyword topics (from config.yml)
2. Extracts URLs with their REAL published dates (not extraction date!)
3. Classifies URLs as contenido/no_contenido (optional, using existing classifiers)
4. Saves to INDEPENDENT POC database (poc_keyword_search/data/poc_news.db)

Key differences from main Stage 01:
- Input: keyword topics (not sources)
- Method: Google News API (not Selenium scraping)
- Date: published_at = article's real date (not today)
- Source column: 'keyword_search' (not source URL)
- Tracking: search_keyword column stores which keyword found it

Usage:
    python poc_keyword_search/01_search_urls_by_topic.py --date 2025-11-24
    python poc_keyword_search/01_search_urls_by_topic.py --keywords "inflación España" "BCE tipos"
"""

import os
import sys
import logging
import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from dotenv import load_dotenv

from poc_keyword_search.src.google_news_searcher import GoogleNewsSearcher
from common.stage01_extraction.url_classifier import RuleBasedClassifier

# Load environment variables
load_dotenv()


def setup_logging(run_date: str) -> logging.Logger:
    """Configure logging for POC."""
    log_dir = Path("poc_keyword_search/logs") / run_date
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "01_search_urls_by_topic.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"POC Keyword Search - Logging initialized: {log_file}")

    return logger


def load_config(config_path: str = "poc_keyword_search/config.yml") -> Dict:
    """Load POC configuration."""
    logger = logging.getLogger(__name__)

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        logger.info(f"Loaded POC config from {config_path}")
        return config

    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        raise


def get_poc_database(config: Dict) -> sqlite3.Connection:
    """Get connection to POC database."""
    db_path = Path(config['database']['path'])

    if not db_path.exists():
        raise FileNotFoundError(
            f"POC database not found: {db_path}\n"
            f"Run: python poc_keyword_search/init_poc_db.py"
        )

    conn = sqlite3.connect(str(db_path))
    return conn


def classify_url(url: str, title: str, classifier: Optional[RuleBasedClassifier]) -> Dict:
    """
    Classify URL as contenido/no_contenido.

    Google News URLs are assumed to be content by default.

    Args:
        url: URL to classify
        title: Article title
        classifier: RuleBasedClassifier instance (not used anymore, kept for compatibility)

    Returns:
        Dict with classification info
    """
    # All Google News results are classified as 'contenido'
    return {
        'content_type': 'contenido',
        'content_subtype': None,
        'classification_method': 'google_news_default',
        'rule_name': 'keyword_search'
    }


def get_or_create_keyword(conn: sqlite3.Connection, keyword_text: str) -> int:
    """
    Get keyword_id for a keyword, creating it if it doesn't exist.

    Args:
        conn: Database connection
        keyword_text: Keyword string

    Returns:
        keyword_id: ID of the keyword in keywords table
    """
    cursor = conn.cursor()

    # Try to get existing keyword
    cursor.execute('SELECT id FROM keywords WHERE keyword = ?', (keyword_text,))
    row = cursor.fetchone()

    if row:
        return row[0]

    # Keyword doesn't exist, create it
    cursor.execute('''
        INSERT INTO keywords (keyword, is_active, created_at, last_used_at)
        VALUES (?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ''', (keyword_text,))

    return cursor.lastrowid


def save_articles_to_db(
    conn: sqlite3.Connection,
    articles: List[Dict],
    classifier: Optional[RuleBasedClassifier],
    logger: logging.Logger
) -> Dict:
    """
    Save articles to POC database using normalized keyword schema.

    Args:
        conn: Database connection
        articles: List of article dicts from Google News
        classifier: URL classifier (optional)
        logger: Logger instance

    Returns:
        Dict with stats: total, new, duplicates, content, no_content
    """
    cursor = conn.cursor()
    stats = {
        'total': len(articles),
        'new': 0,
        'new_keywords': 0,  # URLs that already exist but with new keyword
        'duplicate_keywords': 0,  # URL+keyword combination already exists
        'content': 0,
        'no_content': 0
    }

    for article in articles:
        url = article['url']
        google_news_url = article.get('google_news_url')  # May not exist in old data
        title = article['title']
        published_at = article['published_at']
        source = article['source']
        search_keyword = article['search_keyword']

        # Get or create keyword_id from normalized keywords table
        keyword_id = get_or_create_keyword(conn, search_keyword)

        # Check if URL already exists
        cursor.execute("SELECT id FROM urls WHERE url = ?", (url,))
        existing = cursor.fetchone()

        if existing:
            # URL exists! Check if this keyword is new
            url_id = existing[0]

            # Check if this URL+keyword combination already exists (using keyword_id)
            cursor.execute("""
                SELECT 1 FROM url_keywords
                WHERE url_id = ? AND keyword_id = ?
            """, (url_id, keyword_id))

            keyword_exists = cursor.fetchone()

            if keyword_exists:
                # Same URL with same keyword = true duplicate
                stats['duplicate_keywords'] += 1
                logger.debug(f"Duplicate URL+keyword: {url} ({search_keyword})")
                continue
            else:
                # Same URL but NEW keyword! Add the keyword association
                try:
                    cursor.execute("""
                        INSERT INTO url_keywords (url_id, keyword_id, found_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    """, (url_id, keyword_id))
                    stats['new_keywords'] += 1
                    logger.debug(f"Added new keyword '{search_keyword}' to existing URL: {title[:50]}...")

                    # Update keyword last_used_at
                    cursor.execute("""
                        UPDATE keywords SET last_used_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (keyword_id,))

                    conn.commit()
                    continue
                except Exception as e:
                    logger.warning(f"Failed to add keyword association: {e}")
                    continue

        # Classify URL
        classification = classify_url(url, title, classifier)

        # Track content type stats
        if classification['content_type'] == 'contenido':
            stats['content'] += 1
        else:
            stats['no_content'] += 1

        # CRITICAL: Use published_at (article's real date), not today!
        # This allows filtering by actual news date, not extraction date
        extracted_at = published_at
        last_extracted_at = published_at

        # Insert into database (note: search_keyword column is legacy, keeping for now)
        try:
            cursor.execute("""
                INSERT INTO urls (
                    url,
                    google_news_url,
                    title,
                    content_type,
                    content_subtype,
                    classification_method,
                    rule_name,
                    source,
                    extracted_at,
                    last_extracted_at,
                    search_keyword
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                url,
                google_news_url,
                title,
                classification['content_type'],
                classification['content_subtype'],
                classification['classification_method'],
                classification['rule_name'],
                'keyword_search',  # All POC URLs have this source
                extracted_at,
                last_extracted_at,
                search_keyword  # Legacy column, keeping for compatibility
            ))

            url_id = cursor.lastrowid

            # Insert into normalized url_keywords table
            cursor.execute("""
                INSERT INTO url_keywords (url_id, keyword_id, found_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (url_id, keyword_id))

            # Update keyword last_used_at
            cursor.execute("""
                UPDATE keywords SET last_used_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (keyword_id,))

            stats['new'] += 1
            logger.debug(f"Saved: {title[:60]}... ({search_keyword})")

        except Exception as e:
            logger.warning(f"Failed to insert URL: {e}")
            continue

    conn.commit()

    return stats


def main(
    run_date: Optional[str] = None,
    specific_keywords: Optional[List[str]] = None,
    enable_classification: bool = True
):
    """
    Main entry point for POC keyword search.

    Args:
        run_date: Date string YYYY-MM-DD (for logging)
        specific_keywords: List of specific keywords to search (overrides config)
        enable_classification: Whether to classify URLs (default True)
    """
    # Setup
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")

    logger = setup_logging(run_date)
    logger.info(f"{'='*60}")
    logger.info(f"POC KEYWORD SEARCH - Stage 01 Alternative")
    logger.info(f"Date: {run_date}")
    logger.info(f"{'='*60}")

    # Load config
    config = load_config()
    search_config = config['search_config']
    keyword_topics = config['keyword_topics']

    # Filter to specific keywords if provided
    if specific_keywords:
        keyword_topics = [
            kw for kw in keyword_topics
            if kw['topic'] in specific_keywords
        ]
        logger.info(f"Filtering to {len(keyword_topics)} specific keywords")

    if not keyword_topics:
        logger.error("No keyword topics to search!")
        return

    logger.info(f"Total keywords to search: {len(keyword_topics)}")

    # Initialize Google News searcher
    resolve_urls = search_config.get('resolve_urls', False)
    searcher = GoogleNewsSearcher(
        language=search_config['language'],
        country=search_config['country'],
        resolve_urls=resolve_urls
    )

    if resolve_urls:
        logger.info("URL resolution ENABLED (decodes Google News URLs to real article URLs)")
    else:
        logger.info("URL resolution DISABLED (Google News URLs will be kept)")

    # Initialize URL classifier (optional)
    classifier = None
    if enable_classification:
        try:
            classifier = RuleBasedClassifier()
            logger.info("URL classifier initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize classifier: {e}")
            logger.warning("Continuing without classification (all URLs = contenido)")

    # Get POC database
    try:
        db_conn = get_poc_database(config)
        logger.info("Connected to POC database")
    except Exception as e:
        logger.error(f"Database error: {e}")
        return

    # Search all keywords
    all_stats = {
        'total_keywords': len(keyword_topics),
        'total_articles': 0,
        'new_articles': 0,
        'duplicates': 0,
        'content': 0,
        'no_content': 0
    }

    try:
        for i, kw_config in enumerate(keyword_topics, 1):
            keyword = kw_config['topic']
            when = kw_config.get('when', '1d')
            max_results = kw_config.get('max_results')

            logger.info(f"\n[{i}/{len(keyword_topics)}] Searching: '{keyword}' (when={when})")

            # Search Google News
            articles = searcher.search(keyword, when=when, max_results=max_results)

            if not articles:
                logger.warning(f"No articles found for '{keyword}'")
                continue

            # Save to database
            stats = save_articles_to_db(db_conn, articles, classifier, logger)

            # Calculate total duplicates (both duplicate keywords and new keywords)
            total_duplicates = stats['duplicate_keywords'] + stats['new_keywords']

            logger.info(
                f"✓ '{keyword}': {stats['new']} new, "
                f"{total_duplicates} duplicates ({stats['new_keywords']} new keywords), "
                f"{stats['content']} content, {stats['no_content']} no_content"
            )

            # Update totals
            all_stats['total_articles'] += stats['total']
            all_stats['new_articles'] += stats['new']
            all_stats['duplicates'] += total_duplicates
            all_stats['content'] += stats['content']
            all_stats['no_content'] += stats['no_content']

            # Rate limiting (be nice to Google)
            import time
            rate_limit = search_config.get('rate_limit_delay', 1.0)
            if i < len(keyword_topics):
                time.sleep(rate_limit)

    finally:
        db_conn.close()

    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info("POC STAGE 01 COMPLETED")
    logger.info(f"{'='*60}")
    logger.info(f"Keywords searched: {all_stats['total_keywords']}")
    logger.info(f"Total articles found: {all_stats['total_articles']}")
    logger.info(f"New articles saved: {all_stats['new_articles']}")
    logger.info(f"  - Content URLs: {all_stats['content']}")
    logger.info(f"  - No-content URLs: {all_stats['no_content']}")
    logger.info(f"Duplicates skipped: {all_stats['duplicates']}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="POC: Search URLs by keyword topics (Google News)"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Date for logging (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--keywords",
        type=str,
        nargs="+",
        default=None,
        help="Specific keywords to search (overrides config)"
    )
    parser.add_argument(
        "--no-classification",
        action="store_true",
        help="Skip URL classification (all URLs = contenido)"
    )

    args = parser.parse_args()

    main(
        run_date=args.date,
        specific_keywords=args.keywords,
        enable_classification=not args.no_classification
    )
