"""
Celery tasks for scheduled execution management.
"""
from celery_app import celery
from croniter import croniter
from datetime import datetime, date, time, timedelta, timezone
import os
import logging
import json
import random

logger = logging.getLogger(__name__)


def is_schedule_for_date(schedule: dict, target_date: date):
    """Return whether cron has an occurrence on target_date and its previous run."""
    day_end = datetime.combine(target_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    cron = croniter(schedule['cron_expression'], day_end)
    prev_run = cron.get_prev(datetime)
    return prev_run.date() == target_date, prev_run


@celery.task(name='process_scheduled_executions')
def process_scheduled_executions_task():
    """
    Check for due schedules and launch executions (both Stage 1 and Newsletter pipelines).
    This task runs every minute via Celery Beat.
    """
    from common.postgres_db import PostgreSQLURLDatabase
    from celery_app.tasks.stage01_tasks import execute_stage01_task
    from celery_app.tasks.newsletter_tasks import execute_newsletter_pipeline_task

    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL not configured")
        return

    db = PostgreSQLURLDatabase(database_url)

    try:
        # Get active schedules (includes both Stage 1 and Newsletter pipelines)
        schedules = db.get_active_schedules()

        logger.info(f"Processing {len(schedules)} active schedules")

        # Randomize schedule order to handle ties in execution time fairly
        random.shuffle(schedules)

        for schedule in schedules:
            try:
                execution_target = schedule.get('execution_target', '01_extract_urls')

                # Route based on execution_target
                if execution_target == '01_extract_urls':
                    # STAGE 1 EXECUTION
                    now = datetime.now(timezone.utc)
                    cron = croniter(schedule['cron_expression'], now)
                    prev_run = cron.get_prev(datetime)

                    # Check if we're within 15 minutes AFTER the scheduled time
                    # Wider window for Stage 1 to ensure resilience against worker delays
                    time_since_scheduled = (now - prev_run).total_seconds()
                    STAGE1_WINDOW_SECONDS = 900  # 15 minutes

                    logger.info(f"Schedule {schedule['id']} ({schedule['name']}): "
                               f"target={execution_target}, "
                               f"cron={schedule['cron_expression']}, "
                               f"prev_run={prev_run}, "
                               f"time_since={time_since_scheduled}s, "
                               f"last_run_at={schedule['last_run_at']}")

                    should_execute = (
                        0 <= time_since_scheduled < STAGE1_WINDOW_SECONDS and
                        (schedule['last_run_at'] is None or
                         (now - schedule['last_run_at']).total_seconds() > STAGE1_WINDOW_SECONDS)
                    )

                    if not should_execute:
                        continue

                    # Check global lock for Stage 1
                    if db.has_running_execution():
                        logger.info(f"Skipping Stage 1 schedule {schedule['id']} - another execution is already running")
                        continue

                    params = schedule.get('parameters') or {}
                    if isinstance(params, str):
                        try:
                            params = json.loads(params)
                        except Exception:
                            params = {}
                    source_filter = params.get('source_filter', [])
                    source_ids = []

                    if source_filter:
                        for source_name in source_filter:
                            source = db.get_source_by_name(source_name)
                            if source:
                                source_ids.append(source['id'])
                            else:
                                logger.warning(f"Source '{source_name}' not found")

                    exec_params = {'source_names': source_filter} if source_filter else {}
                    parameters_json = json.dumps(exec_params) if exec_params else None

                    execution_id = db.create_execution(
                        schedule_id=schedule['id'],
                        execution_type='scheduled',
                        api_key_id=schedule['api_key_id'],
                        stage_name='01_extract_urls',
                        parameters=parameters_json
                    )

                    logger.info(f"Created Stage 1 execution {execution_id}")

                    execute_stage01_task.apply_async(
                        args=[execution_id, schedule['api_key_id'], source_ids if source_ids else None],
                        queue='stage01'
                    )

                    db.update_schedule_last_run(schedule['id'], datetime.now(timezone.utc))

                elif execution_target == 'newsletter_pipeline':
                    # NEWSLETTER PIPELINE EXECUTION
                    newsletter_config_id = schedule.get('newsletter_config_id')

                    params = schedule.get('parameters') or {}
                    if isinstance(params, str):
                        try:
                            params = json.loads(params)
                        except Exception:
                            params = {}
                    trigger_on_stage1_ready = params.get('trigger_on_stage1_ready', False)

                    if not newsletter_config_id:
                        logger.error(f"Schedule {schedule['id']}: newsletter_config_id is required for newsletter_pipeline")
                        continue

                    config = db.get_newsletter_config_by_id(newsletter_config_id)
                    if not config:
                        logger.error(f"Schedule {schedule['id']}: Newsletter config {newsletter_config_id} not found")
                        continue

                    today = datetime.now(timezone.utc).date()
                    required_sources = config.get('source_ids') or []

                    if trigger_on_stage1_ready:
                        is_for_today, scheduled_time = is_schedule_for_date(schedule, today)
                        logger.info(
                            f"Schedule {schedule['id']} ({schedule['name']}): "
                            f"target={execution_target}, mode=stage1_ready, "
                            f"cron={schedule['cron_expression']}, scheduled_time={scheduled_time}, "
                            f"last_run_at={schedule['last_run_at']}"
                        )
                        if not is_for_today:
                            logger.info(f"Skipping newsletter schedule {schedule['id']}: CRON does not target {today}")
                            continue
                        now = datetime.now(timezone.utc)
                        # Do not trigger before the scheduled time for the day
                        if now < scheduled_time:
                            logger.info(
                                f"Skipping newsletter schedule {schedule['id']}: "
                                f"current time {now} is before scheduled {scheduled_time}"
                            )
                            continue
                        # Avoid double triggering for the same scheduled occurrence
                        last_run_at = schedule.get('last_run_at')
                        if last_run_at and last_run_at >= scheduled_time:
                            logger.info(
                                f"Skipping newsletter schedule {schedule['id']}: already triggered for this window "
                                f"(scheduled at {scheduled_time}, last_run_at={last_run_at})"
                            )
                            continue
                        should_execute = True
                        time_since_scheduled = (now - scheduled_time).total_seconds()
                    else:
                        now = datetime.now(timezone.utc)
                        cron = croniter(schedule['cron_expression'], now)
                        prev_run = cron.get_prev(datetime)

                        time_since_scheduled = (now - prev_run).total_seconds()

                        logger.info(f"Schedule {schedule['id']} ({schedule['name']}): "
                                   f"target={execution_target}, "
                                   f"cron={schedule['cron_expression']}, "
                                   f"prev_run={prev_run}, "
                                   f"time_since={time_since_scheduled}s, "
                                   f"last_run_at={schedule['last_run_at']}")

                        should_execute = (
                            0 <= time_since_scheduled < 60 and
                            (schedule['last_run_at'] is None or
                             (now - schedule['last_run_at']).total_seconds() > 60)
                        )

                    if not should_execute:
                        continue

                    # Verify that Stage 1 has run for today with the required sources
                    if not db.has_stage01_executions_for_sources(today, required_sources):
                        logger.warning(
                            f"Skipping newsletter schedule {schedule['id']}: "
                            f"No Stage 1 execution found for required sources on {today}"
                        )
                        continue

                    # Check execution mode for concurrency control
                    execution_mode = db.get_system_config('newsletter_execution_mode') or 'parallel'
                    sequential_mode = (execution_mode == 'sequential')

                    # Create newsletter execution with atomic lock (if sequential)
                    execution_id = db.create_newsletter_execution(
                        newsletter_config_id=newsletter_config_id,
                        run_date=today,
                        execution_type='scheduled',
                        schedule_id=schedule['id'],
                        api_key_id=schedule['api_key_id'],
                        sequential_mode=sequential_mode
                    )

                    # If lock not acquired (sequential mode), skip this execution
                    if not execution_id:
                        logger.info(
                            f"Skipping newsletter schedule {schedule['id']}: "
                            f"Could not acquire lock (sequential mode active)"
                        )
                        continue

                    logger.info(f"Created newsletter execution {execution_id} for config {newsletter_config_id}")

                    # Create stage execution records (4 stages: 2, 3, 4, 5)
                    for stage_num, stage_name in [(2, '02_filter'), (3, '03_ranker'), (4, '04_extract_content'), (5, '05_generate')]:
                        db.create_newsletter_stage_execution(
                            newsletter_execution_id=execution_id,
                            stage_number=stage_num,
                            stage_name=stage_name
                        )

                    # Launch newsletter pipeline task
                    execute_newsletter_pipeline_task.apply_async(
                        args=[execution_id],
                        kwargs={'api_key_id': schedule['api_key_id']},
                        queue='newsletters'
                    )

                    db.update_schedule_last_run(schedule['id'], datetime.now(timezone.utc))

                else:
                    logger.warning(f"Unknown execution_target: {execution_target}")

            except Exception as e:
                logger.error(f"Error processing schedule {schedule.get('id')}: {e}", exc_info=True)
                continue

    except Exception as e:
        logger.error(f"Error in scheduled executions task: {e}", exc_info=True)
