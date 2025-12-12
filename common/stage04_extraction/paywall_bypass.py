"""
Paywall Bypass Strategies

Multiple strategies to bypass client-side paywalls:
1. Fetch without JavaScript (requests only)
2. Fetch with JavaScript disabled (Selenium)
3. Archive.today fallback (current implementation)

Author: Newsletter Utils Team
Created: 2025-11-13
"""

import logging
import requests
import time
from typing import Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException

logger = logging.getLogger(__name__)


def fetch_without_javascript(url: str, timeout: int = 30) -> Optional[str]:
    """
    Fetch HTML content without JavaScript execution.

    Many paywalls are client-side JavaScript that won't trigger
    with a simple HTTP request.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        HTML content or None if failed
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

        logger.info(f"Trying fetch without JavaScript: {url}")
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()

        html = response.text
        logger.info(f"✓ Fetched {len(html)} bytes without JS")
        return html

    except requests.RequestException as e:
        logger.warning(f"Fetch without JS failed: {e}")
        return None


def fetch_with_js_disabled_selenium(url: str, timeout: int = 30) -> Optional[str]:
    """
    Fetch HTML using Selenium with JavaScript disabled.

    This bypasses JavaScript-based paywalls while still handling
    redirects and cookies properly.

    Args:
        url: URL to fetch
        timeout: Page load timeout in seconds

    Returns:
        HTML content or None if failed
    """
    driver = None
    try:
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')

        # CRITICAL: Disable JavaScript
        prefs = {
            'profile.managed_default_content_settings.javascript': 2,  # 2 = block
            'profile.managed_default_content_settings.images': 2,  # Optimize loading
            'profile.default_content_setting_values.notifications': 2
        }
        options.add_experimental_option('prefs', prefs)

        # User agent
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        options.add_argument(f'user-agent={user_agent}')

        # Hide automation
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)

        logger.info(f"Trying fetch with JS disabled (Selenium): {url}")

        service = Service('/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(timeout)

        # Navigate
        driver.get(url)

        # Small wait for page structure
        time.sleep(2)

        html = driver.page_source
        logger.info(f"✓ Fetched {len(html)} bytes with JS disabled")
        return html

    except WebDriverException as e:
        logger.warning(f"Fetch with JS disabled failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in JS-disabled fetch: {e}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def try_paywall_bypass_strategies(
    url: str,
    direct_html: str,
    llm_client: Any,
    timeout: int = 30
) -> Dict[str, Any]:
    """
    Try multiple bypass strategies for paywalled content.

    Strategy cascade:
    1. Check if direct fetch (with JS) is already OK
    2. Try fetch without JS (requests only)
    3. Try fetch with Selenium but JS disabled
    4. Try archive.today (existing method)

    Each method is validated for paywall before returning.

    Args:
        url: URL to fetch
        direct_html: Already-fetched HTML from direct request
        llm_client: LLM client for paywall detection
        timeout: Timeout for each method

    Returns:
        Dict with:
            - success: bool
            - html: str or None
            - method: str (which method worked)
            - bypass_used: bool
    """
    from .paywall_validator import detect_paywall_with_llm
    from .archive_fetcher import fetch_archive_selenium

    # Method 1: Check direct HTML first
    logger.info("Bypass strategy 1/4: Check direct fetch (already done)")
    is_paywalled = detect_paywall_with_llm(direct_html, url, llm_client)

    if not is_paywalled:
        logger.info("✓ Direct fetch has no paywall!")
        return {
            'success': True,
            'html': direct_html,
            'method': 'direct',
            'bypass_used': False
        }

    logger.warning("⚠ Direct fetch has paywall, trying bypass strategies...")

    # Method 2: Fetch without JavaScript (simple requests)
    logger.info("Bypass strategy 2/4: Fetch without JavaScript")
    html_no_js = fetch_without_javascript(url, timeout)

    if html_no_js:
        is_paywalled = detect_paywall_with_llm(html_no_js, url, llm_client)
        if not is_paywalled:
            logger.info("✓ No-JS fetch bypassed paywall!")
            return {
                'success': True,
                'html': html_no_js,
                'method': 'no_javascript',
                'bypass_used': True
            }
        logger.warning("✗ No-JS fetch still has paywall")

    # Method 3: Selenium with JavaScript disabled
    logger.info("Bypass strategy 3/4: Selenium with JS disabled")
    html_selenium_no_js = fetch_with_js_disabled_selenium(url, timeout)

    if html_selenium_no_js:
        is_paywalled = detect_paywall_with_llm(html_selenium_no_js, url, llm_client)
        if not is_paywalled:
            logger.info("✓ Selenium (JS disabled) bypassed paywall!")
            return {
                'success': True,
                'html': html_selenium_no_js,
                'method': 'selenium_no_js',
                'bypass_used': True
            }
        logger.warning("✗ Selenium (JS disabled) still has paywall")

    # Method 4: Archive.today fallback
    logger.info("Bypass strategy 4/4: Archive.today")
    archive_html = fetch_archive_selenium(url)

    if archive_html:
        is_paywalled = detect_paywall_with_llm(archive_html, url, llm_client)
        if not is_paywalled:
            logger.info("✓ Archive.today bypassed paywall!")
            return {
                'success': True,
                'html': archive_html,
                'method': 'archive_today',
                'bypass_used': True,
                'archive_url': f"https://archive.today/newest/{url}"
            }
        logger.warning("✗ Archive.today also has paywall (server-side paywall)")

    # All methods failed
    logger.error("✗ All bypass strategies failed - paywall cannot be bypassed")
    return {
        'success': False,
        'html': None,
        'method': 'none',
        'bypass_used': False,
        'error': 'Paywall cannot be bypassed (tried: direct, no-js, selenium-no-js, archive.today)'
    }
