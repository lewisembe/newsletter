"""
Celery tasks for newsletter generation pipeline (Stages 2-5).
"""

import os
import subprocess
import logging
import csv
from datetime import datetime, date, timezone, timedelta
from pathlib import Path
from typing import List, Optional
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from celery_app import celery_app
from common.postgres_db import PostgreSQLURLDatabase
from common.encryption import get_encryption_manager

logger = logging.getLogger(__name__)

# Initialize database
db = PostgreSQLURLDatabase(os.getenv('DATABASE_URL'))


@celery_app.task(name="execute_newsletter_pipeline", bind=True, max_retries=0)
def execute_newsletter_pipeline_task(
    self,
    newsletter_execution_id: int,
    api_key_id: Optional[int] = None,
    force: bool = False
):
    """
    Execute complete newsletter pipeline: Stage 2 → 3 → 4 → 5

    Args:
        newsletter_execution_id: ID of newsletter_execution record
        api_key_id: Optional API key ID to use
        force: Force re-execution of stages

    Returns:
        dict with execution results
    """
    logger.info(f"Starting newsletter pipeline for execution {newsletter_execution_id}")

    # Propagate execution id to token tracker so token_usage rows are tagged correctly
    os.environ["TOKEN_TRACKER_NEWSLETTER_EXECUTION_ID"] = str(newsletter_execution_id)

    try:
        # Enforce sequential mode before starting if configured
        execution_mode = db.get_system_config('newsletter_execution_mode') or os.getenv('NEWSLETTER_EXECUTION_MODE') or 'parallel'
        max_parallel = int(db.get_system_config('newsletter_max_parallel') or os.getenv('NEWSLETTER_MAX_PARALLEL') or '3')
        if max_parallel < 1:
            max_parallel = 1
        if execution_mode == 'sequential':
            # Atomic guard: only one pending/running allowed
            acquired = db.try_start_sequential_newsletter_execution(
                newsletter_execution_id,
                celery_task_id=self.request.id
            )
            if not acquired:
                logger.info(f"Sequential mode active. Execution {newsletter_execution_id} moved to queue because another run is in progress.")
                db.update_newsletter_execution_status(
                    newsletter_execution_id,
                    'queued',
                    error_message="Queued automatically due to sequential execution mode"
                )
                return {
                    'success': True,
                    'execution_id': newsletter_execution_id,
                    'queued': True,
                    'reason': 'sequential_mode'
                }
        else:
            # Parallel mode with max_parallel cap
            acquired = db.try_start_newsletter_execution_with_limit(
                newsletter_execution_id,
                max_parallel,
                celery_task_id=self.request.id
            )
            if not acquired:
                logger.info(f"Parallel mode with max {max_parallel}. Execution {newsletter_execution_id} moved to queue because running limit reached.")
                db.update_newsletter_execution_status(
                    newsletter_execution_id,
                    'queued',
                    error_message="Queued automatically due to max parallel limit"
                )
                return {
                    'success': True,
                    'execution_id': newsletter_execution_id,
                    'queued': True,
                    'reason': 'parallel_limit'
                }

        # 2. Get execution configuration
        execution = db.get_newsletter_execution_by_id(newsletter_execution_id)
        if not execution:
            raise ValueError(f"Newsletter execution {newsletter_execution_id} not found")

        config = execution['config_snapshot']
        run_date = execution['run_date']
        api_key_id = execution.get('api_key_id') or api_key_id

        # 3. Get and decrypt user's API key
        user_openai_key = None
        if api_key_id:
            api_key_record = db.get_api_key_by_id(api_key_id)
            if api_key_record:
                encryption_manager = get_encryption_manager()
                user_openai_key = encryption_manager.decrypt(api_key_record['encrypted_key'])
                logger.info(f"Using API key: {api_key_record['alias']}")
            else:
                logger.warning(f"API key {api_key_id} not found, will use system default")

        logger.info(f"Executing newsletter '{config['name']}' for date {run_date}")

        # 3. Execute Stage 02 (Classification) - with coordination for duplicates
        logger.info("Starting Stage 02: Classification")
        stage02_id = execute_stage02_coordinated(
            newsletter_execution_id=newsletter_execution_id,
            run_date=run_date,
            source_ids=config.get('source_ids'),
            category_ids=config.get('category_ids'),
            force=force,
            openai_api_key=user_openai_key
        )
        logger.info(f"Stage 02 completed: {stage02_id}")

        # Update completed stages count
        db.update_newsletter_execution_status(
            newsletter_execution_id,
            'running',
            completed_stages=1
        )

        # 4. Execute Stage 03 (Ranking)
        logger.info("Starting Stage 03: Ranking")
        stage03_id = execute_stage03(
            newsletter_execution_id=newsletter_execution_id,
            newsletter_name=config['name'],
            run_date=run_date,
            category_ids=config.get('category_ids'),
            ranker_method=config.get('ranker_method', 'level_scoring'),
            max_articles=config.get('articles_count', 20),
            source_ids=config.get('source_ids'),
            openai_api_key=user_openai_key
        )
        logger.info(f"Stage 03 completed: {stage03_id}")

        db.update_newsletter_execution_status(
            newsletter_execution_id,
            'running',
            completed_stages=2
        )

        # 5. Execute Stage 04 (Content Extraction)
        logger.info("Starting Stage 04: Content Extraction")
        stage04_id = execute_stage04(
            newsletter_execution_id=newsletter_execution_id,
            newsletter_name=config['name'],
            run_date=run_date,
            skip_paywall_check=config.get('skip_paywall_check', False),
            force=force,
            openai_api_key=user_openai_key
        )
        logger.info(f"Stage 04 completed: {stage04_id}")

        db.update_newsletter_execution_status(
            newsletter_execution_id,
            'running',
            completed_stages=3
        )

        # 6. Execute Stage 05 (Newsletter Generation)
        logger.info("Starting Stage 05: Newsletter Generation")
        stage05_id, output_files = execute_stage05(
            newsletter_execution_id=newsletter_execution_id,
            newsletter_name=config['name'],
            run_date=run_date,
            output_format=config.get('output_format', 'markdown'),
            template=config.get('template_name', 'default'),
            related_window_days=config.get('related_window_days', 365),
            openai_api_key=user_openai_key
        )
        logger.info(f"Stage 05 completed: {stage05_id}")

        db.update_newsletter_execution_status(
            newsletter_execution_id,
            'running',
            completed_stages=4,
            newsletter_generated=True,
            **output_files
        )

        # 7. Consolidate metrics from all stages
        consolidate_execution_metrics(newsletter_execution_id, run_date=run_date)

        # 8. Mark as completed
        db.update_newsletter_execution_status(
            newsletter_execution_id,
            'completed',
            completed_at=datetime.utcnow()
        )

        logger.info(f"Newsletter pipeline completed successfully for execution {newsletter_execution_id}")

        # 9. Process next queued execution (if sequential mode)
        process_next_queued_execution()

        return {
            'success': True,
            'execution_id': newsletter_execution_id,
            'stages_completed': 4
        }

    except Exception as e:
        logger.error(f"Newsletter pipeline failed for execution {newsletter_execution_id}: {str(e)}", exc_info=True)

        db.update_newsletter_execution_status(
            newsletter_execution_id,
            'failed',
            error_message=str(e)[:1000],  # Truncate long error messages
            completed_at=datetime.utcnow()
        )

        # Process next queued execution even if this one failed
        process_next_queued_execution()

        raise


def execute_stage02_coordinated(
    newsletter_execution_id: int,
    run_date: date,
    source_ids: Optional[List[int]],
    category_ids: List[int],
    force: bool = False,
    openai_api_key: str = None
) -> int:
    """
    Execute Stage 02 (Classification) with coordination to avoid duplicates.

    Strategy:
    1. Get candidate URLs (unclassified or force=True)
    2. Attempt to lock URLs
    3. If already locked by another execution, wait for completion
    4. Classify only unlocked URLs

    Returns:
        stage_execution_id
    """
    # Get existing stage execution (created by API endpoint)
    stage_exec_id = db.get_newsletter_stage_execution_id(newsletter_execution_id, 2)
    stage_start = datetime.utcnow()

    try:
        db.update_newsletter_stage_execution_status(
            stage_exec_id,
            'running',
            started_at=stage_start
        )

        # Get URLs that need classification
        urls = db.get_urls_for_classification(
            run_date=run_date,
            source_ids=source_ids,
            force=force
        )

        # Guardrail: drop any non-content URLs to avoid counting them as failures
        urls = [u for u in urls if u.get('content_type') in (None, 'contenido')]

        if not urls:
            logger.info(f"No URLs to classify for date {run_date}")
            db.update_newsletter_stage_execution_status(
                stage_exec_id,
                'completed',
                completed_at=datetime.utcnow(),
                items_processed=0
            )
            return stage_exec_id

        # Separate locked vs unlocked URLs
        locked_urls = [u for u in urls if u.get('classification_lock_at') is not None]
        unlocked_urls = [u for u in urls if u.get('classification_lock_at') is None]

        logger.info(f"Found {len(urls)} URLs: {len(unlocked_urls)} unlocked, {len(locked_urls)} locked")

        # Classify unlocked URLs
        if unlocked_urls:
            url_ids = [u['id'] for u in unlocked_urls]

            # Lock URLs
            db.lock_urls_for_classification(
                url_ids=url_ids,
                lock_by=f'newsletter_exec_{newsletter_execution_id}'
            )

            try:
                # Execute Stage 02 via subprocess
                cmd = [
                    'python',
                    'stages/02_filter_for_newsletters.py',
                    '--date', str(run_date)
                ]

                # Add source filter if specified
                if source_ids:
                    # Get source names from IDs
                    sources = db.get_sources_by_ids(source_ids)
                    if sources:
                        cmd.extend(['--sources'] + [s['name'] for s in sources])

                # Add category filter (category_ids are already slugs)
                if category_ids:
                    cmd.extend(['--categories'] + category_ids)

                logger.info(f"Executing: {' '.join(cmd)}")

                # Prepare environment with user's API key
                env = os.environ.copy()
                env['TOKEN_TRACKER_NEWSLETTER_EXECUTION_ID'] = str(newsletter_execution_id)
                if openai_api_key:
                    env['OPENAI_API_KEY'] = openai_api_key

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 min timeout
                    env=env
                )

                if result.returncode != 0:
                    raise Exception(f"Stage 02 failed: {result.stderr}")

                logger.info(f"Stage 02 subprocess completed: {result.stdout[:500]}")

            finally:
                # Always unlock URLs
                db.unlock_urls_for_classification(url_ids)

        # Wait for locked URLs to complete (if any)
        if locked_urls:
            logger.info(f"Waiting for {len(locked_urls)} locked URLs to be classified...")
            locked_url_ids = [u['id'] for u in locked_urls]
            success = db.wait_for_url_classification(
                url_ids=locked_url_ids,
                timeout=600  # 10 min timeout (increased from 5 min to handle large batches)
            )
            if not success:
                error_msg = f"Timeout waiting for {len(locked_urls)} locked URLs to be classified after 10 minutes"
                logger.error(error_msg)
                raise Exception(error_msg)

        # Get final classification metrics
        all_url_ids = [u['id'] for u in urls]
        metrics = get_classification_metrics(all_url_ids, category_ids)
        stage_end = datetime.utcnow()
        token_costs = calculate_stage_costs(
            "02",
            stage_start,
            stage_end,
            newsletter_execution_id=newsletter_execution_id,
            run_date=run_date,
        )

        db.update_newsletter_stage_execution_status(
            stage_exec_id,
            'completed',
            completed_at=stage_end,
            items_processed=metrics['total'],
            items_successful=metrics['classified'],
            items_failed=metrics['failed'],
            stage_metadata=metrics.get('breakdown', {}),
            input_tokens=token_costs['input_tokens'],
            output_tokens=token_costs['output_tokens'],
            cost_usd=token_costs['cost_usd']
        )

        return stage_exec_id

    except Exception as e:
        logger.error(f"Stage 02 failed: {str(e)}", exc_info=True)
        db.update_newsletter_stage_execution_status(
            stage_exec_id,
            'failed',
            error_message=str(e)[:1000],
            completed_at=datetime.utcnow()
        )
        raise


def execute_stage03(
    newsletter_execution_id: int,
    newsletter_name: str,
    run_date: date,
    category_ids: List[int],
    ranker_method: str,
    max_articles: int,
    source_ids: Optional[List[int]] = None,
    openai_api_key: str = None
) -> int:
    """Execute Stage 03 (Ranking)."""
    # Get existing stage execution (created by API endpoint)
    stage_exec_id = db.get_newsletter_stage_execution_id(newsletter_execution_id, 3)
    stage_start = datetime.utcnow()

    try:
        db.update_newsletter_stage_execution_status(
            stage_exec_id,
            'running',
            started_at=stage_start
        )

        # Build command
        cmd = [
            'python',
            'stages/03_ranker.py',
            '--newsletter-name', newsletter_name,
            '--date', str(run_date),
            '--ranker-method', ranker_method,
            '--articles-count', str(max_articles)
        ]

        # Add sources (convert IDs to strings for command line)
        if source_ids:
            cmd.extend(['--sources'] + [str(sid) for sid in source_ids])

        # Add categories (category_ids are already slugs)
        if category_ids:
            cmd.extend(['--categories'] + category_ids)

        logger.info(f"Executing: {' '.join(cmd)}")

        # Prepare environment with user's API key
        env = os.environ.copy()
        env['TOKEN_TRACKER_NEWSLETTER_EXECUTION_ID'] = str(newsletter_execution_id)
        if openai_api_key:
            env['OPENAI_API_KEY'] = openai_api_key

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min timeout
            env=env
        )

        if result.returncode != 0:
            raise Exception(f"Stage 03 failed: {result.stderr}")

        logger.info(f"Stage 03 completed: {result.stdout[:500]}")

        # Get metrics from DB (ranking_runs, ranked_urls)
        metrics = get_ranking_metrics(newsletter_name, run_date)
        stage_end = datetime.utcnow()
        token_costs = calculate_stage_costs(
            "03",
            stage_start,
            stage_end,
            newsletter_execution_id=newsletter_execution_id,
            run_date=run_date,
        )

        db.update_newsletter_stage_execution_status(
            stage_exec_id,
            'completed',
            completed_at=stage_end,
            items_processed=metrics.get('total_urls', 0),
            items_successful=metrics.get('ranked_urls', 0),
            stage_metadata=metrics,
            input_tokens=token_costs['input_tokens'],
            output_tokens=token_costs['output_tokens'],
            cost_usd=token_costs['cost_usd']
        )

        return stage_exec_id

    except Exception as e:
        logger.error(f"Stage 03 failed: {str(e)}", exc_info=True)
        db.update_newsletter_stage_execution_status(
            stage_exec_id,
            'failed',
            error_message=str(e)[:1000],
            completed_at=datetime.utcnow()
        )
        raise


def execute_stage04(
    newsletter_execution_id: int,
    newsletter_name: str,
    run_date: date,
    skip_paywall_check: bool,
    force: bool,
    openai_api_key: str = None
) -> int:
    """Execute Stage 04 (Content Extraction)."""
    # Get existing stage execution (created by API endpoint)
    stage_exec_id = db.get_newsletter_stage_execution_id(newsletter_execution_id, 4)
    stage_start = datetime.utcnow()

    try:
        db.update_newsletter_stage_execution_status(
            stage_exec_id,
            'running',
            started_at=stage_start
        )

        cmd = [
            'python',
            'stages/04_extract_content.py',
            '--newsletter-name', newsletter_name,
            '--date', str(run_date)
        ]

        if skip_paywall_check:
            cmd.append('--skip-paywall-check')

        if force:
            cmd.append('--force')

        logger.info(f"Executing: {' '.join(cmd)}")

        # Prepare environment with user's API key
        env = os.environ.copy()
        env['TOKEN_TRACKER_NEWSLETTER_EXECUTION_ID'] = str(newsletter_execution_id)
        if openai_api_key:
            env['OPENAI_API_KEY'] = openai_api_key

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout
            env=env
        )

        if result.returncode != 0:
            # Stage failed - include both stdout and stderr for debugging
            error_output = result.stderr if result.stderr else result.stdout
            raise Exception(f"Stage 04 failed with exit code {result.returncode}: {error_output[:1000]}")

        logger.info(f"Stage 04 completed: {result.stdout[:500]}")

        # Get metrics
        metrics = get_content_extraction_metrics(newsletter_name, run_date)
        stage_end = datetime.utcnow()
        token_costs = calculate_stage_costs(
            "04",
            stage_start,
            stage_end,
            newsletter_execution_id=newsletter_execution_id,
            run_date=run_date,
        )

        db.update_newsletter_stage_execution_status(
            stage_exec_id,
            'completed',
            completed_at=stage_end,
            items_processed=metrics.get('total_urls', 0),
            items_successful=metrics.get('extracted_success', 0),
            items_failed=metrics.get('extracted_failed', 0),
            stage_metadata=metrics,
            input_tokens=token_costs['input_tokens'],
            output_tokens=token_costs['output_tokens'],
            cost_usd=token_costs['cost_usd']
        )

        return stage_exec_id

    except Exception as e:
        logger.error(f"Stage 04 failed: {str(e)}", exc_info=True)
        db.update_newsletter_stage_execution_status(
            stage_exec_id,
            'failed',
            error_message=str(e)[:1000],
            completed_at=datetime.utcnow()
        )
        raise


def execute_stage05(
    newsletter_execution_id: int,
    newsletter_name: str,
    run_date: date,
    output_format: str,
    template: str,
    related_window_days: int,
    openai_api_key: str = None
) -> tuple:
    """
    Execute Stage 05 (Newsletter Generation).

    Returns:
        (stage_exec_id, output_files_dict)
    """
    # Get existing stage execution (created by API endpoint)
    stage_exec_id = db.get_newsletter_stage_execution_id(newsletter_execution_id, 5)
    stage_start = datetime.utcnow()

    try:
        db.update_newsletter_stage_execution_status(
            stage_exec_id,
            'running',
            started_at=stage_start
        )

        cmd = [
            'python',
            'stages/05_generate_newsletters.py',
            '--newsletter-name', newsletter_name,
            '--date', str(run_date),
            '--output-format', output_format,
            '--template', template,
            '--related-window-days', str(related_window_days)
        ]

        logger.info(f"Executing: {' '.join(cmd)}")

        # Prepare environment with user's API key
        env = os.environ.copy()
        env['TOKEN_TRACKER_NEWSLETTER_EXECUTION_ID'] = str(newsletter_execution_id)
        if openai_api_key:
            env['OPENAI_API_KEY'] = openai_api_key

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout
            env=env
        )

        if result.returncode != 0:
            raise Exception(f"Stage 05 failed: {result.stderr}")

        logger.info(f"Stage 05 completed: {result.stdout[:500]}")

        # Parse output to get file paths
        output_files = parse_stage05_output(result.stdout, newsletter_name, run_date, output_format)

        # Get metrics
        metrics = get_newsletter_generation_metrics(newsletter_name, run_date)
        stage_end = datetime.utcnow()
        token_costs = calculate_stage_costs(
            "05",
            stage_start,
            stage_end,
            newsletter_execution_id=newsletter_execution_id,
            run_date=run_date,
        )

        db.update_newsletter_stage_execution_status(
            stage_exec_id,
            'completed',
            completed_at=stage_end,
            items_processed=metrics.get('total_articles', 0),
            items_successful=metrics.get('articles_with_content', 0),
            stage_metadata=metrics,
            input_tokens=token_costs['input_tokens'],
            output_tokens=token_costs['output_tokens'],
            cost_usd=token_costs['cost_usd']
        )

        return stage_exec_id, output_files

    except Exception as e:
        logger.error(f"Stage 05 failed: {str(e)}", exc_info=True)
        db.update_newsletter_stage_execution_status(
            stage_exec_id,
            'failed',
            error_message=str(e)[:1000],
            completed_at=datetime.utcnow()
        )
        raise


# Helper functions

def get_classification_metrics(url_ids: List[int], category_ids: List[int]) -> dict:
    """Get classification metrics for URLs."""
    # Query categorized URLs
    query = """
    SELECT
        COUNT(*) FILTER (WHERE categoria_tematica IS NOT NULL) as classified,
        COUNT(*) FILTER (WHERE categoria_tematica IS NULL) as failed,
        COUNT(*) as total
    FROM urls
    WHERE id = ANY(%s);
    """
    result = db.execute_query(query, (url_ids,), fetch_one=True)

    return {
        'total': result['total'] if result else 0,
        'classified': result['classified'] if result else 0,
        'failed': result['failed'] if result else 0
    }


def get_ranking_metrics(newsletter_name: str, run_date: date) -> dict:
    """Get ranking metrics from ranking_runs table."""
    query = """
    SELECT
        rr.id,
        COUNT(ru.id) as ranked_urls
    FROM ranking_runs rr
    LEFT JOIN ranked_urls ru ON rr.id = ru.ranking_run_id
    WHERE rr.newsletter_name = %s
    AND DATE(rr.run_date) = %s
    GROUP BY rr.id
    ORDER BY rr.run_date DESC
    LIMIT 1;
    """
    result = db.execute_query(query, (newsletter_name, run_date), fetch_one=True)

    return {
        'ranking_run_id': result['id'] if result else None,
        'ranked_urls': result['ranked_urls'] if result else 0
    }


def get_content_extraction_metrics(newsletter_name: str, run_date: date) -> dict:
    """Get content extraction metrics."""
    # Get ranking run
    ranking_run = get_ranking_metrics(newsletter_name, run_date)
    if not ranking_run.get('ranking_run_id'):
        return {}

    query = """
    SELECT
        COUNT(*) as total_urls,
        COUNT(*) FILTER (WHERE full_content IS NOT NULL) as extracted_success,
        COUNT(*) FILTER (WHERE full_content IS NULL) as extracted_failed
    FROM ranked_urls ru
    JOIN urls u ON ru.url_id = u.id
    WHERE ru.ranking_run_id = %s;
    """
    result = db.execute_query(query, (ranking_run['ranking_run_id'],), fetch_one=True)

    return {
        'total_urls': result['total_urls'] if result else 0,
        'extracted_success': result['extracted_success'] if result else 0,
        'extracted_failed': result['extracted_failed'] if result else 0
    }


def get_newsletter_generation_metrics(newsletter_name: str, run_date: date) -> dict:
    """Get newsletter generation metrics from newsletters table."""
    query = """
    SELECT
        articles_count as total_articles,
        articles_with_content
    FROM newsletters
    WHERE newsletter_name = %s
    AND DATE(run_date) = %s
    ORDER BY generated_at DESC
    LIMIT 1;
    """
    result = db.execute_query(query, (newsletter_name, run_date), fetch_one=True)

    return {
        'total_articles': result['total_articles'] if result else 0,
        'articles_with_content': result['articles_with_content'] if result else 0
    }


def parse_stage05_output(stdout: str, newsletter_name: str, run_date: date, output_format: str) -> dict:
    """Parse Stage 05 output to extract file paths."""
    # Expected output pattern from Stage 05:
    # "Newsletter saved to: <path>"
    # "Context report saved to: <path>"

    output_files = {}

    for line in stdout.split('\n'):
        if 'Newsletter saved to:' in line:
            path = line.split('Newsletter saved to:')[1].strip()
            if path.endswith('.md'):
                output_files['output_markdown_path'] = path
            elif path.endswith('.html'):
                output_files['output_html_path'] = path

        elif 'Context report saved to:' in line:
            path = line.split('Context report saved to:')[1].strip()
            output_files['context_report_path'] = path

    return output_files


def calculate_stage_costs(
    stage: str,
    started_at: datetime,
    completed_at: datetime,
    newsletter_execution_id: int | None = None,
    run_date: date | None = None,
) -> dict:
    """
    Calculate token usage and cost for a stage using Postgres token_usage between start/end timestamps.

    Args:
        stage: Stage number as string (e.g., "02")
        started_at: Stage start time (UTC)
        completed_at: Stage end time (UTC)
        newsletter_execution_id: Optional newsletter execution id for filtering
        run_date: Optional run date to use as an extra fallback filter
    """

    def _normalize(dt) -> datetime:
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except Exception:
                return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    start = _normalize(started_at)
    end = _normalize(completed_at or datetime.utcnow().replace(tzinfo=timezone.utc))
    if not start:
        return {'input_tokens': 0, 'output_tokens': 0, 'cost_usd': 0.0}
    if not end:
        end = datetime.utcnow().replace(tzinfo=timezone.utc)

    try:
        # Try to filter by newsletter_execution_id when available
        usage = db.get_token_usage_between(
            stage=stage,
            start_ts=start,
            end_ts=end,
            newsletter_execution_id=newsletter_execution_id
        )
        if (usage.get('input_tokens', 0) == 0 and usage.get('output_tokens', 0) == 0) and newsletter_execution_id:
            # Fallback: use only time window if no rows tied to the execution_id
            usage = db.get_token_usage_between(
                stage=stage,
                start_ts=start,
                end_ts=end
            )
        # Second fallback: try only by execution id (no time filter) to capture missing timestamps
        if (usage.get('input_tokens', 0) == 0 and usage.get('output_tokens', 0) == 0) and newsletter_execution_id:
            usage = db.get_token_usage_between(
                stage=stage,
                newsletter_execution_id=newsletter_execution_id
            )
        # Third fallback: use run_date window if provided (helps when timestamps lose timezone)
        if (usage.get('input_tokens', 0) == 0 and usage.get('output_tokens', 0) == 0) and run_date:
            day_start = datetime.combine(run_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            day_end = day_start + timedelta(days=1)
            usage = db.get_token_usage_between(
                stage=stage,
                start_ts=day_start,
                end_ts=day_end
            )

        return {
            'input_tokens': usage.get('input_tokens', 0),
            'output_tokens': usage.get('output_tokens', 0),
            'cost_usd': round(float(usage.get('cost_usd', 0.0)), 4)
        }
    except Exception as e:
        logger.error(f"Error calculating stage costs for stage {stage}: {e}")
        return {'input_tokens': 0, 'output_tokens': 0, 'cost_usd': 0.0}


def consolidate_execution_metrics(newsletter_execution_id: int, run_date: date | None = None) -> None:
    """Consolidate metrics from all stage executions into newsletter_execution."""
    stages = db.get_newsletter_stage_executions(newsletter_execution_id)

    total_input_tokens = 0
    total_output_tokens = 0
    total_cost_usd = 0.0

    # Fill missing token metrics from CSV if not already populated
    for stage in stages:
        input_tokens = stage.get('input_tokens') or 0
        output_tokens = stage.get('output_tokens') or 0
        cost_usd = float(stage.get('cost_usd') or 0.0)

        if (input_tokens == 0 and output_tokens == 0) and stage.get('started_at') and stage.get('completed_at'):
            # Attempt to recover from token_usage.csv using stored timestamps
            recovered = calculate_stage_costs(
                stage=str(stage.get('stage_number')).zfill(2),
                started_at=stage.get('started_at'),
                completed_at=stage.get('completed_at'),
                newsletter_execution_id=newsletter_execution_id,
                run_date=run_date,
            )
            input_tokens = recovered['input_tokens']
            output_tokens = recovered['output_tokens']
            cost_usd = recovered['cost_usd']

            # Persist recovered metrics for the stage record
            db.update_newsletter_stage_execution_status(
                stage['id'],
                stage.get('status', 'completed'),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd
            )

        total_input_tokens += input_tokens
        total_output_tokens += output_tokens
        total_cost_usd += cost_usd

    # Count URLs processed, ranked, with content
    stage_02 = next((s for s in stages if s['stage_number'] == 2), None)
    stage_03 = next((s for s in stages if s['stage_number'] == 3), None)
    stage_04 = next((s for s in stages if s['stage_number'] == 4), None)

    db.update_newsletter_execution_status(
        newsletter_execution_id,
        'running',  # Keep running status, will be updated to completed by caller
        total_urls_processed=stage_02.get('items_processed', 0) if stage_02 else 0,
        total_urls_ranked=stage_03.get('items_successful', 0) if stage_03 else 0,
        total_urls_with_content=stage_04.get('items_successful', 0) if stage_04 else 0,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_cost_usd=float(total_cost_usd)
    )


def process_next_queued_execution():
    """
    Process the next queued newsletter execution (if any).
    Called after an execution completes to start the next one in the queue.
    """
    try:
        execution_mode = db.get_system_config('newsletter_execution_mode') or os.getenv('NEWSLETTER_EXECUTION_MODE') or 'parallel'
        max_parallel = int(db.get_system_config('newsletter_max_parallel') or os.getenv('NEWSLETTER_MAX_PARALLEL') or '3')
        if max_parallel < 1:
            max_parallel = 1

        limit = 1 if execution_mode == 'sequential' else max_parallel

        running = db.count_running_newsletter_executions_only()
        if running >= limit:
            return  # No free slots

        # Get oldest queued execution
        query = """
        SELECT id, api_key_id
        FROM newsletter_executions
        WHERE status = 'queued'
        ORDER BY created_at ASC
        LIMIT 1;
        """
        queued = db.execute_query(query, fetch_one=True)

        if not queued:
            logger.info("No queued executions to process")
            return

        execution_id = queued['id']
        api_key_id = queued.get('api_key_id')

        logger.info(f"Processing queued execution {execution_id}")

        # Update status from queued to pending
        db.update_newsletter_execution_status(execution_id, 'pending')

        # Launch the task
        execute_newsletter_pipeline_task.apply_async(
            args=[execution_id],
            kwargs={'api_key_id': api_key_id},
            queue='newsletters'
        )

        logger.info(f"Launched queued execution {execution_id}")

    except Exception as e:
        logger.error(f"Error processing next queued execution: {e}", exc_info=True)
