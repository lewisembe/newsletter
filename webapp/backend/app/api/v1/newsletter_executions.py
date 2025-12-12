"""
API endpoints for newsletter executions.
"""
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.newsletter_executions import (
    NewsletterExecutionTriggerRequest,
    NewsletterExecutionResponse,
    NewsletterExecutionDetailResponse,
    StageExecutionResponse
)
from app.auth.dependencies import get_current_admin
from common.postgres_db import PostgreSQLURLDatabase
from celery import Celery
import os
import psycopg
from datetime import datetime
from celery_app.tasks.newsletter_tasks import process_next_queued_execution

router = APIRouter()

def get_db():
    """Get database instance."""
    return PostgreSQLURLDatabase(os.getenv('DATABASE_URL'))

def get_celery_app():
    """Get Celery app instance for sending tasks."""
    return Celery(
        broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1'),
        backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')
    )


@router.post("", response_model=NewsletterExecutionResponse, status_code=status.HTTP_201_CREATED)
async def trigger_newsletter_execution(
    request: NewsletterExecutionTriggerRequest,
    current_user: dict = Depends(get_current_admin)
):
    """
    Trigger a manual newsletter pipeline execution.
    Requires admin privileges.
    """
    db = get_db()

    try:
        # 1. Verify newsletter config exists
        config = db.get_newsletter_config_by_id(request.newsletter_config_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Newsletter config {request.newsletter_config_id} not found"
            )

        # 2. Verify Stage 1 has run for this date
        required_sources = config.get('source_ids') or []
        if not db.has_stage01_executions_for_sources(request.run_date, required_sources):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No Stage 1 execution found for required sources on {request.run_date}. Please run Stage 1 first."
            )

        # 3. Check execution mode and enforce concurrency limits
        execution_mode = db.get_system_config('newsletter_execution_mode') or 'parallel'
        max_parallel = int(db.get_system_config('newsletter_max_parallel') or '3')

        sequential_mode = (execution_mode == 'sequential')

        # 4. Create newsletter execution record
        # In sequential mode: try to acquire lock first
        # If lock not acquired, create as 'queued' status
        if sequential_mode:
            # Try to acquire lock and create execution
            execution_id = db.create_newsletter_execution(
                newsletter_config_id=request.newsletter_config_id,
                run_date=request.run_date,
                execution_type='manual',
                api_key_id=request.api_key_id,
                sequential_mode=True
            )

            # If lock not acquired, create as queued
            if not execution_id:
                execution_id = db.create_newsletter_execution(
                    newsletter_config_id=request.newsletter_config_id,
                    run_date=request.run_date,
                    execution_type='manual',
                    api_key_id=request.api_key_id,
                    sequential_mode=False,  # Don't try lock again
                    initial_status='queued'  # Start as queued
                )
        else:
            # Parallel mode: create directly
            execution_id = db.create_newsletter_execution(
                newsletter_config_id=request.newsletter_config_id,
                run_date=request.run_date,
                execution_type='manual',
                api_key_id=request.api_key_id,
                sequential_mode=False
            )

            # Check concurrency limit (informational only)
            running_count = db.count_running_newsletter_executions()
            if running_count >= max_parallel:
                # Task will be queued by Celery
                pass

        # 5. Create stage execution records (4 stages: 2, 3, 4, 5)
        for stage_num, stage_name in [(2, '02_filter'), (3, '03_ranker'), (4, '04_extract_content'), (5, '05_generate')]:
            db.create_newsletter_stage_execution(
                newsletter_execution_id=execution_id,
                stage_number=stage_num,
                stage_name=stage_name
            )

        # 6. Launch Celery task (only if not queued)
        execution = db.get_newsletter_execution_by_id(execution_id)
        if execution and execution.get('status') != 'queued':
            celery_app = get_celery_app()
            celery_app.send_task(
                'execute_newsletter_pipeline',
                args=[execution_id],
                kwargs={
                    'api_key_id': request.api_key_id,
                    'force': request.force
                },
                queue='newsletters'
            )

        # 7. Return execution details
        execution = db.get_newsletter_execution_by_id(execution_id)
        return execution

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error triggering newsletter execution: {str(e)}"
        )


@router.post("/{execution_id}/abort", response_model=NewsletterExecutionResponse)
async def abort_newsletter_execution(
    execution_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Abort a running/pending newsletter execution and its stages.
    """
    db = get_db()

    execution = db.get_newsletter_execution_by_id(execution_id)
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Newsletter execution not found")

    if execution['status'] in ('completed', 'failed', 'aborted'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Execution is already finished")

    # Revoke Celery task if available
    task_id = execution.get('celery_task_id')
    if task_id:
        try:
            celery_app = get_celery_app()
            celery_app.control.revoke(task_id, terminate=True)
        except Exception as e:
            # Log and continue
            print(f"Failed to revoke celery task {task_id}: {e}")

    # Mark stages as aborted if pending/running
    stages = db.get_newsletter_stage_executions(execution_id)
    for stage in stages:
        if stage.get('status') in ('pending', 'running'):
            db.update_newsletter_stage_execution_status(
                stage['id'],
                'aborted',
                completed_at=datetime.utcnow(),
                error_message="Aborted manually by admin"
            )

    # Mark execution as aborted
    db.update_newsletter_execution_status(
        execution_id,
        'aborted',
        completed_at=datetime.utcnow(),
        error_message="Aborted manually by admin"
    )

    # In sequential mode, advance the queue
    try:
        process_next_queued_execution()
    except Exception as e:
        # Log but do not block abort endpoint
        print(f"Failed to trigger next queued execution after abort: {e}")

    return db.get_newsletter_execution_by_id(execution_id)


@router.post("/{execution_id}/retry", response_model=NewsletterExecutionResponse, status_code=status.HTTP_201_CREATED)
async def retry_newsletter_execution(
    execution_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Retry a failed newsletter execution.
    Creates a new execution with the same configuration.
    """
    db = get_db()

    # Get original execution
    original_execution = db.get_newsletter_execution_by_id(execution_id)
    if not original_execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Newsletter execution not found")

    # Only allow retry for failed executions
    if original_execution['status'] != 'failed':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only retry failed executions. Current status: {original_execution['status']}"
        )

    # Get config from snapshot
    config = original_execution['config_snapshot']
    newsletter_config_id = original_execution['newsletter_config_id']
    run_date = original_execution['run_date']
    api_key_id = original_execution.get('api_key_id')

    # Verify Stage 1 has run for this date
    required_sources = config.get('source_ids') or []
    if not db.has_stage01_executions_for_sources(run_date, required_sources):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No Stage 1 execution found for required sources on {run_date}. Please run Stage 1 first."
        )

    # Check execution mode and enforce concurrency limits
    execution_mode = db.get_system_config('newsletter_execution_mode') or 'parallel'
    sequential_mode = (execution_mode == 'sequential')

    # Create new newsletter execution (retry)
    new_execution_id = db.create_newsletter_execution(
        newsletter_config_id=newsletter_config_id,
        run_date=run_date,
        execution_type='manual',  # Retry is considered manual
        api_key_id=api_key_id,
        sequential_mode=sequential_mode
    )

    # If lock not acquired in sequential mode, create as queued
    if not new_execution_id and sequential_mode:
        new_execution_id = db.create_newsletter_execution(
            newsletter_config_id=newsletter_config_id,
            run_date=run_date,
            execution_type='manual',
            api_key_id=api_key_id,
            sequential_mode=False,
            initial_status='queued'
        )

    # Create stage execution records (4 stages: 2, 3, 4, 5)
    for stage_num, stage_name in [(2, '02_filter'), (3, '03_ranker'), (4, '04_extract_content'), (5, '05_generate')]:
        db.create_newsletter_stage_execution(
            newsletter_execution_id=new_execution_id,
            stage_number=stage_num,
            stage_name=stage_name
        )

    # Launch Celery task (only if not queued)
    new_execution = db.get_newsletter_execution_by_id(new_execution_id)
    if new_execution and new_execution.get('status') != 'queued':
        celery_app = get_celery_app()
        celery_app.send_task(
            'execute_newsletter_pipeline',
            args=[new_execution_id],
            kwargs={'api_key_id': api_key_id},
            queue='newsletters'
        )

    return db.get_newsletter_execution_by_id(new_execution_id)


@router.get("", response_model=List[NewsletterExecutionResponse])
async def list_newsletter_executions(
    limit: int = 50,
    offset: int = 0,
    newsletter_config_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    current_user: dict = Depends(get_current_admin)
):
    """
    List newsletter executions with pagination and filters.
    """
    db = get_db()

    try:
        executions = db.get_newsletter_executions(
            limit=limit,
            offset=offset,
            newsletter_config_id=newsletter_config_id,
            status_filter=status_filter
        )
        return executions

    except psycopg.errors.UndefinedTable:
        # Gracefully handle missing tables on fresh databases
        return []
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching newsletter executions: {str(e)}"
        )


@router.get("/{execution_id}", response_model=NewsletterExecutionResponse)
async def get_newsletter_execution(
    execution_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Get a specific newsletter execution by ID.
    """
    db = get_db()

    try:
        execution = db.get_newsletter_execution_by_id(execution_id)

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Newsletter execution {execution_id} not found"
            )

        return execution

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching newsletter execution: {str(e)}"
        )


@router.get("/{execution_id}/status", response_model=NewsletterExecutionResponse)
async def poll_newsletter_execution_status(
    execution_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Poll newsletter execution status (for real-time updates).
    """
    db = get_db()

    try:
        execution = db.get_newsletter_execution_by_id(execution_id)

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Newsletter execution {execution_id} not found"
            )

        return execution

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error polling newsletter execution: {str(e)}"
        )


@router.get("/{execution_id}/stages", response_model=List[StageExecutionResponse])
async def get_stage_executions(
    execution_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Get all stage executions for a newsletter execution.
    """
    db = get_db()

    try:
        stages = db.get_newsletter_stage_executions(execution_id)
        return stages

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching stage executions: {str(e)}"
        )


@router.get("/{execution_id}/details", response_model=NewsletterExecutionDetailResponse)
async def get_newsletter_execution_details(
    execution_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Get complete details of a newsletter execution including stages and output files.
    """
    db = get_db()

    try:
        execution = db.get_newsletter_execution_by_id(execution_id)

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Newsletter execution {execution_id} not found"
            )

        stages = db.get_newsletter_stage_executions(execution_id)

        # Build output files dict
        output_files = {}
        if execution.get('output_markdown_path'):
            output_files['markdown'] = execution['output_markdown_path']
        if execution.get('output_html_path'):
            output_files['html'] = execution['output_html_path']
        if execution.get('context_report_path'):
            output_files['context_report'] = execution['context_report_path']

        return NewsletterExecutionDetailResponse(
            execution=execution,
            stages=stages,
            output_files=output_files if output_files else None
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching execution details: {str(e)}"
        )
