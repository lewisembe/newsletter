"""
API endpoints for newsletter configurations.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
import psycopg
from app.schemas.newsletter_configs import (
    NewsletterConfigCreate,
    NewsletterConfigUpdate,
    NewsletterConfigResponse
)
from app.auth.dependencies import get_current_user, get_current_admin
from common.postgres_db import PostgreSQLURLDatabase
import os

router = APIRouter()

def get_db():
    """Get database instance."""
    return PostgreSQLURLDatabase(os.getenv('DATABASE_URL'))


@router.post("", response_model=NewsletterConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_newsletter_config(
    config: NewsletterConfigCreate,
    current_user: dict = Depends(get_current_admin)
):
    """
    Create a new newsletter configuration.
    Requires admin privileges.
    """
    db = get_db()

    try:
        # Check if name already exists
        existing = db.get_newsletter_config_by_name(config.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Newsletter config with name '{config.name}' already exists"
            )

        # Prepare config data
        config_data = config.model_dump()
        config_data['created_by_user_id'] = current_user['id']

        # Create config
        created_config = db.create_newsletter_config(config_data)

        if not created_config:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create newsletter config"
            )

        return created_config

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating newsletter config: {str(e)}"
        )


@router.get("", response_model=List[NewsletterConfigResponse])
async def list_newsletter_configs(
    only_active: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """
    List all newsletter configurations with enriched data (source count, categories).
    """
    db = get_db()

    try:
        configs = db.get_all_newsletter_configs(only_active=only_active)
    except psycopg.errors.UndefinedColumn:
        # Fallback before visibility column exists
        configs = db.execute_query("SELECT * FROM newsletter_configs ORDER BY name;")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching newsletter configs: {str(e)}"
        )

    # Enforce visibility rules for non-admin users
    if current_user.get("role") != "admin":
        configs = [
            cfg for cfg in configs
            if cfg.get("visibility", "public") == "public" or cfg.get("created_by_user_id") == current_user["id"]
        ]

    # Enrich each config with computed fields
    enriched_configs = []
    for config in configs:
        enriched = dict(config)
        # Default visibility to public for legacy rows
        enriched.setdefault("visibility", "public")

        # Count sources
        source_ids = config.get('source_ids', [])
        enriched['source_count'] = len(source_ids) if source_ids else 0

        # Get category names (category_ids contains strings, not IDs)
        category_ids = config.get('category_ids', [])
        enriched['categories'] = category_ids if category_ids else []

        enriched_configs.append(enriched)

    return enriched_configs


@router.get("/{config_id}", response_model=NewsletterConfigResponse)
async def get_newsletter_config(
    config_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific newsletter configuration by ID.
    """
    db = get_db()

    try:
        config = db.get_newsletter_config_by_id(config_id)

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Newsletter config {config_id} not found"
            )

        # Enforce visibility for non-admin users
        if current_user.get("role") != "admin":
            if config.get("visibility") == "private" and config.get("created_by_user_id") != current_user["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permiso para ver esta newsletter"
                )

        return config

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching newsletter config: {str(e)}"
        )


@router.put("/{config_id}", response_model=NewsletterConfigResponse)
async def update_newsletter_config(
    config_id: int,
    config_update: NewsletterConfigUpdate,
    current_user: dict = Depends(get_current_admin)
):
    """
    Update a newsletter configuration.
    Requires admin privileges.
    """
    db = get_db()

    try:
        # Check if config exists
        existing = db.get_newsletter_config_by_id(config_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Newsletter config {config_id} not found"
            )

        # Prepare update data (exclude None values)
        update_data = config_update.model_dump(exclude_none=True)

        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        # Update config
        updated_config = db.update_newsletter_config(config_id, update_data)

        if not updated_config:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update newsletter config"
            )

        return updated_config

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating newsletter config: {str(e)}"
        )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_newsletter_config(
    config_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Delete a newsletter configuration.
    Requires admin privileges.
    """
    db = get_db()

    try:
        # Check if config exists
        existing = db.get_newsletter_config_by_id(config_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Newsletter config {config_id} not found"
            )

        # Delete config
        db.delete_newsletter_config(config_id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting newsletter config: {str(e)}"
        )
