#!/usr/bin/env python3
"""
Stage 04: Extract Content - Full Article Content Extraction

This script extracts full article content from ALL ranked URLs using multiple extraction methods:
1. XPath Cache - Reuse domain-specific selectors (free, instant)
2. JSON-LD - Schema.org structured data (free, standard)
3. newspaper3k - Automatic extraction (free, 70-80% success)
4. readability-lxml - Mozilla algorithm (free, fallback)
5. LLM XPath Discovery - Intelligent selector discovery (paid, caches result)
6. LLM Direct Extraction - Last resort (paid, slowest)

Key Features:
- Paywall detection with archive.today fallback
- XPath cache for efficient domain-specific extraction
- Multiple extraction methods with cascading fallback
- Content cleaning and validation
- Database persistence with extraction metadata

SIMPLIFIED ARCHITECTURE (v2.0):
- Input: Ranked JSON with list of URLs
- Process: Extract content for ALL URLs in the list (no substitution logic)
- Output: Database updates only (no JSON output)

Author: Newsletter Utils Team
Created: 2025-11-13
Simplified: 2025-11-17
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from common.postgres_db import PostgreSQLURLDatabase
from common.llm import LLMClient
from common.stage04_extraction import (
    load_xpath_cache,
    extract_content_with_cache,
    clean_content,
    fetch_html_with_cascade
)
from common.stage04_extraction.authenticated_scraper import (
    AuthenticatedScraper,
    get_domain_from_url
)
import re
from bs4 import BeautifulSoup
from common.logging_utils import setup_rotating_file_logger

# Load environment variables
load_dotenv()

# Configuration
XPATH_CACHE_PATH = os.getenv('XPATH_CACHE_PATH', 'config/xpath_cache.yml')
STAGE04_TIMEOUT = int(os.getenv('STAGE04_TIMEOUT', '30'))
STAGE04_MIN_WORD_COUNT = int(os.getenv('STAGE04_MIN_WORD_COUNT', '100'))
STAGE04_MAX_WORD_COUNT = int(os.getenv('STAGE04_MAX_WORD_COUNT', '10000'))

# Setup logging
logger = logging.getLogger(__name__)


def extract_title_from_html(html: str) -> Optional[str]:
    """
    Extract article title from HTML.

    Tries multiple methods in order of preference:
    1. og:title meta tag (most reliable for articles)
    2. <title> tag
    3. <h1> tag

    Args:
        html: HTML content

    Returns:
        Extracted title or None
    """
    if not html:
        return None

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 1. Try og:title (Open Graph - most reliable for articles)
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content'].strip()
            if len(title) > 10:  # Sanity check
                return title

        # 2. Try <title> tag
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            title = title_tag.string.strip()
            # Often title tags include site name, try to clean
            # Common patterns: "Article Title | Site Name", "Article Title - Site Name"
            for separator in [' | ', ' - ', ' — ', ' :: ', ' » ']:
                if separator in title:
                    parts = title.split(separator)
                    # Usually article title is first, site name is last
                    if len(parts) >= 2:
                        # Take the longer part (usually the article title)
                        main_part = max(parts, key=len).strip()
                        if len(main_part) > 10:
                            title = main_part
                            break
            if len(title) > 10:
                return title

        # 3. Try <h1> tag
        h1_tag = soup.find('h1')
        if h1_tag:
            title = h1_tag.get_text(strip=True)
            if len(title) > 10:
                return title

        return None

    except Exception as e:
        logger.debug(f"Failed to extract title from HTML: {e}")
        return None


def setup_logging(run_date: str, verbose: bool = False) -> str:
    """
    Setup logging for Stage 04.

    Args:
        run_date: Date string for log directory
        verbose: Enable verbose logging

    Returns:
        Path to log file
    """
    log_file = setup_rotating_file_logger(
        run_date,
        "04_extract_content.log",
        log_level=logging.INFO,
        verbose=verbose,
    )

    logger.info(f"Stage 04 logging initialized: {log_file}")
    return str(log_file)


def process_url(
    url_data: Dict[str, Any],
    rank: int,
    total: int,
    db: PostgreSQLURLDatabase,
    llm_client: LLMClient,
    xpath_cache: Dict,
    args: argparse.Namespace,
    cookie_manager = None
) -> Dict[str, Any]:
    """
    Process a single URL: fetch, detect paywall, extract content, save to DB.

    Args:
        url_data: URL data dict from ranking JSON
        rank: Current rank number (for logging)
        total: Total URLs to process
        db: Database instance
        llm_client: LLM client instance
        xpath_cache: Loaded XPath cache
        args: Command-line arguments
        cookie_manager: Cookie manager for authenticated requests

    Returns:
        Result dictionary with success status and metadata
    """
    url_id = url_data['id']
    url = url_data['url']
    title = url_data.get('title', 'Untitled')

    logger.info("="*80)
    logger.info(f"[{rank}/{total}] Processing: {title}")
    logger.info(f"URL: {url}")
    logger.info(f"ID: {url_id}")
    logger.info("="*80)

    # Check if already extracted (unless --force)
    if not args.force:
        existing = db.get_url_by_id(url_id)
        if existing and existing.get('full_content'):
            logger.info(f"✓ Already extracted ({existing.get('word_count')} words), skipping")
            return {
                'success': True,
                'url_id': url_id,
                'method': 'cached',
                'word_count': existing.get('word_count'),
                'skipped': True
            }

    # STEP 1: Fetch HTML using cascade (tries multiple methods until success)
    logger.info("")
    logger.info("="*80)
    logger.info("STEP 1: FETCH HTML (with cascade of methods)")
    logger.info("="*80)

    fetch_result = fetch_html_with_cascade(
        url=url,
        llm_client=llm_client,
        cookie_manager=cookie_manager,
        skip_paywall_check=args.skip_paywall_check,
        timeout=STAGE04_TIMEOUT,
        title=title  # Pass title for content validation
    )

    if not fetch_result['success']:
        logger.error(f"✗ All fetch methods failed: {fetch_result['error']}")
        db.update_content_extraction(
            url_id,
            extraction_status='failed',
            extraction_error=fetch_result['error']
        )
        return {
            'success': False,
            'url_id': url_id,
            'error': fetch_result['error']
        }

    # Extract results
    html = fetch_result['html']
    fetch_method = fetch_result['method']
    archive_url_used = fetch_result.get('archive_url')

    logger.info("")
    logger.info("="*80)
    logger.info(f"✓ HTML FETCHED SUCCESSFULLY via: {fetch_method}")
    if archive_url_used:
        logger.info(f"  Archive URL: {archive_url_used}")
    logger.info("="*80)
    logger.info("")

    # STEP 2: Extract content
    logger.info("="*80)
    logger.info("STEP 2: EXTRACT CONTENT (newspaper/readability/LLM)")
    logger.info("="*80)
    result = extract_content_with_cache(url, html, llm_client, xpath_cache, title=title)

    if not result['success']:
        logger.error(f"✗ Extraction failed: {result.get('error')}")
        db.update_content_extraction(
            url_id,
            extraction_status='failed',
            extraction_error=result.get('error', 'Unknown extraction error'),
            extraction_method=result.get('method', 'unknown')
        )
        return {
            'success': False,
            'url_id': url_id,
            'error': result.get('error'),
            'method': result.get('method')
        }

    logger.info(f"✓ Content extracted via: {result['method']}")
    logger.info("")

    # STEP 3: Clean content
    logger.info("="*80)
    logger.info("STEP 3: CLEAN & VALIDATE CONTENT")
    logger.info("="*80)
    raw_content = result['content']
    clean_text = clean_content(raw_content, max_length=STAGE04_MAX_WORD_COUNT * 5)

    word_count = len(clean_text.split())

    # Validate word count
    if word_count < STAGE04_MIN_WORD_COUNT:
        logger.error(f"✗ Content too short: {word_count} words (min: {STAGE04_MIN_WORD_COUNT})")
        db.update_content_extraction(
            url_id,
            full_content=clean_text,
            extraction_status='failed',
            extraction_error=f'Content too short ({word_count} words)',
            extraction_method=result['method'],
            word_count=word_count,
            archive_url=archive_url_used
        )
        return {
            'success': False,
            'url_id': url_id,
            'error': f'Content too short ({word_count} words)',
            'method': result['method'],
            'word_count': word_count
        }

    if word_count > STAGE04_MAX_WORD_COUNT:
        logger.warning(f"⚠ Content too long: {word_count} words (may include page boilerplate)")
    else:
        logger.info(f"✓ Content validated: {word_count} words")

    logger.info("")

    # STEP 4: Extract proper title from HTML
    logger.info("="*80)
    logger.info("STEP 4: EXTRACT TITLE FROM HTML")
    logger.info("="*80)
    extracted_title = extract_title_from_html(html)
    title_updated = False
    if extracted_title and extracted_title != title:
        logger.info(f"  Original title: {title}")
        logger.info(f"  Extracted title: {extracted_title}")
        title_updated = True
    else:
        extracted_title = None  # Don't update if same or not found
        logger.info(f"  Title unchanged: {title}")

    logger.info("")

    # STEP 5: Save to database
    logger.info("="*80)
    logger.info("STEP 5: SAVE TO DATABASE")
    logger.info("="*80)
    db.update_content_extraction(
        url_id,
        full_content=clean_text,
        extraction_method=result['method'],
        extraction_status='success',
        word_count=word_count,
        archive_url=archive_url_used,
        title=extracted_title
    )

    logger.info("")
    logger.info("="*80)
    logger.info(f"✓✓✓ SUCCESS ✓✓✓")
    logger.info(f"  Fetch method: {fetch_method}")
    logger.info(f"  Extraction method: {result['method']}")
    logger.info(f"  Word count: {word_count}")
    if title_updated:
        logger.info(f"  Title updated: Yes")
    if archive_url_used:
        logger.info(f"  Archive URL: {archive_url_used}")
    logger.info("="*80)

    return {
        'success': True,
        'url_id': url_id,
        'method': result['method'],
        'word_count': word_count,
        'used_archive': bool(archive_url_used),
        'title_updated': title_updated
    }


def setup_cookie_manager(db: PostgreSQLURLDatabase) -> Optional[AuthenticatedScraper]:
    """
    Setup cookie manager for authenticated scraping.

    Args:
        db: Database instance

    Returns:
        AuthenticatedScraper instance or None
    """
    use_cookies = os.getenv('STAGE04_USE_COOKIES', 'true').lower() == 'true'

    if not use_cookies:
        logger.info("Cookie-based authentication: DISABLED")
        return None

    try:
        cookie_manager = AuthenticatedScraper(db)
        logger.info("Cookie-based authentication: ENABLED")
        return cookie_manager
    except Exception as e:
        logger.warning(f"Failed to initialize cookie manager: {e}")
        logger.info("Continuing without cookie authentication")
        return None


def print_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Print execution summary and return metrics.

    Args:
        results: List of processing results

    Returns:
        Dict with summary metrics
    """
    total = len(results)
    successful = sum(1 for r in results if r['success'])
    skipped = sum(1 for r in results if r.get('skipped', False))
    failed = total - successful

    # Count by method
    methods = {}
    for r in results:
        if r['success'] and not r.get('skipped'):
            method = r.get('method', 'unknown')
            methods[method] = methods.get(method, 0) + 1

    # Total word count
    total_words = sum(r.get('word_count', 0) for r in results if r['success'])
    avg_words = total_words // successful if successful > 0 else 0

    # Used archive
    used_archive = sum(1 for r in results if r.get('used_archive', False))

    logger.info("")
    logger.info("="*80)
    logger.info("STAGE 04 SUMMARY")
    logger.info("="*80)
    logger.info(f"Total URLs processed: {total}")
    logger.info(f"  ✓ Successfully extracted: {successful}")
    if skipped > 0:
        logger.info(f"    (including {skipped} already extracted)")
    logger.info(f"  ✗ Failed: {failed}")

    if methods:
        logger.info("")
        logger.info("Extraction methods used:")
        for method, count in sorted(methods.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {method}: {count}")

    if successful > 0:
        logger.info("")
        logger.info(f"Total words extracted: {total_words:,}")
        logger.info(f"Average words per article: {avg_words}")

    if used_archive > 0:
        logger.info("")
        logger.info(f"Archive.today used: {used_archive} URLs")

    logger.info("")

    # Status
    if failed == 0:
        status = "success"
        logger.info(f"  Status: {status}")
    elif successful > 0:
        status = "partial_success"
        logger.info(f"  Status: {status}")
    else:
        status = "failed"
        logger.info(f"  Status: {status}")

    logger.info("="*80)

    # Return metrics
    return {
        "success_count": successful,
        "failed_count": failed,
        "skipped_count": skipped,
        "total_count": total,
        "methods": methods,
        "total_words": total_words,
        "avg_words": avg_words,
        "used_archive_count": used_archive,
        "status": status
    }


def main():
    """
    Main entry point for Stage 04.

    REFACTORED (v3.0 - DB-centric):
    1. Query ranked URLs from database by ranking_run_id
    2. Process each URL (fetch + extract + save to DB)
    3. Return extraction metrics
    """
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Stage 04: Extract full article content from ranked URLs (reads from database)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract content for all ranked URLs
  %(prog)s --newsletter-name noticias_diarias --date 2025-11-17

  # Force re-extraction even if already extracted
  %(prog)s --newsletter-name noticias_diarias --date 2025-11-17 --force

  # Skip paywall validation (faster, may get truncated content)
  %(prog)s --newsletter-name noticias_diarias --date 2025-11-17 --skip-paywall-check
        """
    )

    parser.add_argument(
        '--newsletter-name',
        type=str,
        required=True,
        help='Name of the newsletter'
    )

    parser.add_argument(
        '--date',
        type=str,
        required=True,
        help='Run date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-extraction even if content already exists'
    )

    parser.add_argument(
        '--skip-paywall-check',
        action='store_true',
        help='Skip paywall validation (faster but may get incomplete content)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level)'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.date, args.verbose)

    logger.info("="*80)
    logger.info("STAGE 04: EXTRACT CONTENT")
    logger.info("="*80)
    logger.info(f"Newsletter: {args.newsletter_name}")
    logger.info(f"Run date: {args.date}")
    logger.info(f"Force re-extraction: {args.force}")
    logger.info(f"Skip paywall check: {args.skip_paywall_check}")

    # Start timing
    import time
    stage_start_time = time.time()

    # Initialize database
    db = PostgreSQLURLDatabase(os.getenv('DATABASE_URL'))

    # Get ranking run from database
    ranking_run = db.get_ranking_run(args.newsletter_name, args.date)
    if not ranking_run:
        logger.error(f"No ranking found for {args.newsletter_name} on {args.date}")
        logger.error("Run Stage 03 first to generate ranking")
        return {
            "status": "failed",
            "error": f"No ranking found for {args.newsletter_name} on {args.date}"
        }

    ranking_run_id = ranking_run['id']
    logger.info(f"Ranking run ID: {ranking_run_id}")

    # Get ranked URLs from database
    ranked_urls = db.get_ranked_urls(ranking_run_id)
    logger.info(f"Total URLs to process: {len(ranked_urls)}")

    if not ranked_urls:
        logger.warning("No URLs found in ranking")
        execution_time = time.time() - stage_start_time
        return {
            "status": "success",
            "total_urls": 0,
            "extracted_success": 0,
            "extracted_failed": 0,
            "methods_used": {},
            "failed_urls": [],
            "execution_time": execution_time
        }

    # Initialize LLM client
    llm_client = LLMClient()

    # Load XPath cache
    xpath_cache = load_xpath_cache(XPATH_CACHE_PATH)
    logger.info(f"Loaded XPath cache with {len(xpath_cache)} domains")

    # Setup cookie manager
    cookie_manager = setup_cookie_manager(db)

    # Process all URLs
    logger.info("")
    logger.info("="*80)
    logger.info("PROCESSING ALL URLS")
    logger.info("="*80)

    results = []
    for i, url_data in enumerate(ranked_urls, 1):
        result = process_url(
            url_data,
            rank=i,
            total=len(ranked_urls),
            db=db,
            llm_client=llm_client,
            xpath_cache=xpath_cache,
            args=args,
            cookie_manager=cookie_manager
        )
        results.append(result)
        logger.info("")  # Blank line between URLs

    # Calculate execution time
    execution_time = time.time() - stage_start_time

    # Get cookies usage report
    cookies_report = None
    if cookie_manager:
        cookies_report = cookie_manager.get_cookies_usage_report()
        logger.info(f"\n{'='*60}")
        logger.info("COOKIES USAGE REPORT")
        logger.info(f"{'='*60}")
        if cookies_report['total'] > 0:
            logger.info(f"Total domains with cookies: {cookies_report['total']}")
            logger.info(f"✓ Successful: {len(cookies_report['successful'])} ({cookies_report['success_rate']:.1f}%)")
            if cookies_report['successful']:
                logger.info(f"  Domains: {', '.join(cookies_report['successful'])}")
            if cookies_report['failed']:
                logger.info(f"✗ Failed: {len(cookies_report['failed'])}")
                logger.info(f"  Domains: {', '.join(cookies_report['failed'])}")
        else:
            logger.info("No cookies were used during this execution")
        logger.info(f"{'='*60}\n")

    # Print summary
    summary = print_summary(results)

    logger.info(f"\nExecution time: {execution_time:.2f}s")
    logger.info("Stage 04 completed")

    try:
        # Return metadata for orchestrator
        methods_used = {}
        for result in results:
            method = result.get('method', 'unknown')
            methods_used[method] = methods_used.get(method, 0) + 1

        failed_urls = [
            {
                "url_id": r.get('url_id'),
                "url": r.get('url'),
                "error": r.get('error', 'Unknown error')
            }
            for r in results if not r.get('success', False)
        ]

        result_dict = {
            "status": "success",
            "total_urls": len(ranked_urls),
            "extracted_success": summary['success_count'],
            "extracted_failed": summary['failed_count'],
            "methods_used": methods_used,
            "failed_urls": failed_urls,
            "execution_time": execution_time,
            "cookies_report": cookies_report  # Add cookies usage report
        }

        # IMPORTANT: Print to stdout for subprocess to capture
        print(f"RESULT: {result_dict}", flush=True)

        return result_dict
    except Exception as e:
        logger.error(f"ERROR building result dict: {e}", exc_info=True)
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    result = main()
    if isinstance(result, dict):
        # Called from orchestrator or programmatically
        exit_code = 0 if result["status"] == "success" else 1
        print(f"DEBUG: Exiting with code {exit_code}, status={result['status']}", file=sys.stderr)
        sys.exit(exit_code)
    else:
        # Legacy CLI usage
        print(f"DEBUG: Exiting with legacy result {result}", file=sys.stderr)
        sys.exit(result)
