"""
Selenium utilities for web scraping.
Provides a wrapper for Selenium WebDriver with headless mode and robust error handling.
"""

import os
import re
import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException
)

logger = logging.getLogger(__name__)


def get_base_domain(url: str) -> str:
    """
    Extract base domain from URL (scheme + netloc).

    Args:
        url: Full URL

    Returns:
        Base domain (e.g., 'https://elpais.com')
    """
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


class SeleniumDriver:
    """Wrapper for Selenium WebDriver with configuration from environment."""

    def __init__(self, headless: bool = True, user_agent: Optional[str] = None, timeout: int = 10):
        """
        Initialize Selenium driver with configuration.

        Args:
            headless: Run browser in headless mode
            user_agent: Custom user agent string
            timeout: Default timeout for page loads and element waits
        """
        self.headless = headless
        self.user_agent = user_agent
        self.timeout = timeout
        self.driver = None

    def __enter__(self):
        """Context manager entry - initialize driver."""
        self.driver = self._create_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup driver."""
        if self.driver:
            self.driver.quit()

    def _create_driver(self) -> webdriver.Chrome:
        """Create and configure Chrome WebDriver."""
        options = Options()

        # Set binary location for Chromium (Raspberry Pi / ARM64 systems)
        options.binary_location = '/usr/bin/chromium'

        if self.headless:
            options.add_argument('--headless=new')

        # Common arguments for stability
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Set user agent if provided
        if self.user_agent:
            options.add_argument(f'user-agent={self.user_agent}')

        # Disable images and CSS for faster loading (optional)
        # prefs = {'profile.managed_default_content_settings.images': 2}
        # options.add_experimental_option('prefs', prefs)

        try:
            # Use system chromedriver
            service = Service('/usr/bin/chromedriver')
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(self.timeout)
            logger.info("Chrome WebDriver initialized successfully")
            return driver
        except WebDriverException as e:
            logger.error(f"Failed to initialize Chrome WebDriver: {e}")
            raise

    def _extract_title_robust(self, element) -> str:
        """
        Extract title from link element using textContent.

        Uses JavaScript textContent which gets all text from the <a> element
        and its descendants, regardless of nesting or visibility.

        Sanitizes HTML tags that may be included in the extracted text as plain text
        (e.g., <img> tags from some news sites like Le Monde that embed HTML as text).

        Args:
            element: Selenium WebElement (the <a> tag)

        Returns:
            Extracted title string (sanitized), or empty string if not found
        """
        try:
            raw_title = self.driver.execute_script(
                "return arguments[0].textContent || '';",
                element
            ).strip()

            # Remove HTML tags that appear as plain text in the title
            # Pattern matches: <tag>, <tag attr="value">, </tag>, etc.
            # This handles cases where HTML is embedded as text (not parsed elements)
            sanitized_title = re.sub(r'<[^>]+>', '', raw_title)

            # Clean up any extra whitespace created by tag removal
            sanitized_title = ' '.join(sanitized_title.split())

            return sanitized_title.strip()
        except:
            return ''

    def get_page(self, url: str) -> bool:
        """
        Navigate to a URL.

        Args:
            url: URL to navigate to

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Navigating to: {url}")
            self.driver.get(url)
            # Wait for page to load
            WebDriverWait(self.driver, self.timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            logger.debug(f"Successfully loaded: {url}")
            return True
        except TimeoutException:
            logger.error(f"Timeout loading page: {url}")
            return False
        except WebDriverException as e:
            logger.error(f"Error loading page {url}: {e}")
            return False

    def extract_links(self, selectors: List[str]) -> List[Dict[str, str]]:
        """
        Extract links from page using CSS selectors.

        For duplicate titles from the same domain, keeps the shortest URL
        (to avoid tracking parameters).

        Args:
            selectors: List of CSS selectors to try

        Returns:
            List of dicts with 'url' and 'title' keys
        """
        # Track best link per (domain, title) combination
        # Key: (base_domain, title) -> Value: {'url': ..., 'title': ...}
        best_links = {}

        # Get minimum title length from environment (default: 10)
        min_title_length = int(os.getenv('MIN_TITLE_LENGTH', '10'))

        # Track statistics
        skipped_empty = 0
        skipped_short = 0
        skipped_duplicate_title = 0
        replaced_with_shorter = 0

        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                logger.debug(f"Found {len(elements)} elements with selector: {selector}")

                for element in elements:
                    try:
                        url = element.get_attribute('href')

                        # Skip invalid URLs early
                        if not url:
                            continue

                        # Skip anchors and javascript links
                        if url.startswith('#') or url.startswith('javascript:'):
                            continue

                        # Skip non-http(s) protocols
                        if not url.startswith('http'):
                            continue

                        # Extract title using robust multi-strategy approach
                        title = self._extract_title_robust(element)

                        # Remove all leading/trailing whitespace (spaces, tabs, newlines)
                        title = ' '.join(title.split()).strip() if title else ''

                        # Skip links without sufficient title text
                        if not title:
                            skipped_empty += 1
                            logger.debug(f"Skipped link with empty title: {url}")
                            continue

                        # Skip titles that are too short OR single-word
                        if len(title) < min_title_length or len(title.split()) == 1:
                            skipped_short += 1
                            logger.debug(f"Skipped link with short title ({len(title)} chars, {len(title.split())} words): {url} → '{title}'")
                            continue

                        # Skip comment links (navigation elements)
                        if '#ancla_comentarios' in url or url.endswith('#comentarios'):
                            skipped_short += 1
                            logger.debug(f"Skipped comment link: {url}")
                            continue

                        # Skip common navigation/footer elements
                        navigation_patterns = [
                            'comentarios', 'comentario',
                            'skip advertisement', 'advertisement',
                            'revelación', 'política de privacidad', 'política de cookies',
                            'privacy policy', 'cookie policy', 'newsletters'
                        ]
                        title_lower = title.lower()
                        if any(pattern in title_lower for pattern in navigation_patterns):
                            skipped_short += 1
                            logger.debug(f"Skipped navigation element: {title}")
                            continue

                        # Create deduplication key: (base_domain, title)
                        base_domain = get_base_domain(url)
                        dedup_key = (base_domain, title)

                        # Check if this (domain, title) combination already exists
                        if dedup_key in best_links:
                            existing_url = best_links[dedup_key]['url']
                            existing_url_len = len(existing_url)
                            new_url_len = len(url)

                            # Replace if new URL is shorter (cleaner, less tracking params)
                            if new_url_len < existing_url_len:
                                logger.debug(
                                    f"Replacing duplicate title '{title[:50]}...': "
                                    f"shorter URL ({new_url_len} vs {existing_url_len} chars)"
                                )
                                best_links[dedup_key] = {'url': url, 'title': title}
                                replaced_with_shorter += 1
                            else:
                                # Skip this duplicate (already have shorter version)
                                skipped_duplicate_title += 1
                                logger.debug(f"Skipped duplicate title (longer URL): '{title[:50]}...'")
                        else:
                            # First occurrence of this (domain, title) combination
                            best_links[dedup_key] = {'url': url, 'title': title}

                    except Exception as e:
                        logger.debug(f"Error extracting link data: {e}")
                        continue

            except NoSuchElementException:
                logger.debug(f"No elements found for selector: {selector}")
                continue
            except Exception as e:
                logger.warning(f"Error with selector '{selector}': {e}")
                continue

        # Convert dict to list
        links = list(best_links.values())

        logger.info(
            f"Extracted {len(links)} unique links "
            f"({skipped_empty} skipped: empty title, {skipped_short} skipped: title too short, "
            f"{skipped_duplicate_title} skipped: duplicate title, "
            f"{replaced_with_shorter} replaced with shorter URL)"
        )
        return links

    def scroll_page(self, scrolls: int = 3, pause: float = 1.0):
        """
        Scroll page to load dynamic content.

        Args:
            scrolls: Number of scroll actions
            pause: Pause between scrolls in seconds
        """
        import time

        for i in range(scrolls):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause)
            logger.debug(f"Scroll {i+1}/{scrolls} completed")

    def scroll_and_extract(self, selectors: List[str], max_links: int = 250) -> List[Dict[str, str]]:
        """
        Scroll page while extracting links until reaching limit or end of content.
        Uses human-like keyboard simulation (END key) instead of JavaScript scrolling.

        Args:
            selectors: List of CSS selectors to try
            max_links: Maximum number of links to extract (stops when reached)

        Returns:
            List of dicts with 'url' and 'title' keys (max max_links items)
        """
        import time

        all_links = {}  # Use dict to track unique URLs by URL as key
        previous_count = 0
        no_change_iterations = 0

        logger.info(f"Starting scroll extraction with human-like behavior (max_links={max_links})")

        # Get the body element to send keys to
        try:
            body = self.driver.find_element(By.TAG_NAME, 'body')
        except NoSuchElementException:
            logger.error("Could not find body element for keyboard simulation")
            return []

        while True:
            # Extract links at current scroll position
            current_links = self.extract_links(selectors)

            # Add new unique links
            for link in current_links:
                if link['url'] not in all_links:
                    all_links[link['url']] = link

            current_count = len(all_links)
            logger.debug(f"Current: {current_count} total links found")

            # CONDITION 1: Reached max_links limit
            if current_count >= max_links:
                logger.info(f"✓ Reached link limit: {current_count} links (limit: {max_links})")
                break

            # CONDITION 2: No new links found (end of content)
            if current_count == previous_count:
                no_change_iterations += 1
                if no_change_iterations >= 3:
                    logger.info(f"✓ No more content: {current_count} links found (no new links after 3 scroll attempts)")
                    break
            else:
                no_change_iterations = 0

            previous_count = current_count

            # Simulate human scrolling: press END key to go to bottom
            body.send_keys(Keys.END)

            # Wait for lazy-loaded content to appear (human-like pause)
            time.sleep(2.5)

        # Convert dict back to list and limit to max_links
        result = list(all_links.values())[:max_links]
        logger.info(f"Scroll extraction completed: {len(result)} links extracted")

        return result


def create_driver_from_env() -> SeleniumDriver:
    """
    Create SeleniumDriver instance using .env configuration.

    Returns:
        Configured SeleniumDriver instance
    """
    from dotenv import load_dotenv
    load_dotenv()

    headless = os.getenv('SELENIUM_HEADLESS', 'true').lower() == 'true'
    user_agent = os.getenv('SELENIUM_USER_AGENT')
    timeout = int(os.getenv('SELENIUM_TIMEOUT', '10'))

    return SeleniumDriver(
        headless=headless,
        user_agent=user_agent,
        timeout=timeout
    )
