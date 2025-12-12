"""
Authenticated Scraper for Stage 04
Uses persistent cookies for bypassing paywalls on authenticated sites.

Adapted from: content_POC/authenticated_scraper.py
Author: Newsletter Utils Team
Created: 2025-11-14
"""

import json
import os
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from urllib.parse import urlparse
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


class AuthenticatedScraper:
    """Scraper that uses persistent cookies for authenticated requests."""

    def __init__(
        self,
        cookies_dir: str = "config",
        headless: bool = True,
        timeout: int = 30,
        db_connection_string: Optional[str] = None,
        use_database: bool = True
    ):
        """
        Initialize the authenticated scraper.

        Args:
            cookies_dir: Directory containing cookie files (fallback)
            headless: Run browser in headless mode
            timeout: Page load timeout in seconds
            db_connection_string: PostgreSQL connection string (for DB cookies)
            use_database: Whether to use database for cookies (True by default)
        """
        self.cookies_dir = Path(cookies_dir)
        self.timeout = timeout
        self.headless = headless
        self.driver = None
        self.use_database = use_database
        self.db_connection_string = db_connection_string or os.getenv('DATABASE_URL')
        self._domain_cookie_map = self._build_cookie_map()

        # Track cookies usage for reporting
        self.cookies_used = {}  # domain -> {success: bool, url: str, timestamp: str}

    def _build_cookie_map(self) -> Dict[str, str]:
        """
        Build mapping of domains to cookie files.

        Scans cookies_dir for cookies_*.json files and maps them to domains.

        Returns:
            Dict mapping domain → cookie file path
        """
        cookie_map = {}

        if not self.cookies_dir.exists():
            logger.warning(f"Cookies directory not found: {self.cookies_dir}")
            return cookie_map

        # Find all cookies_*.json files
        for cookie_file in self.cookies_dir.glob("cookies_*.json"):
            # Extract domain from filename: cookies_ft.json → ft.com
            domain_part = cookie_file.stem.replace("cookies_", "")

            # Map common abbreviations to full domains
            domain_mapping = {
                "ft": "ft.com",
                "nyt": "nytimes.com",
                "wsj": "wsj.com",
                "bloomberg": "bloomberg.com",
                "economist": "economist.com"
            }

            domain = domain_mapping.get(domain_part, f"{domain_part}.com")
            cookie_map[domain] = str(cookie_file)

            logger.debug(f"Mapped domain {domain} → {cookie_file.name}")

        logger.info(f"Loaded cookie mappings for {len(cookie_map)} domains")
        return cookie_map

    def _setup_driver(self):
        """Setup Selenium WebDriver with Chrome."""
        options = Options()

        if self.headless:
            options.add_argument('--headless=new')

        # Stealth options to avoid detection
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # User agent
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        # Use system chromedriver (try multiple locations)
        chromedriver_paths = [
            '/usr/bin/chromedriver',     # Standard location
            '/usr/lib/chromium-browser/chromedriver',  # Raspberry Pi
        ]

        chromedriver_path = None
        for path in chromedriver_paths:
            if os.path.exists(path):
                chromedriver_path = path
                break

        if chromedriver_path:
            service = Service(chromedriver_path)
        else:
            service = Service()  # Let Selenium find it

        # Try chromium binary locations
        chromium_paths = [
            '/usr/bin/chromium-browser',  # Raspberry Pi
            '/usr/bin/chromium',          # Debian/Ubuntu
        ]

        for chromium_path in chromium_paths:
            if os.path.exists(chromium_path):
                options.binary_location = chromium_path
                break

        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_page_load_timeout(self.timeout)

        logger.debug("Selenium WebDriver initialized")

    def _get_cookies_from_db(self, domain: str) -> Optional[List[Dict]]:
        """
        Get cookies from database for the specified domain.

        Args:
            domain: Domain to get cookies for (e.g., "ft.com")

        Returns:
            List of cookie dictionaries or None
        """
        if not self.use_database or not self.db_connection_string:
            return None

        try:
            from common.postgres_db import PostgreSQLURLDatabase
            db = PostgreSQLURLDatabase(self.db_connection_string)
            cookie_record = db.get_cookies_by_domain(domain)

            if cookie_record and cookie_record.get('cookies'):
                # Parse JSONB cookies field
                cookies_data = cookie_record['cookies']
                if isinstance(cookies_data, str):
                    cookies = json.loads(cookies_data)
                else:
                    cookies = cookies_data

                logger.debug(f"Loaded {len(cookies)} cookies from database for {domain}")
                return cookies

            logger.debug(f"No cookies in database for domain: {domain}")
            return None

        except Exception as e:
            logger.warning(f"Failed to load cookies from database for {domain}: {e}")
            return None

    def _load_cookies_for_domain(self, domain: str) -> bool:
        """
        Load cookies from database or file for the specified domain.

        Args:
            domain: Domain to load cookies for (e.g., "ft.com")

        Returns:
            True if cookies were loaded successfully
        """
        # Try database first
        cookies = self._get_cookies_from_db(domain)

        # Fallback to file if database doesn't have cookies
        if not cookies:
            # Find cookie file for this domain
            cookie_file = self._domain_cookie_map.get(domain)

            if not cookie_file:
                logger.debug(f"No cookie file found for domain: {domain}")
                return False

            if not os.path.exists(cookie_file):
                logger.warning(f"Cookie file not found: {cookie_file}")
                return False

            try:
                with open(cookie_file, 'r') as f:
                    cookies = json.load(f)
            except Exception as e:
                logger.error(f"Error loading cookies from {cookie_file}: {e}")
                return False

        # At this point, we have cookies (either from DB or file)
        if not cookies:
            logger.warning(f"No cookies available for {domain}")
            return False

        # Clean domain for navigation (remove leading dot if present)
        # Cookies may be stored as ".ft.com" but we need to navigate to "ft.com"
        navigable_domain = domain.lstrip('.')

        # Navigate to domain first (required to set cookies)
        self.driver.get(f"https://{navigable_domain}")

        # Add each cookie
        loaded_count = 0
        for cookie in cookies:
            # Filter cookies for this domain
            cookie_domain = cookie.get('domain', '').lstrip('.')
            if cookie_domain in domain or domain in cookie_domain:
                try:
                    # Prepare cookie dict for Selenium
                    cookie_dict = {
                        'name': cookie['name'],
                        'value': cookie['value'],
                        'domain': cookie.get('domain', domain),
                        'path': cookie.get('path', '/'),
                        'secure': cookie.get('secure', False),
                    }

                    # Optional fields
                    if 'httpOnly' in cookie:
                        cookie_dict['httpOnly'] = cookie['httpOnly']

                    # Handle sameSite
                    if 'sameSite' in cookie and cookie['sameSite']:
                        same_site = cookie['sameSite']
                        if same_site in ['Strict', 'Lax', 'None']:
                            cookie_dict['sameSite'] = same_site

                    # Handle expiry
                    if 'expirationDate' in cookie:
                        cookie_dict['expiry'] = int(cookie['expirationDate'])
                    elif 'expiry' in cookie:
                        cookie_dict['expiry'] = int(cookie['expiry'])

                    self.driver.add_cookie(cookie_dict)
                    loaded_count += 1

                except Exception as e:
                    logger.debug(f"Failed to add cookie {cookie.get('name')}: {e}")

        logger.info(f"✓ Loaded {loaded_count} cookies for {domain}")
        return loaded_count > 0

    def fetch_with_cookies(self, url: str) -> Optional[str]:
        """
        Fetch HTML from URL using cookies for authentication.

        Args:
            url: URL to fetch

        Returns:
            HTML content or None if failed
        """
        try:
            # Parse domain from URL
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')

            # Check if we have cookies for this domain
            if domain not in self._domain_cookie_map:
                logger.debug(f"No cookies available for domain: {domain}")
                return None

            # Setup driver if not already initialized
            if self.driver is None:
                self._setup_driver()

            # Load cookies for this domain
            cookies_loaded = self._load_cookies_for_domain(domain)

            if not cookies_loaded:
                logger.warning(f"Failed to load cookies for {domain}")
                return None

            # Navigate to the URL (now with cookies)
            logger.info(f"Fetching with cookies: {url}")
            self.driver.get(url)

            # Wait for body to load
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Get page source
            html = self.driver.page_source

            logger.info(f"✓ Fetched with cookies: {len(html)} bytes")

            # Track successful cookie usage
            self.cookies_used[domain] = {
                'success': True,
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'response_size': len(html)
            }

            return html

        except Exception as e:
            logger.error(f"Authenticated fetch failed for {url}: {e}", exc_info=True)

            # Track failed cookie usage
            self.cookies_used[domain] = {
                'success': False,
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

            # Update cookie status in database if using DB
            if self.use_database and self.db_connection_string:
                try:
                    from common.postgres_db import PostgreSQLURLDatabase
                    db = PostgreSQLURLDatabase(self.db_connection_string)
                    db.update_cookie_validation(domain, {
                        'status': 'invalid',
                        'message': f'Cookie falló durante scraping: {str(e)}',
                        'tested_at': datetime.now(),
                        'test_url': url,
                        'response_size': 0,
                        'error': str(e)
                    })
                    logger.warning(f"✗ Cookie status updated to 'invalid' for {domain} in database")
                except Exception as db_error:
                    logger.warning(f"Failed to update cookie status in DB: {db_error}")

            return None

    def has_cookies_for_domain(self, domain: str) -> bool:
        """
        Check if cookies are available for the given domain.

        Args:
            domain: Domain to check (e.g., "ft.com")

        Returns:
            True if cookies exist for this domain
        """
        return domain in self._domain_cookie_map

    def get_cookies_usage_report(self) -> Dict[str, Any]:
        """
        Get report of cookies usage during this session.

        Returns:
            Dict with:
                - domains_used: List of domains where cookies were used
                - successful: List of successful domain names
                - failed: List of failed domain names
                - total: Total domains attempted
                - success_rate: Percentage of successful cookie usage
                - details: Detailed info per domain
        """
        successful = [d for d, info in self.cookies_used.items() if info['success']]
        failed = [d for d, info in self.cookies_used.items() if not info['success']]

        return {
            'domains_used': list(self.cookies_used.keys()),
            'successful': successful,
            'failed': failed,
            'total': len(self.cookies_used),
            'success_rate': (len(successful) / len(self.cookies_used) * 100) if self.cookies_used else 0,
            'details': self.cookies_used
        }

    def close(self):
        """Close the browser."""
        if self.driver:
            try:
                self.driver.quit()
                logger.debug("WebDriver closed")
            except Exception as e:
                logger.warning(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def get_domain_from_url(url: str) -> str:
    """
    Extract clean domain from URL.

    Args:
        url: Full URL

    Returns:
        Clean domain (e.g., "ft.com")
    """
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')
    return domain
