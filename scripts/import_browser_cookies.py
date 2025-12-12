#!/usr/bin/env python3
"""
Import cookies from browser export to Selenium-compatible format

Usage:
    python scripts/import_browser_cookies.py \
      --input cookies_export.json \
      --domain ft.com \
      --output data/cookies/ft_com_cookies.pkl
"""

import argparse
import json
import pickle
from pathlib import Path
from datetime import datetime


def convert_browser_cookies_to_selenium(browser_cookies):
    """
    Convert browser cookie format to Selenium format

    Browser format (EditThisCookie/Cookie-Editor):
    {
        "name": "cookie_name",
        "value": "cookie_value",
        "domain": ".ft.com",
        "path": "/",
        "expires": 1234567890,  # Unix timestamp
        "httpOnly": true,
        "secure": true
    }

    Selenium format:
    {
        "name": "cookie_name",
        "value": "cookie_value",
        "domain": ".ft.com",
        "path": "/",
        "expiry": 1234567890,  # Note: "expiry" not "expires"
        "httpOnly": True,
        "secure": True
    }
    """
    selenium_cookies = []

    for cookie in browser_cookies:
        selenium_cookie = {
            "name": cookie.get("name"),
            "value": cookie.get("value"),
            "domain": cookie.get("domain"),
            "path": cookie.get("path", "/"),
        }

        # Convert expires to expiry
        if "expires" in cookie and cookie["expires"]:
            selenium_cookie["expiry"] = int(cookie["expires"])
        elif "expirationDate" in cookie and cookie["expirationDate"]:
            selenium_cookie["expiry"] = int(cookie["expirationDate"])

        # Add security flags
        if "httpOnly" in cookie:
            selenium_cookie["httpOnly"] = cookie["httpOnly"]
        if "secure" in cookie:
            selenium_cookie["secure"] = cookie["secure"]
        if "sameSite" in cookie:
            selenium_cookie["sameSite"] = cookie["sameSite"]

        selenium_cookies.append(selenium_cookie)

    return selenium_cookies


def main():
    parser = argparse.ArgumentParser(description="Import browser cookies for Selenium")
    parser.add_argument("--input", required=True, help="JSON file with exported cookies")
    parser.add_argument("--domain", required=True, help="Domain name (e.g., ft.com)")
    parser.add_argument("--output", help="Output pickle file (optional)")
    args = parser.parse_args()

    # Read browser cookies
    with open(args.input, 'r') as f:
        browser_cookies = json.load(f)

    print(f"📖 Read {len(browser_cookies)} cookies from {args.input}")

    # Convert to Selenium format
    selenium_cookies = convert_browser_cookies_to_selenium(browser_cookies)

    # Create cookie data structure
    cookie_data = {
        "cookies": selenium_cookies,
        "saved_at": datetime.now().isoformat(),
        "domain": args.domain,
        "source": "browser_import"
    }

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        cookies_dir = Path("data/cookies")
        cookies_dir.mkdir(parents=True, exist_ok=True)
        safe_domain = args.domain.replace(".", "_")
        output_path = cookies_dir / f"{safe_domain}_cookies.pkl"

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'wb') as f:
        pickle.dump(cookie_data, f)

    print(f"💾 Cookies saved to: {output_path}")
    print(f"✅ You can now use --use-cookies with your script!")
    print(f"\nExample:")
    print(f"  venv/bin/python scripts/poc_authenticated_extraction.py \\")
    print(f"    --url 'https://{args.domain}/...' \\")
    print(f"    --use-cookies \\")
    print(f"    --headless")


if __name__ == "__main__":
    main()
