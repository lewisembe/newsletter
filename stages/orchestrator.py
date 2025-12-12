#!/usr/bin/env python3
"""
Pipeline Orchestrator - Newsletter Generation Pipeline

This script orchestrates the complete execution of stages 01-05 for multiple
newsletters defined in config/newsletters.yml.

Process:
1. Load newsletter configurations from YAML
2. Run Stage 01 once for all newsletters (common extraction)
3. For each newsletter:
   - Stage 02: Filter & Classify
   - Stage 03: Ranker
   - Stage 04: Extract Content
   - Stage 05: Generate Newsletter (AI-powered narrative generation)
4. Track execution state in database (pipeline_runs table)
5. Continue on errors (log and move to next newsletter)

Author: Newsletter Utils Team
Created: 2025-11-13
"""

import os
import sys
import yaml
import argparse
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from common.postgres_db import PostgreSQLURLDatabase
from common.logging_utils import setup_rotating_file_logger

# Load environment variables
load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)


def setup_logging(run_date: str) -> str:
    """
    Setup logging for orchestrator.

    Args:
        run_date: Date string in YYYY-MM-DD format

    Returns:
        Path to log file
    """
    # Create logs directory for this date
    log_file = setup_rotating_file_logger(
        run_date,
        "orchestrator.log",
        log_level=logging.INFO,
        verbose=False,
    )

    logger.info(f"Orchestrator logging initialized: {log_file}")
    return str(log_file)


def load_newsletter_config(config_path: str) -> List[Dict[str, Any]]:
    """
    Load newsletter configurations from YAML file.

    Args:
        config_path: Path to newsletters.yml

    Returns:
        List of newsletter configuration dictionaries

    Raises:
        ValueError: If config file is invalid
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        newsletters = config.get('newsletters', [])

        if not newsletters:
            raise ValueError("No newsletters found in configuration")

        logger.info(f"Loaded {len(newsletters)} newsletter configurations from {config_path}")
        return newsletters

    except Exception as e:
        logger.error(f"Failed to load newsletter config from {config_path}: {e}")
        raise


def run_stage_01(date: str, dry_run: bool = False) -> bool:
    """
    Run Stage 01: URL Extraction (common for all newsletters).

    Args:
        date: Date string (YYYY-MM-DD)
        dry_run: If True, only show what would be executed

    Returns:
        True if successful, False otherwise
    """
    logger.info("="*80)
    logger.info("STAGE 01: URL EXTRACTION (COMMON)")
    logger.info("="*80)

    cmd = [
        "venv/bin/python",
        "stages/01_extract_urls.py",
        "--date", date
    ]

    if dry_run:
        logger.info(f"[DRY RUN] Would execute: {' '.join(cmd)}")
        return True

    try:
        logger.info(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        logger.info("Stage 01 completed successfully")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Stage 01 failed with exit code {e.returncode}")
        return False


def build_stage_02_command(newsletter: Dict[str, Any]) -> List[str]:
    """
    Build command for Stage 02 based on newsletter config.

    Args:
        newsletter: Newsletter configuration dictionary

    Returns:
        List of command arguments
    """
    cmd = ["venv/bin/python", "stages/02_filter_for_newsletters.py"]

    # Date/time arguments
    if 'date' in newsletter:
        cmd.extend(["--date", newsletter['date']])
    elif 'start' in newsletter and 'end' in newsletter:
        cmd.extend(["--start", newsletter['start'], "--end", newsletter['end']])

    # Sources filter
    if 'sources' in newsletter and newsletter['sources']:
        cmd.extend(["--sources"] + newsletter['sources'])

    # Stage 02 specific params
    stage02 = newsletter.get('stage02', {})

    if 'categories' in stage02 and stage02['categories']:
        cmd.extend(["--categories"] + stage02['categories'])

    if stage02.get('no_temporality', False):
        cmd.append("--no-temporality")

    if stage02.get('force', False):
        cmd.append("--force")

    # Global flags
    if newsletter.get('verbose', False):
        cmd.append("--verbose")

    if 'db_path' in newsletter:
        cmd.extend(["--db", newsletter['db_path']])

    return cmd


def build_stage_03_command(newsletter: Dict[str, Any]) -> List[str]:
    """
    Build command for Stage 03 based on newsletter config (DB-centric).

    Args:
        newsletter: Newsletter configuration dictionary

    Returns:
        List of command arguments
    """
    cmd = ["venv/bin/python", "stages/03_ranker.py"]

    # Newsletter name (required)
    cmd.extend(["--newsletter-name", newsletter['name']])

    # Date argument (required)
    date = newsletter.get('date', datetime.now().strftime('%Y-%m-%d'))
    cmd.extend(["--date", date])

    # Categories come from config (for filtering)
    categories = newsletter.get('categories', [])
    if categories:
        cmd.extend(["--categories"] + categories)

    # Sources filter
    if 'sources' in newsletter and newsletter['sources']:
        cmd.extend(["--sources"] + newsletter['sources'])

    # Articles count (simplified - replaces max_headlines/max_featured)
    articles_count = newsletter.get('articles_count', 20)
    cmd.extend(["--articles-count", str(articles_count)])

    # Ranker method
    ranker_method = newsletter.get('ranker_method', 'level_scoring')
    cmd.extend(["--ranker-method", ranker_method])

    # Force flag
    if newsletter.get('force', False):
        cmd.append("--force")

    # Global flags
    if newsletter.get('verbose', False):
        cmd.append("--verbose")

    return cmd


def build_stage_04_command(newsletter: Dict[str, Any]) -> List[str]:
    """
    Build command for Stage 04 based on newsletter config (DB-centric).

    Args:
        newsletter: Newsletter configuration dictionary

    Returns:
        List of command arguments
    """
    cmd = ["venv/bin/python", "stages/04_extract_content.py"]

    # Newsletter name (required)
    cmd.extend(["--newsletter-name", newsletter['name']])

    # Date argument (required)
    date = newsletter.get('date', datetime.now().strftime('%Y-%m-%d'))
    cmd.extend(["--date", date])

    # Force flag
    if newsletter.get('force', False):
        cmd.append("--force")

    # Skip paywall check
    if newsletter.get('skip_paywall_check', False):
        cmd.append("--skip-paywall-check")

    # Global flags
    if newsletter.get('verbose', False):
        cmd.append("--verbose")

    return cmd


def build_stage_05_command(newsletter: Dict[str, Any]) -> List[str]:
    """
    Build command for Stage 05 based on newsletter config (DB-centric).

    Args:
        newsletter: Newsletter configuration dictionary

    Returns:
        List of command arguments
    """
    cmd = ["venv/bin/python", "stages/05_generate_newsletters.py"]

    # Newsletter name (required)
    cmd.extend(["--newsletter-name", newsletter['name']])

    # Date argument (required)
    date = newsletter.get('date', datetime.now().strftime('%Y-%m-%d'))
    cmd.extend(["--date", date])

    # Output format
    output_format = newsletter.get('output_format', 'markdown')
    cmd.extend(["--output-format", output_format])

    # Template
    template = newsletter.get('template', 'default')
    cmd.extend(["--template", template])

    # Skip LLM flag
    if newsletter.get('skip_llm', False):
        cmd.append("--skip-llm")

    # Force flag
    if newsletter.get('force', False):
        cmd.append("--force")

    # Related window days (v3.3: historical cluster context)
    related_window_days = newsletter.get('related_window_days', 0)
    if related_window_days > 0:
        cmd.extend(["--related-window-days", str(related_window_days)])

    # Global flags
    if newsletter.get('verbose', False):
        cmd.append("--verbose")

    return cmd


def set_env_for_stage(newsletter: Dict[str, Any], stage: int):
    """
    Set environment variables for a specific stage based on newsletter config.

    Args:
        newsletter: Newsletter configuration dictionary
        stage: Stage number (2, 3, 4, or 5)
    """
    if stage == 2:
        stage_config = newsletter.get('stage02', {})
        if 'batch_size' in stage_config:
            os.environ['STAGE02_BATCH_SIZE'] = str(stage_config['batch_size'])
        if 'model_classifier' in stage_config:
            os.environ['MODEL_CLASSIFIER'] = stage_config['model_classifier']

    elif stage == 3:
        stage_config = newsletter.get('stage03', {})
        if 'ranker_method' in stage_config:
            os.environ['RANKER_METHOD'] = stage_config['ranker_method']
        if 'ranker_top_x' in stage_config:
            os.environ['RANKER_TOP_X'] = str(stage_config['ranker_top_x'])
        # Clustering configuration removed - deduplication now handled in Stage 05 prompt
        # if 'enable_clustering' in stage_config:
        #     os.environ['RANKER_ENABLE_CLUSTERING'] = str(stage_config['enable_clustering']).lower()
        # if 'clustering_multiplier' in stage_config:
        #     os.environ['RANKER_CLUSTERING_MULTIPLIER'] = str(stage_config['clustering_multiplier'])
        if 'model_ranker' in stage_config:
            os.environ['MODEL_RANKER'] = stage_config['model_ranker']

    elif stage == 4:
        stage_config = newsletter.get('stage04', {})
        if 'timeout' in stage_config:
            os.environ['STAGE04_TIMEOUT'] = str(stage_config['timeout'])
        if 'min_word_count' in stage_config:
            os.environ['STAGE04_MIN_WORD_COUNT'] = str(stage_config['min_word_count'])
        if 'max_word_count' in stage_config:
            os.environ['STAGE04_MAX_WORD_COUNT'] = str(stage_config['max_word_count'])
        if 'model_paywall_validator' in stage_config:
            os.environ['MODEL_PAYWALL_VALIDATOR'] = stage_config['model_paywall_validator']
        if 'model_xpath_discovery' in stage_config:
            os.environ['MODEL_XPATH_DISCOVERY'] = stage_config['model_xpath_discovery']
        if 'archive_wait_time' in stage_config:
            os.environ['STAGE04_ARCHIVE_WAIT_TIME'] = str(stage_config['archive_wait_time'])
        if 'max_retries' in stage_config:
            os.environ['STAGE04_MAX_RETRIES'] = str(stage_config['max_retries'])

    elif stage == 5:
        stage_config = newsletter.get('stage05', {})
        if 'model_writer' in stage_config:
            os.environ['MODEL_WRITER'] = stage_config['model_writer']
        if 'cantidad_articulos' in stage_config:
            os.environ['STAGE05_CANTIDAD_ARTICULOS'] = str(stage_config['cantidad_articulos'])
        if 'max_content_tokens' in stage_config:
            os.environ['STAGE05_MAX_CONTENT_TOKENS'] = str(stage_config['max_content_tokens'])

        # Set newsletter title and description from config
        if 'title' in newsletter:
            os.environ['NEWSLETTER_TITLE'] = newsletter['title']
        if 'description' in newsletter:
            os.environ['NEWSLETTER_DESCRIPTION'] = newsletter['description']

        # CRITICAL: Pass expected categories from stage02 config to Stage 05 for validation
        # Stage 05 will verify that the ranked JSON used matches these expected categories
        stage02_config = newsletter.get('stage02', {})
        if 'categories' in stage02_config and stage02_config['categories']:
            # Convert list to comma-separated string for env var
            categories_str = ','.join(stage02_config['categories'])
            os.environ['NEWSLETTER_EXPECTED_CATEGORIES'] = categories_str
            logger.debug(f"Stage 05: Setting expected categories: {categories_str}")


def find_ranked_output(newsletter: Dict[str, Any]) -> Optional[str]:
    """
    Find the ranked JSON output file for a newsletter from Stage 03.

    Matches based on:
    - Date
    - Categories (if newsletter has stage02 config with categories)

    Returns most recent file matching these criteria.

    Args:
        newsletter: Newsletter configuration dictionary

    Returns:
        Path to ranked JSON file, or None if not found
    """
    import json

    output_dir = Path("data") / "processed"
    if not output_dir.exists():
        return None

    # Get date for filename pattern
    date = newsletter.get('date')
    if not date and 'start' in newsletter:
        date = newsletter['start'].split('T')[0]

    if not date:
        logger.warning("Cannot determine date for finding ranked output")
        return None

    # Get expected categories from newsletter config
    stage02_config = newsletter.get('stage02', {})
    expected_categories = stage02_config.get('categories', [])

    if expected_categories:
        # Normalize expected categories to IDs (lowercase)
        expected_normalized = sorted([cat.strip().lower() for cat in expected_categories])
        logger.info(f"Looking for ranked file with categories: {expected_normalized}")
    else:
        expected_normalized = None
        logger.info("Looking for ranked file with no category filter (all categories)")

    # Find all ranked files for this date
    pattern = f"ranked_{date}_*.json"
    matching_files = list(output_dir.glob(pattern))

    if not matching_files:
        return None

    # Filter by categories if newsletter has specific requirements
    category_matched_files = []
    for filepath in matching_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            execution_params = data.get('execution_params', {})
            file_categories = execution_params.get('categories_filter')

            if expected_normalized:
                # Newsletter expects specific categories
                if file_categories:
                    file_normalized = sorted([cat.strip().lower() for cat in file_categories])
                    if file_normalized == expected_normalized:
                        category_matched_files.append(filepath)
                        logger.info(f"✓ Match: {filepath.name} has correct categories: {file_categories}")
                    else:
                        logger.info(f"✗ Skip: {filepath.name} has wrong categories: {file_categories} (expected: {expected_categories})")
                else:
                    logger.info(f"✗ Skip: {filepath.name} has no category filter (expected: {expected_categories})")
            else:
                # Newsletter accepts all categories
                if file_categories is None:
                    category_matched_files.append(filepath)
                    logger.info(f"✓ Match: {filepath.name} has no category filter")
                else:
                    logger.info(f"✗ Skip: {filepath.name} has category filter: {file_categories} (expected: all)")

        except Exception as e:
            logger.warning(f"Failed to read {filepath}: {e}")
            continue

    if not category_matched_files:
        logger.warning(
            f"No ranked files found matching date={date} and categories={expected_categories}. "
            f"Found {len(matching_files)} files with matching date but wrong categories."
        )
        return None

    # Return most recent category-matched file (sorted by filename which includes timestamp)
    most_recent = sorted(category_matched_files, reverse=True)[0]
    logger.info(f"Found ranked output: {most_recent}")
    return str(most_recent)


def find_newsletter_output(newsletter: Dict[str, Any]) -> Optional[str]:
    """
    Find the newsletter output file for a newsletter from Stage 05.

    Args:
        newsletter: Newsletter configuration dictionary

    Returns:
        Path to most recent newsletter file, or None if not found
    """
    output_dir = Path("data") / "newsletters"
    if not output_dir.exists():
        return None

    # Get date for filename pattern
    date = newsletter.get('date')
    if not date and 'start' in newsletter:
        date = newsletter['start'].split('T')[0]

    if not date:
        logger.warning("Cannot determine date for finding newsletter output")
        return None

    # Find most recent newsletter file for this newsletter and date
    newsletter_name = newsletter['name']
    pattern = f"newsletter_{newsletter_name}_{date}_*.md"
    matching_files = list(output_dir.glob(pattern))

    # Also check for HTML output if markdown not found
    if not matching_files:
        pattern = f"newsletter_{newsletter_name}_{date}_*.html"
        matching_files = list(output_dir.glob(pattern))

    if matching_files:
        # Return most recent (sorted by filename which includes timestamp)
        most_recent = sorted(matching_files, reverse=True)[0]
        logger.info(f"Found newsletter output: {most_recent}")
        return str(most_recent)

    return None


def run_newsletter_pipeline(
    newsletter: Dict[str, Any],
    db: SQLiteURLDatabase,
    dry_run: bool = False,
    force_all: bool = False,
    debug: bool = False
) -> Dict[str, Any]:
    """
    Run complete pipeline for a single newsletter (stages 02-05).

    REFACTORED: DB-centric approach with debug reports.

    Args:
        newsletter: Newsletter configuration dictionary
        db: Database instance
        dry_run: If True, only show what would be executed
        force_all: If True, force execution of all stages
        debug: If True, generate debug report

    Returns:
        Dictionary with execution results and metrics
    """
    import time
    import json as json_module

    newsletter_name = newsletter['name']
    date = newsletter.get('date', datetime.now().strftime('%Y-%m-%d'))

    logger.info("="*80)
    logger.info(f"NEWSLETTER: {newsletter_name}")
    logger.info("="*80)

    # Create pipeline execution record with config snapshot
    execution_id = db.create_pipeline_execution(
        newsletter_name=newsletter_name,
        run_date=date,
        config_snapshot=newsletter
    )
    logger.info(f"Created pipeline execution ID: {execution_id}")

    pipeline_start_time = time.time()
    last_successful_stage = 1  # Stage 01 is assumed completed before this function

    # Initialize debug report structure
    debug_data = {
        'newsletter_name': newsletter_name,
        'run_date': date,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'stages': {},
        'summary': {}
    }

    results = {
        'newsletter_name': newsletter_name,
        'date': date,
        'stages': {},
        'debug_data': debug_data
    }

    # Stage 02: Filter & Classify
    logger.info("-"*80)
    logger.info("STAGE 02: FILTER & CLASSIFY")
    logger.info("-"*80)

    run_id_02 = db.start_pipeline_run(newsletter_name, date, 2)
    db.link_pipeline_run_to_execution(run_id_02, execution_id)
    set_env_for_stage(newsletter, 2)
    cmd_02 = build_stage_02_command(newsletter)

    # Note: --force-all does NOT force Stage 02 reclassification (expensive LLM calls)
    # Stage 02 will only classify URLs that don't have categoria_tematica set
    # If you need to force reclassification, run Stage 02 manually with --force
    # if force_all and '--force' not in cmd_02:
    #     cmd_02.append('--force')

    if dry_run:
        logger.info(f"[DRY RUN] Would execute: {' '.join(cmd_02)}")
        results['stages'][2] = {'status': 'dry_run', 'command': ' '.join(cmd_02)}
    else:
        try:
            logger.info(f"Executing: {' '.join(cmd_02)}")
            subprocess.run(cmd_02, check=True, capture_output=False, text=True)
            db.complete_pipeline_run(run_id_02, 'completed')
            last_successful_stage = 2
            results['stages'][2] = {'status': 'completed'}
            logger.info("Stage 02 completed successfully")
        except subprocess.CalledProcessError as e:
            error_msg = f"Stage 02 failed with exit code {e.returncode}"
            logger.error(error_msg)
            db.complete_pipeline_run(run_id_02, 'failed', error_message=error_msg)
            db.update_pipeline_execution_status(execution_id, 'failed', last_successful_stage)
            results['stages'][2] = {'status': 'failed', 'error': error_msg}
            return results  # Stop here if Stage 02 fails

    # Stage 03: Ranker
    logger.info("-"*80)
    logger.info("STAGE 03: RANKER")
    logger.info("-"*80)

    stage_03_start = time.time()
    run_id_03 = db.start_pipeline_run(newsletter_name, date, 3)
    db.link_pipeline_run_to_execution(run_id_03, execution_id)
    cmd_03 = build_stage_03_command(newsletter)

    if force_all and '--force' not in cmd_03:
        cmd_03.append('--force')

    if dry_run:
        logger.info(f"[DRY RUN] Would execute: {' '.join(cmd_03)}")
        results['stages'][3] = {'status': 'dry_run', 'command': ' '.join(cmd_03)}
    else:
        try:
            logger.info(f"Executing: {' '.join(cmd_03)}")
            subprocess.run(cmd_03, check=True, capture_output=False, text=True)

            # Stage 03 now writes to DB, no JSON output to find
            db.complete_pipeline_run(run_id_03, 'completed')
            last_successful_stage = 3

            stage_03_duration = time.time() - stage_03_start
            results['stages'][3] = {'status': 'completed', 'duration': stage_03_duration}
            debug_data['stages']['stage_03'] = {
                'duration': stage_03_duration,
                'status': 'completed'
            }
            logger.info(f"Stage 03 completed successfully (DB-centric)")

        except subprocess.CalledProcessError as e:
            error_msg = f"Stage 03 failed with exit code {e.returncode}"
            logger.error(error_msg)
            stage_03_duration = time.time() - stage_03_start
            db.complete_pipeline_run(run_id_03, 'failed', error_message=error_msg)
            db.update_pipeline_execution_status(execution_id, 'failed', last_successful_stage)
            results['stages'][3] = {'status': 'failed', 'error': error_msg}
            debug_data['stages']['stage_03'] = {
                'duration': stage_03_duration,
                'status': 'failed',
                'error': error_msg
            }
            return results  # Stop here if Stage 03 fails

    # Stage 04: Extract Content
    logger.info("-"*80)
    logger.info("STAGE 04: EXTRACT CONTENT")
    logger.info("-"*80)

    stage_04_start = time.time()
    run_id_04 = db.start_pipeline_run(newsletter_name, date, 4)
    db.link_pipeline_run_to_execution(run_id_04, execution_id)
    cmd_04 = build_stage_04_command(newsletter)

    if force_all and '--force' not in cmd_04:
        cmd_04.append('--force')

    if dry_run:
        logger.info(f"[DRY RUN] Would execute: {' '.join(cmd_04)}")
        results['stages'][4] = {'status': 'dry_run', 'command': ' '.join(cmd_04)}
    else:
        try:
            logger.info(f"Executing: {' '.join(cmd_04)}")
            subprocess.run(cmd_04, check=True, capture_output=False, text=True)

            stage_04_duration = time.time() - stage_04_start
            db.complete_pipeline_run(run_id_04, 'completed')
            last_successful_stage = 4
            results['stages'][4] = {'status': 'completed', 'duration': stage_04_duration}
            debug_data['stages']['stage_04'] = {
                'duration': stage_04_duration,
                'status': 'completed'
            }
            logger.info("Stage 04 completed successfully")

        except subprocess.CalledProcessError as e:
            error_msg = f"Stage 04 failed with exit code {e.returncode}"
            logger.error(error_msg)
            stage_04_duration = time.time() - stage_04_start
            db.complete_pipeline_run(run_id_04, 'failed', error_message=error_msg)
            db.update_pipeline_execution_status(execution_id, 'partial', last_successful_stage)
            results['stages'][4] = {'status': 'failed', 'error': error_msg}
            debug_data['stages']['stage_04'] = {
                'duration': stage_04_duration,
                'status': 'failed',
                'error': error_msg
            }
            # Note: Stage 04 failure doesn't stop pipeline, continues to Stage 05

    # Stage 05: Generate Newsletter
    logger.info("-"*80)
    logger.info("STAGE 05: GENERATE NEWSLETTER")
    logger.info("-"*80)

    stage_05_start = time.time()
    run_id_05 = db.start_pipeline_run(newsletter_name, date, 5)
    db.link_pipeline_run_to_execution(run_id_05, execution_id)
    cmd_05 = build_stage_05_command(newsletter)

    if force_all and '--force' not in cmd_05:
        cmd_05.append('--force')

    if dry_run:
        logger.info(f"[DRY RUN] Would execute: {' '.join(cmd_05)}")
        results['stages'][5] = {'status': 'dry_run', 'command': ' '.join(cmd_05)}
    else:
        try:
            logger.info(f"Executing: {' '.join(cmd_05)}")
            subprocess.run(cmd_05, check=True, capture_output=False, text=True)

            stage_05_duration = time.time() - stage_05_start
            db.complete_pipeline_run(run_id_05, 'completed')
            last_successful_stage = 5
            results['stages'][5] = {'status': 'completed', 'duration': stage_05_duration}
            debug_data['stages']['stage_05'] = {
                'duration': stage_05_duration,
                'status': 'completed'
            }
            logger.info("Stage 05 completed successfully")

        except subprocess.CalledProcessError as e:
            error_msg = f"Stage 05 failed with exit code {e.returncode}"
            logger.error(error_msg)
            stage_05_duration = time.time() - stage_05_start
            db.complete_pipeline_run(run_id_05, 'failed', error_message=error_msg)
            db.update_pipeline_execution_status(execution_id, 'partial', last_successful_stage)
            results['stages'][5] = {'status': 'failed', 'error': error_msg}
            debug_data['stages']['stage_05'] = {
                'duration': stage_05_duration,
                'status': 'failed',
                'error': error_msg
            }

    # Calculate total pipeline duration
    pipeline_duration = time.time() - pipeline_start_time
    debug_data['total_duration'] = pipeline_duration

    # Mark execution as completed if all stages succeeded
    if last_successful_stage == 5:
        db.update_pipeline_execution_status(execution_id, 'completed', last_successful_stage)
        logger.info(f"Pipeline execution {execution_id} completed successfully")
    elif last_successful_stage < 5:
        # Already marked as failed/partial in stage error handlers
        logger.warning(f"Pipeline execution {execution_id} completed partially (last_stage={last_successful_stage})")

    # Generate debug report if enabled
    if debug and not dry_run:
        logger.info("-"*80)
        logger.info("GENERATING DEBUG REPORT")
        logger.info("-"*80)

        try:
            # Save to database
            db.save_debug_report(newsletter_name, date, debug_data)

            # Also save as JSON file
            debug_dir = Path("data") / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)

            debug_filename = f"debug_report_{newsletter_name}_{date}.json"
            debug_path = debug_dir / debug_filename

            with open(debug_path, 'w', encoding='utf-8') as f:
                json_module.dump(debug_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Debug report saved: {debug_path}")
            results['debug_report'] = str(debug_path)

        except Exception as e:
            logger.error(f"Failed to generate debug report: {e}")

    return results


def get_url_metrics_for_newsletter(
    db: SQLiteURLDatabase,
    newsletter: Dict[str, Any],
    date: str
) -> Dict[str, Any]:
    """
    Get URL processing metrics for a specific newsletter.

    Args:
        db: Database instance
        newsletter: Newsletter configuration
        date: Date string (YYYY-MM-DD)

    Returns:
        Dictionary with URL metrics
    """
    import sqlite3

    metrics = {
        'urls_classified': 0,
        'urls_ranked': 0,
        'extraction_success': 0,
        'extraction_failed': 0,
        'extraction_pending': 0,
        'methods': {},
        'avg_word_count': 0,
        'failed_urls': []
    }

    try:
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()

        # Get categories for this newsletter
        stage02 = newsletter.get('stage02', {})
        categories = stage02.get('categories', [])

        # URLs classified (Stage 02)
        if categories:
            placeholders = ','.join('?' * len(categories))
            query = f"""
                SELECT COUNT(*)
                FROM urls
                WHERE categorized_at >= ?
                AND categoria_tematica IN ({placeholders})
            """
            cursor.execute(query, [f"{date} 00:00:00"] + categories)
        else:
            cursor.execute("""
                SELECT COUNT(*)
                FROM urls
                WHERE categorized_at >= ?
            """, [f"{date} 00:00:00"])

        metrics['urls_classified'] = cursor.fetchone()[0]

        # Extraction stats (Stage 04)
        if categories:
            # Success count
            query = f"""
                SELECT COUNT(*)
                FROM urls
                WHERE categorized_at >= ?
                AND categoria_tematica IN ({placeholders})
                AND extraction_status = 'success'
            """
            cursor.execute(query, [f"{date} 00:00:00"] + categories)
            metrics['extraction_success'] = cursor.fetchone()[0]

            # Failed count
            query = f"""
                SELECT COUNT(*)
                FROM urls
                WHERE categorized_at >= ?
                AND categoria_tematica IN ({placeholders})
                AND extraction_status = 'failed'
            """
            cursor.execute(query, [f"{date} 00:00:00"] + categories)
            metrics['extraction_failed'] = cursor.fetchone()[0]

            # Pending count
            query = f"""
                SELECT COUNT(*)
                FROM urls
                WHERE categorized_at >= ?
                AND categoria_tematica IN ({placeholders})
                AND (extraction_status IS NULL OR extraction_status = 'pending')
            """
            cursor.execute(query, [f"{date} 00:00:00"] + categories)
            metrics['extraction_pending'] = cursor.fetchone()[0]

            # Methods distribution
            query = f"""
                SELECT content_extraction_method, COUNT(*)
                FROM urls
                WHERE categorized_at >= ?
                AND categoria_tematica IN ({placeholders})
                AND extraction_status = 'success'
                GROUP BY content_extraction_method
            """
            cursor.execute(query, [f"{date} 00:00:00"] + categories)
            for method, count in cursor.fetchall():
                if method:
                    metrics['methods'][method] = count

            # Average word count
            query = f"""
                SELECT AVG(word_count)
                FROM urls
                WHERE categorized_at >= ?
                AND categoria_tematica IN ({placeholders})
                AND extraction_status = 'success'
                AND word_count > 0
            """
            cursor.execute(query, [f"{date} 00:00:00"] + categories)
            avg_wc = cursor.fetchone()[0]
            metrics['avg_word_count'] = int(avg_wc) if avg_wc else 0

            # Failed URLs (for error reporting)
            query = f"""
                SELECT url, extraction_error
                FROM urls
                WHERE categorized_at >= ?
                AND categoria_tematica IN ({placeholders})
                AND extraction_status = 'failed'
                LIMIT 5
            """
            cursor.execute(query, [f"{date} 00:00:00"] + categories)
            metrics['failed_urls'] = cursor.fetchall()

        conn.close()

    except Exception as e:
        logger.warning(f"Failed to get URL metrics: {e}")

    return metrics


def get_execution_times(
    db: SQLiteURLDatabase,
    newsletter_name: str,
    date: str
) -> Dict[int, float]:
    """
    Get execution times for each stage of a newsletter.

    Args:
        db: Database instance
        newsletter_name: Name of newsletter
        date: Date string (YYYY-MM-DD)

    Returns:
        Dictionary mapping stage number to execution time in seconds
    """
    import sqlite3

    times = {}

    try:
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT stage, started_at, completed_at
            FROM pipeline_runs
            WHERE newsletter_name = ?
            AND run_date = ?
            AND started_at IS NOT NULL
            AND completed_at IS NOT NULL
            ORDER BY stage
        """, [newsletter_name, date])

        for stage, started_at, completed_at in cursor.fetchall():
            try:
                start = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                end = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                duration = (end - start).total_seconds()
                times[stage] = duration
            except Exception as e:
                logger.warning(f"Failed to calculate time for stage {stage}: {e}")

        conn.close()

    except Exception as e:
        logger.warning(f"Failed to get execution times: {e}")

    return times


def get_token_costs(date: str) -> Dict[str, float]:
    """
    Get token costs for a specific date from logs/token_usage.csv.

    Args:
        date: Date string (YYYY-MM-DD)

    Returns:
        Dictionary with total costs per stage
    """
    import csv

    costs = {}
    token_file = Path("logs") / "token_usage.csv"

    if not token_file.exists():
        return costs

    try:
        with open(token_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('timestamp', '').startswith(date):
                    stage = row.get('stage', 'unknown')
                    cost = float(row.get('cost_usd', 0))
                    costs[stage] = costs.get(stage, 0) + cost

    except Exception as e:
        logger.warning(f"Failed to read token costs: {e}")

    return costs


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def generate_enhanced_summary(
    all_results: List[Dict[str, Any]],
    newsletters: List[Dict[str, Any]],
    db: SQLiteURLDatabase,
    date: str
):
    """
    Generate enhanced summary with detailed metrics.

    Args:
        all_results: List of execution results
        newsletters: List of newsletter configurations
        db: Database instance
        date: Run date (YYYY-MM-DD)
    """
    logger.info("")
    logger.info("="*80)
    logger.info(f"ORCHESTRATOR SUMMARY - {date}")
    logger.info("="*80)

    # Get token costs for the day
    token_costs = get_token_costs(date)
    total_cost = sum(token_costs.values())

    # Process each newsletter
    for result in all_results:
        name = result['newsletter_name']
        logger.info(f"\n{name}:")

        # Find newsletter config
        newsletter_config = next((n for n in newsletters if n['name'] == name), None)

        if 'error' in result:
            logger.info(f"  ✗ ERROR: {result['error']}")
            continue

        # Get URL metrics
        url_metrics = get_url_metrics_for_newsletter(db, newsletter_config, date) if newsletter_config else {}

        # Get execution times
        exec_times = get_execution_times(db, name, date)
        total_time = sum(exec_times.values())

        # Stage-by-stage breakdown
        stages = result.get('stages', {})

        # Stage 02
        if 2 in stages:
            stage2 = stages[2]
            status_icon = "✓" if stage2['status'] == 'completed' else "✗"
            time_str = format_duration(exec_times.get(2, 0)) if 2 in exec_times else "N/A"
            urls_classified = url_metrics.get('urls_classified', 0)
            logger.info(f"  {status_icon} Stage 2: {stage2['status']} ({time_str}) - {urls_classified} URLs classified")

            # Show parameters
            if newsletter_config:
                stage02_config = newsletter_config.get('stage02', {})
                categories = stage02_config.get('categories', [])
                if categories:
                    logger.info(f"    → Categories: {', '.join(categories)}")

            if 'error' in stage2:
                logger.info(f"    → Error: {stage2['error']}")

        # Stage 03
        if 3 in stages:
            stage3 = stages[3]
            status_icon = "✓" if stage3['status'] == 'completed' else "✗"
            time_str = format_duration(exec_times.get(3, 0)) if 3 in exec_times else "N/A"

            # Get max_headlines from config
            max_headlines = "N/A"
            if newsletter_config:
                stage03_config = newsletter_config.get('stage03', {})
                max_headlines = stage03_config.get('max_headlines', stage03_config.get('top_per_category', 'N/A'))

            logger.info(f"  {status_icon} Stage 3: {stage3['status']} ({time_str}) - Top {max_headlines} ranked")

            if 'output' in stage3:
                output_filename = Path(stage3['output']).name
                logger.info(f"    → Output: {output_filename}")
                logger.info(f"    → Full path: {stage3['output']}")

            if 'error' in stage3:
                logger.info(f"    → Error: {stage3['error']}")

        # Stage 04
        if 4 in stages:
            stage4 = stages[4]
            status_icon = "✓" if stage4['status'] == 'completed' else "✗"
            time_str = format_duration(exec_times.get(4, 0)) if 4 in exec_times else "N/A"

            success = url_metrics.get('extraction_success', 0)
            failed = url_metrics.get('extraction_failed', 0)
            total_processed = success + failed

            if total_processed > 0:
                success_rate = (success / total_processed) * 100
                logger.info(f"  {status_icon} Stage 4: {stage4['status']} ({time_str}) - {total_processed} URLs processed")
                logger.info(f"    → Success: {success}/{total_processed} ({success_rate:.0f}%)")

                # Methods breakdown
                methods = url_metrics.get('methods', {})
                if methods:
                    methods_str = ", ".join([f"{m}({c})" for m, c in methods.items()])
                    logger.info(f"    → Methods: {methods_str}")

                # Word count
                avg_wc = url_metrics.get('avg_word_count', 0)
                if avg_wc > 0:
                    logger.info(f"    → Avg word count: {avg_wc} words")

                # Failed URLs (if any)
                if failed > 0:
                    logger.info(f"    → Failed: {failed} URLs")
                    failed_urls = url_metrics.get('failed_urls', [])
                    for url, error in failed_urls[:3]:  # Show max 3
                        short_url = url[:50] + "..." if len(url) > 50 else url
                        error_msg = error[:60] + "..." if error and len(error) > 60 else error
                        logger.info(f"      • {short_url}")
                        if error_msg:
                            logger.info(f"        Error: {error_msg}")

            else:
                logger.info(f"  {status_icon} Stage 4: {stage4['status']} ({time_str})")

            if 'error' in stage4:
                logger.info(f"    → Error: {stage4['error']}")

        # Stage 05
        if 5 in stages:
            stage5 = stages[5]
            status_icon = "✓" if stage5['status'] == 'completed' else "✗"
            time_str = format_duration(exec_times.get(5, 0)) if 5 in exec_times else "N/A"

            logger.info(f"  {status_icon} Stage 5: {stage5['status']} ({time_str})")

            if 'output' in stage5:
                output_filename = Path(stage5['output']).name
                logger.info(f"    → Output: {output_filename}")

            if 'warning' in stage5:
                logger.info(f"    → Warning: {stage5['warning']}")

            if 'error' in stage5:
                logger.info(f"    → Error: {stage5['error']}")

        # Total time for newsletter
        if total_time > 0:
            logger.info(f"\n  Total time: {format_duration(total_time)}")

    # Overall summary
    logger.info("\n" + "-"*80)
    logger.info("Summary:")
    logger.info(f"  Newsletters: {len(all_results)} processed")

    # Count completed newsletters (Stage 05 if available, otherwise Stage 04)
    completed = 0
    for r in all_results:
        stages = r.get('stages', {})
        if 5 in stages and stages[5].get('status') == 'completed':
            completed += 1
        elif 5 not in stages and 4 in stages and stages[4].get('status') == 'completed':
            completed += 1

    success_rate = (completed / len(all_results) * 100) if all_results else 0
    logger.info(f"  Success rate: {success_rate:.0f}% ({completed}/{len(all_results)} completed)")

    # Total URLs extracted
    total_extracted = 0
    for result in all_results:
        newsletter_config = next((n for n in newsletters if n['name'] == result['newsletter_name']), None)
        if newsletter_config:
            url_metrics = get_url_metrics_for_newsletter(db, newsletter_config, date)
            total_extracted += url_metrics.get('extraction_success', 0)

    if total_extracted > 0:
        logger.info(f"  Total URLs extracted: {total_extracted}")

    # Total execution time
    total_exec_time = 0
    for result in all_results:
        exec_times = get_execution_times(db, result['newsletter_name'], date)
        total_exec_time += sum(exec_times.values())

    if total_exec_time > 0:
        logger.info(f"  Total time: {format_duration(total_exec_time)}")

    # Total cost
    if total_cost > 0:
        logger.info(f"  Total cost: ~${total_cost:.3f}")

    logger.info("")
    logger.info("Orchestrator completed")
    logger.info("="*80)


def handle_resume(db: SQLiteURLDatabase, resume_arg: str, exec_id_arg: Optional[int]) -> Dict[str, Any]:
    """
    Handle --resume flag to continue failed pipeline execution.

    Args:
        db: Database instance
        resume_arg: Resume argument ('auto', date string, or numeric exec_id)
        exec_id_arg: Optional execution ID from --exec-id flag

    Returns:
        Newsletter configuration dictionary with resume metadata

    Raises:
        ValueError: If no failed execution found or invalid parameters
    """
    import json

    execution = None

    # Priority 1: --exec-id flag
    if exec_id_arg:
        execution = db.get_pipeline_execution_by_id(exec_id_arg)
        if not execution:
            raise ValueError(f"Execution ID {exec_id_arg} not found")
        if execution['status'] not in ('failed', 'partial'):
            raise ValueError(f"Execution {exec_id_arg} has status '{execution['status']}' (only 'failed' or 'partial' can be resumed)")

    # Priority 2: Date string (YYYY-MM-DD)
    elif resume_arg and resume_arg != 'auto' and '-' in resume_arg:
        # Try to find newsletter name from last execution on this date
        # We need to query for any newsletter on this date
        # For simplicity, we'll get the last failed execution and filter by date
        execution = db.get_last_failed_execution()
        if execution and execution['run_date'] != resume_arg:
            raise ValueError(f"Last failed execution is for date {execution['run_date']}, not {resume_arg}")

    # Priority 3: Auto (last failed)
    elif resume_arg == 'auto' or resume_arg is None:
        execution = db.get_last_failed_execution()
        if not execution:
            raise ValueError("No failed or partial pipeline executions found")

    # Priority 4: Numeric ID as string
    elif resume_arg and resume_arg.isdigit():
        exec_id = int(resume_arg)
        execution = db.get_pipeline_execution_by_id(exec_id)
        if not execution:
            raise ValueError(f"Execution ID {exec_id} not found")

    else:
        raise ValueError(f"Invalid resume argument: {resume_arg}")

    # Parse config snapshot
    config_snapshot = json.loads(execution['config_snapshot'])

    logger.info("="*80)
    logger.info("RESUMING FAILED PIPELINE EXECUTION")
    logger.info("="*80)
    logger.info(f"Execution ID: {execution['id']}")
    logger.info(f"Newsletter: {execution['newsletter_name']}")
    logger.info(f"Date: {execution['run_date']}")
    logger.info(f"Status: {execution['status']}")
    logger.info(f"Last successful stage: {execution['last_successful_stage']}")
    logger.info("="*80)

    # Add metadata for resume handling
    config_snapshot['_resume_execution_id'] = execution['id']
    config_snapshot['_resume_from_stage'] = execution['last_successful_stage'] + 1

    return config_snapshot


def handle_replay(db: SQLiteURLDatabase, replay_arg: str, exec_id_arg: Optional[int]) -> Dict[str, Any]:
    """
    Handle --replay flag to re-execute complete pipeline with original params.

    Args:
        db: Database instance
        replay_arg: Replay argument (date string or numeric exec_id)
        exec_id_arg: Optional execution ID from --exec-id flag

    Returns:
        Newsletter configuration dictionary from original execution

    Raises:
        ValueError: If execution not found or invalid parameters
    """
    import json

    execution = None

    # Priority 1: --exec-id flag
    if exec_id_arg:
        execution = db.get_pipeline_execution_by_id(exec_id_arg)
        if not execution:
            raise ValueError(f"Execution ID {exec_id_arg} not found")

    # Priority 2: Date string (YYYY-MM-DD)
    elif replay_arg and '-' in replay_arg:
        # For replay by date, we need newsletter name - use last execution on that date
        # This is a simplification; in production you'd want to specify newsletter too
        execution = db.get_last_failed_execution()  # Fallback, should enhance this
        if execution and execution['run_date'] != replay_arg:
            raise ValueError(f"Could not find execution for date {replay_arg}")

    # Priority 3: Numeric ID
    elif replay_arg and replay_arg.isdigit():
        exec_id = int(replay_arg)
        execution = db.get_pipeline_execution_by_id(exec_id)
        if not execution:
            raise ValueError(f"Execution ID {exec_id} not found")

    else:
        raise ValueError(f"Invalid replay argument: {replay_arg}")

    # Parse config snapshot
    config_snapshot = json.loads(execution['config_snapshot'])

    logger.info("="*80)
    logger.info("REPLAYING PIPELINE EXECUTION")
    logger.info("="*80)
    logger.info(f"Execution ID: {execution['id']}")
    logger.info(f"Newsletter: {execution['newsletter_name']}")
    logger.info(f"Date: {execution['run_date']}")
    logger.info(f"Original status: {execution['status']}")
    logger.info("Will re-execute ALL stages with original configuration")
    logger.info("="*80)

    # Add metadata for replay handling (starts from stage 2, forces all)
    config_snapshot['_replay_execution_id'] = execution['id']
    config_snapshot['_replay_mode'] = True

    return config_snapshot


def run_newsletter_pipeline_resume(
    newsletter: Dict[str, Any],
    db: SQLiteURLDatabase,
    execution_id: int,
    start_from_stage: int,
    dry_run: bool = False,
    debug: bool = False
) -> Dict[str, Any]:
    """
    Resume pipeline execution from a specific stage.

    This function invalidates stages >= start_from_stage and re-executes them.

    Args:
        newsletter: Newsletter configuration dictionary
        db: Database instance
        execution_id: ID of the execution to resume
        start_from_stage: Stage number to start from (2-5)
        dry_run: If True, only show what would be executed
        debug: If True, generate debug report

    Returns:
        Dictionary with execution results and metrics
    """
    import subprocess

    newsletter_name = newsletter['name']
    date = newsletter.get('date', datetime.now().strftime('%Y-%m-%d'))

    logger.info(f"Resuming execution {execution_id} from stage {start_from_stage}")

    # Invalidate subsequent stages
    invalidated_count = db.invalidate_subsequent_stages(execution_id, start_from_stage)
    logger.info(f"Invalidated {invalidated_count} stages for re-execution")

    # Update execution status to 'running'
    db.update_pipeline_execution_status(execution_id, 'running')

    # Build results structure
    results = {
        'newsletter_name': newsletter_name,
        'date': date,
        'stages': {},
        'resumed_from_stage': start_from_stage,
        'execution_id': execution_id
    }

    last_successful_stage = start_from_stage - 1

    # Execute stages from start_from_stage to 5
    stages_to_run = list(range(start_from_stage, 6))  # e.g. [3, 4, 5]

    for stage_num in stages_to_run:
        logger.info("-"*80)
        logger.info(f"STAGE {stage_num:02d}")
        logger.info("-"*80)

        # Start pipeline run for this stage
        run_id = db.start_pipeline_run(newsletter_name, date, stage_num)
        db.link_pipeline_run_to_execution(run_id, execution_id)

        # Build command based on stage
        if stage_num == 2:
            cmd = build_stage_02_command(newsletter)
        elif stage_num == 3:
            cmd = build_stage_03_command(newsletter)
        elif stage_num == 4:
            cmd = build_stage_04_command(newsletter)
        elif stage_num == 5:
            cmd = build_stage_05_command(newsletter)
        else:
            logger.error(f"Invalid stage number: {stage_num}")
            continue

        # Execute command
        if dry_run:
            logger.info(f"[DRY RUN] Would execute: {' '.join(cmd)}")
            results['stages'][stage_num] = {'status': 'dry_run', 'command': ' '.join(cmd)}
        else:
            try:
                logger.info(f"Executing: {' '.join(cmd)}")
                subprocess.run(cmd, check=True, capture_output=False, text=True)
                db.complete_pipeline_run(run_id, 'completed')
                last_successful_stage = stage_num
                results['stages'][stage_num] = {'status': 'completed'}
                logger.info(f"Stage {stage_num:02d} completed successfully")

            except subprocess.CalledProcessError as e:
                error_msg = f"Stage {stage_num:02d} failed with exit code {e.returncode}"
                logger.error(error_msg)
                db.complete_pipeline_run(run_id, 'failed', error_message=error_msg)
                db.update_pipeline_execution_status(execution_id, 'failed', last_successful_stage)
                results['stages'][stage_num] = {'status': 'failed', 'error': error_msg}
                return results  # Stop on first failure

    # Mark execution as completed if all stages succeeded
    if last_successful_stage == 5:
        db.update_pipeline_execution_status(execution_id, 'completed', last_successful_stage)
        logger.info(f"Pipeline execution {execution_id} completed successfully")
    else:
        db.update_pipeline_execution_status(execution_id, 'partial', last_successful_stage)

    return results


def main():
    """Main entry point for orchestrator."""
    parser = argparse.ArgumentParser(
        description='Orchestrate complete newsletter generation pipeline (stages 01-05)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all newsletters from config
  %(prog)s --config config/newsletters.yml

  # Dry run (show what would be executed)
  %(prog)s --config config/newsletters.yml --dry-run

  # Force re-execution of all stages
  %(prog)s --config config/newsletters.yml --force-all

  # Skip Stage 01 (assume URLs already extracted)
  %(prog)s --config config/newsletters.yml --skip-stage-01
        """
    )

    parser.add_argument(
        '--config',
        type=str,
        required=False,  # Not required if using --resume or --replay
        help='Path to newsletters.yml configuration file'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be executed without running commands'
    )

    parser.add_argument(
        '--force-all',
        action='store_true',
        help='Force re-execution of all stages (override idempotency)'
    )

    parser.add_argument(
        '--skip-stage-01',
        action='store_true',
        help='Skip Stage 01 URL extraction (assume already done)'
    )

    parser.add_argument(
        '--only-newsletter',
        type=str,
        help='Only run specific newsletter by name'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Generate debug reports for all newsletters'
    )

    parser.add_argument(
        '--resume',
        nargs='?',
        const='auto',
        metavar='DATE_OR_EXEC_ID',
        help='Resume failed pipeline execution (auto=last failed, YYYY-MM-DD=by date, ID=by execution_id)'
    )

    parser.add_argument(
        '--replay',
        type=str,
        metavar='DATE_OR_EXEC_ID',
        help='Re-execute complete pipeline with original params (YYYY-MM-DD or execution_id)'
    )

    parser.add_argument(
        '--exec-id',
        type=int,
        help='Specify execution ID (use with --resume or --replay)'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.resume and not args.replay and not args.config:
        parser.error("--config is required unless using --resume or --replay")

    # Initialize database early for resume/replay
    db = PostgreSQLURLDatabase(os.getenv('DATABASE_URL'))

    # Handle --resume or --replay mode
    if args.resume is not None or args.replay:
        # Setup minimal logging
        from pathlib import Path
        log_dir = Path("logs") / datetime.now().strftime('%Y-%m-%d')
        log_dir.mkdir(parents=True, exist_ok=True)

        try:
            if args.resume is not None:
                # Resume mode
                newsletter_config = handle_resume(db, args.resume, args.exec_id)
                execution_id = newsletter_config['_resume_execution_id']
                start_from_stage = newsletter_config['_resume_from_stage']

                # Run resume logic
                results = run_newsletter_pipeline_resume(
                    newsletter_config,
                    db,
                    execution_id,
                    start_from_stage,
                    dry_run=args.dry_run,
                    debug=args.debug
                )

                logger.info("="*80)
                logger.info("RESUME COMPLETED")
                logger.info(f"Execution ID: {execution_id}")
                logger.info(f"Final status: {results.get('stages', {})}")
                logger.info("="*80)

                return 0

            elif args.replay:
                # Replay mode
                newsletter_config = handle_replay(db, args.replay, args.exec_id)

                # Run full pipeline with force_all=True
                results = run_newsletter_pipeline(
                    newsletter_config,
                    db,
                    dry_run=args.dry_run,
                    force_all=True,  # Force all stages to re-run
                    debug=args.debug
                )

                logger.info("="*80)
                logger.info("REPLAY COMPLETED")
                logger.info(f"Newsletter: {newsletter_config['name']}")
                logger.info(f"Final status: {results.get('stages', {})}")
                logger.info("="*80)

                return 0

        except ValueError as e:
            logger.error(f"Error: {e}")
            return 1
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return 1

    # Normal mode: Load newsletter configurations
    try:
        newsletters = load_newsletter_config(args.config)
    except Exception as e:
        logger.error(f"Failed to load newsletter config: {e}")
        return 1

    # Filter newsletters if --only-newsletter specified
    if args.only_newsletter:
        newsletters = [n for n in newsletters if n['name'] == args.only_newsletter]
        if not newsletters:
            logger.error(f"Newsletter '{args.only_newsletter}' not found in config")
            return 1

    # Get unique dates for Stage 01
    dates = set()
    for newsletter in newsletters:
        if 'date' in newsletter:
            dates.add(newsletter['date'])
        elif 'start' in newsletter:
            dates.add(newsletter['start'].split('T')[0])

    if not dates:
        logger.error("No dates found in newsletter configurations")
        return 1

    # Setup logging (use first date)
    run_date = sorted(dates)[0]
    setup_logging(run_date)

    logger.info("="*80)
    logger.info("NEWSLETTER PIPELINE ORCHESTRATOR")
    logger.info("="*80)
    logger.info(f"Config file: {args.config}")
    logger.info(f"Newsletters to process: {len(newsletters)}")
    logger.info(f"Unique dates: {sorted(dates)}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Force all: {args.force_all}")
    logger.info(f"Skip Stage 01: {args.skip_stage_01}")

    # Database already initialized earlier

    # Run Stage 01 for each unique date (unless skipped)
    if not args.skip_stage_01:
        for date in sorted(dates):
            success = run_stage_01(date, dry_run=args.dry_run)
            if not success and not args.dry_run:
                logger.error(f"Stage 01 failed for date {date}. Continuing with other dates...")

    # Run pipeline for each newsletter
    all_results = []
    for i, newsletter in enumerate(newsletters, 1):
        logger.info("")
        logger.info("="*80)
        logger.info(f"PROCESSING NEWSLETTER {i}/{len(newsletters)}")
        logger.info("="*80)

        try:
            # Check if debug is enabled in config or CLI
            debug_enabled = args.debug or newsletter.get('debug', False)

            results = run_newsletter_pipeline(
                newsletter,
                db,
                dry_run=args.dry_run,
                force_all=args.force_all,
                debug=debug_enabled
            )
            all_results.append(results)

        except Exception as e:
            logger.error(f"Unexpected error processing newsletter '{newsletter['name']}': {e}", exc_info=True)
            all_results.append({
                'newsletter_name': newsletter['name'],
                'error': str(e),
                'stages': {}
            })

    # Generate enhanced summary
    generate_enhanced_summary(all_results, newsletters, db, run_date)

    return 0


if __name__ == "__main__":
    sys.exit(main())
