"""
Fetch Cascade - Clean HTML Fetching with Multiple Methods

This module provides a clean cascade of fetch methods to obtain HTML content
without paywalls. Each method is tried sequentially until success.

Separation of concerns:
- Fetching: Different HTTP/Selenium strategies to get HTML
- Validation: Paywall detection (delegated to paywall_validator)

Author: Newsletter Utils Team
Created: 2025-11-16
"""

import logging
import requests
from typing import Dict, Any, Optional, Callable
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
import time

logger = logging.getLogger(__name__)


def fetch_with_cookies(url: str, cookie_manager, timeout: int = 30) -> Optional[str]:
    """
    Fetch HTML using authenticated session (cookies from AuthenticatedScraper).

    Args:
        url: URL to fetch
        cookie_manager: AuthenticatedScraper instance
        timeout: Request timeout in seconds

    Returns:
        HTML content or None if failed
    """
    if not cookie_manager:
        return None

    # Import here to get the helper function
    from urllib.parse import urlparse

    # Extract domain from URL
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')

    # Check if we have cookies for this domain
    if not cookie_manager.has_cookies_for_domain(domain):
        logger.debug(f"No cookies available for domain: {domain}")
        return None

    try:
        logger.info(f"Fetching with cookies (authenticated session) for {domain}")
        # Use AuthenticatedScraper's fetch_with_cookies method
        html = cookie_manager.fetch_with_cookies(url)

        if html:
            logger.info(f"✓ Authenticated fetch successful: {len(html)} bytes")

        return html

    except Exception as e:
        logger.warning(f"Authenticated fetch failed: {e}")
        return None


def fetch_direct_http(url: str, timeout: int = 30) -> Optional[str]:
    """
    Standard HTTP request with browser-like headers.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        HTML content or None if failed
    """
    try:
        logger.info(f"Fetching with direct HTTP")
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        logger.info(f"✓ Direct HTTP successful: {len(response.text)} bytes")
        return response.text

    except requests.RequestException as e:
        logger.warning(f"Direct HTTP failed: {e}")
        return None


def fetch_without_javascript(url: str, timeout: int = 30) -> Optional[str]:
    """
    HTTP request without JavaScript execution (client-side paywall bypass).

    Many paywalls are implemented with JavaScript that hides content.
    This method fetches the raw HTML which often contains the full article.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        HTML content or None if failed
    """
    try:
        logger.info(f"Fetching without JavaScript (requests only)")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()

        logger.info(f"✓ No-JS fetch successful: {len(response.text)} bytes")
        return response.text

    except requests.RequestException as e:
        logger.warning(f"No-JS fetch failed: {e}")
        return None


def fetch_selenium_js_disabled(url: str, timeout: int = 30) -> Optional[str]:
    """
    Selenium with JavaScript disabled (handles complex redirects/cookies).

    Similar to fetch_without_javascript but uses Selenium which can:
    - Handle complex redirects
    - Manage cookies automatically
    - Render initial page structure

    Args:
        url: URL to fetch
        timeout: Page load timeout in seconds

    Returns:
        HTML content or None if failed
    """
    driver = None
    try:
        logger.info(f"Fetching with Selenium (JS disabled)")

        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')

        # Disable JavaScript
        prefs = {
            'profile.managed_default_content_settings.javascript': 2,
            'profile.managed_default_content_settings.images': 2,
            'profile.default_content_setting_values.notifications': 2
        }
        options.add_experimental_option('prefs', prefs)

        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        options.add_argument(f'user-agent={user_agent}')

        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)

        service = Service('/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(timeout)

        driver.get(url)
        time.sleep(2)  # Wait for page structure

        html = driver.page_source
        logger.info(f"✓ Selenium (JS disabled) successful: {len(html)} bytes")
        return html

    except WebDriverException as e:
        logger.warning(f"Selenium (JS disabled) failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Selenium unexpected error: {e}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def fetch_archive_today(url: str) -> Optional[str]:
    """
    Fetch from archive.today (external cached copy).

    Uses archive.today's newest snapshot. This bypasses server-side paywalls
    as archive.today caches the full content when it crawls.

    Args:
        url: Original URL to fetch from archive

    Returns:
        HTML content or None if failed
    """
    from .archive_fetcher import fetch_archive_selenium

    logger.info(f"Fetching from archive.today")
    html = fetch_archive_selenium(url)

    if html:
        logger.info(f"✓ Archive.today successful: {len(html)} bytes")
    else:
        logger.warning(f"Archive.today failed")

    return html


def fetch_html_with_cascade(
    url: str,
    llm_client,
    cookie_manager = None,
    skip_paywall_check: bool = False,
    timeout: int = 30,
    title: str = ""
) -> Dict[str, Any]:
    """
    Try multiple fetch methods in cascade until getting complete HTML content.

    Cascade order (optimized for speed and cost):
    1. Cookies (authenticated) - Free, instant, no paywall
    2. Direct HTTP - Free, fast, works if no paywall
    3. HTTP without JS - Free, fast, bypasses client-side paywalls
    4. Selenium (JS disabled) - Free but slower, handles complex sites
    5. Archive.today - Free but slowest, bypasses server-side paywalls

    For each method:
    - Attempts fetch
    - If successful → Validates content quality (paywall + completeness) with LLM
    - If valid content OR skip_paywall_check → Returns
    - If invalid (paywall/insufficient content) → Next method

    Args:
        url: URL to fetch
        llm_client: LLM client for content validation
        cookie_manager: Optional CookieManager for authenticated fetching
        skip_paywall_check: Skip content validation (use any HTML)
        timeout: Timeout for each fetch method
        title: Expected article title (for validation context)

    Returns:
        Dict with:
            - success: bool
            - html: str or None
            - method: str (which method worked)
            - has_auth: bool (True if cookies were used)
            - archive_url: str or None (if archive.today was used)
            - validation: dict with validation results
            - error: str or None
    """
    from .content_validator import validate_content_quality

    # Define cascade of methods
    # Each tuple: (name, fetch_function, skip_paywall_check_for_this_method)
    methods = [
        ('cookies', lambda: fetch_with_cookies(url, cookie_manager, timeout), True),
        ('direct', lambda: fetch_direct_http(url, timeout), False),
        ('no_js', lambda: fetch_without_javascript(url, timeout), False),
        ('selenium_no_js', lambda: fetch_selenium_js_disabled(url, timeout), False),
        ('archive', lambda: fetch_archive_today(url), False)
    ]

    logger.info("="*80)
    logger.info("FETCH CASCADE: Trying multiple methods until success")
    logger.info("="*80)

    for method_name, fetch_func, skip_check_for_method in methods:
        logger.info(f"→ Method {methods.index((method_name, fetch_func, skip_check_for_method)) + 1}/{len(methods)}: {method_name}")

        try:
            html = fetch_func()

            if not html:
                logger.debug(f"  ✗ Method '{method_name}' failed to fetch HTML")
                continue

            # Skip content validation for authenticated methods or if globally disabled
            should_validate = not skip_paywall_check and not skip_check_for_method

            validation_result = None

            if should_validate:
                logger.debug(f"  → Validating content quality (paywall + completeness)...")
                # Pass is_archive=True if this is the archive method
                validation_result = validate_content_quality(
                    html=html,
                    url=url,
                    title=title,
                    llm_client=llm_client,
                    is_archive=(method_name == 'archive')
                )

                logger.info(f"  → Validation: paywall={validation_result['has_paywall']}, "
                           f"content={validation_result['has_content']}, "
                           f"words={validation_result['word_count']}")

                if not validation_result['is_valid']:
                    if validation_result['has_paywall']:
                        logger.warning(f"  ✗ Method '{method_name}' has PAYWALL, trying next method")
                    else:
                        logger.warning(f"  ✗ Method '{method_name}' has INSUFFICIENT CONTENT "
                                     f"({validation_result['word_count']} words), trying next method")
                    logger.debug(f"     Reason: {validation_result['reason']}")
                    continue
                else:
                    logger.info(f"  ✓ Content validated: {validation_result['reason']}")
            else:
                logger.info(f"  ⏭️  Content validation skipped (authenticated or --skip-paywall-check)")
                # Create dummy validation result
                validation_result = {
                    'is_valid': True,
                    'has_paywall': False,
                    'has_content': True,
                    'word_count': len(html.split()),
                    'confidence': 100,
                    'reason': 'Validation skipped (authenticated session)'
                }

            # Success!
            logger.info("="*80)
            logger.info(f"✓ FETCH SUCCESS via '{method_name}'")
            if validation_result:
                logger.info(f"  Content quality: {validation_result['confidence']}% confidence")
                logger.info(f"  Word count: {validation_result['word_count']} words")
            logger.info("="*80)

            return {
                'success': True,
                'html': html,
                'method': method_name,
                'has_auth': method_name == 'cookies',
                'archive_url': f"https://archive.today/newest/{url}" if method_name == 'archive' else None,
                'validation': validation_result,
                'error': None
            }

        except Exception as e:
            logger.error(f"  ✗ Method '{method_name}' raised exception: {e}")
            continue

    # All methods failed
    logger.error("="*80)
    logger.error("✗ ALL FETCH METHODS FAILED")
    logger.error("="*80)

    return {
        'success': False,
        'html': None,
        'method': 'none',
        'has_auth': False,
        'archive_url': None,
        'error': 'All fetch methods failed (tried: cookies, direct, no-js, selenium-no-js, archive.today)'
    }
