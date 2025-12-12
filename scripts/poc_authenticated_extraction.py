#!/usr/bin/env python3
"""
POC: Authenticated Content Extraction
======================================

Proof of concept for automated login and content extraction from paywalled sources
using LLM-guided Selenium interactions.

Usage:
    python scripts/poc_authenticated_extraction.py --url <article_url>

Example:
    python scripts/poc_authenticated_extraction.py --url "https://www.ft.com/content/..."
"""

import os
import sys
import argparse
import time
import json
import pickle
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import shutil
import random

from common.llm import LLMClient
from dotenv import load_dotenv

load_dotenv()

# Initialize LLM client
llm_client = LLMClient()

# Credentials configuration
CREDENTIALS = {
    "ft.com": {
        "email": "201001166@alu.upcomillas.edu",
        "password": "luisbarack",
        "login_url": "https://www.ft.com/login"
    }
}


class AuthenticatedExtractor:
    """Handles authenticated session and content extraction using LLM-guided Selenium"""

    def __init__(self, headless: bool = False, cookies_dir: str = "data/cookies"):
        self.headless = headless
        self.driver = None
        self.wait = None
        self.cookies_dir = Path(cookies_dir)
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

    def _init_driver(self):
        """Initialize Selenium WebDriver with extensive human-like characteristics"""
        chrome_options = Options()

        # Find Chromium browser path
        chromium_path = shutil.which('chromium') or shutil.which('chromium-browser') or shutil.which('google-chrome')
        if chromium_path:
            chrome_options.binary_location = chromium_path
            print(f"ℹ️  Using browser: {chromium_path}")

        if self.headless:
            chrome_options.add_argument("--headless=new")

        # Window size - simulate real desktop browser
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")

        # Anti-detection measures
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Additional stealth
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        chrome_options.add_argument("--disable-site-isolation-trials")
        chrome_options.add_argument("--disable-infobars")

        # Language and locale
        chrome_options.add_argument("--lang=en-US")

        # Preferences to appear more like a real user
        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.geolocation": 1,
            "profile.managed_default_content_settings.images": 1,
            # Accept language
            "intl.accept_languages": "en-US,en;q=0.9",
            # Timezone
            "profile.default_content_settings.timezone": "America/New_York",
        }
        chrome_options.add_experimental_option("prefs", prefs)

        # Realistic user agent (Windows instead of Linux to be more common)
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Find ChromeDriver path
        chromedriver_path = shutil.which('chromedriver') or '/usr/bin/chromedriver'
        print(f"ℹ️  Using ChromeDriver: {chromedriver_path}")

        # Create service with explicit path
        service = Service(executable_path=chromedriver_path)

        self.driver = webdriver.Chrome(service=service, options=chrome_options)

        # Execute CDP commands to create realistic browser fingerprint
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                // Remove webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // Override permissions API
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );

                // Add chrome runtime (present in real Chrome)
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };

                // Realistic plugin array
                Object.defineProperty(navigator, 'plugins', {
                    get: () => {
                        return [
                            {
                                0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                                description: "Portable Document Format",
                                filename: "internal-pdf-viewer",
                                length: 1,
                                name: "Chrome PDF Plugin"
                            },
                            {
                                0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format"},
                                description: "Portable Document Format",
                                filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                                length: 1,
                                name: "Chrome PDF Viewer"
                            },
                            {
                                0: {type: "application/x-nacl", suffixes: "", description: "Native Client Executable"},
                                1: {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable"},
                                description: "",
                                filename: "internal-nacl-plugin",
                                length: 2,
                                name: "Native Client"
                            }
                        ];
                    }
                });

                // Languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });

                // Platform
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
                });

                // Hardware concurrency (CPU cores)
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });

                // Device memory
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });

                // Connection (realistic network info)
                Object.defineProperty(navigator, 'connection', {
                    get: () => ({
                        effectiveType: '4g',
                        rtt: 50,
                        downlink: 10,
                        saveData: false
                    })
                });

                // Screen resolution (common desktop)
                Object.defineProperty(screen, 'width', {
                    get: () => 1920
                });
                Object.defineProperty(screen, 'height', {
                    get: () => 1080
                });
                Object.defineProperty(screen, 'availWidth', {
                    get: () => 1920
                });
                Object.defineProperty(screen, 'availHeight', {
                    get: () => 1040
                });

                // Battery API (make it look real)
                if (navigator.getBattery) {
                    navigator.getBattery = () => Promise.resolve({
                        charging: true,
                        chargingTime: 0,
                        dischargingTime: Infinity,
                        level: 1
                    });
                }

                // Override toString methods to hide proxying
                const toStringProxy = new Proxy(Function.prototype.toString, {
                    apply: function(target, thisArg, argumentsList) {
                        if (thisArg === navigator.permissions.query) {
                            return 'function query() { [native code] }';
                        }
                        return target.apply(thisArg, argumentsList);
                    }
                });
                Function.prototype.toString = toStringProxy;
            """
        })

        self.wait = WebDriverWait(self.driver, 20)

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        # Remove www. prefix if present
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _get_page_html(self) -> str:
        """Get current page HTML"""
        return self.driver.page_source

    def _human_delay(self, min_seconds=0.5, max_seconds=2.0):
        """Random delay to simulate human thinking/reading time"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def _move_mouse_to_element(self, element):
        """Simulate human-like mouse movement to element"""
        try:
            actions = ActionChains(self.driver)

            # Get element position
            location = element.location
            size = element.size

            # Random point within element
            offset_x = random.randint(5, max(6, size['width'] - 5))
            offset_y = random.randint(5, max(6, size['height'] - 5))

            # Move to element with random path
            actions.move_to_element_with_offset(element, offset_x, offset_y)
            actions.perform()

            # Small delay after mouse movement
            time.sleep(random.uniform(0.1, 0.3))
        except Exception as e:
            # If mouse movement fails, just continue
            pass

    def _human_click(self, element):
        """Click element with human-like behavior"""
        try:
            # Scroll element into view
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            self._human_delay(0.3, 0.8)

            # Move mouse to element
            self._move_mouse_to_element(element)

            # Small delay before click
            time.sleep(random.uniform(0.1, 0.3))

            # Click
            element.click()
        except Exception as e:
            # Fallback to JavaScript click if regular click fails
            self.driver.execute_script("arguments[0].click();", element)

    def _human_type(self, element, text):
        """Type text with human-like timing"""
        try:
            element.clear()
        except Exception:
            # If clear fails, element might be read-only or not interactable yet
            # Wait a bit and try to click it again
            self._human_delay(0.5, 1.0)
            try:
                element.click()
                time.sleep(0.3)
            except Exception:
                pass

        self._human_delay(0.3, 0.7)

        for char in text:
            element.send_keys(char)
            # Variable typing speed: 50-150ms per character
            delay = random.uniform(0.05, 0.15)
            # Occasional longer pause (simulating thinking)
            if random.random() < 0.1:
                delay += random.uniform(0.2, 0.5)
            time.sleep(delay)

    def _ask_llm_for_selectors(self, html_snippet: str, action: str) -> Dict:
        """
        Ask LLM to identify selectors for login form elements

        Args:
            html_snippet: Relevant portion of HTML (first 10000 chars)
            action: Description of what we need (e.g., "find email input field")

        Returns:
            Dict with selector information
        """
        system_prompt = """You are an expert at analyzing HTML and identifying DOM selectors.
Your task is to find the correct CSS selector or XPath for specific elements.
Return ONLY valid JSON - no extra text."""

        user_prompt = f"""Analyze this HTML snippet from a login page and identify the CSS selector or XPath for: {action}

HTML snippet (truncated):
```html
{html_snippet[:10000]}
```

Return ONLY a JSON object with this structure:
{{
    "selector_type": "css" or "xpath",
    "selector": "the actual selector string",
    "confidence": "high/medium/low",
    "reasoning": "brief explanation"
}}

Be precise - the selector must work with Selenium's find_element method."""

        response = llm_client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=os.getenv("MODEL_XPATH_DISCOVERY", "gpt-4o-mini"),
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"},
            stage="poc",
            operation="xpath_discovery"
        )

        # Extract JSON from response
        try:
            # Try to find JSON in code blocks first
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            return json.loads(json_str)
        except Exception as e:
            print(f"❌ Failed to parse LLM response: {e}")
            print(f"Response was: {response}")
            return None

    def _find_element_with_llm(self, action: str, max_retries: int = 2):
        """
        Use LLM to find element on page

        Args:
            action: Description of element to find
            max_retries: Number of times to retry if element not found

        Returns:
            Selenium WebElement or None
        """
        html = self._get_page_html()

        for attempt in range(max_retries):
            print(f"🤖 Asking LLM to identify selector for: {action} (attempt {attempt + 1}/{max_retries})")

            selector_info = self._ask_llm_for_selectors(html, action)

            if not selector_info:
                continue

            print(f"   Selector: {selector_info.get('selector')} (confidence: {selector_info.get('confidence')})")

            try:
                selector_type = selector_info.get("selector_type", "css")
                selector = selector_info.get("selector")

                if selector_type == "css":
                    element = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                else:  # xpath
                    element = self.wait.until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )

                print(f"   ✅ Element found!")
                return element

            except (TimeoutException, NoSuchElementException) as e:
                print(f"   ⚠️  Element not found with suggested selector")
                if attempt < max_retries - 1:
                    print(f"   Retrying...")
                continue

        print(f"❌ Failed to find element after {max_retries} attempts")
        return None

    def login(self, url: str) -> bool:
        """
        Perform login using LLM-guided element detection

        Args:
            url: Article URL to access after login

        Returns:
            True if login successful, False otherwise
        """
        domain = self._get_domain(url)

        if domain not in CREDENTIALS:
            print(f"❌ No credentials configured for {domain}")
            return False

        creds = CREDENTIALS[domain]
        print(f"🔐 Attempting login to {domain}...")

        try:
            # Initialize driver
            if not self.driver:
                self._init_driver()

            # Simulate arriving from Google search (realistic referer)
            print(f"🔍 Simulating Google search arrival...")
            google_search_url = f"https://www.google.com/search?q=financial+times+login"
            self.driver.get(google_search_url)
            self._human_delay(1.0, 2.0)  # "Read" search results

            # Navigate to login page
            print(f"📄 Loading login page: {creds['login_url']}")
            self.driver.get(creds['login_url'])
            self._human_delay(2.0, 3.5)  # Wait for page to fully load + simulate reading

            # Screenshot for debugging
            self._save_screenshot("01_login_page")

            # Step 1: Find and fill email field
            email_field = self._find_element_with_llm("email input field in the login form")
            if not email_field:
                return False

            print(f"✍️  Entering email: {creds['email']}")
            # Move mouse and click on field first
            self._human_click(email_field)
            # Type with human timing
            self._human_type(email_field, creds['email'])
            self._human_delay(0.5, 1.2)

            # Step 2: Try to find and click "Next" or "Continue" button (for multi-step login)
            print(f"🔍 Looking for Next/Continue button...")
            continue_button = self._find_element_with_llm("Next button or Continue button to proceed after entering email (NOT Google or Apple sign in buttons, the main blue/teal Next or Continue button)")

            password_field = None

            if continue_button:
                print(f"🖱️  Clicking Continue button")
                self._human_click(continue_button)
                self._human_delay(3.0, 4.5)  # Wait for password field to appear/become visible
                self._save_screenshot("02_after_continue")

                # Step 3: Find password field (should now be visible)
                print(f"🔍 Looking for password field...")
                password_field = self._find_element_with_llm("password input field that is visible on the page")

            if not password_field:
                # Maybe it's a single-page login, try to find password directly
                print(f"⚠️  Password field not found after Continue. Trying direct search...")
                time.sleep(2)
                password_field = self._find_element_with_llm("password input field")

            if not password_field:
                print(f"❌ Could not find password field")
                return False

            print(f"✍️  Entering password")
            # Click and type password with human behavior
            self._human_click(password_field)
            self._human_type(password_field, creds['password'])
            self._human_delay(0.8, 1.5)

            self._save_screenshot("03_credentials_entered")

            # Step 4: Find submit button for password
            submit_button = self._find_element_with_llm("Sign in button or submit button for the password form (NOT the Google button, the main Sign in button)")
            if not submit_button:
                return False

            print(f"🖱️  Clicking submit/sign in button")
            self._human_click(submit_button)

            # Wait for login to complete (human would wait to see result)
            print(f"⏳ Waiting for login to complete...")
            self._human_delay(4.0, 6.0)

            self._save_screenshot("04_after_submit")

            # Check for CAPTCHA
            html = self._get_page_html()
            if any(keyword in html.lower() for keyword in ["captcha", "recaptcha", "puzzle", "slider"]):
                print(f"\n🔒 CAPTCHA detected!")
                print(f"⚠️  FT is showing a CAPTCHA challenge.")
                print(f"")
                print(f"Options:")
                print(f"  1. Run in non-headless mode: remove --headless flag")
                print(f"  2. Solve manually: The browser will wait for you to solve it")
                print(f"  3. Use CAPTCHA solving service (2captcha, anticaptcha)")
                print(f"")

                if not self.headless:
                    print(f"👤 Please solve the CAPTCHA manually in the browser window...")
                    print(f"   Waiting 60 seconds for manual solve...")
                    time.sleep(60)
                    self._save_screenshot("05_after_captcha_solve")
                else:
                    print(f"❌ Cannot solve CAPTCHA in headless mode.")
                    return False

            # Check if login was successful (check if we're still on login page or got redirected)
            current_url = self.driver.current_url
            if "login" in current_url.lower():
                print(f"⚠️  Still on login page, checking for errors...")
                # Look for error messages using LLM
                error_check = self._ask_llm_for_selectors(
                    self._get_page_html(),
                    "error message or warning indicating failed login"
                )
                if error_check:
                    print(f"❌ Login failed: {error_check.get('reasoning', 'Unknown error')}")
                    return False

            print(f"✅ Login successful! Current URL: {current_url}")
            return True

        except Exception as e:
            print(f"❌ Login failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return False

    def extract_content(self, url: str) -> Optional[Dict]:
        """
        Extract article content from authenticated page

        Args:
            url: Article URL

        Returns:
            Dict with extracted content or None if failed
        """
        try:
            print(f"\n📰 Navigating to article: {url}")
            self.driver.get(url)
            time.sleep(3)

            self._save_screenshot("05_article_page")

            # Check if we hit a paywall
            html = self._get_page_html()
            if any(keyword in html.lower() for keyword in ["subscribe", "paywall", "premium content"]):
                print("⚠️  Potential paywall detected, but we're logged in - proceeding...")

            # Use LLM to find article content
            print("🤖 Using LLM to identify article content...")

            # Find article title
            title_element = self._find_element_with_llm("main article headline or title")
            title = title_element.text if title_element else "Unknown Title"

            # Find article body
            content_element = self._find_element_with_llm("main article body or content div")

            if content_element:
                content_text = content_element.text
                word_count = len(content_text.split())

                print(f"\n✅ Content extracted successfully!")
                print(f"   Title: {title[:100]}...")
                print(f"   Word count: {word_count}")

                return {
                    "url": url,
                    "title": title,
                    "content": content_text,
                    "word_count": word_count,
                    "extracted_at": datetime.now().isoformat(),
                    "method": "authenticated_selenium_llm"
                }
            else:
                print("❌ Failed to find article content")
                return None

        except Exception as e:
            print(f"❌ Content extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _save_screenshot(self, name: str):
        """Save screenshot for debugging"""
        screenshots_dir = Path("logs/screenshots")
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = screenshots_dir / f"{timestamp}_{name}.png"

        try:
            self.driver.save_screenshot(str(filepath))
            print(f"📸 Screenshot saved: {filepath}")
        except Exception as e:
            print(f"⚠️  Failed to save screenshot: {e}")

    def _get_cookies_path(self, domain: str) -> Path:
        """Get path to cookies file for a domain"""
        # Sanitize domain name for filename
        safe_domain = domain.replace(".", "_")
        return self.cookies_dir / f"{safe_domain}_cookies.pkl"

    def save_cookies(self, domain: str) -> bool:
        """
        Save current browser cookies to file

        Args:
            domain: Domain name (e.g., 'ft.com')

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            cookies = self.driver.get_cookies()
            cookies_path = self._get_cookies_path(domain)

            # Save with metadata
            cookie_data = {
                "cookies": cookies,
                "saved_at": datetime.now().isoformat(),
                "domain": domain
            }

            with open(cookies_path, 'wb') as f:
                pickle.dump(cookie_data, f)

            print(f"💾 Cookies saved to: {cookies_path}")
            print(f"   ({len(cookies)} cookies)")
            return True

        except Exception as e:
            print(f"❌ Failed to save cookies: {e}")
            return False

    def load_cookies(self, domain: str, url: str) -> bool:
        """
        Load cookies from file and apply to browser

        Args:
            domain: Domain name (e.g., 'ft.com')
            url: URL to navigate to before loading cookies

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            cookies_path = self._get_cookies_path(domain)

            if not cookies_path.exists():
                print(f"⚠️  No saved cookies found for {domain}")
                return False

            # Load cookie data
            with open(cookies_path, 'rb') as f:
                cookie_data = pickle.load(f)

            cookies = cookie_data.get('cookies', [])
            saved_at = cookie_data.get('saved_at', 'unknown')

            print(f"🔑 Loading cookies from: {cookies_path}")
            print(f"   Saved at: {saved_at}")
            print(f"   Count: {len(cookies)} cookies")

            # Navigate to domain first (required to set cookies)
            self.driver.get(url)
            time.sleep(2)

            # Add each cookie
            for cookie in cookies:
                try:
                    # Remove problematic keys
                    if 'expiry' in cookie:
                        cookie['expiry'] = int(cookie['expiry'])

                    self.driver.add_cookie(cookie)
                except Exception as e:
                    print(f"⚠️  Could not add cookie: {cookie.get('name', 'unknown')} - {e}")

            print(f"✅ Cookies loaded successfully")
            return True

        except Exception as e:
            print(f"❌ Failed to load cookies: {e}")
            return False

    def validate_cookies(self, test_url: str) -> bool:
        """
        Validate that cookies are still valid by checking if we can access protected content

        Args:
            test_url: URL of a protected page to test access

        Returns:
            True if cookies are valid (can access content), False otherwise
        """
        try:
            print(f"🔍 Validating cookies by accessing: {test_url}")
            self.driver.get(test_url)
            time.sleep(3)

            # Check if we're redirected to login page
            current_url = self.driver.current_url.lower()
            if "login" in current_url or "signin" in current_url:
                print(f"❌ Cookies expired - redirected to login")
                return False

            # Check page content for login indicators
            page_html = self.driver.page_source.lower()
            login_indicators = ["sign in", "log in", "subscribe now", "create account"]

            # If page has minimal login indicators, cookies are probably valid
            indicator_count = sum(1 for indicator in login_indicators if indicator in page_html)

            if indicator_count > 3:  # Threshold: if we see too many login prompts
                print(f"❌ Cookies may be expired - login prompts detected")
                return False

            print(f"✅ Cookies appear valid - access granted")
            return True

        except Exception as e:
            print(f"⚠️  Cookie validation failed: {e}")
            return False

    def close(self):
        """Close browser and cleanup"""
        if self.driver:
            self.driver.quit()
            self.driver = None


def main():
    parser = argparse.ArgumentParser(
        description="POC: Extract content from paywalled sources using authenticated sessions"
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Article URL to extract content from"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    parser.add_argument(
        "--output",
        help="Output file path for extracted content (optional)"
    )
    parser.add_argument(
        "--use-cookies",
        action="store_true",
        help="Try to use saved cookies before attempting login"
    )
    parser.add_argument(
        "--save-cookies",
        action="store_true",
        help="Save cookies after successful login (for future use)"
    )
    parser.add_argument(
        "--cookies-dir",
        default="data/cookies",
        help="Directory to store cookies (default: data/cookies)"
    )

    args = parser.parse_args()

    print("=" * 80)
    print("🚀 POC: Authenticated Content Extraction")
    print("=" * 80)

    extractor = AuthenticatedExtractor(
        headless=args.headless,
        cookies_dir=args.cookies_dir
    )

    try:
        # Determine domain from URL
        from urllib.parse import urlparse
        parsed_url = urlparse(args.url)
        domain = parsed_url.netloc
        if domain.startswith("www."):
            domain = domain[4:]

        login_successful = False
        used_cookies = False

        # Step 1: Try to use saved cookies if requested
        if args.use_cookies:
            print(f"\n🔑 Attempting to use saved cookies for {domain}...")

            # Initialize driver first
            extractor._init_driver()

            # Try to load cookies
            cookies_loaded = extractor.load_cookies(domain, args.url)

            if cookies_loaded:
                # Validate cookies work
                if extractor.validate_cookies(args.url):
                    print(f"✅ Cookies are valid! Skipping login.")
                    login_successful = True
                    used_cookies = True
                else:
                    print(f"⚠️  Cookies expired or invalid. Will attempt login...")

        # Step 2: Login if cookies didn't work
        if not login_successful:
            print(f"\n🔐 Proceeding with login...")
            success = extractor.login(args.url)

            if not success:
                print("\n❌ Login failed. Exiting.")
                print("\n💡 Tip: If you solved the CAPTCHA manually, run again with --save-cookies")
                print("   to save the session for future use.")
                return 1

            login_successful = True

            # Save cookies if requested
            if args.save_cookies:
                print(f"\n💾 Saving cookies for future use...")
                extractor.save_cookies(domain)

        # Step 3: Extract content
        content = extractor.extract_content(args.url)

        if not content:
            print("\n❌ Content extraction failed. Exiting.")
            return 1

        # Step 3: Save results
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, ensure_ascii=False)

            print(f"\n💾 Content saved to: {output_path}")
        else:
            # Print content preview
            print("\n" + "=" * 80)
            print("📄 EXTRACTED CONTENT PREVIEW")
            print("=" * 80)
            print(f"\nTitle: {content['title']}")
            print(f"Word count: {content['word_count']}")
            print(f"\nContent (first 500 chars):\n{content['content'][:500]}...")

        print("\n✅ POC completed successfully!")
        return 0

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        extractor.close()


if __name__ == "__main__":
    sys.exit(main())
