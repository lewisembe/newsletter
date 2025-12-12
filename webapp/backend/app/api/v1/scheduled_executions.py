"""
Scheduled Executions API endpoints.
Provides CRUD operations for scheduled executions filtered by execution_target.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
import os
import logging
import psycopg

from common.postgres_db import PostgreSQLURLDatabase
from app.auth.dependencies import get_current_admin
from app.schemas.stage_executions import (
    ScheduledExecutionResponse,
    ScheduledExecutionCreate,
    ScheduledExecutionUpdate
)

logger = logging.getLogger(__name__)
router = APIRouter()


def get_db() -> PostgreSQLURLDatabase:
    """Get database instance."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DATABASE_URL not configured"
        )
    return PostgreSQLURLDatabase(database_url)


@router.get("", response_model=List[ScheduledExecutionResponse])
async def list_scheduled_executions(
    execution_type: Optional[str] = Query(None, description="Filter by execution_target (e.g., 'newsletter_pipeline', '01_extract_urls')"),
    current_user: dict = Depends(get_current_admin)
):
    """
    List scheduled executions, optionally filtered by execution_target.

    Args:
        execution_type: Filter by execution_target value (maps to database column 'execution_target')

    Returns:
        List of scheduled executions matching the filter
    """
    db = get_db()

    try:
        # Note: frontend uses 'execution_type' but database column is 'execution_target'
        schedules = db.get_scheduled_executions(execution_target=execution_type)
        return schedules
    except psycopg.errors.UndefinedTable:
        # Return empty list if the table is not yet created to avoid breaking the UI
        return []
    except Exception as e:
        logger.error(f"Failed to retrieve scheduled executions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve scheduled executions: {str(e)}"
        )


@router.post("", response_model=ScheduledExecutionResponse, status_code=status.HTTP_201_CREATED)
async def create_scheduled_execution(
    schedule: ScheduledExecutionCreate,
    current_user: dict = Depends(get_current_admin)
):
    """
    Create a new scheduled execution.

    Args:
        schedule: Scheduled execution data

    Returns:
        Created scheduled execution
    """
    db = get_db()

    try:
        # Validate execution_target and newsletter_config_id relationship
        if schedule.execution_target == "newsletter_pipeline" and not schedule.newsletter_config_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="newsletter_config_id is required for newsletter_pipeline execution target"
            )

        if schedule.execution_target != "newsletter_pipeline" and schedule.newsletter_config_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="newsletter_config_id should only be provided for newsletter_pipeline execution target"
            )

        # Prepare schedule data
        schedule_data = {
            "name": schedule.name,
            "cron_expression": schedule.cron_expression,
            "api_key_id": schedule.api_key_id,
            "execution_target": schedule.execution_target,
            "newsletter_config_id": schedule.newsletter_config_id,
            "parameters": {
                "source_filter": schedule.source_filter,
                "trigger_on_stage1_ready": schedule.trigger_on_stage1_ready
            },
            "is_enabled": schedule.is_active,
            "created_by_user_id": current_user.get("id")
        }

        created_schedule = db.create_scheduled_execution(schedule_data)
        return created_schedule
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create scheduled execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create scheduled execution: {str(e)}"
        )


@router.get("/{schedule_id}", response_model=ScheduledExecutionResponse)
async def get_scheduled_execution(
    schedule_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Get a specific scheduled execution by ID.

    Args:
        schedule_id: ID of the scheduled execution

    Returns:
        Scheduled execution details
    """
    db = get_db()

    try:
        schedule = db.get_scheduled_execution_by_id(schedule_id)
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduled execution with ID {schedule_id} not found"
            )
        return schedule
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve scheduled execution {schedule_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve scheduled execution: {str(e)}"
        )


@router.put("/{schedule_id}", response_model=ScheduledExecutionResponse)
async def update_scheduled_execution(
    schedule_id: int,
    schedule: ScheduledExecutionUpdate,
    current_user: dict = Depends(get_current_admin)
):
    """
    Update a scheduled execution.

    Args:
        schedule_id: ID of the scheduled execution to update
        schedule: Updated schedule data

    Returns:
        Updated scheduled execution
    """
    db = get_db()

    try:
        # Check if schedule exists
        existing_schedule = db.get_scheduled_execution_by_id(schedule_id)
        if not existing_schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduled execution with ID {schedule_id} not found"
            )

        # Validate execution_target and newsletter_config_id relationship
        execution_target = schedule.execution_target or existing_schedule.get("execution_target")
        newsletter_config_id = schedule.newsletter_config_id if schedule.newsletter_config_id is not None else existing_schedule.get("newsletter_config_id")

        if execution_target == "newsletter_pipeline" and not newsletter_config_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="newsletter_config_id is required for newsletter_pipeline execution target"
            )

        # Prepare update data
        update_data = {}
        if schedule.name is not None:
            update_data["name"] = schedule.name
        if schedule.cron_expression is not None:
            update_data["cron_expression"] = schedule.cron_expression
        if schedule.api_key_id is not None:
            update_data["api_key_id"] = schedule.api_key_id
        if schedule.execution_target is not None:
            update_data["execution_target"] = schedule.execution_target
        if schedule.newsletter_config_id is not None:
            update_data["newsletter_config_id"] = schedule.newsletter_config_id
        if schedule.is_active is not None:
            update_data["is_enabled"] = schedule.is_active

        # Handle parameters
        # Rebuild parameters from mapped fields (don't use existing_schedule["parameters"]
        # as it contains the old JSONB, not the mapped values)
        if schedule.source_filter is not None or schedule.trigger_on_stage1_ready is not None:
            # Start with current mapped values
            existing_params = {
                "source_filter": existing_schedule.get("source_filter"),
                "trigger_on_stage1_ready": existing_schedule.get("trigger_on_stage1_ready", False)
            }
            logger.info(f"🔍 [BEFORE] existing_params: {existing_params}")
            logger.info(f"🔍 schedule.trigger_on_stage1_ready: {schedule.trigger_on_stage1_ready} (type: {type(schedule.trigger_on_stage1_ready)})")
            # Override with new values if provided
            if schedule.source_filter is not None:
                existing_params["source_filter"] = schedule.source_filter
            if schedule.trigger_on_stage1_ready is not None:
                existing_params["trigger_on_stage1_ready"] = schedule.trigger_on_stage1_ready
            logger.info(f"🔍 [AFTER] existing_params: {existing_params}")
            update_data["parameters"] = existing_params

        updated_schedule = db.update_scheduled_execution(schedule_id, update_data)
        return updated_schedule
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update scheduled execution {schedule_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update scheduled execution: {str(e)}"
        )


@router.put("/{schedule_id}/toggle", response_model=ScheduledExecutionResponse)
async def toggle_scheduled_execution(
    schedule_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Toggle the active status of a scheduled execution.

    Args:
        schedule_id: ID of the scheduled execution to toggle

    Returns:
        Updated scheduled execution
    """
    db = get_db()

    try:
        # Check if schedule exists
        existing_schedule = db.get_scheduled_execution_by_id(schedule_id)
        if not existing_schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduled execution with ID {schedule_id} not found"
            )

        # Toggle is_enabled
        current_status = existing_schedule.get("is_active", True)
        update_data = {"is_enabled": not current_status}

        updated_schedule = db.update_scheduled_execution(schedule_id, update_data)
        return updated_schedule
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle scheduled execution {schedule_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle scheduled execution: {str(e)}"
        )


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheduled_execution(
    schedule_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Delete a scheduled execution.

    Args:
        schedule_id: ID of the scheduled execution to delete

    Returns:
        No content on success
    """
    db = get_db()

    try:
        # Check if schedule exists
        existing_schedule = db.get_scheduled_execution_by_id(schedule_id)
        if not existing_schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduled execution with ID {schedule_id} not found"
            )

        db.delete_scheduled_execution(schedule_id)
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete scheduled execution {schedule_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete scheduled execution: {str(e)}"
        )
