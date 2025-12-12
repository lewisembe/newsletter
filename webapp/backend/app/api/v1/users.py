"""
User management endpoints for profile and admin operations.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.auth import (
    UserResponse, UserListItem, UserProfileUpdate,
    UserRoleUpdate, MessageResponse
)
from app.auth.utils import hash_password, verify_password
from app.auth.dependencies import get_db, get_current_user, get_current_admin
from common.postgres_db import PostgreSQLURLDatabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# USER PROFILE ENDPOINTS
# ============================================

@router.get("/profile", response_model=UserResponse)
async def get_profile(
    current_user: dict = Depends(get_current_user)
):
    """
    Get own profile (all authenticated users).
    """
    return UserResponse(**current_user)


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    updates: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Update own profile (name and/or password).

    Steps:
    1. If updating password: verify current_password
    2. If updating nombre: validate not empty
    3. Update database
    4. Return updated user data
    """
    user_id = current_user["id"]
    new_password_hash = None

    # Validate password change
    if updates.new_password:
        if not updates.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere la contraseña actual para cambiar la contraseña"
            )

        # Fetch user with hashed_password
        user_with_password = db.get_user_by_email(current_user["email"])
        if not user_with_password:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        # Verify current password
        if not verify_password(updates.current_password, user_with_password["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La contraseña actual es incorrecta"
            )

        # Hash new password
        new_password_hash = hash_password(updates.new_password)

    # Update profile
    success = db.update_user_profile(
        user_id=user_id,
        nombre=updates.nombre,
        new_password_hash=new_password_hash
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar el perfil"
        )

    # Fetch updated user
    updated_user = db.get_user_by_id(user_id)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    logger.info(f"User profile updated: {updated_user['email']}")

    return UserResponse(**updated_user)


@router.delete("/profile", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_own_account(
    current_user: dict = Depends(get_current_user),
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Deactivate own account (soft delete).

    Notes:
    - Admin users cannot deactivate themselves.
    - Sets is_active=False; token becomes invalid on next auth check.
    """
    if current_user.get("role") == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los administradores no pueden eliminar su propia cuenta"
        )

    if not current_user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cuenta ya está desactivada"
        )

    success = db.deactivate_user(current_user["id"])

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al desactivar la cuenta"
        )

    logger.info(f"User self-deactivated: {current_user['email']}")

    return None  # 204 No Content


# ============================================
# ADMIN ENDPOINTS
# ============================================

@router.get("", response_model=List[UserListItem])
async def list_all_users(
    include_inactive: bool = False,
    admin: dict = Depends(get_current_admin),
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Admin: List all users.

    Query params:
    - include_inactive: Include deactivated users (default: False)
    """
    users = db.get_all_users(include_inactive=include_inactive)

    return [UserListItem(**user) for user in users]


@router.put("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    role_update: UserRoleUpdate,
    admin: dict = Depends(get_current_admin),
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Admin: Update user role (user <-> enterprise).

    Validations:
    1. Target user exists
    2. Target user is not admin (cannot change admin roles)
    3. Admin cannot change own role
    4. Role is valid ('user' or 'enterprise')
    """
    # Check if target user exists
    target_user = db.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    # Cannot change admin roles
    if target_user["role"] == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede cambiar el rol de administrador"
        )

    # Admin cannot change own role
    if target_user["id"] == admin["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes cambiar tu propio rol"
        )

    # Update role
    success = db.update_user_role(user_id, role_update.role)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar el rol del usuario"
        )

    # Fetch updated user
    updated_user = db.get_user_by_id(user_id)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    logger.info(f"User role updated: {updated_user['email']} -> {role_update.role}")

    return UserResponse(**updated_user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: int,
    admin: dict = Depends(get_current_admin),
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Admin: Soft delete user (set is_active=False).

    Validations:
    - Cannot deactivate admin users
    - Cannot deactivate self
    """
    # Check if target user exists
    target_user = db.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    # Cannot deactivate admin
    if target_user["role"] == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede desactivar un usuario administrador"
        )

    # Cannot deactivate self
    if target_user["id"] == admin["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivarte a ti mismo"
        )

    # Deactivate user
    success = db.deactivate_user(user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al desactivar el usuario"
        )

    logger.info(f"User deactivated: {target_user['email']}")

    return None  # 204 No Content


@router.post("/{user_id}/reactivate", response_model=UserResponse)
async def reactivate_user(
    user_id: int,
    admin: dict = Depends(get_current_admin),
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Admin: Reactivate user (set is_active=True).

    Validations:
    - User must exist
    - User must be inactive
    """
    # Check if target user exists
    target_user = db.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    # Check if user is already active
    if target_user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya está activo"
        )

    # Reactivate user
    success = db.reactivate_user(user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al reactivar el usuario"
        )

    # Fetch updated user
    updated_user = db.get_user_by_id(user_id)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    logger.info(f"User reactivated: {updated_user['email']}")

    return UserResponse(**updated_user)
