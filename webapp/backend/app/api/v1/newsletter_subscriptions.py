"""
API endpoints for user newsletter subscriptions (PostgreSQL-backed).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.auth.dependencies import get_current_user
from common.postgres_db import PostgreSQLURLDatabase
from app.config import settings

router = APIRouter()


def get_db():
    """Get database instance."""
    return PostgreSQLURLDatabase(settings.DATABASE_URL)


class SubscriptionCreate(BaseModel):
    newsletter_name: str = Field(..., min_length=1, max_length=200)


@router.get("", status_code=status.HTTP_200_OK)
async def list_subscriptions(current_user: dict = Depends(get_current_user)):
    """List newsletter subscriptions for the current user."""
    db = get_db()
    return db.get_user_newsletter_subscriptions(current_user["id"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def subscribe(
    payload: SubscriptionCreate,
    current_user: dict = Depends(get_current_user),
):
    """Subscribe current user to a newsletter by name."""
    db = get_db()
    config = db.get_newsletter_config_by_name(payload.newsletter_name)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Newsletter no encontrada")

    # Private newsletters can only be accessed by their owner
    if config.get("visibility", "public") == "private" and config.get("created_by_user_id") != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para suscribirte a esta newsletter"
        )

    if config.get("created_by_user_id") == current_user["id"] and current_user.get("role") == "enterprise":
        # allow subscribing to own newsletters (for clarity); no-op
        pass
    inserted = db.add_user_newsletter_subscription(current_user["id"], payload.newsletter_name)
    if not inserted:
        # Already exists
        inserted = {
            "newsletter_name": config["name"],
            "display_name": config.get("display_name"),
            "description": config.get("description"),
            "is_active": config.get("is_active", True),
            "visibility": config.get("visibility"),
            "created_by_user_id": config.get("created_by_user_id"),
        }
    return inserted


@router.delete("/{newsletter_name}", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    newsletter_name: str,
    current_user: dict = Depends(get_current_user),
):
    """Unsubscribe current user from a newsletter by name."""
    db = get_db()
    db.remove_user_newsletter_subscription(current_user["id"], newsletter_name)
    return None
