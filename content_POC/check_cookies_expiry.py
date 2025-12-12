#!/usr/bin/env python3
"""
Cookie Expiry Checker
Analyzes cookies.json to determine when cookies expire.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def check_cookie_expiry(cookies_file: str = "cookies.json"):
    """
    Analyze cookies and report expiration dates.

    Args:
        cookies_file: Path to cookies JSON file
    """
    if not Path(cookies_file).exists():
        print(f"❌ Cookie file not found: {cookies_file}")
        return

    with open(cookies_file, 'r') as f:
        cookies = json.load(f)

    print("🔍 Cookie Expiry Analysis")
    print("=" * 70)

    now = datetime.now(timezone.utc)
    now_timestamp = now.timestamp()

    session_cookies = []
    expiring_cookies = []

    for cookie in cookies:
        name = cookie.get('name', 'Unknown')
        domain = cookie.get('domain', 'Unknown')

        # Check if it's a session cookie (no expiration)
        if cookie.get('session', False) or 'expirationDate' not in cookie:
            session_cookies.append({
                'name': name,
                'domain': domain,
                'type': 'Session cookie (expires when browser closes)'
            })
        else:
            # Has expiration date
            expiry_timestamp = cookie['expirationDate']
            expiry_date = datetime.fromtimestamp(expiry_timestamp, tz=timezone.utc)

            days_until_expiry = (expiry_timestamp - now_timestamp) / (60 * 60 * 24)

            expiring_cookies.append({
                'name': name,
                'domain': domain,
                'expiry_date': expiry_date,
                'days_until_expiry': days_until_expiry,
                'expired': days_until_expiry < 0
            })

    # Sort by days until expiry
    expiring_cookies.sort(key=lambda x: x['days_until_expiry'])

    print(f"\n📅 Current time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"\n📊 Summary:")
    print(f"   Total cookies: {len(cookies)}")
    print(f"   Session cookies: {len(session_cookies)}")
    print(f"   Cookies with expiration: {len(expiring_cookies)}")

    # Check for expired cookies
    expired = [c for c in expiring_cookies if c['expired']]
    if expired:
        print(f"\n⚠️  EXPIRED COOKIES: {len(expired)}")
        for cookie in expired:
            print(f"   - {cookie['name']}: expired {abs(cookie['days_until_expiry']):.1f} days ago")

    # Show session cookies
    if session_cookies:
        print(f"\n🔄 Session Cookies (expire when browser closes):")
        for cookie in session_cookies:
            print(f"   - {cookie['name']}")

    # Show expiring cookies timeline
    if expiring_cookies:
        print(f"\n⏰ Cookies with Expiration Dates:")
        print(f"{'Cookie Name':<30} {'Domain':<20} {'Days Until Expiry':<20} {'Expiry Date'}")
        print("-" * 100)

        for cookie in expiring_cookies:
            if not cookie['expired']:
                days_str = f"{cookie['days_until_expiry']:.1f} days"
                expiry_str = cookie['expiry_date'].strftime('%Y-%m-%d')
                print(f"{cookie['name']:<30} {cookie['domain']:<20} {days_str:<20} {expiry_str}")

    # Find the cookie that expires first
    valid_cookies = [c for c in expiring_cookies if not c['expired']]
    if valid_cookies:
        first_to_expire = valid_cookies[0]
        print(f"\n⚡ First cookie to expire:")
        print(f"   Name: {first_to_expire['name']}")
        print(f"   Days until expiry: {first_to_expire['days_until_expiry']:.1f}")
        print(f"   Date: {first_to_expire['expiry_date'].strftime('%Y-%m-%d %H:%M:%S UTC')}")

        # Recommendation
        print(f"\n💡 Recommendation:")
        if first_to_expire['days_until_expiry'] < 7:
            print("   ⚠️  URGENT: Renew cookies within the next week!")
        elif first_to_expire['days_until_expiry'] < 30:
            print(f"   ⚠️  Consider renewing cookies soon (within {int(first_to_expire['days_until_expiry'])} days)")
        elif first_to_expire['days_until_expiry'] < 90:
            print(f"   ✅ Cookies are valid for ~{int(first_to_expire['days_until_expiry'])} days")
        else:
            print(f"   ✅ Cookies are valid for ~{int(first_to_expire['days_until_expiry'])} days - you're good!")

        # Session cookies warning
        if session_cookies:
            print(f"\n⚠️  Note: You have {len(session_cookies)} session cookie(s).")
            print("   These expire when you close your browser, so:")
            print("   - If you logged out or restarted browser after exporting, they may be invalid")
            print("   - Re-export cookies if authentication fails")

    # Overall recommendation for daily usage
    print(f"\n📆 For daily usage:")
    if valid_cookies:
        min_days = first_to_expire['days_until_expiry']
        if min_days < 30:
            print("   🔄 Renew cookies: Every 1-2 weeks (or when authentication fails)")
        elif min_days < 90:
            print("   🔄 Renew cookies: Every month")
        else:
            print("   🔄 Renew cookies: Every 2-3 months (or when authentication fails)")

    print(f"\n💾 Tip: Set a calendar reminder to re-export cookies before they expire!")


if __name__ == '__main__':
    check_cookie_expiry()
