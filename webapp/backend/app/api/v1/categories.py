"""
Categories management endpoints for admin operations.
Includes CRUD operations and reclassification workflow.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from app.schemas.categories import (
    CategoryCreate, CategoryUpdate, CategoryResponse, CategoryListItem,
    ReclassificationRequest, ReclassificationJobResponse, CategoryStatsResponse
)
from app.auth.dependencies import get_db, get_current_admin
from common.postgres_db import PostgreSQLURLDatabase
import logging
import subprocess
import os
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# CATEGORIES CRUD ENDPOINTS
# ============================================

@router.get("", response_model=List[CategoryListItem])
async def list_categories(
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Get all categories (public endpoint for reading).

    Returns:
        List of categories with URL counts
    """
    try:
        categories = db.get_all_categories()
        url_counts = db.count_urls_by_category()

        # Enrich categories with URL counts
        result = []
        for cat in categories:
            result.append(CategoryListItem(
                id=cat['id'],
                name=cat['name'],
                description=cat['description'],
                url_count=url_counts.get(cat['id'], 0),
                created_at=cat['created_at'],
                updated_at=cat['updated_at']
            ))

        return result

    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener categorías"
        )


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: str,
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Get a specific category by ID.

    Args:
        category_id: Category identifier

    Returns:
        Category details with URL count
    """
    category = db.get_category_by_id(category_id)

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Categoría '{category_id}' no encontrada"
        )

    url_counts = db.count_urls_by_category()

    return CategoryResponse(
        id=category['id'],
        name=category['name'],
        description=category['description'],
        consolidates=category['consolidates'],
        examples=category['examples'],
        created_at=category['created_at'],
        updated_at=category['updated_at'],
        url_count=url_counts.get(category['id'], 0)
    )


@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category: CategoryCreate,
    admin: dict = Depends(get_current_admin),
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Create a new category (admin only).

    Args:
        category: Category data

    Returns:
        Created category
    """
    # Check if category ID already exists
    existing = db.get_category_by_id(category.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La categoría '{category.id}' ya existe"
        )

    # Create category
    success = db.create_category(
        category_id=category.id,
        name=category.name,
        description=category.description,
        consolidates=category.consolidates,
        examples=category.examples
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al crear categoría"
        )

    # Log the change
    db.log_category_change(
        category_id=category.id,
        changed_by=admin['id'],
        change_type='created',
        new_values=category.model_dump()
    )

    # Return created category
    created_category = db.get_category_by_id(category.id)
    url_counts = db.count_urls_by_category()

    return CategoryResponse(
        id=created_category['id'],
        name=created_category['name'],
        description=created_category['description'],
        consolidates=created_category['consolidates'],
        examples=created_category['examples'],
        created_at=created_category['created_at'],
        updated_at=created_category['updated_at'],
        url_count=url_counts.get(created_category['id'], 0)
    )


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: str,
    updates: CategoryUpdate,
    admin: dict = Depends(get_current_admin),
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Update an existing category (admin only).

    Args:
        category_id: Category identifier
        updates: Fields to update

    Returns:
        Updated category
    """
    # Check if category exists
    old_category = db.get_category_by_id(category_id)
    if not old_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Categoría '{category_id}' no encontrada"
        )

    # Update category
    success = db.update_category(
        category_id=category_id,
        name=updates.name,
        description=updates.description,
        consolidates=updates.consolidates,
        examples=updates.examples
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar categoría"
        )

    # Log the change
    db.log_category_change(
        category_id=category_id,
        changed_by=admin['id'],
        change_type='updated',
        old_values={
            'name': old_category['name'],
            'description': old_category['description'],
            'consolidates': old_category['consolidates'],
            'examples': old_category['examples']
        },
        new_values=updates.model_dump(exclude_unset=True)
    )

    # Return updated category
    updated_category = db.get_category_by_id(category_id)
    url_counts = db.count_urls_by_category()

    return CategoryResponse(
        id=updated_category['id'],
        name=updated_category['name'],
        description=updated_category['description'],
        consolidates=updated_category['consolidates'],
        examples=updated_category['examples'],
        created_at=updated_category['created_at'],
        updated_at=updated_category['updated_at'],
        url_count=url_counts.get(updated_category['id'], 0)
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: str,
    admin: dict = Depends(get_current_admin),
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Delete a category (admin only).

    Args:
        category_id: Category identifier

    Notes:
        - Sets categoria_tematica to NULL for affected URLs (via FK constraint)
        - Cannot delete 'otros' category (fallback category)
    """
    # Prevent deletion of 'otros' category (fallback)
    if category_id == 'otros':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar la categoría 'otros' (categoría de respaldo)"
        )

    # Check if category exists
    old_category = db.get_category_by_id(category_id)
    if not old_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Categoría '{category_id}' no encontrada"
        )

    # Log the change BEFORE deletion
    db.log_category_change(
        category_id=category_id,
        changed_by=admin['id'],
        change_type='deleted',
        old_values={
            'name': old_category['name'],
            'description': old_category['description'],
            'consolidates': old_category['consolidates'],
            'examples': old_category['examples']
        }
    )

    # Delete category (FK constraint handles URL updates)
    success = db.delete_category(category_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al eliminar categoría"
        )

    return None


# ============================================
# RECLASSIFICATION ENDPOINTS
# ============================================

def run_reclassification_background(job_id: int, db_path: str):
    """
    Background task to run reclassification using stage 02.

    Args:
        job_id: Reclassification job ID
        db_path: Database path (not used, but kept for compatibility)
    """
    from common.postgres_db import PostgreSQLURLDatabase
    import sys

    db = PostgreSQLURLDatabase(db_path)

    try:
        # Update job status to running
        db.update_reclassification_job(job_id, status='running')
        logger.info(f"Starting reclassification job {job_id}")

        # Get project root (where venv is located)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..'))
        venv_python = os.path.join(project_root, 'venv', 'bin', 'python')
        stage02_script = os.path.join(project_root, 'stages', '02_filter_for_newsletters.py')

        # Run stage 02 with --force flag to reclassify all URLs
        # Use a date range that covers all existing URLs
        cmd = [
            venv_python,
            stage02_script,
            '--date', datetime.now().strftime('%Y-%m-%d'),
            '--force',  # Force reclassification of all URLs
            '--no-temporality'  # Skip temporality classification (faster)
        ]

        logger.info(f"Running command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutes timeout
        )

        if result.returncode == 0:
            # Count processed URLs
            url_counts = db.count_urls_by_category()
            total_processed = sum(url_counts.values())

            db.update_reclassification_job(
                job_id,
                status='completed',
                processed_urls=total_processed,
                failed_urls=0
            )
            logger.info(f"Reclassification job {job_id} completed: {total_processed} URLs")
        else:
            error_msg = result.stderr[:500] if result.stderr else "Unknown error"
            db.update_reclassification_job(
                job_id,
                status='failed',
                error_message=error_msg
            )
            logger.error(f"Reclassification job {job_id} failed: {error_msg}")

    except subprocess.TimeoutExpired:
        db.update_reclassification_job(
            job_id,
            status='failed',
            error_message="Reclassification timed out after 30 minutes"
        )
        logger.error(f"Reclassification job {job_id} timed out")

    except Exception as e:
        db.update_reclassification_job(
            job_id,
            status='failed',
            error_message=str(e)[:500]
        )
        logger.error(f"Reclassification job {job_id} failed: {e}")


@router.post("/reclassify", response_model=ReclassificationJobResponse)
async def trigger_reclassification(
    request: ReclassificationRequest,
    background_tasks: BackgroundTasks,
    admin: dict = Depends(get_current_admin),
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Trigger reclassification of all URLs (admin only).

    This endpoint runs stage 02 in the background to reclassify all URLs
    using the updated category definitions.

    Args:
        request: Reclassification request (category IDs that were modified)
        background_tasks: FastAPI background tasks

    Returns:
        Reclassification job details
    """
    # Create reclassification job
    job_id = db.create_reclassification_job(
        triggered_by=admin['id'],
        category_ids=request.category_ids
    )

    if not job_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al crear trabajo de reclasificación"
        )

    # Add background task
    db_path = os.getenv('DATABASE_URL', '')
    background_tasks.add_task(run_reclassification_background, job_id, db_path)

    logger.info(f"Reclassification job {job_id} queued by admin {admin['id']}")

    # Return job details
    job = db.get_reclassification_job(job_id)
    return ReclassificationJobResponse(**job)


@router.get("/reclassify/jobs", response_model=List[ReclassificationJobResponse])
async def get_reclassification_jobs(
    limit: int = 10,
    admin: dict = Depends(get_current_admin),
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Get recent reclassification jobs (admin only).

    Args:
        limit: Maximum number of jobs to return (default: 10)

    Returns:
        List of recent reclassification jobs
    """
    jobs = db.get_recent_reclassification_jobs(limit=limit)
    return [ReclassificationJobResponse(**job) for job in jobs]


@router.get("/reclassify/jobs/{job_id}", response_model=ReclassificationJobResponse)
async def get_reclassification_job(
    job_id: int,
    admin: dict = Depends(get_current_admin),
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Get reclassification job status (admin only).

    Args:
        job_id: Job identifier

    Returns:
        Job details and status
    """
    job = db.get_reclassification_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trabajo de reclasificación {job_id} no encontrado"
        )

    return ReclassificationJobResponse(**job)


# ============================================
# STATISTICS ENDPOINTS
# ============================================

@router.get("/stats", response_model=CategoryStatsResponse)
async def get_category_stats(
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Get category statistics.

    Returns:
        Category statistics including URL counts
    """
    categories = db.get_all_categories()
    url_counts = db.count_urls_by_category()

    return CategoryStatsResponse(
        total_categories=len(categories),
        total_urls_categorized=sum(url_counts.values()),
        urls_by_category=url_counts
    )
