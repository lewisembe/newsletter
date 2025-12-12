"""
Celery tasks for Stage 01 (Extract URLs) execution.
"""
from celery import current_task
from celery_app import celery
import sys
import os
from datetime import datetime, date, time, timedelta
import subprocess
import logging
from croniter import croniter

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from common.postgres_db import PostgreSQLURLDatabase
from celery_app.utils.api_key_selector import select_api_key
from celery_app.utils.cost_calculator import calculate_execution_cost

logger = logging.getLogger(__name__)


def schedule_targets_date(schedule: dict, target_date: date):
    """Check if a CRON expression has an occurrence for the provided date."""
    day_end = datetime.combine(target_date + timedelta(days=1), time.min)
    cron = croniter(schedule['cron_expression'], day_end)
    prev_run = cron.get_prev(datetime)
    return prev_run.date() == target_date, prev_run


def _parse_schedule_parameters(schedule: dict) -> dict:
    params = schedule.get('parameters') or {}
    if isinstance(params, str):
        try:
            import json
            params = json.loads(params)
        except Exception:
            params = {}
    return params if isinstance(params, dict) else {}


def trigger_newsletters_after_stage1(db, run_date: date, source_ids: list | None):
    """
    Trigger newsletter schedules configured to run as soon as Stage 1 data is ready.
    """
    from celery_app.tasks.newsletter_tasks import execute_newsletter_pipeline_task

    schedules = db.get_active_schedules()
    for schedule in schedules:
        if schedule.get('execution_target') != 'newsletter_pipeline':
            continue

        params = _parse_schedule_parameters(schedule)
        if not params.get('trigger_on_stage1_ready'):
            continue

        # Only trigger once per day
        if schedule.get('last_run_at') and schedule['last_run_at'].date() == run_date:
            continue

        is_for_today, prev_run = schedule_targets_date(schedule, run_date)
        if not is_for_today:
            continue

        newsletter_config_id = schedule.get('newsletter_config_id')
        if not newsletter_config_id:
            logger.warning(f"Skipping schedule {schedule.get('id')} without newsletter_config_id")
            continue

        config = db.get_newsletter_config_by_id(newsletter_config_id)
        if not config:
            logger.warning(f"Skipping schedule {schedule.get('id')}: config {newsletter_config_id} not found")
            continue

        required_sources = config.get('source_ids') or []
        if not db.has_stage01_executions_for_sources(run_date, required_sources):
            logger.info(
                f"Schedule {schedule.get('id')} waiting for Stage 1 sources "
                f"{required_sources} on {run_date}"
            )
            continue

        # Check execution mode for concurrency control
        execution_mode = db.get_system_config('newsletter_execution_mode') or 'parallel'
        sequential_mode = (execution_mode == 'sequential')

        # Create newsletter execution with atomic lock (if sequential)
        execution_id = db.create_newsletter_execution(
            newsletter_config_id=newsletter_config_id,
            run_date=run_date,
            execution_type='scheduled',
            schedule_id=schedule.get('id'),
            api_key_id=schedule.get('api_key_id'),
            sequential_mode=sequential_mode
        )

        # If lock not acquired (sequential mode), skip this execution
        if not execution_id:
            logger.info(
                f"Skipping newsletter schedule {schedule.get('id')}: "
                f"Could not acquire lock (sequential mode active)"
            )
            continue

        logger.info(
            f"Triggered newsletter execution {execution_id} after Stage 1 for schedule {schedule.get('id')}, "
            f"prev_run={prev_run}"
        )

        # Create stage execution records (4 stages: 2, 3, 4, 5)
        for stage_num, stage_name in [(2, '02_filter'), (3, '03_ranker'), (4, '04_extract_content'), (5, '05_generate')]:
            db.create_newsletter_stage_execution(
                newsletter_execution_id=execution_id,
                stage_number=stage_num,
                stage_name=stage_name
            )

        execute_newsletter_pipeline_task.apply_async(
            args=[execution_id],
            kwargs={'api_key_id': schedule.get('api_key_id')},
            queue='newsletters'
        )

        db.update_schedule_last_run(schedule.get('id'), datetime.utcnow())


@celery.task(bind=True, name='execute_stage01', max_retries=0)
def execute_stage01_task(self, execution_id: int, api_key_id: int = None,
                         source_ids: list = None, use_fallback: bool = True):
    """
    Execute Stage 01 with full tracking.

    Args:
        execution_id: ID in execution_history table
        api_key_id: API key ID to use (None = automatic rotation)
        source_ids: List of source IDs to process (None = all active)
        use_fallback: Enable automatic fallback to other API keys (default: True)

    Returns:
        Dict with execution results
    """
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not configured")

    db = PostgreSQLURLDatabase(database_url)

    try:
        # Update status: RUNNING
        db.update_execution_status(
            execution_id,
            'running',
            started_at=datetime.utcnow()
        )

        # Select API key (manual or round-robin)
        api_key_data = select_api_key(db, api_key_id)
        if not api_key_data:
            raise Exception("No API key available")

        selected_api_key_id = api_key_data['id']
        logger.info(f"Selected API key: {api_key_data['alias']} (ID: {selected_api_key_id})")

        # Execute Stage 01 (subprocess for isolation)
        run_date = datetime.now().strftime('%Y-%m-%d')  # Always current date
        log_file = f"logs/{run_date}/celery_stage01_{execution_id}.log"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        # Get source names from IDs
        source_names = []
        if source_ids:
            for sid in source_ids:
                source = db.get_source_by_id(sid)
                if source:
                    source_names.append(source['name'])

        # Build command (pass execution_id and api_key_id for tracking + fallback)
        cmd = [
            sys.executable,
            'stages/01_extract_urls.py',
            '--date', run_date,
            '--execution-id', str(execution_id),
            '--api-key-id', str(selected_api_key_id)  # ✅ Pass api_key_id for fallback support
        ]
        if source_names:
            cmd.extend(['--sources'] + source_names)

        # Add --no-fallback flag if fallback is disabled
        if not use_fallback:
            cmd.append('--no-fallback')
            logger.info(f"Executing Stage 01 WITHOUT fallback (only selected key will be used)")
        else:
            logger.info(f"Executing Stage 01 WITH fallback support")

        logger.info(f"Command: {' '.join(cmd)}")

        # Execute (no need to pass OPENAI_API_KEY in env anymore)
        env = os.environ.copy()
        env['TOKEN_TRACKER_EXECUTION_ID'] = str(execution_id)
        with open(log_file, 'w') as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                env=env  # ✅ No decrypted key in env
            )

        if result.returncode != 0:
            raise Exception(f"Stage 01 failed with exit code {result.returncode}")

        # Mark as completed first (to set completed_at timestamp)
        db.update_execution_status(
            execution_id,
            'completed',
            completed_at=datetime.utcnow(),
            log_file=log_file
        )

        # Calculate costs from token_usage.csv using execution timestamps
        cost_data = calculate_execution_cost(execution_id, db=db, stage='01')

        # Update execution_history with token costs
        # (URL metrics already updated by Stage 01 script)
        db.update_execution_status(
            execution_id,
            'completed',
            input_tokens=cost_data['input_tokens'],
            output_tokens=cost_data['output_tokens'],
            cost_usd=cost_data['cost_usd'],
            cost_eur=0.0  # Not calculated for now
        )

        # Update API key usage
        db.update_api_key_usage(api_key_data['id'])

        # Fetch final metrics from execution_history for return
        execution_data = db.get_execution_by_id(execution_id)

        logger.info(f"Stage 01 completed: {execution_data['total_items']} URLs ({execution_data['processed_items']} new), ${cost_data['cost_usd']}")

        # Trigger any newsletter schedules waiting for Stage 1 data
        trigger_newsletters_after_stage1(
            db=db,
            run_date=datetime.utcnow().date(),
            source_ids=source_ids
        )

        return {
            'status': 'completed',
            'urls_extracted': execution_data['total_items'],
            'urls_inserted': execution_data['processed_items'],
            'cost_usd': cost_data['cost_usd']
        }

    except Exception as e:
        logger.error(f"Stage 01 execution failed: {e}", exc_info=True)

        # Update as failed
        db.update_execution_status(
            execution_id,
            'failed',
            completed_at=datetime.utcnow(),
            error_message=str(e)
        )

        raise  # Re-raise for Celery to mark as FAILURE
