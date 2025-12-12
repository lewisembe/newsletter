"""
Stage Execution Management API endpoints.
Handles manual execution triggers, execution history, and CRON schedules.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timedelta
import os
import logging
from celery import Celery

from common.postgres_db import PostgreSQLURLDatabase
from app.auth.dependencies import get_current_admin
from app.schemas.stage_executions import (
    ExecutionHistoryCreate,
    ExecutionHistoryUpdate,
    ExecutionHistoryResponse,
    ScheduledExecutionCreate,
    ScheduledExecutionUpdate,
    ScheduledExecutionResponse,
    ExecutionTriggerRequest,
    ExecutionDetailResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize Celery client (lazy loading)
_celery_app = None

def get_celery_app() -> Celery:
    """Get or create Celery app instance."""
    global _celery_app
    if _celery_app is None:
        broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1")
        result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2")
        _celery_app = Celery(
            "newsletter_tasks",
            broker=broker_url,
            backend=result_backend
        )
    return _celery_app


def get_db() -> PostgreSQLURLDatabase:
    """Get database instance."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DATABASE_URL not configured"
        )
    return PostgreSQLURLDatabase(database_url)


# ============================================================================
# EXECUTION ENDPOINTS
# ============================================================================

@router.post("", response_model=ExecutionHistoryResponse, status_code=status.HTTP_201_CREATED)
async def trigger_execution(
    request: ExecutionTriggerRequest,
    current_user: dict = Depends(get_current_admin)
):
    """
    Trigger a manual Stage 01 execution.
    Creates execution record and launches Celery task.
    """
    db = get_db()

    try:
        # Check for concurrent executions
        if db.has_running_execution():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another execution is already running. Please wait for it to complete."
            )

        # Validate API key exists
        api_key = db.get_api_key_by_id(request.api_key_id)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"API key with id {request.api_key_id} not found"
            )

        # Validate sources if specified
        if request.source_names:
            sources = db.get_all_sources(include_inactive=False)
            available_names = [s['name'] for s in sources]
            invalid_sources = [name for name in request.source_names if name not in available_names]
            if invalid_sources:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid source names: {', '.join(invalid_sources)}"
                )

        # Create execution record (status=pending)
        import json
        parameters_json = json.dumps({"source_names": request.source_names}) if request.source_names else None
        execution_id = db.create_execution(
            schedule_id=None,
            execution_type="manual",
            api_key_id=request.api_key_id,
            stage_name="stage_01",
            parameters=parameters_json
        )

        # Convert source names to source IDs
        source_ids = []
        if request.source_names:
            for name in request.source_names:
                source = db.get_source_by_name(name)
                if source:
                    source_ids.append(source['id'])

        # Launch Celery task asynchronously using send_task
        celery = get_celery_app()
        task = celery.send_task(
            "execute_stage01",  # Use the registered task name
            kwargs={
                "execution_id": execution_id,
                "api_key_id": request.api_key_id,
                "source_ids": source_ids if source_ids else None,
                "use_fallback": request.use_fallback,
            },
            queue="stage01"  # Route to the correct queue that the worker is consuming
        )

        # Update with Celery task ID
        db.update_execution_status(execution_id, status="pending", celery_task_id=str(task.id))

        # Fetch and return the created execution
        execution = db.get_execution_by_id(execution_id)
        return execution

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger execution: {str(e)}"
        )


@router.post("/{execution_id}/abort", response_model=ExecutionHistoryResponse)
async def abort_execution(
    execution_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Abort a running/pending Stage 01 execution.
    """
    db = get_db()
    execution = db.get_execution_by_id(execution_id)

    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")

    if execution['status'] in ('completed', 'failed', 'aborted'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Execution is already finished")

    # Revoke Celery task if available
    task_id = execution.get('celery_task_id')
    if task_id:
        try:
            celery = get_celery_app()
            celery.control.revoke(task_id, terminate=True)
        except Exception as e:
            logger.warning(f"Failed to revoke celery task {task_id}: {e}")

    # Mark as aborted
    db.update_execution_status(
        execution_id,
        status="aborted",
        completed_at=datetime.utcnow(),
        error_message="Aborted manually by admin"
    )

    return db.get_execution_by_id(execution_id)


@router.get("", response_model=List[ExecutionHistoryResponse])
async def list_executions(
    limit: int = 50,
    offset: int = 0,
    stage_name: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: dict = Depends(get_current_admin)
):
    """
    List execution history with optional filters.
    """
    db = get_db()

    try:
        executions = db.get_execution_history(
            limit=limit,
            offset=offset,
            stage_name=stage_name,
            status=status_filter
        )
        return executions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve executions: {str(e)}"
        )


# ============================================================================
# SCHEDULE ENDPOINTS (must be before /{execution_id} to avoid route conflicts)
# ============================================================================

@router.post("/schedules", response_model=ScheduledExecutionResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule: ScheduledExecutionCreate,
    current_user: dict = Depends(get_current_admin)
):
    """
    Create a new CRON schedule for automatic executions.
    """
    db = get_db()

    try:
        # Validate API key exists
        api_key = db.get_api_key_by_id(schedule.api_key_id)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"API key with id {schedule.api_key_id} not found"
            )

        # Validate CRON expression (basic validation)
        cron_parts = schedule.cron_expression.split()
        if len(cron_parts) != 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid CRON expression. Must have 5 fields: minute hour day month weekday"
            )

        # Validate sources if specified
        if schedule.source_filter:
            sources = db.get_all_sources(include_inactive=False)
            available_names = [s['name'] for s in sources]
            invalid_sources = [name for name in schedule.source_filter if name not in available_names]
            if invalid_sources:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid source names: {', '.join(invalid_sources)}"
                )

        # Validate newsletter config if target is newsletter_pipeline
        if schedule.execution_target == "newsletter_pipeline":
            if not schedule.newsletter_config_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="newsletter_config_id is required when execution_target=newsletter_pipeline"
                )
            config = db.get_newsletter_config_by_id(schedule.newsletter_config_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Newsletter config with id {schedule.newsletter_config_id} not found"
                )

        created_schedule = db.create_scheduled_execution(schedule.model_dump())
        return created_schedule

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create schedule: {str(e)}"
        )


@router.get("/schedules", response_model=List[ScheduledExecutionResponse])
async def list_schedules(
    execution_type: Optional[str] = None,
    current_user: dict = Depends(get_current_admin)
):
    """
    List CRON schedules, optionally filtered by execution_target.

    Args:
        execution_type: Filter by execution_target (e.g., '01_extract_urls', 'newsletter_pipeline')
    """
    db = get_db()

    try:
        # Note: frontend uses 'execution_type' but database column is 'execution_target'
        schedules = db.get_scheduled_executions(execution_target=execution_type)
        return schedules
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve schedules: {str(e)}"
        )


@router.put("/schedules/{schedule_id}", response_model=ScheduledExecutionResponse)
async def update_schedule(
    schedule_id: int,
    schedule_update: ScheduledExecutionUpdate,
    current_user: dict = Depends(get_current_admin)
):
    """
    Update an existing schedule.
    """
    db = get_db()

    try:
        # Check schedule exists
        existing = db.get_scheduled_execution_by_id(schedule_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule with id {schedule_id} not found"
            )

        # Validate API key if changed
        update_data = schedule_update.model_dump(exclude_unset=True)
        if "api_key_id" in update_data:
            api_key = db.get_api_key_by_id(update_data["api_key_id"])
            if not api_key:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"API key with id {update_data['api_key_id']} not found"
                )

        # Validate CRON if changed
        if "cron_expression" in update_data:
            cron_parts = update_data["cron_expression"].split()
            if len(cron_parts) != 5:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid CRON expression. Must have 5 fields: minute hour day month weekday"
                )

        # Validate sources if changed
        if "source_filter" in update_data and update_data["source_filter"]:
            sources = db.get_all_sources(include_inactive=False)
            available_names = [s['name'] for s in sources]
            invalid_sources = [name for name in update_data["source_filter"] if name not in available_names]
            if invalid_sources:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid source names: {', '.join(invalid_sources)}"
                )

        # Validate newsletter config if changed or target updated
        effective_target = update_data.get("execution_target", existing.get("execution_target", "01_extract_urls"))
        effective_config_id = update_data.get("newsletter_config_id", existing.get("newsletter_config_id"))
        if effective_target == "newsletter_pipeline":
            if not effective_config_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="newsletter_config_id is required when execution_target=newsletter_pipeline"
                )
            config = db.get_newsletter_config_by_id(effective_config_id)
            if not config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Newsletter config with id {effective_config_id} not found"
                )

        updated_schedule = db.update_scheduled_execution(schedule_id, update_data)
        if not updated_schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule with id {schedule_id} not found"
            )

        return updated_schedule

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update schedule: {str(e)}"
        )


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Delete a schedule.
    """
    db = get_db()

    try:
        success = db.delete_scheduled_execution(schedule_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule with id {schedule_id} not found"
            )
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete schedule: {str(e)}"
        )


@router.put("/schedules/{schedule_id}/toggle", response_model=ScheduledExecutionResponse)
async def toggle_schedule(
    schedule_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Toggle schedule active/inactive status.
    """
    db = get_db()

    try:
        # Get current schedule
        schedule = db.get_scheduled_execution_by_id(schedule_id)
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule with id {schedule_id} not found"
            )

        # Toggle is_active
        new_status = not schedule["is_active"]
        updated_schedule = db.update_scheduled_execution(
            schedule_id,
            {"is_active": new_status}
        )

        return updated_schedule

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle schedule: {str(e)}"
        )


# ============================================================================
# DASHBOARD ENDPOINT (must be before /{execution_id} to avoid conflicts)
# ============================================================================

@router.get("/dashboard")
async def get_dashboard_stats(
    period: str = "all",  # Options: "7d", "30d", "month", "all"
    current_user: dict = Depends(get_current_admin)
):
    """
    Get aggregated dashboard statistics with optional period filter.

    Args:
        period: Time period for stats aggregation
            - "7d": Last 7 days
            - "30d": Last 30 days
            - "month": Current month
            - "all": All time (default)

    Returns system status, recent executions, and resource counts.
    """
    from app.schemas.stage_executions import (
        DashboardResponse,
        DashboardSystemStatus,
        DashboardExecutionStats,
        DashboardResourceCounts,
        DashboardStageCostBreakdown
    )

    db = get_db()

    try:
        # Calculate date filter based on period
        date_filter = ""
        token_start_date = None
        token_end_date = datetime.utcnow().date()
        if period == "7d":
            date_filter = "WHERE created_at >= NOW() - INTERVAL '7 days'"
            token_start_date = token_end_date - timedelta(days=7)
        elif period == "30d":
            date_filter = "WHERE created_at >= NOW() - INTERVAL '30 days'"
            token_start_date = token_end_date - timedelta(days=30)
        elif period == "month":
            date_filter = "WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())"
            token_start_date = token_end_date.replace(day=1)
        # "all" means no filter

        # 1. System Status (always current, no period filter)
        has_running = db.has_running_execution()

        # Get last execution
        recent = db.get_execution_history(limit=1, offset=0)
        last_execution = recent[0] if recent else None

        system_status = DashboardSystemStatus(
            has_running_execution=has_running,
            last_execution=last_execution
        )

        # 2. Recent Executions (last 5, no period filter)
        recent_executions = db.get_execution_history(limit=5, offset=0)

        # 3. Execution Stats (aggregated with period filter)
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Count by status with period filter
            query = f"""
                SELECT
                    status,
                    COUNT(*) as count,
                    COALESCE(SUM(cost_usd), 0) as total_cost,
                    COALESCE(SUM(total_tokens), 0) as total_tokens
                FROM execution_history
                {date_filter}
                GROUP BY status
            """
            cursor.execute(query)
            stats_raw = cursor.fetchall()

            # Initialize counters
            total_executions = 0
            completed = 0
            failed = 0
            running = 0
            pending = 0
            total_cost_usd = 0.0
            total_tokens = 0

            # Process results
            for row in stats_raw:
                status_val = row['status']
                count = row['count']
                total_executions += count
                total_cost_usd += float(row['total_cost'])
                total_tokens += int(row['total_tokens'])

                if status_val == 'completed':
                    completed = count
                elif status_val == 'failed':
                    failed = count
                elif status_val == 'running':
                    running = count
                elif status_val == 'pending':
                    pending = count

            # Calculate success rate
            success_rate = (completed / total_executions * 100) if total_executions > 0 else 0.0

            execution_stats = DashboardExecutionStats(
                total_executions=total_executions,
                completed=completed,
                failed=failed,
                running=running,
                pending=pending,
                success_rate=round(success_rate, 2),
                # Cost/tokens are recalculated below from token_usage to keep a single source of truth
                total_cost_usd=0.0,
                total_tokens=0
            )

        # 4. Resource Counts
        users = db.get_all_users(include_inactive=True)
        active_users = [u for u in users if u.get('is_active', True)]

        sources = db.get_all_sources(include_inactive=True)
        active_sources = [s for s in sources if s.get('is_active', True)]

        schedules = db.get_scheduled_executions()
        active_schedules = [s for s in schedules if s.get('is_active', True)]

        # Dashboard should count every API key, not just admin-level ones
        api_keys = db.get_all_api_keys(include_inactive=True, admin_only=False)

        resource_counts = DashboardResourceCounts(
            total_users=len(users),
            active_users=len(active_users),
            total_sources=len(sources),
            active_sources=len(active_sources),
            active_schedules=len(active_schedules),
            total_api_keys=len(api_keys)
        )

        # 5. Cost breakdown by stage (with period filter)
        cost_by_stage = []
        try:
            token_costs = db.get_token_usage_grouped_by_stage(token_start_date, token_end_date)
            for row in token_costs:
                raw_stage = row.get('stage')
                if raw_stage and raw_stage.startswith('stage_'):
                    stage_name = raw_stage
                elif raw_stage:
                    stage_name = f"stage_{raw_stage.zfill(2)}"
                else:
                    stage_name = "stage_unknown"

                cost_by_stage.append(DashboardStageCostBreakdown(
                    stage_name=stage_name,
                    total_cost_usd=round(float(row.get('total_cost_usd', 0)), 4),
                    total_tokens=int(row.get('total_tokens', 0)),
                    executions=int(row.get('executions', 0)),
                    avg_cost_per_execution=round(float(row.get('avg_cost_per_execution', 0)), 4)
                ))
        except Exception as e:
            logger.warning(f"Failed to aggregate cost by stage from token_usage: {e}")
            cost_by_stage = []

        # Ensure all canonical stages are present (even if zero cost) for UI completeness
        canonical_stages = ["stage_01", "stage_02", "stage_03", "stage_04", "stage_05"]
        existing = {item.stage_name: item for item in cost_by_stage}
        for canonical in canonical_stages:
            if canonical not in existing:
                cost_by_stage.append(DashboardStageCostBreakdown(
                    stage_name=canonical,
                    total_cost_usd=0.0,
                    total_tokens=0,
                    executions=0,
                    avg_cost_per_execution=0.0
                ))

        # Use token_usage (cost_by_stage) as single source of truth for totals
        token_total_cost_usd = round(sum(stage.total_cost_usd for stage in cost_by_stage), 4)
        token_total_tokens = sum(stage.total_tokens for stage in cost_by_stage)

        # Update execution stats with aggregated token usage
        execution_stats.total_cost_usd = token_total_cost_usd
        execution_stats.total_tokens = token_total_tokens

        # Build response
        dashboard_data = DashboardResponse(
            system_status=system_status,
            recent_executions=recent_executions,
            execution_stats=execution_stats,
            resource_counts=resource_counts,
            cost_by_stage=cost_by_stage
        )

        return dashboard_data

    except Exception as e:
        logger.error(f"Failed to retrieve dashboard stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve dashboard statistics: {str(e)}"
        )


# ============================================================================
# EXECUTION DETAIL ENDPOINTS (must be after /schedules to avoid conflicts)
# ============================================================================

@router.get("/{execution_id}", response_model=ExecutionHistoryResponse)
async def get_execution(
    execution_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Get details of a specific execution.
    """
    db = get_db()

    try:
        execution = db.get_execution_by_id(execution_id)
        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution with id {execution_id} not found"
            )
        return execution
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve execution: {str(e)}"
        )


@router.get("/{execution_id}/status", response_model=ExecutionHistoryResponse)
async def poll_execution_status(
    execution_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Polling endpoint for real-time execution status updates.
    Frontend should call this every 3 seconds for running executions.
    """
    db = get_db()

    try:
        execution = db.get_execution_by_id(execution_id)
        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution with id {execution_id} not found"
            )
        return execution
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to poll execution status: {str(e)}"
        )


@router.get("/{execution_id}/details", response_model=ExecutionDetailResponse)
async def get_execution_details(
    execution_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Get detailed information about an execution including:
    - URLs extracted with classification
    - Statistics by source
    - Statistics by category
    """
    db = get_db()

    try:
        details = db.get_execution_details(execution_id)
        if not details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution with id {execution_id} not found"
            )
        return details
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve execution details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve execution details: {str(e)}"
        )


@router.get("/running/check")
async def check_running_execution(
    current_user: dict = Depends(get_current_admin)
):
    """
    Check if there's any execution currently running or pending.
    Returns: { "has_running": true/false }
    """
    db = get_db()

    try:
        has_running = db.has_running_execution()
        return {"has_running": has_running}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check running executions: {str(e)}"
        )
