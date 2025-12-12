#!/usr/bin/env python3
"""
Stage 01: Extract URLs from news sources.

This script:
1. Loads news sources from config/sources.yml
2. Uses Selenium to scrape links from each source
3. Uses OpenAI LLM to filter actual news articles from navigation/ads
4. Saves results to data/raw/urls_YYYY-MM-DD_HHMMSS.csv with TAB separator

Usage:
    python stages/01_extract_urls.py [--date YYYY-MM-DD]

    Or as a module:
    from stages.extract_urls import main
    main(run_date="2025-11-09")
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.postgres_db import PostgreSQLURLDatabase

import yaml
from dotenv import load_dotenv

from common.stage01_extraction.selenium_utils import create_driver_from_env
from common.llm import filter_content_urls, LLMClient
from common.stage01_extraction.url_classifier import (
    RuleBasedClassifier,
    discover_patterns_from_urls,
    save_rules_to_yaml,
    save_cached_no_content_urls,
    get_classification_stats
)
from poc_clustering.src.persistent_clusterer import PersistentClusterer
from common.logging_utils import setup_rotating_file_logger

# Load environment variables
load_dotenv()


def setup_logging(run_date: str) -> logging.Logger:
    """
    Configure logging for this stage.

    Args:
        run_date: Date string in YYYY-MM-DD format

    Returns:
        Configured logger instance
    """
    setup_rotating_file_logger(
        run_date,
        "01_extract_urls.log",
        log_level=logging.INFO,
        verbose=False,
        stream_to_stdout=True,
    )

    stage_logger = logging.getLogger(__name__)
    stage_logger.info(f"Logging initialized - output to logs/{run_date}/01_extract_urls.log")

    return stage_logger


def load_sources_from_db() -> List[Dict]:
    """
    Load news sources from PostgreSQL database.

    Returns:
        List of source configurations (active only)
    """
    logger = logging.getLogger(__name__)

    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")

        db = PostgreSQLURLDatabase(database_url)
        sources_data = db.get_all_sources(include_inactive=False)

        # Convert DB format to Stage 01 expected format
        enabled_sources = []
        for source in sources_data:
            enabled_sources.append({
                'id': source['name'],  # Use 'name' as 'id' for Stage 01
                'name': source['display_name'],
                'url': source['base_url'],
                'enabled': source['is_active'],
                'priority': source['priority'],
                'language': source['language'],
                'description': source['description'] or ''
            })

        logger.info(f"Loaded {len(enabled_sources)} enabled sources from PostgreSQL")

        return enabled_sources

    except Exception as e:
        logger.error(f"Error loading sources from database: {e}")
        raise


def load_clustering_config(config_path: str) -> Dict:
    """Load clustering configuration and normalize relative paths.
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Clustering config not found: {config_file}")

    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    base_dir = config_file.parent.resolve()
    model_cfg = config.get("model", {})
    cache_dir = model_cfg.get("cache_dir")
    if cache_dir:
        cache_path = Path(cache_dir)
        if not cache_path.is_absolute():
            model_cfg["cache_dir"] = str((base_dir / cache_path).resolve())
    config["model"] = model_cfg

    state_cfg = config.get("state", {})
    state_dir = state_cfg.get("directory")
    if state_dir:
        state_path = Path(state_dir)
        if not state_path.is_absolute():
            state_cfg["directory"] = str((base_dir / state_path).resolve())
    config["state"] = state_cfg
    config["_base_dir"] = str(base_dir)
    return config


def assign_clusters_incremental(db: PostgreSQLURLDatabase, run_date: str) -> Optional[Dict[str, int]]:
    """Incrementally cluster newly ingested URLs across the full dataset."""
    enable_clustering = os.getenv('ENABLE_NEWS_CLUSTERING', 'true').lower() == 'true'
    if not enable_clustering:
        logging.getLogger(__name__).info("News clustering disabled via ENABLE_NEWS_CLUSTERING")
        return None

    config_path = os.getenv('CLUSTERING_CONFIG_PATH', 'poc_clustering/config.yml')
    try:
        config = load_clustering_config(config_path)
    except FileNotFoundError as exc:
        logging.getLogger(__name__).warning(str(exc))
        return None

    clusterer = PersistentClusterer(config, db, run_date)
    summary = clusterer.run()
    return summary if summary else None


def extract_urls_from_source(
    source: Dict,
    selenium_driver,
    llm_client: LLMClient,
    rule_classifier: Optional[RuleBasedClassifier],
    run_date: str,
    db: Optional[PostgreSQLURLDatabase] = None,
    reclassify: bool = False
) -> List[Dict[str, str]]:
    """
    Extract and filter URLs from a single news source.

    Args:
        source: Source configuration dict
        selenium_driver: Selenium driver instance
        llm_client: LLM client instance
        rule_classifier: Rule-based classifier instance (optional)
        run_date: Run date for tracking
        db: SQLite database instance for deduplication check (optional)
        reclassify: If True, reclassify existing URLs (default: False)

    Returns:
        List of filtered news URLs with titles
    """
    logger = logging.getLogger(__name__)

    source_id = source.get('id', 'unknown')
    source_name = source.get('name', source_id)
    source_url = source.get('url')

    logger.info(f"Processing source: {source_name} ({source_url})")

    # Navigate to source
    if not selenium_driver.get_page(source_url):
        logger.error(f"Failed to load {source_name}")
        return []

    # Extract ALL links using simple 'a' selector (no limit at this stage)
    selectors = ['a']  # Just get all anchor tags
    # Use a very high limit to extract as many raw links as possible
    raw_links = selenium_driver.scroll_and_extract(selectors, max_links=10000)

    if not raw_links:
        logger.warning(f"No links found for {source_name}")
        return []

    logger.info(f"Extracted {len(raw_links)} raw links from {source_name}")

    # For testing: optionally limit raw links before classification
    test_limit = os.getenv('TEST_MAX_RAW_LINKS')
    if test_limit and test_limit.strip():
        test_limit = int(test_limit)
        if len(raw_links) > test_limit:
            logger.info(f"TEST MODE: Limiting from {len(raw_links)} to {test_limit} raw links for faster testing")
            raw_links = raw_links[:test_limit]

    # OPTIMIZATION: Separate existing URLs from new ones to skip re-classification
    existing_urls_data = {}
    new_links = raw_links

    if db and not reclassify:
        # Bulk lookup existing URLs
        url_list = [link['url'] for link in raw_links]
        existing_urls_data = db.get_existing_urls(url_list)

        if existing_urls_data:
            # Separate new vs existing
            existing_url_set = set(existing_urls_data.keys())
            new_links = [link for link in raw_links if link['url'] not in existing_url_set]

            logger.info(f"Deduplication: {len(existing_urls_data)} URLs already in DB, "
                       f"{len(new_links)} new URLs need classification")
        else:
            logger.info(f"No existing URLs found - all {len(raw_links)} URLs are new")
    elif reclassify:
        logger.info(f"--reclassify enabled: Will reclassify all {len(raw_links)} URLs")
    else:
        logger.debug("Database instance not provided - will classify all URLs")

    # Check if we should use cached rules
    use_cached_rules = os.getenv('USE_CACHED_RULES', 'true').lower() == 'true'

    classified_by_rules = []
    unclassified_links = new_links

    # Try rule-based classification first (only for NEW links)
    if use_cached_rules and rule_classifier and new_links:
        logger.info(f"Applying regex rules to {len(new_links)} NEW links from {source_name}")
        classified_by_rules, unclassified_links = rule_classifier.classify_batch(new_links)
        logger.info(f"Rules matched {len(classified_by_rules)} links, {len(unclassified_links)} need LLM classification")

    # Classify remaining links with LLM (LEVEL 1: content_type)
    classified_by_llm = []
    if unclassified_links:
        logger.info(f"Classifying {len(unclassified_links)} unmatched links with LLM (Level 1: content_type)")
        classified_by_llm = filter_content_urls(
            links=unclassified_links,
            source_name=source_name,
            llm_client=llm_client,
            stage="01",
            run_date=run_date
        )
        # Add classification metadata to LLM results
        for link in classified_by_llm:
            link['classification_method'] = 'llm_api'
            link['rule_name'] = None

    # Reconstruct existing URLs with updated title (if better)
    existing_urls_list = []
    for link in raw_links:
        if link['url'] in existing_urls_data:
            existing_data = existing_urls_data[link['url']]
            # Preserve classification from DB
            reconstructed = {
                'url': link['url'],
                'title': link['title'] if len(link['title']) > len(existing_data.get('title', '')) else existing_data['title'],
                'content_type': existing_data['content_type'],
                'content_subtype': existing_data.get('content_subtype'),
                'classification_method': existing_data['classification_method'],
                'rule_name': existing_data.get('rule_name')
            }
            existing_urls_list.append(reconstructed)

    # Combine results: newly classified + existing (with preserved classification)
    all_classified = classified_by_rules + classified_by_llm + existing_urls_list

    if existing_urls_list:
        logger.info(f"Reconstructed {len(existing_urls_list)} existing URLs with preserved classification")

    # OPTIONAL: LEVEL 2 classification (content_subtype: noticia vs otros)
    # Only if CLASSIFY_CONTENT_SUBTYPE=true and content_type='contenido'
    classify_subtype = os.getenv('CLASSIFY_CONTENT_SUBTYPE', 'false').lower() == 'true'

    if classify_subtype:
        # Filter only 'contenido' URLs for subtype classification
        contenido_urls = [link for link in all_classified if link.get('content_type') == 'contenido']

        if contenido_urls:
            logger.info(f"LEVEL 2: Classifying content_subtype for {len(contenido_urls)} 'contenido' URLs")

            # Classify subtypes in batch
            subtyped_urls = classify_content_subtype(
                links=contenido_urls,
                source_name=source_name,
                llm_client=llm_client,
                stage="01",
                run_date=run_date
            )

            # Update all_classified with subtype info
            # Create a lookup dict for fast matching
            subtype_lookup = {url['url']: url.get('content_subtype') for url in subtyped_urls}
            for link in all_classified:
                if link['url'] in subtype_lookup:
                    link['content_subtype'] = subtype_lookup[link['url']]

            logger.info(f"LEVEL 2: Classified {len(subtyped_urls)} URLs with content_subtype")
    else:
        logger.debug("LEVEL 2 classification disabled (CLASSIFY_CONTENT_SUBTYPE=false)")

    # Log classification statistics
    stats = get_classification_stats(all_classified)
    logger.info(f"Classification stats for {source_name}: "
                f"total={stats['total']}, "
                f"regex={stats['by_method'].get('regex_rule', 0)}, "
                f"llm={stats['by_method'].get('llm_api', 0)}, "
                f"coverage={stats['regex_coverage_pct']:.1f}%")

    # NOW apply the max_links limit to ALL classified links
    max_links = int(os.getenv('MAX_LINKS_PER_SOURCE', '250'))
    if len(all_classified) > max_links:
        logger.info(f"Limiting from {len(all_classified)} to {max_links} links")
        all_classified = all_classified[:max_links]

    # Add source information to each link
    for link in all_classified:
        link['source'] = source_url
        link['source_id'] = source_id

    return all_classified


# Removed save_urls_to_csv - now using SQLite directly


def main(run_date: Optional[str] = None, filter_sources: Optional[List[str]] = None,
         reclassify: bool = False, execution_id: Optional[int] = None, api_key_id: Optional[int] = None,
         use_fallback: bool = True) -> int:
    """
    Main execution function for Stage 01.

    Args:
        run_date: Date string in YYYY-MM-DD format (defaults to today)
        filter_sources: Optional list of source IDs to process (e.g., ['elconfidencial', 'bbc'])
                       If None, processes all enabled sources
        reclassify: If True, reclassify existing URLs (ignores optimization)
        execution_id: Optional execution ID from execution_history table (for Celery tracking)
        api_key_id: Optional API key ID to use (enables fallback support)
        use_fallback: If False, only use the selected API key (no fallback)

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Determine run date
    if run_date is None:
        run_date = os.getenv('RUN_DATE', datetime.now().strftime('%Y-%m-%d'))

    # Setup logging
    logger = setup_logging(run_date)
    logger.info("="*60)
    logger.info(f"Stage 01: Extract URLs - Starting for {run_date}")
    logger.info("="*60)

    start_time = datetime.now()

    try:
        # Check if we should update rules
        update_rules = os.getenv('UPDATE_RULES_ON_RUN', 'false').lower() == 'true'
        use_cached_rules = os.getenv('USE_CACHED_RULES', 'true').lower() == 'true'

        # If UPDATE_RULES_ON_RUN=true, clean cached files first (full regeneration)
        # NOTE: If only generating rules for new sources, keep existing cached files
        if update_rules:
            logger.info("="*60)
            logger.info("UPDATE_RULES_ON_RUN=true: Cleaning cached files before full regeneration")
            logger.info("="*60)

            cached_files = [
                'config/url_classification_rules.yml',
                'config/source_structure.yml',
                'config/cached_no_content_urls.yml'
            ]

            for cached_file in cached_files:
                if os.path.exists(cached_file):
                    os.remove(cached_file)
                    logger.info(f"Deleted cached file: {cached_file}")
                else:
                    logger.info(f"Cached file not found (skipping): {cached_file}")

            logger.info("Cache cleaned successfully")

        # Load sources configuration from PostgreSQL
        sources = load_sources_from_db()

        if not sources:
            logger.error("No enabled sources found")
            return 1

        # Filter sources if requested
        if filter_sources:
            original_count = len(sources)
            sources = [s for s in sources if s['id'] in filter_sources]
            logger.info(f"Filtered sources: {len(sources)}/{original_count} (requested: {filter_sources})")

            if not sources:
                logger.error(f"No sources matched filter: {filter_sources}")
                return 1

        # Initialize LLM client (with fallback support if api_key_id provided and use_fallback enabled)
        if api_key_id:
            if use_fallback:
                logger.info(f"Initializing LLM client with API key ID {api_key_id} (fallback ENABLED)")
                llm_client = LLMClient(api_key_id=api_key_id, enable_fallback=True)
            else:
                logger.info(f"Initializing LLM client with API key ID {api_key_id} (fallback DISABLED - only this key)")
                llm_client = LLMClient(api_key_id=api_key_id, enable_fallback=False)
        else:
            logger.info("Initializing LLM client with default API key (no fallback)")
            llm_client = LLMClient()

        # Initialize rule-based classifier
        rule_classifier = None
        if use_cached_rules:
            rule_classifier = RuleBasedClassifier()
            if not rule_classifier.rules:
                logger.warning("No rules loaded, will use LLM for all classifications")
                rule_classifier = None

        # Initialize PostgreSQL database
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        db = PostgreSQLURLDatabase(database_url)
        logger.info(f"PostgreSQL database initialized")

        # Get initial database statistics
        initial_stats = db.get_stats()
        logger.info(f"Current database: {initial_stats['total_urls']} URLs "
                   f"({initial_stats['contenido_count']} contenido, "
                   f"{initial_stats['no_contenido_count']} no_contenido)")

        # Track URLs for pattern discovery and statistics
        all_urls = []  # For statistics and pattern discovery
        urls_by_source = {}  # For pattern discovery

        # Track sources without rules (for auto-generation)
        sources_without_rules = []
        if rule_classifier:
            for source in sources:
                source_id = source.get('id', 'unknown')
                if not rule_classifier.has_rules_for_source(source_id):
                    sources_without_rules.append(source_id)
                    logger.info(f"Source '{source_id}' has no rules - will generate after extraction")

        # Statistics tracking
        total_inserted = 0  # New URLs inserted
        total_updated = 0   # Existing URLs updated

        # Track source names for counting total URLs in BD
        processed_source_names = [s.get('id') or s.get('name') for s in sources]

        # Create Selenium driver and process each source
        with create_driver_from_env() as driver:
            for source in sources:
                try:
                    source_name = source.get('name', source.get('id', 'unknown'))
                    logger.info("="*60)
                    logger.info(f"Processing and upserting source: {source_name}")
                    logger.info("="*60)

                    urls = extract_urls_from_source(
                        source,
                        driver,
                        llm_client,
                        rule_classifier,
                        run_date,
                        db=db,
                        reclassify=reclassify
                    )

                    # Add extraction timestamp and execution_id
                    extracted_at = datetime.now().isoformat()
                    for url in urls:
                        url['extracted_at'] = extracted_at
                        if execution_id:
                            url['execution_id'] = execution_id

                    # Track for statistics and pattern discovery
                    all_urls.extend(urls)

                    # Store for pattern discovery if needed
                    source_domain = source.get('id', 'unknown')
                    # Store URLs if: (1) explicit update requested OR (2) source has no rules
                    if update_rules or source_domain in sources_without_rules:
                        urls_by_source[source_domain] = urls

                    # INCREMENTAL UPSERT: Save this source's URLs immediately to SQLite
                    if urls:
                        logger.info(f"Upserting {len(urls)} URLs from {source_name} to database")

                        # Batch upsert to SQLite
                        # SQLite handles deduplication via UNIQUE constraint
                        upsert_stats = db.batch_upsert(urls)

                        # Update counters
                        total_inserted += upsert_stats['inserted']
                        total_updated += upsert_stats['updated']

                        logger.info(
                            f"Source {source_name}: {upsert_stats['inserted']} new URLs, "
                            f"{upsert_stats['updated']} updated"
                        )

                        if upsert_stats['errors'] > 0:
                            logger.warning(f"Encountered {upsert_stats['errors']} errors during upsert")
                    else:
                        logger.warning(f"No URLs extracted from {source_name}")

                except Exception as e:
                    logger.error(f"Error processing source {source.get('name')}: {e}")
                    continue

        # Update rules if: (1) explicitly requested OR (2) some sources lack rules
        should_generate_rules = (update_rules or len(sources_without_rules) > 0) and urls_by_source

        if should_generate_rules:
            logger.info("="*60)
            if update_rules:
                logger.info("UPDATE_RULES_ON_RUN=true: Discovering patterns from extracted URLs")
            else:
                logger.info(f"Auto-generating rules for sources without rules: {sources_without_rules}")
            logger.info("="*60)

            min_coverage = int(os.getenv('MIN_PATTERN_COVERAGE', '5'))
            min_coverage_pct = float(os.getenv('RULE_COVERAGE_PERCENTAGE', '0.0'))

            try:
                discovered_rules, no_contenido_urls = discover_patterns_from_urls(
                    urls_by_source=urls_by_source,
                    llm_client=llm_client,
                    model=os.getenv('MODEL_URL_FILTER', 'gpt-4o-mini'),
                    min_coverage=min_coverage,
                    min_coverage_percentage=min_coverage_pct
                )

                # Save discovered rules
                save_rules_to_yaml(discovered_rules)
                logger.info("Successfully updated classification rules")

                # Save cached no_contenido URLs
                if no_contenido_urls:
                    save_cached_no_content_urls(no_contenido_urls)
                    total_cached = sum(len(urls) for urls in no_contenido_urls.values())
                    logger.info(f"Successfully cached {total_cached} no_contenido URLs")

            except Exception as e:
                logger.error(f"Failed to update rules: {e}", exc_info=True)

        # Assign semantic clusters incrementally across the dataset
        clustering_summary = None
        try:
            clustering_summary = assign_clusters_incremental(db, run_date)
        except Exception as clustering_error:
            logger.error(f"Cluster assignment failed: {clustering_error}", exc_info=True)

        # Final statistics summary (URLs already saved incrementally)
        if all_urls:
            # Calculate and log overall statistics
            overall_stats = get_classification_stats(all_urls)

            # Get final database stats
            final_stats = db.get_stats()

            logger.info("="*60)
            logger.info("FINAL SUMMARY")
            logger.info("="*60)
            logger.info(f"Successfully extracted {len(all_urls)} URLs from {len(sources)} sources")
            logger.info(f"Database changes: {total_inserted} inserted, {total_updated} updated")
            logger.info(f"Total URLs in database: {final_stats['total_urls']}")
            logger.info(f"Classification breakdown: "
                       f"regex={overall_stats['by_method'].get('regex_rule', 0)}, "
                       f"llm={overall_stats['by_method'].get('llm_api', 0)}")
            logger.info(f"Regex coverage: {overall_stats['regex_coverage_pct']:.1f}%")
            logger.info(f"Category breakdown: {overall_stats['by_category']}")
            if clustering_summary:
                logger.info(
                    f"Clustering: {clustering_summary['assigned']} new URLs processed "
                    f"({clustering_summary['new_clusters']} clusters created)"
                )
                logger.info(
                    f"Total clusters: {clustering_summary['total_clusters']} | "
                    f"Index vectors: {clustering_summary['index_vectors']}"
                )
        else:
            logger.warning("No URLs extracted from any source")

        # Update execution_history with URL metrics if execution_id provided
        if execution_id:
            try:
                # Get API keys used (if fallback was enabled)
                api_keys_used = llm_client.get_api_keys_used() if hasattr(llm_client, 'get_api_keys_used') else []

                # Calculate total URLs extracted/processed for THIS execution (day)
                # This should be the sum of new + updated URLs for this specific execution
                total_urls_this_execution = total_inserted + total_updated

                update_params = {
                    'total_items': total_urls_this_execution,  # URLs del día (nuevas + actualizadas)
                    'processed_items': total_inserted,
                    'updated_items': total_updated,
                    'failed_items': 0
                }

                # Add API keys used if any
                if api_keys_used:
                    update_params['api_keys_used'] = api_keys_used
                    logger.info(f"API keys used during execution: {api_keys_used}")

                db.update_execution_status(
                    execution_id,
                    'running',  # Keep status as running, Celery task will mark as completed
                    **update_params
                )
                logger.info(f"Updated execution_history #{execution_id} with metrics: {total_urls_this_execution} URLs del día ({total_inserted} nuevas, {total_updated} actualizadas)")
            except Exception as e:
                logger.warning(f"Failed to update execution_history: {e}")

        # Log summary
        duration = (datetime.now() - start_time).total_seconds()
        logger.info("="*60)
        logger.info(f"Stage 01: Extract URLs - Completed in {duration:.2f}s")
        logger.info(f"Total URLs extracted: {len(all_urls)}")
        logger.info("="*60)

        return 0

    except Exception as e:
        logger.error(f"Stage 01 failed with error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Extract URLs from news sources (Stage 01)'
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Run date in YYYY-MM-DD format (default: today)'
    )
    parser.add_argument(
        '--sources',
        type=str,
        nargs='+',
        help='Filter by specific source IDs (e.g., --sources elconfidencial bbc)'
    )
    parser.add_argument(
        '--reclassify',
        action='store_true',
        help='Force reclassification of existing URLs (disables optimization)'
    )
    parser.add_argument(
        '--execution-id',
        type=int,
        help='Execution ID from execution_history table (for Celery tracking)'
    )
    parser.add_argument(
        '--api-key-id',
        type=int,
        help='API key ID to use (enables fallback support)'
    )
    parser.add_argument(
        '--no-fallback',
        action='store_true',
        help='Disable fallback (only use the selected API key)'
    )

    args = parser.parse_args()

    exit_code = main(
        run_date=args.date,
        filter_sources=args.sources,
        reclassify=args.reclassify,
        execution_id=args.execution_id,
        api_key_id=args.api_key_id,
        use_fallback=not args.no_fallback  # Invert the flag
    )
    sys.exit(exit_code)
