"""
Authentication endpoints for user registration, login, and logout.
"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from app.schemas.auth import (
    UserRegister, UserLogin, UserResponse, MessageResponse
)
from app.auth.utils import hash_password, verify_password, create_access_token
from app.auth.dependencies import get_db, get_current_user
from app.config import settings
from common.postgres_db import PostgreSQLURLDatabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

def _set_auth_cookie(response: Response, request: Request, token: str, max_age: int):
    """
    Centralized cookie setter so we apply consistent params across endpoints.
    Uses HTTPS-only cookies in production but relaxes on HTTP (local dev).
    """
    secure = settings.COOKIE_SECURE and request.url.scheme == "https"
    cookie_params = {
        "key": "token",
        "value": token,
        "httponly": True,
        "secure": secure,
        "samesite": settings.cookie_samesite,
        "max_age": max_age,
        "path": "/",
    }

    if settings.COOKIE_DOMAIN:
        cookie_params["domain"] = settings.COOKIE_DOMAIN

    response.set_cookie(**cookie_params)


def _delete_auth_cookie(response: Response, request: Request):
    """Delete auth cookie with the same parameters used to set it."""
    secure = settings.COOKIE_SECURE and request.url.scheme == "https"
    cookie_params = {
        "key": "token",
        "secure": secure,
        "samesite": settings.cookie_samesite,
        "path": "/",
    }

    if settings.COOKIE_DOMAIN:
        cookie_params["domain"] = settings.COOKIE_DOMAIN

    response.delete_cookie(**cookie_params)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    response: Response,
    request: Request,
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Register new user and auto-login (set JWT cookie).

    Steps:
    1. Check if email already exists
    2. Hash password
    3. Create user with role='user'
    4. Generate JWT token
    5. Set HTTP-only cookie
    6. Return user data
    """
    # Check if user already exists
    existing_user = db.get_user_by_email(user_data.email)
    if existing_user:
        # If user is inactive, reactivate and update their data
        if not existing_user.get("is_active", False):
            # Hash new password
            hashed_password = hash_password(user_data.password)

            # Update user profile (name and password)
            success = db.update_user_profile(
                user_id=existing_user["id"],
                nombre=user_data.nombre,
                new_password_hash=hashed_password
            )

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error al actualizar el usuario"
                )

            # Reactivate user
            if not db.reactivate_user(existing_user["id"]):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error al reactivar el usuario"
                )

            # Fetch updated user
            user = db.get_user_by_id(existing_user["id"])
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error al obtener el usuario actualizado"
                )

            logger.info(f"Inactive user reactivated via registration: {user['email']}")
        else:
            # User is active, cannot register again
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El correo electrónico ya está registrado"
            )
    else:
        # Hash password
        hashed_password = hash_password(user_data.password)

        # Create new user
        user = db.create_user(
            nombre=user_data.nombre,
            email=user_data.email,
            hashed_password=hashed_password,
            role="user"
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear el usuario"
            )

    # Update last_login
    db.update_last_login(user["id"])

    # Generate JWT token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user["id"]),
            "email": user["email"],
            "role": user["role"]
        },
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=access_token_expires
    )

    # Set HTTP-only cookie (auto-login)
    _set_auth_cookie(
        response=response,
        request=request,
        token=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # seconds
    )

    logger.info(f"User registered and auto-logged in: {user['email']}")

    return UserResponse(**user)


@router.post("/login", response_model=MessageResponse)
async def login(
    credentials: UserLogin,
    response: Response,
    request: Request,
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Login user and set JWT cookie.

    Steps:
    1. Fetch user by email
    2. Verify password
    3. Check is_active=True
    4. Update last_login
    5. Generate JWT token
    6. Set HTTP-only cookie
    """
    # Fetch user
    user = db.get_user_by_email(credentials.email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos"
        )

    # Verify password
    if not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos"
        )

    # Check if user is active
    if not user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La cuenta está desactivada"
        )

    # Update last_login
    db.update_last_login(user["id"])

    # Generate JWT token with extended expiration if remember_me=True
    if credentials.remember_me:
        access_token_expires = timedelta(days=settings.REMEMBER_ME_EXPIRE_DAYS)
        max_age = settings.REMEMBER_ME_EXPIRE_DAYS * 24 * 60 * 60  # Convert to seconds
        logger.info(f"User logged in with 'Remember Me': {user['email']} (expires in {settings.REMEMBER_ME_EXPIRE_DAYS} days)")
    else:
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
        logger.info(f"User logged in: {user['email']} (expires in {settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutes)")

    access_token = create_access_token(
        data={
            "sub": str(user["id"]),
            "email": user["email"],
            "role": user["role"]
        },
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=access_token_expires
    )

    # Set HTTP-only cookie with dynamic expiration
    _set_auth_cookie(
        response=response,
        request=request,
        token=access_token,
        max_age=max_age
    )

    return MessageResponse(message="Inicio de sesión exitoso")


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response, request: Request):
    """
    Logout user by clearing the JWT cookie.

    Note: JWT is stateless, so this just removes the cookie client-side.
    """
    _delete_auth_cookie(response=response, request=request)

    logger.info("User logged out")

    return MessageResponse(message="Cierre de sesión exitoso")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user)
):
    """
    Get current authenticated user info.

    Returns user data from token validation.
    """
    return UserResponse(**current_user)
