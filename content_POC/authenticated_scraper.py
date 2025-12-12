#!/usr/bin/env python3
"""
Authenticated Content Scraper POC
Extracts content from news sites using persistent cookies.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup


class AuthenticatedScraper:
    """Scraper that uses persistent cookies for authentication."""

    def __init__(self, cookies_file: str, headless: bool = False, timeout: int = 30):
        """
        Initialize the scraper.

        Args:
            cookies_file: Path to JSON file with cookies
            headless: Run browser in headless mode
            timeout: Default timeout for page loads
        """
        self.cookies_file = cookies_file
        self.timeout = timeout
        self.driver = None
        self.setup_driver(headless)

    def setup_driver(self, headless: bool):
        """Setup Selenium WebDriver with Chrome."""
        options = Options()
        if headless:
            options.add_argument('--headless')

        # Additional options for stability
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # User agent to avoid detection
        options.add_argument('user-agent=Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36')

        # Use system chromedriver (better for ARM/Raspberry Pi)
        # Try to use system chromedriver, fallback to chromium if needed
        chromedriver_path = '/usr/bin/chromedriver'
        if os.path.exists(chromedriver_path):
            service = Service(chromedriver_path)
        else:
            service = Service()  # Let Selenium find it

        # Try chromium-browser binary for Raspberry Pi
        chromium_path = '/usr/bin/chromium-browser'
        if os.path.exists(chromium_path):
            options.binary_location = chromium_path

        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_page_load_timeout(self.timeout)

    def load_cookies(self, domain: str) -> bool:
        """
        Load cookies from JSON file for the specified domain.

        Args:
            domain: Domain to load cookies for

        Returns:
            True if cookies were loaded successfully
        """
        if not os.path.exists(self.cookies_file):
            print(f"❌ Cookie file not found: {self.cookies_file}")
            return False

        try:
            with open(self.cookies_file, 'r') as f:
                cookies = json.load(f)

            # First, navigate to the domain to set cookies
            # We need to be on the domain before adding cookies
            self.driver.get(f"https://{domain}")

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

                        # Handle sameSite (convert null to None, or use valid values)
                        if 'sameSite' in cookie and cookie['sameSite']:
                            # Selenium expects: 'Strict', 'Lax', or 'None'
                            same_site = cookie['sameSite']
                            if same_site in ['Strict', 'Lax', 'None']:
                                cookie_dict['sameSite'] = same_site

                        # Handle expiry: convert expirationDate to expiry (Unix timestamp as int)
                        if 'expirationDate' in cookie:
                            cookie_dict['expiry'] = int(cookie['expirationDate'])
                        elif 'expiry' in cookie:
                            cookie_dict['expiry'] = int(cookie['expiry'])

                        self.driver.add_cookie(cookie_dict)
                        loaded_count += 1
                    except Exception as e:
                        print(f"⚠️  Failed to add cookie {cookie.get('name')}: {e}")

            print(f"✅ Loaded {loaded_count} cookies for {domain}")
            return loaded_count > 0

        except Exception as e:
            print(f"❌ Error loading cookies: {e}")
            return False

    def extract_content(self, url: str) -> Dict[str, Any]:
        """
        Extract content from a URL.

        Args:
            url: URL to scrape

        Returns:
            Dictionary with extracted content
        """
        result = {
            'url': url,
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'title': None,
            'content': None,
            'word_count': 0,
            'error': None
        }

        try:
            # Parse domain from URL
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')

            # Load cookies for this domain
            cookies_loaded = self.load_cookies(domain)
            if not cookies_loaded:
                print(f"⚠️  Warning: No cookies loaded for {domain}")

            # Navigate to the URL
            print(f"📄 Fetching: {url}")
            self.driver.get(url)

            # Wait for body to load
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Get page source
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'lxml')

            # Extract title
            title_tag = soup.find('title')
            if title_tag:
                result['title'] = title_tag.get_text(strip=True)

            # Try to find main content
            # This is a generic approach - may need site-specific selectors
            content_candidates = [
                soup.find('article'),
                soup.find('main'),
                soup.find(attrs={'role': 'main'}),
                soup.find(class_=['article-body', 'article-content', 'story-body', 'content-body']),
                soup.find('body')
            ]

            for candidate in content_candidates:
                if candidate:
                    # Remove script and style tags
                    for script in candidate(['script', 'style', 'nav', 'header', 'footer']):
                        script.decompose()

                    # Get text
                    text = candidate.get_text(separator='\n', strip=True)
                    if len(text) > 200:  # Minimum viable content
                        result['content'] = text
                        result['word_count'] = len(text.split())
                        result['success'] = True
                        break

            if not result['success']:
                result['error'] = 'Could not extract meaningful content'

        except Exception as e:
            result['error'] = str(e)
            print(f"❌ Error extracting {url}: {e}")

        return result

    def scrape_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Scrape multiple URLs.

        Args:
            urls: List of URLs to scrape

        Returns:
            List of results
        """
        results = []
        for url in urls:
            result = self.extract_content(url)
            results.append(result)
            print(f"{'✅' if result['success'] else '❌'} {url}")
            if result['success']:
                print(f"   Title: {result['title']}")
                print(f"   Words: {result['word_count']}")
            else:
                print(f"   Error: {result['error']}")
        return results

    def close(self):
        """Close the browser."""
        if self.driver:
            self.driver.quit()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def save_results(results: List[Dict[str, Any]], output_dir: str):
    """
    Save results to JSON file.

    Args:
        results: List of scraping results
        output_dir: Output directory
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_path / f"scrape_results_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Results saved to: {output_file}")

    # Print summary
    successful = sum(1 for r in results if r['success'])
    print(f"\n📊 Summary:")
    print(f"   Total URLs: {len(results)}")
    print(f"   Successful: {successful}")
    print(f"   Failed: {len(results) - successful}")


def check_and_renew_cookies(cookies_file: str, days_threshold: int = 7) -> bool:
    """
    Check if cookies need renewal and renew them if necessary.

    Args:
        cookies_file: Path to cookies file
        days_threshold: Renew if any cookie expires within this many days

    Returns:
        True if cookies are valid or were successfully renewed
    """
    if not os.path.exists(cookies_file):
        print(f"⚠️  Cookie file not found: {cookies_file}")
        return False

    # Import renewer only when needed
    try:
        from cookie_auto_renewer import CookieAutoRenewer
    except ImportError:
        print("⚠️  Cookie auto-renewer not available")
        return True  # Continue anyway

    renewer = CookieAutoRenewer(cookies_file=cookies_file, headless=True)

    # Check if renewal needed
    needs_renewal = renewer.check_cookies_need_renewal(days_threshold=days_threshold)

    if needs_renewal:
        print(f"\n🔄 Auto-renewing cookies...")
        success = renewer.renew_cookies(domain="ft.com")

        if success:
            print("✅ Cookies renewed successfully!")
            return True
        else:
            print("⚠️  Auto-renewal failed - continuing with existing cookies")
            print("💡 Tip: Manually re-export cookies if authentication fails")
            return True  # Try to continue anyway

    return True


def main():
    """Main execution function."""
    # Load environment variables
    load_dotenv()

    # Get configuration
    test_urls = os.getenv('TEST_URLS', '').split(',')
    test_urls = [url.strip() for url in test_urls if url.strip()]

    if not test_urls:
        print("❌ No TEST_URLS configured in .env file")
        sys.exit(1)

    cookies_file = os.getenv('COOKIES_FILE', 'cookies.json')
    headless = os.getenv('HEADLESS', 'false').lower() == 'true'
    timeout = int(os.getenv('TIMEOUT', '30'))
    output_dir = os.getenv('OUTPUT_DIR', 'output')
    auto_renew = os.getenv('AUTO_RENEW_COOKIES', 'true').lower() == 'true'

    print("🚀 Authenticated Scraper POC")
    print(f"   URLs to scrape: {len(test_urls)}")
    print(f"   Cookies file: {cookies_file}")
    print(f"   Headless mode: {headless}")
    print(f"   Timeout: {timeout}s")
    print(f"   Auto-renew cookies: {auto_renew}")
    print()

    # Check and renew cookies if needed
    if auto_renew:
        check_and_renew_cookies(cookies_file, days_threshold=7)
        print()

    # Run scraper
    try:
        with AuthenticatedScraper(cookies_file, headless, timeout) as scraper:
            results = scraper.scrape_urls(test_urls)
            save_results(results, output_dir)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
