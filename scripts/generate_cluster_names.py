#!/usr/bin/env python3
"""
Script to generate names/hashtags for existing clusters.

Finds clusters with 2+ articles that don't have a name yet
and generates descriptive hashtags using the LLM.

Usage:
    python scripts/generate_cluster_names.py [--db-path path/to/news.db]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from common.postgres_db import PostgreSQLURLDatabase

# Add poc_clustering to path
poc_path = project_root / "poc_clustering" / "src"
sys.path.insert(0, str(poc_path))

from hashtag_generator import HashtagGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate names for existing clusters")
    parser.add_argument(
        "--db-path",
        dest="db_path",
        default=Path(__file__).parent.parent / "data" / "news.db",
        help="Path to news.db (default: data/news.db)",
    )
    parser.add_argument(
        "--min-articles",
        type=int,
        default=2,
        help="Minimum articles for a cluster to get a name (default: 2)",
    )
    parser.add_argument(
        "--max-titles",
        type=int,
        default=5,
        help="Maximum titles to send to LLM for context (default: 5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of clusters to process (default: all)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    db_path = Path(args.db_path)

    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return 1

    # Initialize database and hashtag generator
    db = PostgreSQLURLDatabase(str(db_path))
    generator = HashtagGenerator(
        model="gpt-4o-mini",
        temperature=0.3,
        max_tokens=50,
    )

    # Get clusters without names
    clusters = db.get_clusters_without_name(min_article_count=args.min_articles)

    if not clusters:
        logger.info("No clusters need naming")
        return 0

    logger.info(f"Found {len(clusters)} clusters needing names")

    # Apply limit if specified
    if args.limit and args.limit < len(clusters):
        clusters = clusters[:args.limit]
        logger.info(f"Limited to {len(clusters)} clusters")

    named_count = 0
    for cluster in clusters:
        cluster_id = cluster["id"]
        article_count = cluster["article_count"]

        # Get titles for this cluster
        titles = db.get_cluster_titles(cluster_id, limit=args.max_titles)

        if not titles:
            logger.warning(f"No titles found for cluster {cluster_id}")
            continue

        # Generate hashtag
        hashtag = generator.generate(titles, max_titles=args.max_titles)

        logger.info(f"\nCluster {cluster_id} ({article_count} articles):")
        for title in titles:
            logger.info(f"  - {title[:80]}...")
        logger.info(f"  → {hashtag}")

        if not args.dry_run:
            db.update_cluster_name(cluster_id, hashtag)
            named_count += 1

    if args.dry_run:
        logger.info(f"\nDry run complete. Would name {len(clusters)} clusters.")
    else:
        logger.info(f"\nNamed {named_count} clusters successfully")

    return 0


if __name__ == "__main__":
    sys.exit(main())
