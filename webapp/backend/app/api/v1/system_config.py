"""
API endpoints for system configuration.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.system_config import SystemConfigUpdate, SystemConfigResponse
from app.auth.dependencies import get_current_admin
from common.postgres_db import PostgreSQLURLDatabase
import os
from pydantic import BaseModel, Field

router = APIRouter()

def get_db():
    """Get database instance."""
    return PostgreSQLURLDatabase(os.getenv('DATABASE_URL'))


@router.get("", response_model=SystemConfigResponse)
async def get_system_config(
    current_user: dict = Depends(get_current_admin)
):
    """
    Get system configuration.
    Requires admin privileges.
    """
    db = get_db()

    try:
        execution_mode = db.get_system_config('newsletter_execution_mode') or 'parallel'
        max_parallel = int(db.get_system_config('newsletter_max_parallel') or '3')

        return SystemConfigResponse(
            newsletter_execution_mode=execution_mode,
            newsletter_max_parallel=max_parallel
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching system config: {str(e)}"
        )


class ExecutionModeUpdate(BaseModel):
    value: str = Field(..., pattern="^(sequential|parallel)$")


class MaxParallelUpdate(BaseModel):
    value: int = Field(..., ge=1, le=50)


@router.put("/execution_mode", response_model=SystemConfigResponse)
async def update_execution_mode(
    payload: ExecutionModeUpdate,
    current_user: dict = Depends(get_current_admin)
):
    """Set newsletter execution mode (compat endpoint for frontend)."""
    db = get_db()
    try:
        db.set_system_config('newsletter_execution_mode', payload.value)
        # Preserve existing max_parallel
        max_parallel = int(db.get_system_config('newsletter_max_parallel') or '3')
        return SystemConfigResponse(
            newsletter_execution_mode=payload.value,
            newsletter_max_parallel=max_parallel
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating execution mode: {str(e)}"
        )


@router.put("/max_parallel_executions", response_model=SystemConfigResponse)
async def update_max_parallel(
    payload: MaxParallelUpdate,
    current_user: dict = Depends(get_current_admin)
):
    """Set max parallel executions (compat endpoint for frontend)."""
    db = get_db()
    try:
        db.set_system_config('newsletter_max_parallel', str(payload.value))
        execution_mode = db.get_system_config('newsletter_execution_mode') or 'parallel'
        return SystemConfigResponse(
            newsletter_execution_mode=execution_mode,
            newsletter_max_parallel=payload.value
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating max parallel executions: {str(e)}"
        )


@router.put("", response_model=SystemConfigResponse)
async def update_system_config(
    config: SystemConfigUpdate,
    current_user: dict = Depends(get_current_admin)
):
    """
    Update system configuration.
    Requires admin privileges.
    """
    db = get_db()

    try:
        # Validate execution mode
        if config.newsletter_execution_mode not in ['sequential', 'parallel']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid execution mode. Must be 'sequential' or 'parallel'"
            )

        # Update config
        db.set_system_config('newsletter_execution_mode', config.newsletter_execution_mode)
        db.set_system_config('newsletter_max_parallel', str(config.newsletter_max_parallel))

        return SystemConfigResponse(
            newsletter_execution_mode=config.newsletter_execution_mode,
            newsletter_max_parallel=config.newsletter_max_parallel
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating system config: {str(e)}"
        )
