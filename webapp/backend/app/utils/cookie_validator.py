"""
Cookie validation utilities.

Tests cookies by attempting to fetch content from the target domain.
"""
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def validate_cookies_quick(
    domain: str,
    cookies: list,
    test_url: Optional[str] = None,
    timeout: int = 15,
    use_database: bool = False,
    db_connection_string: Optional[str] = None
) -> Dict[str, Any]:
    """
    Quickly validate cookies by attempting a fetch.

    Args:
        domain: Domain to test (e.g., 'elpais.com')
        cookies: List of cookie dictionaries
        test_url: URL to test (defaults to https://{domain})
        timeout: Request timeout in seconds
        use_database: Use database for cookies instead of temp files
        db_connection_string: PostgreSQL connection string

    Returns:
        Dict with:
            - success: bool
            - status: 'active' | 'invalid' | 'error'
            - message: str
            - test_url: str
            - response_size: int (if success)
            - error: str (if failed)
    """
    # Import here to avoid circular dependencies
    from common.stage04_extraction.authenticated_scraper import AuthenticatedScraper
    import os

    # Default test URL
    if not test_url:
        test_url = f"https://{domain}"

    # Get DB connection string from environment if not provided
    if not db_connection_string:
        db_connection_string = os.getenv('DATABASE_URL')

    try:
        logger.info(f"Testing cookies for domain: {domain}")
        logger.debug(f"Test URL: {test_url}")
        logger.debug(f"Cookie count: {len(cookies)}")

        if use_database and db_connection_string:
            # Save cookies to database temporarily for validation
            from common.postgres_db import PostgreSQLURLDatabase
            db = PostgreSQLURLDatabase(db_connection_string)

            # Save to DB
            db.save_cookies(
                domain=domain,
                cookies=cookies,
                validation_info={'status': 'not_tested'}
            )

            # Initialize scraper with database support
            logger.info(f"Initializing scraper with database support")
            scraper = AuthenticatedScraper(
                headless=True,
                timeout=timeout,
                db_connection_string=db_connection_string,
                use_database=True
            )
        else:
            # Fallback to temp file method
            # Extract domain prefix for filename (e.g., "ft.com" -> "ft")
            domain_prefix = domain.split('.')[0]
            temp_dir = Path(tempfile.gettempdir())
            temp_cookie_file = temp_dir / f"cookies_{domain_prefix}.json"

            # Write cookies to temp file
            with open(temp_cookie_file, 'w') as f:
                json.dump(cookies, f, indent=2)

            # Initialize scraper with temp directory
            logger.info(f"Initializing scraper with cookies_dir={temp_dir}")
            scraper = AuthenticatedScraper(
                cookies_dir=str(temp_dir),
                headless=True,
                timeout=timeout,
                use_database=False
            )

        # Attempt to fetch with cookies
        logger.info(f"Attempting to fetch: {test_url}")
        html = scraper.fetch_with_cookies(test_url)
        logger.info(f"Fetch completed. HTML is None: {html is None}, HTML length: {len(html) if html else 0}")

        # Cleanup
        scraper.close()

        # Log detailed response info for debugging
        html_size = len(html) if html else 0
        logger.info(f"Cookie validation for {domain}: response size = {html_size} bytes")
        if html:
            html_preview = html[:500] if len(html) > 500 else html
            logger.debug(f"HTML preview (first 500 chars): {html_preview}")

        if html and len(html) > 1000:  # Minimum reasonable page size
            logger.info(f"✓ Cookie validation SUCCESS for {domain}")
            logger.info(f"  Response size: {len(html)} bytes")

            return {
                "success": True,
                "status": "active",
                "message": f"Cookies válidas. Página descargada: {len(html)} bytes",
                "test_url": test_url,
                "response_size": len(html),
                "error": None,
                "tested_at": datetime.utcnow()
            }
        else:
            logger.warning(f"✗ Cookie validation FAILED for {domain}: Response too small (got {html_size} bytes, need >1000)")
            if html:
                logger.warning(f"HTML preview: {html[:200]}")
            return {
                "success": False,
                "status": "invalid",
                "message": f"Cookies inválidas: respuesta muy pequeña ({html_size} bytes, se requieren >1000 bytes)",
                "test_url": test_url,
                "response_size": html_size,
                "error": "Response too small (possible auth failure or redirect)",
                "tested_at": datetime.utcnow()
            }

    except Exception as e:
        logger.error(f"✗ Cookie validation ERROR for {domain}: {e}")
        return {
            "success": False,
            "status": "invalid",
            "message": f"Error al validar cookies: {str(e)}",
            "test_url": test_url,
            "response_size": None,
            "error": str(e),
            "tested_at": datetime.utcnow()
        }

    finally:
        # Cleanup temp file (only if not using database)
        if not use_database:
            try:
                domain_prefix = domain.split('.')[0]
                temp_dir = Path(tempfile.gettempdir())
                temp_cookie_file = temp_dir / f"cookies_{domain_prefix}.json"
                if temp_cookie_file.exists():
                    temp_cookie_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to cleanup temp cookie file: {e}")


def check_cookie_expiry(cookies: list) -> Dict[str, Any]:
    """
    Check if cookies are expired or expiring soon.

    Args:
        cookies: List of cookie dictionaries

    Returns:
        Dict with:
            - has_expired: bool
            - expired_count: int
            - expiring_soon: bool (within 7 days)
            - expiring_soon_count: int
            - total_count: int
            - earliest_expiry: datetime (if any)
            - days_until_expiry: int (if any, can be negative if expired)
    """
    from datetime import timedelta

    now = datetime.utcnow().timestamp()
    seven_days_ahead = (datetime.utcnow() + timedelta(days=7)).timestamp()

    expired_count = 0
    expiring_soon_count = 0
    earliest_expiry = None

    for cookie in cookies:
        # Check expirationDate or expiry field
        expiry = cookie.get('expirationDate') or cookie.get('expiry')

        if expiry:
            expiry_timestamp = float(expiry)

            # Check if expired
            if expiry_timestamp < now:
                expired_count += 1
            # Check if expiring within 7 days
            elif expiry_timestamp < seven_days_ahead:
                expiring_soon_count += 1

            # Track earliest expiry
            if earliest_expiry is None or expiry_timestamp < earliest_expiry:
                earliest_expiry = expiry_timestamp

    days_until_expiry = None
    if earliest_expiry:
        delta = datetime.fromtimestamp(earliest_expiry) - datetime.utcnow()
        days_until_expiry = delta.days

    return {
        "has_expired": expired_count > 0,
        "expired_count": expired_count,
        "expiring_soon": expiring_soon_count > 0,
        "expiring_soon_count": expiring_soon_count,
        "total_count": len(cookies),
        "earliest_expiry": datetime.fromtimestamp(earliest_expiry) if earliest_expiry else None,
        "days_until_expiry": days_until_expiry
    }
