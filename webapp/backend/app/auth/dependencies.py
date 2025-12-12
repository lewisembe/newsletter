"""
FastAPI dependencies for authentication and authorization.
"""

from typing import Dict, Optional
from fastapi import Depends, HTTPException, status, Request
from app.config import settings
from app.auth.utils import decode_access_token
from app.utils.jwt_secret_manager import get_jwt_validation_keys
from common.postgres_db import PostgreSQLURLDatabase
import logging

logger = logging.getLogger(__name__)


def get_db() -> PostgreSQLURLDatabase:
    """
    Dependency: Get database instance.

    Returns:
        PostgreSQLURLDatabase instance
    """
    return PostgreSQLURLDatabase(settings.DATABASE_URL)


def get_token_from_cookie(request: Request) -> str:
    """
    Extract JWT token from HTTP-only cookie.

    Args:
        request: FastAPI Request object

    Returns:
        JWT token string

    Raises:
        HTTPException: If token not found
    """
    token = request.cookies.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token


async def get_current_user(
    request: Request,
    db: PostgreSQLURLDatabase = Depends(get_db)
) -> Dict:
    """
    Dependency: Extract and validate current user from JWT token.

    Args:
        request: FastAPI Request object
        db: Database instance

    Returns:
        User dict with id, nombre, email, role, is_active

    Raises:
        HTTPException: If token invalid, user not found, or user inactive
    """
    token = get_token_from_cookie(request)

    # Build list of JWT secrets (current + recent history) to allow seamless rotation
    secret_keys = get_jwt_validation_keys(db)

    # Decode token (supports key rotation)
    payload = decode_access_token(
        token,
        secret_keys,
        settings.JWT_ALGORITHM
    )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    # Fetch user from database
    user = db.get_user_by_id(int(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Check if user is active
    if not user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated"
        )

    return user


async def get_current_user_optional(
    request: Request,
    db: PostgreSQLURLDatabase = Depends(get_db)
) -> Optional[Dict]:
    """
    Dependency: Return current user if auth cookie present; otherwise None.

    Returns:
        User dict or None when no auth cookie is present.

    Raises:
        HTTPException: If token is present but invalid or user inactive/not found.
    """
    token = request.cookies.get("token")
    if not token:
        return None

    # Reuse existing validation flow from get_current_user
    secret_keys = get_jwt_validation_keys(db)
    payload = decode_access_token(
        token,
        secret_keys,
        settings.JWT_ALGORITHM
    )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    user = db.get_user_by_id(int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if not user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated"
        )

    return user


async def get_current_admin(
    current_user: Dict = Depends(get_current_user)
) -> Dict:
    """
    Dependency: Require admin role.

    Args:
        current_user: Current authenticated user

    Returns:
        User dict (only if admin)

    Raises:
        HTTPException: If user is not admin
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    return current_user
