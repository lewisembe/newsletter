"""
Google News Searcher

Searches Google News by keyword topics and extracts:
- URL
- Title
- Published date (from Google News, not extraction date!)
- Source

Uses pygooglenews library (free, no API key required).
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone
import time
import re
import requests

try:
    from pygooglenews import GoogleNews
except ImportError:
    raise ImportError(
        "pygooglenews not installed. Run: pip install pygooglenews"
    )

logger = logging.getLogger(__name__)


class GoogleNewsSearcher:
    """
    Search Google News by keyword topics.

    Features:
    - Free (RSS-based, no API key)
    - Multi-language support
    - Date filtering (1d, 7d, 30d)
    - Extracts actual publication date from Google News
    """

    def __init__(self, language: str = "es", country: str = "ES", resolve_urls: bool = True):
        """
        Initialize Google News searcher.

        Args:
            language: Language code (es, en, fr)
            country: Country code (ES, US, FR)
            resolve_urls: If True (default), resolve Google News URLs to original article URLs.
                         Uses multiple strategies: HTTP with session, Selenium fallback.
                         If False, Google News URLs are kept as-is.
        """
        self.language = language
        self.country = country
        self.resolve_urls = resolve_urls
        self.gn = GoogleNews(lang=language, country=country)

        # Create persistent session for URL resolution
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

        logger.info(f"Initialized Google News searcher: lang={language}, country={country}, resolve_urls={resolve_urls}")

    def search(
        self,
        keyword: str,
        when: str = "1d",
        max_results: Optional[int] = None
    ) -> List[Dict]:
        """
        Search Google News for keyword.

        Args:
            keyword: Search term (e.g., "inflación España")
            when: Time range - "1h", "1d" (default), "7d", "30d"
            max_results: Maximum results to return (None = all)

        Returns:
            List of dicts with keys:
            - url: Article URL
            - title: Article title
            - published_at: Publication datetime (from Google News)
            - source: Source name (e.g., "El País")
            - search_keyword: The keyword used to find it
        """
        try:
            logger.info(f"Searching Google News: keyword='{keyword}', when={when}")

            # Search Google News
            search_result = self.gn.search(keyword, when=when)

            if not search_result or 'entries' not in search_result:
                logger.warning(f"No results found for keyword: {keyword}")
                return []

            entries = search_result['entries']
            logger.info(f"Found {len(entries)} results for '{keyword}'")

            # Parse entries
            results = []
            for entry in entries:
                try:
                    article = self._parse_entry(entry, keyword)
                    if article:
                        results.append(article)

                        # Respect max_results
                        if max_results and len(results) >= max_results:
                            break

                except Exception as e:
                    logger.warning(f"Failed to parse entry: {e}")
                    continue

            logger.info(f"Successfully parsed {len(results)} articles")
            return results

        except Exception as e:
            logger.error(f"Search failed for '{keyword}': {e}")
            return []

    def _parse_entry(self, entry: Dict, keyword: str) -> Optional[Dict]:
        """
        Parse Google News RSS entry into article dict.

        Args:
            entry: feedparser entry object
            keyword: Search keyword (for tracking)

        Returns:
            Article dict or None if parsing fails
        """
        try:
            # Extract URL (Google News redirect URL)
            google_news_url = entry.get('link')
            if not google_news_url:
                logger.warning("Entry missing URL")
                return None

            # Resolve to original URL (only if enabled)
            if self.resolve_urls:
                original_url = self._resolve_original_url(google_news_url)
            else:
                # Keep Google News URL (they still work!)
                original_url = google_news_url

            # Extract title
            raw_title = entry.get('title', '').strip()
            if not raw_title:
                logger.warning(f"Entry missing title: {google_news_url}")
                return None

            # Clean title (remove " - Source" suffix)
            title = self._clean_title(raw_title)

            # Extract published date (CRITICAL: This is the article's real date!)
            published_at = self._parse_published_date(entry)
            if not published_at:
                logger.warning(f"Could not parse date for: {google_news_url}")
                return None

            # Extract source
            source = self._extract_source(entry)

            return {
                'url': original_url,
                'google_news_url': google_news_url,
                'title': title,
                'published_at': published_at,
                'source': source or 'unknown',
                'search_keyword': keyword
            }

        except Exception as e:
            logger.warning(f"Failed to parse entry: {e}")
            return None

    def _resolve_original_url(self, google_news_url: str) -> str:
        """
        Resolve Google News redirect URL to original article URL.

        Google News URLs are redirects like:
        https://news.google.com/rss/articles/...

        This method tries multiple strategies:
        1. Direct HTTP GET with session (follows all redirects)
        2. Manual redirect following with cookies
        3. Return Google News URL if all else fails

        Args:
            google_news_url: Google News redirect URL

        Returns:
            Original article URL, or google_news_url if resolution fails
        """
        # Try direct resolution with session (most common case)
        resolved_url = self._resolve_with_session(google_news_url)
        if resolved_url and self._is_valid_article_url(resolved_url):
            return resolved_url

        # Fallback: Try manual redirect following
        resolved_url = self._resolve_manual_redirect(google_news_url)
        if resolved_url and self._is_valid_article_url(resolved_url):
            return resolved_url

        # Last resort: return original Google News URL
        logger.debug(f"Could not resolve URL, keeping Google News URL: {google_news_url[:80]}...")
        return google_news_url

    def _is_valid_article_url(self, url: str) -> bool:
        """
        Check if URL is a valid article URL (not Google redirect).

        Args:
            url: URL to check

        Returns:
            True if valid article URL, False otherwise
        """
        if not url:
            return False

        url_lower = url.lower()

        # Reject Google URLs
        if any(domain in url_lower for domain in ['news.google.com', 'consent.google.com', 'accounts.google.com']):
            return False

        # Must be HTTP/HTTPS
        if not url.startswith('http'):
            return False

        return True

    def _resolve_with_session(self, google_news_url: str) -> Optional[str]:
        """
        Resolve URL using googlenewsdecoder library.

        This uses a specialized library that decodes Google News URLs.

        Args:
            google_news_url: Google News redirect URL

        Returns:
            Decoded URL or None if resolution fails
        """
        try:
            from googlenewsdecoder import new_decoderv1

            result = new_decoderv1(google_news_url, interval=0.5)

            if result and result.get("status"):
                decoded_url = result.get("decoded_url")
                if decoded_url:
                    logger.debug(f"Decoded URL: {google_news_url[:50]}... -> {decoded_url[:50]}...")
                    return decoded_url
                else:
                    logger.debug(f"Decoder succeeded but no URL returned")
                    return None
            else:
                error_msg = result.get("message", "Unknown error") if result else "No result"
                logger.debug(f"Decoder failed: {error_msg}")
                return None

        except ImportError:
            logger.debug("googlenewsdecoder not available")
            return None
        except Exception as e:
            logger.debug(f"googlenewsdecoder failed: {e}")
            return None

    def _resolve_manual_redirect(self, google_news_url: str) -> Optional[str]:
        """
        Resolve URL using Base64 decoding (fallback method).

        This decodes the Google News article ID to extract the original URL.

        Args:
            google_news_url: Google News redirect URL

        Returns:
            Decoded URL or None if resolution fails
        """
        try:
            import base64
            import re
            from urllib.parse import urlparse

            # Pattern for Google News article URLs
            match = re.search(r'/articles/([^?]+)', google_news_url)
            if not match:
                logger.debug("URL doesn't match Google News article pattern")
                return None

            encoded_str = match.group(1)

            # Add padding if needed
            padding = (4 - len(encoded_str) % 4) % 4
            encoded_str += '=' * padding

            try:
                # Decode base64
                decoded_bytes = base64.urlsafe_b64decode(encoded_str)
                decoded_str = decoded_bytes.decode('latin1')

                # Remove prefix bytes (0x08, 0x13, 0x22)
                prefix = bytes([0x08, 0x13, 0x22]).decode('latin1')
                if decoded_str.startswith(prefix):
                    decoded_str = decoded_str[len(prefix):]

                # Remove suffix bytes (0xd2, 0x01, 0x00)
                suffix = bytes([0xd2, 0x01, 0x00]).decode('latin1')
                if suffix in decoded_str:
                    decoded_str = decoded_str[:decoded_str.index(suffix)]

                # Extract URL length and content
                if decoded_str:
                    bytes_array = bytearray(decoded_str, 'latin1')
                    length = bytes_array[0]

                    if length >= 0x80:
                        # Multi-byte length
                        url_start = 2
                        actual_length = length
                    else:
                        # Single-byte length
                        url_start = 1
                        actual_length = length

                    # Extract the URL
                    article_url = decoded_str[url_start:url_start + actual_length]

                    if article_url.startswith('http'):
                        logger.debug(f"Base64 decoded: {google_news_url[:50]}... -> {article_url[:50]}...")
                        return article_url

            except Exception as e:
                logger.debug(f"Base64 decoding failed: {e}")
                return None

            return None

        except Exception as e:
            logger.debug(f"Manual redirect resolution failed: {e}")
            return None


    def _clean_title(self, raw_title: str) -> str:
        """
        Clean title by removing " - SourceName" suffix.

        Google News titles often have format:
        "Article Title - El País"
        "Breaking news about economy - The New York Times"

        This method removes the last " - Source" part.

        Args:
            raw_title: Raw title from Google News

        Returns:
            Cleaned title without source suffix
        """
        try:
            # Regex to match everything before the last " - Source"
            # Pattern: capture group 1 is everything before " - " at the end
            match = re.match(r'^(.*?)\s*-\s*[^-]+$', raw_title)

            if match:
                cleaned = match.group(1).strip()
                if cleaned:  # Ensure we didn't get an empty string
                    logger.debug(f"Cleaned title: '{raw_title}' -> '{cleaned}'")
                    return cleaned

            # If no match or empty result, return original
            logger.debug(f"No title cleaning applied: '{raw_title}'")
            return raw_title

        except Exception as e:
            logger.warning(f"Error cleaning title '{raw_title}': {e}")
            return raw_title

    def _parse_published_date(self, entry: Dict) -> Optional[datetime]:
        """
        Extract published date from entry.

        Google News provides:
        - published_parsed: time.struct_time
        - published: string representation

        Returns:
            datetime object (UTC) or None
        """
        try:
            # Try published_parsed first (most reliable)
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                time_tuple = entry.published_parsed
                dt = datetime(
                    time_tuple.tm_year,
                    time_tuple.tm_mon,
                    time_tuple.tm_mday,
                    time_tuple.tm_hour,
                    time_tuple.tm_min,
                    time_tuple.tm_sec,
                    tzinfo=timezone.utc
                )
                return dt

            # Fallback: Try parsing string (less reliable)
            if hasattr(entry, 'published'):
                from dateutil import parser
                dt = parser.parse(entry.published)

                # Ensure timezone aware
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)

                return dt

            logger.warning("No published date found in entry")
            return None

        except Exception as e:
            logger.warning(f"Failed to parse published date: {e}")
            return None

    def _extract_source(self, entry: Dict) -> Optional[str]:
        """
        Extract source name from entry.

        Google News provides source in:
        - source.title (most reliable)
        - sub_articles[0].source.title (for grouped articles)
        """
        try:
            # Try main source
            if hasattr(entry, 'source') and hasattr(entry.source, 'title'):
                return entry.source.title

            # Try sub-articles
            if hasattr(entry, 'sub_articles') and entry.sub_articles:
                first = entry.sub_articles[0]
                if hasattr(first, 'source') and hasattr(first.source, 'title'):
                    return first.source.title

            return None

        except Exception as e:
            logger.warning(f"Failed to extract source: {e}")
            return None

    def search_multiple_keywords(
        self,
        keywords: List[Dict],
        rate_limit_delay: float = 1.0
    ) -> Dict[str, List[Dict]]:
        """
        Search multiple keywords with rate limiting.

        Args:
            keywords: List of dicts with 'topic', 'when', 'max_results'
            rate_limit_delay: Seconds to wait between requests

        Returns:
            Dict mapping keyword -> list of articles
        """
        results = {}

        for i, kw_config in enumerate(keywords):
            keyword = kw_config['topic']
            when = kw_config.get('when', '1d')
            max_results = kw_config.get('max_results')

            logger.info(f"Searching keyword {i+1}/{len(keywords)}: '{keyword}'")

            articles = self.search(keyword, when=when, max_results=max_results)
            results[keyword] = articles

            # Rate limiting (be nice to Google)
            if i < len(keywords) - 1:
                time.sleep(rate_limit_delay)

        total = sum(len(v) for v in results.values())
        logger.info(f"Total articles found: {total} across {len(keywords)} keywords")

        return results


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test Spanish news search
    searcher = GoogleNewsSearcher(language="es", country="ES")

    test_keywords = [
        "inflación España",
        "BCE tipos de interés",
        "guerra Ucrania"
    ]

    for keyword in test_keywords:
        print(f"\n{'='*60}")
        print(f"Searching: {keyword}")
        print('='*60)

        articles = searcher.search(keyword, when="1d", max_results=5)

        for i, article in enumerate(articles, 1):
            print(f"\n{i}. {article['title']}")
            print(f"   URL: {article['url']}")
            print(f"   Published: {article['published_at']}")
            print(f"   Source: {article['source']}")
