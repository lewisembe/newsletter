"""
Archive.today Fetcher

Fetches archived versions of URLs from archive.today using Selenium.
Bypasses paywalls by retrieving cached snapshots.

Adapted from: old/article_retriver/archive_retriever_selenium.py
Author: Newsletter Utils Team
Created: 2025-11-13
"""

import os
import sys
import time
import logging
from urllib.parse import quote
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)


def setup_archive_driver(headless: bool = True) -> webdriver.Chrome:
    """
    Configure Chrome driver with anti-detection measures.

    Args:
        headless: Run in headless mode (no visible window)

    Returns:
        Configured Selenium webdriver

    Raises:
        WebDriverException: If driver initialization fails
    """
    options = Options()

    if headless:
        options.add_argument('--headless=new')

    # Anti-detection options
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-infobars')
    options.add_argument('--start-maximized')
    options.add_argument('--window-size=1920,1080')

    # Realistic user agent
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    options.add_argument(f'user-agent={user_agent}')

    # Additional preferences
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)

    # Disable images for faster loading
    prefs = {
        'profile.managed_default_content_settings.images': 2,
        'profile.default_content_setting_values.notifications': 2
    }
    options.add_experimental_option('prefs', prefs)

    try:
        # Try system chromedriver first
        service = Service('/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=options)

        # Hide Selenium traces
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": user_agent
        })
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        logger.debug("Archive driver initialized successfully")
        return driver

    except WebDriverException as e:
        logger.error(f"Failed to initialize Chrome driver: {e}")
        logger.error("Ensure Chrome/Chromium and chromedriver are installed")
        raise


def fetch_archive_selenium(
    url: str,
    wait_time: int = None,
    max_retries: int = None
) -> Optional[str]:
    """
    Fetch HTML content from archive.today using Selenium.

    Strategy:
    1. Navigate to archive.today/newest/{url}
    2. Wait for page load (JavaScript execution)
    3. Check for CAPTCHA/protection pages
    4. Return full HTML if successful

    Args:
        url: Original URL to find in archive
        wait_time: Max seconds to wait for page load (default: from env)
        max_retries: Number of retry attempts (default: from env)

    Returns:
        HTML content string if successful, None if failed
    """
    if wait_time is None:
        wait_time = int(os.getenv('STAGE04_ARCHIVE_WAIT_TIME', '15'))

    if max_retries is None:
        max_retries = int(os.getenv('STAGE04_MAX_RETRIES', '2'))

    for attempt in range(max_retries):
        driver = None
        try:
            driver = setup_archive_driver(headless=True)

            # Build search URL
            archive_search_url = f"https://archive.today/newest/{quote(url, safe='')}"

            logger.info(f"Fetching from archive.today (attempt {attempt + 1}/{max_retries}): {url}")
            driver.get(archive_search_url)

            # Critical: Wait for JavaScript execution
            # Archive.today uses heavy JS, needs time to render
            time.sleep(8)  # Extended initial wait

            # Wait for body element
            try:
                WebDriverWait(driver, wait_time).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except TimeoutException:
                logger.warning(f"Timeout waiting for page load (attempt {attempt + 1})")
                continue

            # Check for 404
            page_title = driver.title.lower()
            if '404' in page_title or 'not found' in page_title:
                logger.info(f"Archive not found for {url}")
                return None

            # Get full HTML
            html_content = driver.page_source

            # Check for CAPTCHA/protection page
            # Archive.today shows a yellow CAPTCHA page with minimal HTML
            if len(html_content) < 5000 and 'background-color:#FFFAE1' in html_content:
                logger.warning(f"CAPTCHA/protection page detected (attempt {attempt + 1}), retrying...")
                time.sleep(5)  # Extra wait before retry
                continue

            # Success!
            logger.info(f"✓ Fetched archive content: {len(html_content)} bytes")
            return html_content

        except WebDriverException as e:
            logger.error(f"Selenium error on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                logger.error(f"All retry attempts failed for {url}")
                return None

        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    logger.debug(f"Error closing driver: {e}")

        # Wait before retry
        if attempt < max_retries - 1:
            retry_delay = int(os.getenv('STAGE04_RETRY_DELAYS', '5,10,20').split(',')[attempt])
            logger.info(f"Waiting {retry_delay}s before retry...")
            time.sleep(retry_delay)

    return None


def fetch_direct_archive_snapshot(
    snapshot_url: str,
    wait_time: int = None
) -> Optional[str]:
    """
    Fetch HTML from a direct archive.today snapshot URL.

    Use this when you already have a specific snapshot URL
    (e.g., https://archive.ph/xxxxx) instead of searching.

    Args:
        snapshot_url: Direct archive.today snapshot URL
        wait_time: Max seconds to wait for page load

    Returns:
        HTML content string if successful, None if failed
    """
    if wait_time is None:
        wait_time = int(os.getenv('STAGE04_ARCHIVE_WAIT_TIME', '15'))

    driver = None
    try:
        driver = setup_archive_driver(headless=True)

        logger.info(f"Fetching direct snapshot: {snapshot_url}")
        driver.get(snapshot_url)

        time.sleep(3)  # Initial wait

        try:
            WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            logger.warning("Timeout waiting for snapshot")
            return None

        html_content = driver.page_source
        logger.info(f"✓ Fetched snapshot: {len(html_content)} bytes")
        return html_content

    except WebDriverException as e:
        logger.error(f"Error fetching direct snapshot: {e}")
        return None

    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.debug(f"Error closing driver: {e}")
