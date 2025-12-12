"""
Newsletter endpoints.

IMPORTANT: Reuses existing common/postgres_db.py (NO duplicate models).
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from common.postgres_db import PostgreSQLURLDatabase
from app.config import settings
from app.auth.dependencies import get_current_user_optional
import logging

router = APIRouter(prefix="/newsletters")
logger = logging.getLogger(__name__)


def get_db():
    """Get database instance (reuses existing PostgreSQL layer)"""
    return PostgreSQLURLDatabase(settings.DATABASE_URL)


@router.get("/latest")
async def get_latest_newsletters(
    limit: int = 10,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Get latest newsletters (public endpoint, no auth required).

    Args:
        limit: Number of newsletters to return (default: 10, max: 50)

    Returns:
        List of newsletter objects
    """
    if limit > 50:
        limit = 50

    try:
        db = get_db()
        user_id = current_user["id"] if current_user else None
        newsletters = db.get_latest_newsletters(limit=limit, user_id=user_id)
        return newsletters
    except Exception as e:
        logger.error(f"Error fetching latest newsletters: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch newsletters")


@router.get("/{newsletter_id}")
async def get_newsletter(
    newsletter_id: int,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Get newsletter by ID.

    Args:
        newsletter_id: Newsletter database ID

    Returns:
        Newsletter object
    """
    try:
        db = get_db()
        newsletter = db.get_newsletter_by_id(newsletter_id)

        if not newsletter:
            raise HTTPException(status_code=404, detail="Newsletter not found")

        config = db.get_newsletter_config_by_name(newsletter.get("newsletter_name"))
        if not config:
            raise HTTPException(status_code=404, detail="Newsletter config not found")

        # Enforce visibility: private newsletters only accessible by owner
        if config.get("visibility") == "private":
            if not current_user or config.get("created_by_user_id") != current_user["id"]:
                raise HTTPException(status_code=403, detail="No tienes permiso para ver esta newsletter")

        return newsletter
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching newsletter {newsletter_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch newsletter")
