"""
FastAPI main application entry point.

Provides REST API for Newsletter Utils webapp frontend.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.v1.router import api_router
from app.auth.utils import hash_password
from app.utils.jwt_secret_manager import ensure_current_secret_logged
from common.postgres_db import PostgreSQLURLDatabase
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Newsletter Utils API",
    version="1.0.0",
    description="API for AI-powered newsletter curation pipeline",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for Next.js frontend
# Must use explicit origins so browsers allow credentials (cookies)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def create_admin_user():
    """
    Create admin user on startup (idempotent).
    Uses credentials from .env (ADMIN_EMAIL, ADMIN_PASSWORD).
    """
    try:
        db = PostgreSQLURLDatabase(settings.DATABASE_URL)

        # Record current JWT secret for future rotations
        ensure_current_secret_logged(db)

        # Check if admin exists
        existing_admin = db.get_user_by_email(settings.ADMIN_EMAIL)

        if existing_admin:
            logger.info(f"Admin user already exists: {settings.ADMIN_EMAIL}")
            return

        # Create admin
        hashed_password = hash_password(settings.ADMIN_PASSWORD)
        admin_user = db.create_user(
            nombre="Administrator",
            email=settings.ADMIN_EMAIL,
            hashed_password=hashed_password,
            role="admin"
        )

        if admin_user:
            logger.info(f"Admin user created: {settings.ADMIN_EMAIL}")
        else:
            logger.error("Failed to create admin user")

    except Exception as e:
        logger.error(f"Error creating admin user: {e}")
        # Don't crash the app if admin creation fails


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Newsletter Utils API",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health():
    """Health check for monitoring"""
    return {"status": "healthy"}
