#!/usr/bin/env python3
"""
Migrate cookies from filesystem to PostgreSQL database.

Reads all cookies_*.json files and imports them into the source_cookies table.
"""
import sys
import json
import os
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.postgres_db import PostgreSQLURLDatabase


def get_domain_from_filename(file_path: Path) -> str:
    """Extract domain from cookie filename."""
    domain_abbrev = file_path.stem.replace("cookies_", "")

    # Common domain mappings
    domain_mapping = {
        "ft": "ft.com",
        "nyt": "nytimes.com",
        "wsj": "wsj.com",
        "bloomberg": "bloomberg.com",
        "economist": "economist.com"
    }

    return domain_mapping.get(domain_abbrev, f"{domain_abbrev}.com")


def main():
    """Migrate cookies from files to database."""
    # Get database connection
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return 1

    db = PostgreSQLURLDatabase(database_url)

    # Find all cookie files
    cookies_dir = Path("config")
    if not cookies_dir.exists():
        # Try content_POC directory
        cookies_dir = Path("content_POC")

    cookie_files = list(cookies_dir.glob("cookies*.json"))

    if not cookie_files:
        logger.warning(f"No cookie files found in {cookies_dir}")
        return 0

    logger.info(f"Found {len(cookie_files)} cookie file(s) to migrate")

    migrated = 0
    failed = 0

    for cookie_file in cookie_files:
        try:
            domain = get_domain_from_filename(cookie_file)
            logger.info(f"Migrating {cookie_file.name} → {domain}")

            # Load cookies
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)

            logger.info(f"  Loaded {len(cookies)} cookies")

            # Save to database (without source_id for now)
            result = db.save_cookies(
                domain=domain,
                cookies=cookies,
                source_id=None,  # Can be updated later via UI
                validation_info={'status': 'not_tested'},
                user_email='migration_script'
            )

            if result:
                logger.info(f"  ✓ Migrated successfully (DB ID: {result['id']})")
                migrated += 1
            else:
                logger.error(f"  ✗ Failed to save to database")
                failed += 1

        except Exception as e:
            logger.error(f"  ✗ Error migrating {cookie_file}: {e}")
            failed += 1

    logger.info(f"\nMigration complete:")
    logger.info(f"  Migrated: {migrated}")
    logger.info(f"  Failed: {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
