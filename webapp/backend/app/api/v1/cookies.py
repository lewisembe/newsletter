"""
API endpoints for Cookie management.

Manages authentication cookies for web scraping with automatic validation.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
import os
import json
import logging
from pathlib import Path
from datetime import datetime

from app.schemas.cookies import (
    CookieUpload, CookieTestRequest, CookieTestResult,
    CookieInfo, CookieListResponse, CookieStatus
)
from app.auth.dependencies import get_current_admin
from app.utils.cookie_validator import validate_cookies_quick, check_cookie_expiry
from common.postgres_db import PostgreSQLURLDatabase

logger = logging.getLogger(__name__)
router = APIRouter()

# Cookie storage directory
COOKIES_DIR = Path("config")
COOKIES_DIR.mkdir(exist_ok=True, parents=True)


def get_db() -> PostgreSQLURLDatabase:
    """Get database instance."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DATABASE_URL not configured"
        )
    return PostgreSQLURLDatabase(database_url)


def get_cookie_file_path(domain: str) -> Path:
    """Get cookie file path for domain."""
    # Extract domain abbreviation for filename
    # e.g., "elpais.com" -> "elpais"
    domain_abbrev = domain.split('.')[0]
    return COOKIES_DIR / f"cookies_{domain_abbrev}.json"


def get_domain_from_cookie_file(file_path: Path) -> str:
    """Extract domain from cookie filename."""
    # cookies_elpais.json -> elpais
    domain_abbrev = file_path.stem.replace("cookies_", "")

    # Common domain mappings
    domain_mapping = {
        "ft": "ft.com",
        "nyt": "nytimes.com",
        "wsj": "wsj.com",
        "bloomberg": "bloomberg.com",
        "economist": "economist.com"
    }

    return domain_mapping.get(domain_abbrev, f"{domain_abbrev}.com")


@router.get("", response_model=CookieListResponse)
async def list_cookies(
    current_user: dict = Depends(get_current_admin)
):
    """
    List all available cookies (admin only).

    Returns cookie status, validation info, and associated source.
    Reads from PostgreSQL database.
    """
    try:
        db = get_db()
        cookie_records = db.list_all_cookies()
        cookies_info = []

        for record in cookie_records:
            domain = record['domain']

            # Parse cookies JSON
            cookies_data = record['cookies']
            if isinstance(cookies_data, str):
                cookies_data = json.loads(cookies_data)
            cookie_count = len(cookies_data) if cookies_data else 0

            # Map validation status
            validation_status_map = {
                'active': CookieStatus.ACTIVE,
                'invalid': CookieStatus.INVALID,
                'expired': CookieStatus.EXPIRED,
                'not_tested': CookieStatus.NOT_TESTED
            }
            cookie_status = validation_status_map.get(
                record.get('validation_status', 'not_tested'),
                CookieStatus.NOT_TESTED
            )

            # Try to find associated source
            source = None
            if record.get('source_id'):
                source = db.get_source_by_id(record['source_id'])

            cookies_info.append(CookieInfo(
                domain=domain,
                status=cookie_status,
                cookie_count=cookie_count,
                file_path=None,  # Not used anymore (DB storage)
                file_size=None,  # Not applicable
                created_at=record.get('created_at'),
                last_tested_at=record.get('last_validated_at'),
                last_test_result=record.get('validation_message'),
                source_id=source['id'] if source else None,
                source_name=source['display_name'] if source else None,
                has_expired_cookies=record.get('has_expired_cookies', False),
                expiring_soon=record.get('expiring_soon', False),
                days_until_expiry=record.get('days_until_expiry')
            ))

        return CookieListResponse(
            cookies=cookies_info,
            total=len(cookies_info)
        )

    except Exception as e:
        logger.error(f"Error listing cookies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=CookieTestResult, status_code=status.HTTP_201_CREATED)
async def upload_cookies(
    cookie_upload: CookieUpload,
    current_user: dict = Depends(get_current_admin)
):
    """
    Upload cookies for a domain (admin only).

    **Automatic Validation:**
    - If auto_validate=true (default), cookies are tested before saving
    - Only valid cookies are saved to database
    - Returns validation result

    **Cookie Format:**
    - Export cookies from browser extension (e.g., EditThisCookie)
    - Must be JSON array of cookie objects
    - Each cookie must have at least: name, value
    """
    try:
        domain = cookie_upload.domain
        cookies = cookie_upload.cookies
        db = get_db()

        logger.info(f"Uploading cookies for domain: {domain}")
        logger.info(f"Cookie count: {len(cookies)}")
        logger.info(f"Auto-validate: {cookie_upload.auto_validate}")

        # Find associated source by base URL
        source = db.get_source_by_base_url(f"https://{domain}")
        if not source:
            source = db.get_source_by_base_url(f"https://www.{domain}")
        source_id = source['id'] if source else None

        if source:
            logger.info(f"Cookies associated with source: {source['display_name']} (ID: {source_id})")
        else:
            logger.warning(f"No source found for domain {domain}. Cookies will be saved without source association.")

        # Validate cookies if requested
        if cookie_upload.auto_validate:
            logger.info("Validating cookies before saving...")
            test_result = validate_cookies_quick(
                domain=domain,
                cookies=cookies,
                test_url=cookie_upload.test_url,
                use_database=True
            )

            if not test_result['success']:
                logger.warning(f"Cookie validation failed: {test_result['message']}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cookie validation failed: {test_result['message']}"
                )

            logger.info(f"✓ Cookie validation SUCCESS")

            # Update validation info in DB
            db.update_cookie_validation(domain, test_result)
        else:
            # Create dummy test result
            test_result = {
                "success": True,
                "status": "not_tested",
                "message": "Cookies saved without validation",
                "test_url": cookie_upload.test_url or f"https://{domain}",
                "response_size": None,
                "error": None,
                "tested_at": datetime.utcnow()
            }

            # Save cookies to database
            db.save_cookies(
                domain=domain,
                cookies=cookies,
                source_id=source_id,
                validation_info=test_result,
                user_email=current_user.get('email')
            )

        logger.info(f"✓ Cookies saved to database for {domain}")

        return CookieTestResult(**test_result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading cookies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test", response_model=CookieTestResult)
async def test_cookies(
    test_request: CookieTestRequest,
    current_user: dict = Depends(get_current_admin)
):
    """
    Test existing cookies for a domain (admin only).

    Tests cookies by attempting to fetch content from the domain.
    Updates validation info in database.
    """
    try:
        domain = test_request.domain
        db = get_db()

        # Load cookies from database
        cookie_record = db.get_cookies_by_domain(domain)

        if not cookie_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No cookies found for domain: {domain}"
            )

        # Parse cookies
        cookies_data = cookie_record['cookies']
        if isinstance(cookies_data, str):
            cookies = json.loads(cookies_data)
        else:
            cookies = cookies_data

        logger.info(f"Testing cookies for domain: {domain}")

        # Run validation
        test_result = validate_cookies_quick(
            domain=domain,
            cookies=cookies,
            test_url=test_request.test_url,
            use_database=False  # Don't save during test, just validate
        )

        # Update validation info in DB
        db.update_cookie_validation(domain, test_result)

        # If test was successful, mark cookies as working (ignore theoretical expiry)
        if test_result['success']:
            expiry_info = check_cookie_expiry(cookies)

            # Update expiry fields
            # Note: If cookies work, we mark has_expired_cookies as False
            # because what matters is that they WORK, not their theoretical expiry date
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE source_cookies
                    SET
                        has_expired_cookies = FALSE,
                        expiring_soon = %s,
                        days_until_expiry = %s,
                        earliest_expiry = %s,
                        updated_at = NOW()
                    WHERE domain = %s
                """, (
                    expiry_info['expiring_soon'],
                    expiry_info['days_until_expiry'],
                    expiry_info['earliest_expiry'],
                    domain
                ))
                conn.commit()
                logger.info(f"✓ Cookies marked as working for {domain} (theoretical expiry ignored)")

        return CookieTestResult(**test_result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing cookies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{domain}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cookies(
    domain: str,
    current_user: dict = Depends(get_current_admin)
):
    """
    Delete cookies for a domain (admin only).
    Removes from database.
    """
    try:
        db = get_db()

        deleted = db.delete_cookies_by_domain(domain)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No cookies found for domain: {domain}"
            )

        logger.info(f"✓ Deleted cookies for domain: {domain}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting cookies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}", response_model=CookieInfo)
async def get_cookies_info(
    domain: str,
    current_user: dict = Depends(get_current_admin)
):
    """
    Get information about cookies for a specific domain (admin only).
    Reads from database.
    """
    try:
        db = get_db()
        record = db.get_cookies_by_domain(domain)

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No cookies found for domain: {domain}"
            )

        # Parse cookies
        cookies_data = record['cookies']
        if isinstance(cookies_data, str):
            cookies_data = json.loads(cookies_data)
        cookie_count = len(cookies_data) if cookies_data else 0

        # Map validation status
        validation_status_map = {
            'active': CookieStatus.ACTIVE,
            'invalid': CookieStatus.INVALID,
            'expired': CookieStatus.EXPIRED,
            'not_tested': CookieStatus.NOT_TESTED
        }
        cookie_status = validation_status_map.get(
            record.get('validation_status', 'not_tested'),
            CookieStatus.NOT_TESTED
        )

        # Try to find associated source
        source = None
        if record.get('source_id'):
            source = db.get_source_by_id(record['source_id'])

        return CookieInfo(
            domain=domain,
            status=cookie_status,
            cookie_count=cookie_count,
            file_path=None,  # Not used anymore
            file_size=None,  # Not applicable
            created_at=record.get('created_at'),
            last_tested_at=record.get('last_validated_at'),
            last_test_result=record.get('validation_message'),
            source_id=source['id'] if source else None,
            source_name=source['display_name'] if source else None,
            has_expired_cookies=record.get('has_expired_cookies', False),
            expiring_soon=record.get('expiring_soon', False),
            days_until_expiry=record.get('days_until_expiry')
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cookie info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
