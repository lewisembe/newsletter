"""
Deduplicator Module
Identifies and filters out duplicate articles without using AI
"""
import hashlib
import logging
from typing import List, Dict, Set
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from fuzzywuzzy import fuzz

from config import settings

logger = logging.getLogger(__name__)


class Deduplicator:
    """Handles article deduplication"""

    def __init__(self, existing_urls: Set[str] = None, existing_hashes: Set[str] = None):
        """
        Initialize deduplicator

        Args:
            existing_urls: Set of URLs that have already been processed
            existing_hashes: Set of content hashes that have already been processed
        """
        self.existing_urls = existing_urls or set()
        self.existing_hashes = existing_hashes or set()
        self.processed_titles = []  # For fuzzy matching

    def is_duplicate(self, article: Dict) -> bool:
        """
        Check if an article is a duplicate

        Args:
            article: Article dictionary with 'url', 'title', and optionally 'content'

        Returns:
            True if duplicate, False otherwise
        """
        url = article.get('url', '')
        title = article.get('title', '')
        content = article.get('content_truncated', '') or article.get('content', '')

        # Check 1: Exact URL match (after normalization)
        normalized_url = self._normalize_url(url)
        if normalized_url in self.existing_urls:
            logger.debug(f"Duplicate URL found: {url}")
            return True

        # Check 2: Content hash match
        if content:
            content_hash = self._hash_content(content)
            if content_hash in self.existing_hashes:
                logger.debug(f"Duplicate content found for: {title[:50]}")
                return True

        # Check 3: Fuzzy title matching (for very similar titles)
        if title and self._is_similar_title(title):
            logger.debug(f"Similar title found: {title[:50]}")
            return True

        return False

    def mark_as_processed(self, article: Dict):
        """
        Mark an article as processed to avoid future duplicates

        Args:
            article: Article dictionary
        """
        url = article.get('url', '')
        content = article.get('content_truncated', '') or article.get('content', '')
        title = article.get('title', '')

        if url:
            normalized_url = self._normalize_url(url)
            self.existing_urls.add(normalized_url)

        if content:
            content_hash = self._hash_content(content)
            self.existing_hashes.add(content_hash)

        if title:
            self.processed_titles.append(title)

    def filter_duplicates(self, articles: List[Dict]) -> List[Dict]:
        """
        Filter out duplicate articles from a list

        Args:
            articles: List of article dictionaries

        Returns:
            List of unique articles
        """
        unique_articles = []

        for article in articles:
            if not self.is_duplicate(article):
                unique_articles.append(article)
                self.mark_as_processed(article)
            else:
                logger.info(f"Filtered duplicate: {article.get('title', 'Unknown')[:50]}")

        logger.info(f"Filtered {len(articles) - len(unique_articles)} duplicates, {len(unique_articles)} unique articles remain")

        return unique_articles

    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL to detect duplicates with different tracking parameters

        Args:
            url: Original URL

        Returns:
            Normalized URL
        """
        if not url:
            return ''

        try:
            # Parse URL
            parsed = urlparse(url)

            # Remove common tracking parameters
            tracking_params = {
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                'fbclid', 'gclid', 'ref', 'source', '_ga', 'mc_cid', 'mc_eid'
            }

            query_params = parse_qs(parsed.query)
            filtered_params = {
                k: v for k, v in query_params.items()
                if k.lower() not in tracking_params
            }

            # Rebuild query string
            new_query = urlencode(filtered_params, doseq=True)

            # Rebuild URL without fragment and with cleaned query
            normalized = urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip('/'),  # Remove trailing slash
                parsed.params,
                new_query,
                ''  # Remove fragment
            ))

            return normalized

        except Exception as e:
            logger.warning(f"Failed to normalize URL {url}: {e}")
            return url.lower()

    def _hash_content(self, content: str) -> str:
        """
        Create a hash of content for duplicate detection

        Args:
            content: Article content

        Returns:
            SHA256 hash of content
        """
        if not content:
            return ''

        # Normalize content before hashing
        normalized = content.lower().strip()
        normalized = ' '.join(normalized.split())  # Normalize whitespace

        # Create hash
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    def _is_similar_title(self, title: str, similarity_threshold: int = 90) -> bool:
        """
        Check if title is very similar to any processed title

        Args:
            title: Title to check
            similarity_threshold: Minimum similarity score (0-100)

        Returns:
            True if similar title found
        """
        if not title or not self.processed_titles:
            return False

        # Check against recent titles (last 100)
        recent_titles = self.processed_titles[-100:]

        for existing_title in recent_titles:
            # Use token set ratio for better matching of reordered words
            similarity = fuzz.token_set_ratio(title.lower(), existing_title.lower())

            if similarity >= similarity_threshold:
                logger.debug(f"Similar titles (score {similarity}): '{title[:40]}' vs '{existing_title[:40]}'")
                return True

        return False

    def get_content_hash(self, content: str) -> str:
        """
        Public method to get content hash

        Args:
            content: Article content

        Returns:
            Content hash
        """
        return self._hash_content(content)


def create_deduplicator(google_sheets_client=None) -> Deduplicator:
    """
    Create a deduplicator with existing URLs from Google Sheets

    Args:
        google_sheets_client: GoogleSheetsClient instance

    Returns:
        Deduplicator instance
    """
    existing_urls = set()
    existing_hashes = set()

    if google_sheets_client:
        try:
            # Get all processed articles
            processed_articles = google_sheets_client.get_all_processed_news()

            for article in processed_articles:
                url = article.get('url_original', '')
                content_hash = article.get('hash_contenido', '')

                if url:
                    dedup = Deduplicator()  # Temporary instance for normalization
                    normalized_url = dedup._normalize_url(url)
                    existing_urls.add(normalized_url)

                if content_hash:
                    existing_hashes.add(content_hash)

            logger.info(f"Loaded {len(existing_urls)} existing URLs and {len(existing_hashes)} hashes for deduplication")

        except Exception as e:
            logger.error(f"Error loading existing articles for deduplication: {e}")

    return Deduplicator(existing_urls, existing_hashes)


if __name__ == '__main__':
    # Test deduplicator
    dedup = Deduplicator()

    test_articles = [
        {'url': 'https://example.com/article1', 'title': 'Test Article', 'content': 'This is test content'},
        {'url': 'https://example.com/article1?utm_source=twitter', 'title': 'Test Article', 'content': 'Different content'},
        {'url': 'https://example.com/article2', 'title': 'Another Test Article', 'content': 'More test content'},
        {'url': 'https://example.com/article3', 'title': 'Test Article About Something', 'content': 'Even more content'},
    ]

    print("Testing deduplicator...")
    unique = dedup.filter_duplicates(test_articles)
    print(f"Unique articles: {len(unique)}")

    for article in unique:
        print(f"  - {article['title']}")
