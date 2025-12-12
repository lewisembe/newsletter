#!/usr/bin/env python3
"""
Cookie Import Tool for Stage 04 Authenticated Scraping

Imports cookies from JSON files (exported from browser extensions like Cookie Editor)
into the SQLite database for use by authenticated_scraper.

Usage:
    # Import cookies for a domain
    python scripts/import_cookies.py --domain ft.com --file cookies.json

    # List all domains with cookies
    python scripts/import_cookies.py --list

    # List cookies for specific domain
    python scripts/import_cookies.py --list --domain ft.com

    # Delete cookies for a domain
    python scripts/import_cookies.py --delete --domain ft.com

    # Export cookies from DB to JSON file
    python scripts/import_cookies.py --export --domain ft.com --output cookies_ft_backup.json

Author: Newsletter Utils Team
Created: 2025-11-14
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.postgres_db import PostgreSQLURLDatabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def import_cookies_from_file(db: SQLiteURLDatabase, domain: str, file_path: str) -> int:
    """
    Import cookies from JSON file into database.

    Args:
        db: Database instance
        domain: Domain to associate cookies with
        file_path: Path to JSON file with cookies

    Returns:
        Number of cookies imported
    """
    try:
        with open(file_path, 'r') as f:
            cookies = json.load(f)

        if not isinstance(cookies, list):
            logger.error("Cookie file must contain a JSON array of cookies")
            return 0

        logger.info(f"Found {len(cookies)} cookies in {file_path}")

        # Save to database
        count = db.save_cookies(domain, cookies)

        logger.info(f"✅ Successfully imported {count} cookies for {domain}")
        return count

    except FileNotFoundError:
        logger.error(f"❌ File not found: {file_path}")
        return 0
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in {file_path}: {e}")
        return 0
    except Exception as e:
        logger.error(f"❌ Error importing cookies: {e}")
        return 0


def list_cookie_domains(db: SQLiteURLDatabase):
    """List all domains that have cookies stored."""
    domains = db.get_all_cookie_domains()

    if not domains:
        print("No cookies found in database")
        return

    print(f"\n📦 Domains with cookies stored: {len(domains)}")
    print("=" * 60)

    for domain in domains:
        cookies = db.get_cookies_for_domain(domain)
        expiry_check = db.check_cookie_expiry(domain, threshold_days=7)

        status = "✅ Valid"
        if expiry_check['expired']:
            status = f"❌ {len(expiry_check['expired'])} expired"
        elif expiry_check['expiring_soon']:
            status = f"⚠️  {len(expiry_check['expiring_soon'])} expiring soon"

        print(f"  {domain:<30} | {len(cookies)} cookies | {status}")


def list_cookies_for_domain(db: SQLiteURLDatabase, domain: str):
    """List all cookies for a specific domain."""
    cookies = db.get_cookies_for_domain(domain)

    if not cookies:
        print(f"No cookies found for domain: {domain}")
        return

    expiry_check = db.check_cookie_expiry(domain, threshold_days=7)

    print(f"\n🍪 Cookies for {domain}: {len(cookies)}")
    print("=" * 80)

    import time
    now = int(time.time())

    for cookie in cookies:
        name = cookie['cookie_name']
        expiry = cookie['expiry']

        if expiry:
            days_until = (expiry - now) / (60 * 60 * 24)
            if days_until < 0:
                expiry_str = f"❌ EXPIRED {abs(int(days_until))} days ago"
            elif days_until < 7:
                expiry_str = f"⚠️  Expires in {int(days_until)} days"
            else:
                expiry_str = f"✅ Expires in {int(days_until)} days"
        else:
            expiry_str = "🔄 Session cookie"

        secure = "🔒" if cookie['secure'] else "🔓"
        http_only = "HTTP" if cookie['http_only'] else "JS"

        print(f"  {name:<35} | {expiry_str:<30} | {secure} {http_only}")

    # Summary
    if expiry_check['expired']:
        print(f"\n❌ {len(expiry_check['expired'])} expired cookies")
    if expiry_check['expiring_soon']:
        print(f"⚠️  {len(expiry_check['expiring_soon'])} cookies expiring within 7 days")
    if expiry_check['needs_renewal']:
        print(f"\n💡 Recommendation: Re-export cookies from browser to renew")


def delete_cookies_for_domain(db: SQLiteURLDatabase, domain: str):
    """Delete all cookies for a domain."""
    count = db.delete_cookies_for_domain(domain)

    if count > 0:
        print(f"✅ Deleted {count} cookies for {domain}")
    else:
        print(f"No cookies found for {domain}")


def export_cookies_for_domain(db: SQLiteURLDatabase, domain: str, output_file: str):
    """Export cookies from DB to JSON file."""
    cookies = db.get_cookies_for_domain(domain)

    if not cookies:
        print(f"No cookies found for {domain}")
        return

    # Convert to browser extension format
    exported = []
    for cookie in cookies:
        exported.append({
            'domain': cookie['domain'],
            'name': cookie['cookie_name'],
            'value': cookie['cookie_value'],
            'path': cookie['path'],
            'secure': bool(cookie['secure']),
            'httpOnly': bool(cookie['http_only']),
            'sameSite': cookie['same_site'],
            'expirationDate': cookie['expiry'] if cookie['expiry'] else None,
            'session': cookie['expiry'] is None
        })

    # Save to file
    with open(output_file, 'w') as f:
        json.dump(exported, f, indent=2)

    print(f"✅ Exported {len(exported)} cookies for {domain} to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Import, list, or delete cookies for authenticated scraping',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import cookies from browser export
  python scripts/import_cookies.py --domain ft.com --file content_POC/cookies.json

  # List all domains with cookies
  python scripts/import_cookies.py --list

  # List cookies for specific domain
  python scripts/import_cookies.py --list --domain ft.com

  # Delete cookies for a domain
  python scripts/import_cookies.py --delete --domain ft.com

  # Export cookies to file (backup)
  python scripts/import_cookies.py --export --domain ft.com --output backup.json
        """
    )

    parser.add_argument('--domain', type=str, help='Domain name (e.g., ft.com)')
    parser.add_argument('--file', type=str, help='JSON file with cookies to import')
    parser.add_argument('--list', action='store_true', help='List cookies')
    parser.add_argument('--delete', action='store_true', help='Delete cookies for domain')
    parser.add_argument('--export', action='store_true', help='Export cookies to file')
    parser.add_argument('--output', type=str, help='Output file for export')
    parser.add_argument('--db', type=str, default='data/news.db', help='Database path')

    args = parser.parse_args()

    # Initialize database
    db = PostgreSQLURLDatabase(args.db)

    # Ensure site_cookies table exists
    db.init_db()

    # Handle operations
    if args.list:
        if args.domain:
            list_cookies_for_domain(db, args.domain)
        else:
            list_cookie_domains(db)

    elif args.delete:
        if not args.domain:
            parser.error("--delete requires --domain")
        delete_cookies_for_domain(db, args.domain)

    elif args.export:
        if not args.domain or not args.output:
            parser.error("--export requires --domain and --output")
        export_cookies_for_domain(db, args.domain, args.output)

    elif args.file and args.domain:
        import_cookies_from_file(db, args.domain, args.file)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
