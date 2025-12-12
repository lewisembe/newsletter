"""
API endpoints for Sources management.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
import os
import logging

from app.schemas.sources import (
    SourceCreate, SourceUpdate, SourceResponse, SourceListItem
)
from app.auth.dependencies import get_current_admin
from common.postgres_db import PostgreSQLURLDatabase

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


@router.get("", response_model=List[SourceListItem])
async def list_sources(
    include_inactive: bool = False,
    current_user: dict = Depends(get_current_admin)
):
    """
    List all sources (admin only).

    **Query Parameters:**
    - include_inactive: Include inactive sources (default: false)
    """
    try:
        db = get_db()
        sources = db.get_all_sources(include_inactive=include_inactive)
        return sources
    except Exception as e:
        logger.error(f"Error listing sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    source_data: SourceCreate,
    current_user: dict = Depends(get_current_admin)
):
    """
    Create new source (admin only).

    **Note:** Source name must be unique.
    """
    db = get_db()

    try:
        # Check if name already exists
        existing = db.get_source_by_name(source_data.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Source with name '{source_data.name}' already exists"
            )

        source_id = db.create_source(
            name=source_data.name,
            display_name=source_data.display_name,
            base_url=source_data.base_url,
            language=source_data.language,
            description=source_data.description,
            is_active=source_data.is_active,
            priority=source_data.priority,
            notes=source_data.notes
        )

        source = db.get_source_by_id(source_id)
        return source

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Get source by ID (admin only).
    """
    db = get_db()
    source = db.get_source_by_id(source_id)

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found"
        )

    return source


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: int,
    source_update: SourceUpdate,
    current_user: dict = Depends(get_current_admin)
):
    """
    Update source (admin only).

    **Note:** Only provided fields will be updated.
    """
    db = get_db()

    try:
        # Check if source exists
        existing = db.get_source_by_id(source_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source not found"
            )

        # If updating name, check uniqueness
        if source_update.name and source_update.name != existing['name']:
            name_exists = db.get_source_by_name(source_update.name)
            if name_exists:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Source with name '{source_update.name}' already exists"
                )

        success = db.update_source(source_id, **source_update.dict(exclude_unset=True))
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update source"
            )

        source = db.get_source_by_id(source_id)
        return source

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Delete source (soft delete, admin only).

    **Note:** This performs a soft delete by setting is_active=false.
    """
    db = get_db()
    success = db.delete_source(source_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found"
        )

    return None
