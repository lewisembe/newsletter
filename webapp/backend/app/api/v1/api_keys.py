"""
API Keys management endpoints.
Provides CRUD operations for managing encrypted OpenAI API keys.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
import os
import logging

from app.schemas.api_keys import (
    APIKeyCreate,
    APIKeyUpdate,
    APIKeyResponse,
    APIKeyList,
    APIKeyTestRequest,
    APIKeyTestResponse
)
from app.auth.dependencies import get_current_admin
from common.postgres_db import PostgreSQLURLDatabase
from common.encryption import get_encryption_manager

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


@router.get("", response_model=APIKeyList)
async def list_api_keys(
    include_inactive: bool = False,
    current_user: dict = Depends(get_current_admin)
):
    """
    List all API keys for the current user (admin only).

    **Note:** API keys are never returned in plaintext, only previews (sk-xxx...).
    """
    db = get_db()

    # Get all API keys for the current user
    api_keys_data = db.get_all_api_keys(user_id=current_user['id'], include_inactive=include_inactive)

    # Add key preview for each key
    api_keys_response = []
    for key_data in api_keys_data:
        # Fetch full key to get preview
        full_key = db.get_api_key_by_id(key_data['id'])
        if full_key and full_key.get('encrypted_key'):
            try:
                encryption_manager = get_encryption_manager()
                decrypted_key = encryption_manager.decrypt(full_key['encrypted_key'])
                key_preview = decrypted_key[:7] + "..." if len(decrypted_key) > 7 else decrypted_key
            except Exception as e:
                logger.error(f"Error decrypting key for preview: {e}")
                key_preview = "sk-xxx..."
        else:
            key_preview = "sk-xxx..."

        api_keys_response.append({
            **key_data,
            "key_preview": key_preview
        })

    return {
        "total": len(api_keys_response),
        "api_keys": api_keys_response
    }


@router.post("", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    api_key_data: APIKeyCreate,
    current_user: dict = Depends(get_current_admin)
):
    """
    Create a new API key (admin only).

    The API key will be encrypted before storage.
    """
    db = get_db()
    encryption_manager = get_encryption_manager()

    # Check if alias already exists
    existing_key = db.get_api_key_by_alias(api_key_data.alias)
    if existing_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API key with alias '{api_key_data.alias}' already exists"
        )

    # Encrypt the API key
    try:
        encrypted_key = encryption_manager.encrypt(api_key_data.api_key)
    except Exception as e:
        logger.error(f"Error encrypting API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to encrypt API key"
        )

    # Create API key (always associate with current user)
    api_key_id = db.create_api_key(
        alias=api_key_data.alias,
        encrypted_key=encrypted_key,
        user_id=current_user['id'],  # Always use current user's ID
        notes=api_key_data.notes,
        use_as_fallback=api_key_data.use_as_fallback
    )

    if not api_key_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key"
        )

    # Fetch created key
    created_key = db.get_api_key_by_id(api_key_id)
    if not created_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve created API key"
        )

    # Generate preview
    key_preview = api_key_data.api_key[:7] + "..." if len(api_key_data.api_key) > 7 else api_key_data.api_key

    return {
        "id": created_key['id'],
        "alias": created_key['alias'],
        "user_id": created_key['user_id'],
        "is_active": created_key['is_active'],
        "created_at": created_key['created_at'],
        "updated_at": created_key['updated_at'],
        "last_used_at": created_key['last_used_at'],
        "usage_count": created_key['usage_count'],
        "notes": created_key['notes'],
        "key_preview": key_preview,
        "use_as_fallback": created_key['use_as_fallback']
    }


@router.get("/{api_key_id}", response_model=APIKeyResponse)
async def get_api_key(
    api_key_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Get API key by ID (admin only).

    Returns metadata only, not the actual key.
    """
    db = get_db()

    api_key = db.get_api_key_by_id(api_key_id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    # Generate preview
    try:
        encryption_manager = get_encryption_manager()
        decrypted_key = encryption_manager.decrypt(api_key['encrypted_key'])
        key_preview = decrypted_key[:7] + "..." if len(decrypted_key) > 7 else decrypted_key
    except Exception as e:
        logger.error(f"Error decrypting key for preview: {e}")
        key_preview = "sk-xxx..."

    return {
        "id": api_key['id'],
        "alias": api_key['alias'],
        "user_id": api_key['user_id'],
        "is_active": api_key['is_active'],
        "created_at": api_key['created_at'],
        "updated_at": api_key['updated_at'],
        "last_used_at": api_key['last_used_at'],
        "usage_count": api_key['usage_count'],
        "notes": api_key['notes'],
        "key_preview": key_preview,
        "use_as_fallback": api_key['use_as_fallback']
    }


@router.put("/{api_key_id}", response_model=APIKeyResponse)
async def update_api_key(
    api_key_id: int,
    api_key_update: APIKeyUpdate,
    current_user: dict = Depends(get_current_admin)
):
    """
    Update API key (admin only).

    Can update alias, key, active status, and notes.
    """
    db = get_db()
    encryption_manager = get_encryption_manager()

    # Check if key exists
    existing_key = db.get_api_key_by_id(api_key_id)
    if not existing_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    # Encrypt new key if provided
    encrypted_key = None
    if api_key_update.api_key:
        try:
            encrypted_key = encryption_manager.encrypt(api_key_update.api_key)
        except Exception as e:
            logger.error(f"Error encrypting API key: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to encrypt API key"
            )

    # Update API key
    success = db.update_api_key(
        api_key_id=api_key_id,
        alias=api_key_update.alias,
        encrypted_key=encrypted_key,
        is_active=api_key_update.is_active,
        notes=api_key_update.notes,
        use_as_fallback=api_key_update.use_as_fallback
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update API key"
        )

    # Fetch updated key
    updated_key = db.get_api_key_by_id(api_key_id)
    if not updated_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated API key"
        )

    # Generate preview
    try:
        decrypted_key = encryption_manager.decrypt(updated_key['encrypted_key'])
        key_preview = decrypted_key[:7] + "..." if len(decrypted_key) > 7 else decrypted_key
    except Exception as e:
        logger.error(f"Error decrypting key for preview: {e}")
        key_preview = "sk-xxx..."

    return {
        "id": updated_key['id'],
        "alias": updated_key['alias'],
        "user_id": updated_key['user_id'],
        "is_active": updated_key['is_active'],
        "created_at": updated_key['created_at'],
        "updated_at": updated_key['updated_at'],
        "last_used_at": updated_key['last_used_at'],
        "usage_count": updated_key['usage_count'],
        "notes": updated_key['notes'],
        "key_preview": key_preview,
        "use_as_fallback": updated_key['use_as_fallback']
    }


@router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    api_key_id: int,
    current_user: dict = Depends(get_current_admin)
):
    """
    Delete API key (admin only).
    """
    db = get_db()

    success = db.delete_api_key(api_key_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    return None


@router.post("/test", response_model=APIKeyTestResponse)
async def test_api_key(
    test_request: APIKeyTestRequest,
    current_user: dict = Depends(get_current_admin)
):
    """
    Test an API key by making a simple OpenAI API call (admin only).

    Verifies the key works and returns available model.
    """
    db = get_db()
    encryption_manager = get_encryption_manager()

    # Get API key by alias
    api_key = db.get_api_key_by_alias(test_request.alias)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key with alias '{test_request.alias}' not found"
        )

    # Decrypt key
    try:
        decrypted_key = encryption_manager.decrypt(api_key['encrypted_key'])
    except Exception as e:
        logger.error(f"Error decrypting API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt API key"
        )

    # Test key with OpenAI API
    try:
        from openai import OpenAI
        import openai
        client = OpenAI(api_key=decrypted_key)

        # Test 1: List models (basic authentication check)
        try:
            models = client.models.list()
            model_list = [model.id for model in models.data]

            if not model_list:
                return {
                    "success": False,
                    "message": "API key is valid but no models available",
                    "model_available": None,
                    "has_credits": False,
                    "error_code": "no_models"
                }

            # Test 2: Make a minimal API call to check for credits
            # This will fail if the key has no credits
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",  # Cheapest model
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )

                # If we get here, the key has credits
                # Update usage stats
                db.update_api_key_usage(api_key['id'])

                return {
                    "success": True,
                    "message": f"API key is valid and has available credits. Found {len(model_list)} models.",
                    "model_available": model_list[0] if model_list else None,
                    "has_credits": True,
                    "error_code": None
                }

            except openai.RateLimitError as e:
                # Insufficient quota error
                error_msg = str(e)
                if "insufficient_quota" in error_msg.lower() or "quota" in error_msg.lower():
                    return {
                        "success": False,
                        "message": "API key is valid but has no available credits (insufficient quota)",
                        "model_available": model_list[0] if model_list else None,
                        "has_credits": False,
                        "error_code": "insufficient_quota"
                    }
                else:
                    # Other rate limit error
                    return {
                        "success": False,
                        "message": f"API key has rate limit issues: {error_msg}",
                        "model_available": model_list[0] if model_list else None,
                        "has_credits": None,
                        "error_code": "rate_limit"
                    }

        except openai.AuthenticationError as e:
            return {
                "success": False,
                "message": f"Authentication failed: {str(e)}",
                "model_available": None,
                "has_credits": False,
                "error_code": "authentication_error"
            }

    except Exception as e:
        logger.error(f"Error testing API key: {e}")
        error_str = str(e)

        # Parse specific error types
        error_code = "unknown"
        if "authentication" in error_str.lower():
            error_code = "authentication_error"
        elif "quota" in error_str.lower():
            error_code = "insufficient_quota"
        elif "rate" in error_str.lower():
            error_code = "rate_limit"

        return {
            "success": False,
            "message": f"API key test failed: {error_str}",
            "model_available": None,
            "has_credits": False,
            "error_code": error_code
        }
