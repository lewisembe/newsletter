"""
News Fetcher Module
Handles fetching news from RSS feeds and web crawling
"""
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
import time

from config import settings

logger = logging.getLogger(__name__)


class NewsFetcher:
    """Fetches news from various sources"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def fetch_from_source(self, source: Dict[str, str]) -> List[Dict[str, any]]:
        """
        Fetch articles from a source based on its type

        Args:
            source: Dictionary with 'nombre', 'url', 'tipo' keys

        Returns:
            List of article dictionaries
        """
        tipo = source.get('tipo', '').lower()
        url = source.get('url', '')
        nombre = source.get('nombre', 'Unknown')

        if not url:
            logger.warning(f"Source {nombre} has no URL")
            return []

        try:
            if tipo == 'rss':
                return self.fetch_from_rss(url, nombre)
            elif tipo in ['crawl', 'web', 'crawler']:
                return self.fetch_from_web(url, nombre)
            else:
                logger.warning(f"Unknown source type: {tipo} for {nombre}")
                return []
        except Exception as e:
            logger.error(f"Error fetching from {nombre}: {e}")
            return []

    def fetch_from_rss(self, rss_url: str, source_name: str) -> List[Dict[str, any]]:
        """
        Fetch articles from an RSS feed

        Args:
            rss_url: URL of the RSS feed
            source_name: Name of the news source

        Returns:
            List of article dictionaries
        """
        articles = []

        try:
            logger.info(f"Fetching RSS feed from {source_name}: {rss_url}")
            feed = feedparser.parse(rss_url)

            if feed.bozo:
                logger.warning(f"RSS feed has errors: {feed.bozo_exception}")

            for entry in feed.entries:
                article = {
                    'title': entry.get('title', 'No Title'),
                    'url': entry.get('link', ''),
                    'source': source_name,
                    'published_date': self._parse_rss_date(entry),
                    'summary': entry.get('summary', ''),
                    'content': self._extract_rss_content(entry),
                }

                if article['url']:
                    articles.append(article)

            logger.info(f"Fetched {len(articles)} articles from RSS: {source_name}")

        except Exception as e:
            logger.error(f"Error parsing RSS feed {rss_url}: {e}")

        return articles

    def _parse_rss_date(self, entry) -> str:
        """Parse date from RSS entry"""
        # Try different date fields
        for date_field in ['published_parsed', 'updated_parsed', 'created_parsed']:
            if hasattr(entry, date_field):
                time_struct = getattr(entry, date_field)
                if time_struct:
                    try:
                        dt = datetime(*time_struct[:6])
                        return dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass

        # Try string date fields
        for date_field in ['published', 'updated', 'created']:
            if hasattr(entry, date_field):
                date_str = getattr(entry, date_field)
                if date_str:
                    return date_str[:19]  # Simple truncation

        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def _extract_rss_content(self, entry) -> str:
        """Extract content from RSS entry"""
        # Try to get full content
        if hasattr(entry, 'content'):
            return ' '.join([c.value for c in entry.content])

        # Fallback to summary
        if hasattr(entry, 'summary'):
            return entry.summary

        # Fallback to description
        if hasattr(entry, 'description'):
            return entry.description

        return ''

    def fetch_from_web(self, base_url: str, source_name: str, max_articles: int = 20) -> List[Dict[str, any]]:
        """
        Crawl a website to find article links

        Args:
            base_url: Base URL of the website
            source_name: Name of the news source
            max_articles: Maximum number of articles to fetch

        Returns:
            List of article dictionaries
        """
        articles = []

        try:
            logger.info(f"Crawling website: {source_name} - {base_url}")

            # Fetch the main page
            response = self.session.get(base_url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find article links
            article_links = self._find_article_links(soup, base_url)

            logger.info(f"Found {len(article_links)} potential article links")

            # Fetch each article (up to max_articles)
            for i, link in enumerate(article_links[:max_articles]):
                try:
                    article = self._fetch_article_from_url(link, source_name)
                    if article:
                        articles.append(article)

                    # Be polite - don't hammer the server
                    time.sleep(1)

                except Exception as e:
                    logger.warning(f"Error fetching article {link}: {e}")
                    continue

            logger.info(f"Successfully crawled {len(articles)} articles from {source_name}")

        except Exception as e:
            logger.error(f"Error crawling website {base_url}: {e}")

        return articles

    def _find_article_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        Find article links on a page using common patterns

        Args:
            soup: BeautifulSoup object
            base_url: Base URL for resolving relative links

        Returns:
            List of article URLs
        """
        links = set()
        domain = urlparse(base_url).netloc

        # Common article link patterns
        article_selectors = [
            'article a[href]',
            'a[class*="article"]',
            'a[class*="story"]',
            'a[class*="headline"]',
            '.post a[href]',
            '.news-item a[href]',
            'h2 a[href]',
            'h3 a[href]',
        ]

        for selector in article_selectors:
            elements = soup.select(selector)
            for element in elements:
                href = element.get('href', '')
                if href:
                    # Resolve relative URLs
                    full_url = urljoin(base_url, href)

                    # Only include URLs from the same domain
                    if urlparse(full_url).netloc == domain:
                        # Filter out common non-article pages
                        if not any(x in full_url.lower() for x in [
                            '/tag/', '/category/', '/author/', '/about',
                            '/contact', '/privacy', '/terms', '#'
                        ]):
                            links.add(full_url)

        return list(links)

    def _fetch_article_from_url(self, url: str, source_name: str) -> Optional[Dict[str, any]]:
        """
        Fetch a single article from a URL

        Args:
            url: Article URL
            source_name: Name of the news source

        Returns:
            Article dictionary or None
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract title
            title = self._extract_title(soup)

            # Extract date
            published_date = self._extract_date_from_html(soup)

            # Extract content preview (full extraction will be done by content_processor)
            content_preview = self._extract_content_preview(soup)

            if title and content_preview:
                return {
                    'title': title,
                    'url': url,
                    'source': source_name,
                    'published_date': published_date,
                    'summary': content_preview[:200],
                    'content': '',  # Will be filled by content_processor
                }

        except Exception as e:
            logger.debug(f"Could not fetch article from {url}: {e}")

        return None

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract article title from HTML"""
        # Try different title selectors
        selectors = [
            'h1',
            'article h1',
            '[class*="headline"]',
            '[class*="title"]',
            'meta[property="og:title"]',
        ]

        for selector in selectors:
            if selector.startswith('meta'):
                element = soup.select_one(selector)
                if element:
                    return element.get('content', '')
            else:
                element = soup.select_one(selector)
                if element:
                    return element.get_text(strip=True)

        # Fallback to page title
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True)

        return 'No Title'

    def _extract_date_from_html(self, soup: BeautifulSoup) -> str:
        """Extract publication date from HTML without using AI"""
        # Try meta tags first
        meta_selectors = [
            'meta[property="article:published_time"]',
            'meta[name="publish-date"]',
            'meta[name="date"]',
            'meta[property="og:published_time"]',
        ]

        for selector in meta_selectors:
            element = soup.select_one(selector)
            if element:
                date_str = element.get('content', '')
                if date_str:
                    return date_str[:19]  # Truncate to datetime format

        # Try time tags
        time_tag = soup.find('time')
        if time_tag:
            datetime_attr = time_tag.get('datetime', '')
            if datetime_attr:
                return datetime_attr[:19]

        # Try common date class names
        date_selectors = [
            '[class*="publish"]',
            '[class*="date"]',
            '[class*="time"]',
        ]

        for selector in date_selectors:
            element = soup.select_one(selector)
            if element:
                date_text = element.get_text(strip=True)
                if date_text and len(date_text) < 50:  # Reasonable date length
                    return date_text

        # Default to current time
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def _extract_content_preview(self, soup: BeautifulSoup) -> str:
        """Extract a preview of the article content"""
        # Try to find main content
        content_selectors = [
            'article',
            '[class*="content"]',
            '[class*="article-body"]',
            'main',
        ]

        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                # Get text from paragraphs
                paragraphs = element.find_all('p')
                if paragraphs:
                    text = ' '.join([p.get_text(strip=True) for p in paragraphs[:3]])
                    if len(text) > 100:
                        return text

        # Fallback: get all paragraphs
        paragraphs = soup.find_all('p')
        if paragraphs:
            return ' '.join([p.get_text(strip=True) for p in paragraphs[:3]])

        return ''


if __name__ == '__main__':
    # Test the fetcher
    fetcher = NewsFetcher()

    # Test RSS
    print("Testing RSS fetch...")
    test_source = {
        'nombre': 'Financial Times',
        'url': 'https://www.ft.com/rss/home',
        'tipo': 'rss'
    }

    articles = fetcher.fetch_from_source(test_source)
    print(f"Fetched {len(articles)} articles")

    if articles:
        print(f"\nFirst article:")
        print(f"  Title: {articles[0]['title']}")
        print(f"  URL: {articles[0]['url']}")
        print(f"  Date: {articles[0]['published_date']}")
