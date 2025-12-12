"""
Cookie Manager for Stage 04 Authenticated Scraping

Manages cookies stored in SQLite database with auto-renewal capabilities.
Integrates cookie loading from DB and automatic renewal using Selenium.

Author: Newsletter Utils Team
Created: 2025-11-14
"""

import logging
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

logger = logging.getLogger(__name__)


class CookieManager:
    """
    Manages cookies for authenticated scraping with DB storage and auto-renewal.
    """

    def __init__(self, db, headless: bool = True):
        """
        Initialize cookie manager.

        Args:
            db: SQLiteURLDatabase instance
            headless: Run Selenium in headless mode for renewal
        """
        self.db = db
        self.headless = headless

    def get_cookies_for_url(self, url: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get cookies for a URL's domain.

        Args:
            url: URL to get cookies for

        Returns:
            List of cookies, or None if no cookies for this domain
        """
        domain = self._extract_domain(url)
        cookies = self.db.get_cookies_for_domain(domain)

        if not cookies:
            return None

        return cookies

    def has_cookies_for_url(self, url: str) -> bool:
        """
        Check if cookies exist for a URL's domain.

        Args:
            url: URL to check

        Returns:
            True if cookies exist
        """
        domain = self._extract_domain(url)
        return self.db.has_cookies_for_domain(domain)

    def check_and_renew_if_needed(self, url: str, threshold_days: int = 7) -> bool:
        """
        Check if cookies need renewal and auto-renew if necessary.

        Args:
            url: URL to check cookies for
            threshold_days: Renew if any cookie expires within this many days

        Returns:
            True if cookies are valid (or were successfully renewed)
        """
        domain = self._extract_domain(url)

        if not self.db.has_cookies_for_domain(domain):
            logger.debug(f"No cookies for {domain} - skipping renewal check")
            return True

        # Check expiry
        expiry_status = self.db.check_cookie_expiry(domain, threshold_days)

        if not expiry_status['needs_renewal']:
            logger.debug(f"Cookies for {domain} are valid (no renewal needed)")
            return True

        # Needs renewal
        logger.info(f"🔄 Cookies for {domain} need renewal:")
        if expiry_status['expired']:
            logger.info(f"   - {len(expiry_status['expired'])} expired")
        if expiry_status['expiring_soon']:
            logger.info(f"   - {len(expiry_status['expiring_soon'])} expiring soon")

        # Auto-renew
        success = self.auto_renew_cookies(domain)

        if success:
            logger.info(f"✅ Successfully renewed cookies for {domain}")
            return True
        else:
            logger.warning(f"⚠️  Failed to auto-renew cookies for {domain}")
            logger.warning("   Continuing with existing cookies (may fail if expired)")
            return False

    def auto_renew_cookies(self, domain: str) -> bool:
        """
        Automatically renew cookies by refreshing the session with Selenium.

        Loads existing cookies, navigates to domain, and extracts fresh cookies.

        Args:
            domain: Domain to renew cookies for

        Returns:
            True if renewal was successful
        """
        try:
            logger.info(f"Starting cookie auto-renewal for {domain}")

            # Load existing cookies
            existing_cookies = self.db.get_cookies_for_domain(domain)
            if not existing_cookies:
                logger.warning(f"No existing cookies to renew for {domain}")
                return False

            # Setup Selenium
            driver = self._setup_selenium_driver()

            try:
                # Clean domain for navigation (remove leading dot if present)
                # Cookies may be stored as ".ft.com" but we need to navigate to "ft.com"
                navigable_domain = domain.lstrip('.')

                # Navigate to domain first (required to set cookies)
                logger.debug(f"Navigating to https://{navigable_domain}")
                driver.get(f"https://{navigable_domain}")

                # Inject existing cookies
                self._inject_cookies_to_driver(driver, existing_cookies, domain)

                # Refresh page to trigger cookie renewal
                logger.debug(f"Refreshing page to renew cookies")
                driver.refresh()
                time.sleep(3)  # Wait for page load

                # Extract fresh cookies from browser
                fresh_cookies = driver.get_cookies()

                if not fresh_cookies:
                    logger.error("Failed to extract fresh cookies from browser")
                    return False

                # Convert Selenium cookies to storage format
                storage_cookies = self._convert_selenium_cookies(fresh_cookies)

                # Save to database
                count = self.db.save_cookies(domain, storage_cookies)

                logger.info(f"Renewed {count} cookies for {domain}")
                return count > 0

            finally:
                driver.quit()

        except Exception as e:
            logger.error(f"Cookie auto-renewal failed for {domain}: {e}")
            return False

    def _setup_selenium_driver(self) -> webdriver.Chrome:
        """Setup Selenium Chrome driver for cookie renewal."""
        options = Options()

        if self.headless:
            options.add_argument('--headless=new')

        # Standard options
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Anti-bot user agent
        options.add_argument('user-agent=Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36')

        # Use system chromedriver (Raspberry Pi compatible)
        chromedriver_path = '/usr/bin/chromedriver'
        if os.path.exists(chromedriver_path):
            service = Service(chromedriver_path)
        else:
            service = Service()

        # Try chromium-browser binary
        chromium_path = '/usr/bin/chromium-browser'
        if os.path.exists(chromium_path):
            options.binary_location = chromium_path

        return webdriver.Chrome(service=service, options=options)

    def _inject_cookies_to_driver(
        self,
        driver: webdriver.Chrome,
        cookies: List[Dict[str, Any]],
        domain: str
    ):
        """
        Inject cookies from DB into Selenium driver.

        Args:
            driver: Selenium WebDriver instance
            cookies: List of cookie dicts from DB
            domain: Domain these cookies belong to
        """
        loaded = 0

        for cookie in cookies:
            try:
                cookie_dict = {
                    'name': cookie['cookie_name'],
                    'value': cookie['cookie_value'],
                    'domain': cookie['domain'],
                    'path': cookie['path'],
                    'secure': bool(cookie['secure']),
                }

                if cookie['http_only']:
                    cookie_dict['httpOnly'] = True

                if cookie['same_site'] and cookie['same_site'] in ['Strict', 'Lax', 'None']:
                    cookie_dict['sameSite'] = cookie['same_site']

                if cookie['expiry']:
                    cookie_dict['expiry'] = cookie['expiry']

                driver.add_cookie(cookie_dict)
                loaded += 1

            except Exception as e:
                logger.debug(f"Failed to inject cookie {cookie['cookie_name']}: {e}")
                continue

        logger.debug(f"Injected {loaded}/{len(cookies)} cookies into driver")

    def _convert_selenium_cookies(self, selenium_cookies: List[Dict]) -> List[Dict[str, Any]]:
        """
        Convert Selenium cookies to storage format.

        Args:
            selenium_cookies: Cookies from driver.get_cookies()

        Returns:
            List of cookies in storage format
        """
        storage_cookies = []

        for cookie in selenium_cookies:
            storage_cookie = {
                'name': cookie.get('name'),
                'value': cookie.get('value'),
                'domain': cookie.get('domain'),
                'path': cookie.get('path', '/'),
                'secure': cookie.get('secure', False),
                'httpOnly': cookie.get('httpOnly', False),
                'sameSite': cookie.get('sameSite'),
                'expiry': cookie.get('expiry'),
            }

            storage_cookies.append(storage_cookie)

        return storage_cookies

    @staticmethod
    def _extract_domain(url: str) -> str:
        """
        Extract domain from URL.

        Args:
            url: Full URL

        Returns:
            Domain (e.g., 'ft.com')
        """
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        return domain

    def format_cookies_for_requests(self, url: str) -> Optional[Dict[str, str]]:
        """
        Format cookies for use with requests library.

        Args:
            url: URL to get cookies for

        Returns:
            Dictionary of cookie name->value pairs, or None if no cookies
        """
        cookies = self.get_cookies_for_url(url)

        if not cookies:
            return None

        return {c['cookie_name']: c['cookie_value'] for c in cookies}

    def format_cookies_for_selenium(self, url: str) -> Optional[List[Dict[str, Any]]]:
        """
        Format cookies for use with Selenium.

        Args:
            url: URL to get cookies for

        Returns:
            List of cookie dicts formatted for driver.add_cookie(), or None if no cookies
        """
        cookies = self.get_cookies_for_url(url)

        if not cookies:
            return None

        selenium_cookies = []

        for cookie in cookies:
            cookie_dict = {
                'name': cookie['cookie_name'],
                'value': cookie['cookie_value'],
                'domain': cookie['domain'],
                'path': cookie['path'],
                'secure': bool(cookie['secure']),
            }

            if cookie['http_only']:
                cookie_dict['httpOnly'] = True

            if cookie['same_site'] and cookie['same_site'] in ['Strict', 'Lax', 'None']:
                cookie_dict['sameSite'] = cookie['same_site']

            if cookie['expiry']:
                cookie_dict['expiry'] = cookie['expiry']

            selenium_cookies.append(cookie_dict)

        return selenium_cookies
