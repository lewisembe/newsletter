#!/usr/bin/env python3
"""
Cookie Auto-Renewer
Automatically refreshes cookies from an active browser session.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


class CookieAutoRenewer:
    """Automatically renews cookies from active session."""

    def __init__(self, cookies_file: str = "cookies.json", headless: bool = True):
        """
        Initialize the renewer.

        Args:
            cookies_file: Path to cookies JSON file
            headless: Run in headless mode
        """
        self.cookies_file = cookies_file
        self.headless = headless
        self.driver = None

    def setup_driver(self):
        """Setup Selenium WebDriver."""
        options = Options()
        if self.headless:
            options.add_argument('--headless')

        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Use system chromedriver
        chromedriver_path = '/usr/bin/chromedriver'
        if os.path.exists(chromedriver_path):
            service = Service(chromedriver_path)
        else:
            service = Service()

        chromium_path = '/usr/bin/chromium-browser'
        if os.path.exists(chromium_path):
            options.binary_location = chromium_path

        self.driver = webdriver.Chrome(service=service, options=options)

    def check_cookies_need_renewal(self, days_threshold: int = 7) -> bool:
        """
        Check if cookies need renewal.

        Args:
            days_threshold: Renew if any cookie expires within this many days

        Returns:
            True if cookies need renewal
        """
        if not Path(self.cookies_file).exists():
            print(f"⚠️  Cookie file not found: {self.cookies_file}")
            return True

        with open(self.cookies_file, 'r') as f:
            cookies = json.load(f)

        now_timestamp = datetime.now(timezone.utc).timestamp()

        for cookie in cookies:
            # Session cookies always need checking
            if cookie.get('session', False):
                print(f"🔄 Session cookie detected: {cookie.get('name')} - renewal recommended")
                return True

            # Check expiration
            if 'expirationDate' in cookie:
                expiry = cookie['expirationDate']
                days_until_expiry = (expiry - now_timestamp) / (60 * 60 * 24)

                if days_until_expiry < days_threshold:
                    print(f"⚠️  Cookie {cookie.get('name')} expires in {days_until_expiry:.1f} days")
                    return True

        print(f"✅ All cookies valid for at least {days_threshold} days")
        return False

    def load_current_cookies(self, domain: str):
        """
        Load current cookies into browser.

        Args:
            domain: Domain to load cookies for
        """
        if not Path(self.cookies_file).exists():
            print(f"⚠️  No existing cookies to load")
            return

        with open(self.cookies_file, 'r') as f:
            cookies = json.load(f)

        # Navigate to domain first
        self.driver.get(f"https://{domain}")

        # Load existing cookies
        loaded = 0
        for cookie in cookies:
            cookie_domain = cookie.get('domain', '').lstrip('.')
            if cookie_domain in domain or domain in cookie_domain:
                try:
                    cookie_dict = {
                        'name': cookie['name'],
                        'value': cookie['value'],
                        'domain': cookie.get('domain', domain),
                        'path': cookie.get('path', '/'),
                        'secure': cookie.get('secure', False),
                    }

                    if 'httpOnly' in cookie:
                        cookie_dict['httpOnly'] = cookie['httpOnly']

                    if 'sameSite' in cookie and cookie['sameSite']:
                        same_site = cookie['sameSite']
                        if same_site in ['Strict', 'Lax', 'None']:
                            cookie_dict['sameSite'] = same_site

                    if 'expirationDate' in cookie:
                        cookie_dict['expiry'] = int(cookie['expirationDate'])
                    elif 'expiry' in cookie:
                        cookie_dict['expiry'] = int(cookie['expiry'])

                    self.driver.add_cookie(cookie_dict)
                    loaded += 1
                except Exception as e:
                    # Skip cookies that fail to load
                    pass

        print(f"📥 Loaded {loaded} existing cookies")

    def renew_cookies(self, domain: str = "ft.com") -> bool:
        """
        Renew cookies by refreshing the page with current session.

        Args:
            domain: Domain to renew cookies for

        Returns:
            True if renewal was successful
        """
        try:
            print(f"\n🔄 Starting cookie renewal for {domain}...")

            self.setup_driver()

            # Load existing cookies to maintain session
            self.load_current_cookies(domain)

            # Refresh the page to get new cookies
            print(f"🌐 Navigating to https://{domain} to refresh session...")
            self.driver.get(f"https://{domain}")

            # Wait a moment for page to load
            import time
            time.sleep(3)

            # Get fresh cookies from browser
            fresh_cookies = self.driver.get_cookies()

            if not fresh_cookies:
                print("❌ Failed to get fresh cookies")
                return False

            # Convert to storage format (Chrome extension format)
            stored_cookies = []
            for cookie in fresh_cookies:
                stored_cookie = {
                    'domain': cookie.get('domain', ''),
                    'hostOnly': False,
                    'httpOnly': cookie.get('httpOnly', False),
                    'name': cookie.get('name', ''),
                    'path': cookie.get('path', '/'),
                    'sameSite': cookie.get('sameSite', None),
                    'secure': cookie.get('secure', False),
                    'session': 'expiry' not in cookie,
                    'storeId': None,
                    'value': cookie.get('value', ''),
                }

                # Add expiration if present
                if 'expiry' in cookie:
                    stored_cookie['expirationDate'] = cookie['expiry']

                stored_cookies.append(stored_cookie)

            # Backup old cookies
            if Path(self.cookies_file).exists():
                backup_file = f"{self.cookies_file}.backup"
                import shutil
                shutil.copy(self.cookies_file, backup_file)
                print(f"💾 Backed up old cookies to {backup_file}")

            # Save new cookies
            with open(self.cookies_file, 'w') as f:
                json.dump(stored_cookies, f, indent=4)

            print(f"✅ Successfully renewed {len(stored_cookies)} cookies!")
            print(f"💾 Saved to {self.cookies_file}")

            # Show expiry info for key cookies
            self._show_renewal_summary(stored_cookies)

            return True

        except Exception as e:
            print(f"❌ Error renewing cookies: {e}")
            return False

        finally:
            if self.driver:
                self.driver.quit()

    def _show_renewal_summary(self, cookies: List[Dict[str, Any]]):
        """Show summary of renewed cookies."""
        now_timestamp = datetime.now(timezone.utc).timestamp()

        print(f"\n📊 Renewal Summary:")
        print(f"   Total cookies: {len(cookies)}")

        session_count = sum(1 for c in cookies if c.get('session', False))
        print(f"   Session cookies: {session_count}")

        # Find earliest expiry
        expiring = []
        for cookie in cookies:
            if 'expirationDate' in cookie:
                days_until = (cookie['expirationDate'] - now_timestamp) / (60 * 60 * 24)
                expiring.append({
                    'name': cookie['name'],
                    'days': days_until
                })

        if expiring:
            expiring.sort(key=lambda x: x['days'])
            first = expiring[0]
            print(f"\n⏰ First to expire: {first['name']} in {first['days']:.1f} days")
            print(f"   Next renewal recommended in ~{int(first['days'] * 0.7)} days")


def main():
    """Main execution."""
    load_dotenv()

    renewer = CookieAutoRenewer(
        cookies_file="cookies.json",
        headless=True
    )

    # Check if renewal is needed
    print("🔍 Checking cookie status...")
    needs_renewal = renewer.check_cookies_need_renewal(days_threshold=7)

    if needs_renewal:
        print("\n⚡ Renewal needed!")
        success = renewer.renew_cookies(domain="ft.com")

        if success:
            print("\n✅ Cookie renewal completed successfully!")
        else:
            print("\n❌ Cookie renewal failed")
            print("💡 Tip: You may need to manually re-export cookies from your browser")
    else:
        print("\n✅ Cookies are still valid - no renewal needed")


if __name__ == '__main__':
    main()
