"""
Content Processor Module
Cleans and processes article content without using AI
"""
import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import Optional, Dict
from newspaper import Article
import html2text
from readability import Document
import dateparser
from datetime import datetime

from config import settings

logger = logging.getLogger(__name__)


class ContentProcessor:
    """Processes and cleans article content"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True

    def process_article(self, article_dict: Dict) -> Dict:
        """
        Process an article: extract content, clean it, and extract metadata

        Args:
            article_dict: Dictionary with at least 'url' key

        Returns:
            Enhanced article dictionary with cleaned content
        """
        url = article_dict.get('url', '')

        if not url:
            logger.warning("Article has no URL")
            return article_dict

        try:
            # Try newspaper3k first (best for news articles)
            content, full_text = self._extract_with_newspaper(url)

            # If newspaper3k fails, try readability
            if not content:
                content, full_text = self._extract_with_readability(url)

            # If both fail, try manual extraction
            if not content:
                content, full_text = self._extract_manually(url)

            # Clean the content
            cleaned_content = self._clean_content(content)

            # Truncate for token efficiency
            truncated_content = self._truncate_content(cleaned_content, settings.MAX_TOKENS_PER_ARTICLE)

            # Update article dictionary
            article_dict['content'] = full_text
            article_dict['content_truncated'] = truncated_content
            article_dict['content_length'] = len(cleaned_content)

            # Try to extract date if not already present
            if not article_dict.get('published_date') or article_dict['published_date'] == datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
                extracted_date = self._extract_date(url)
                if extracted_date:
                    article_dict['published_date'] = extracted_date

            logger.info(f"Processed article: {article_dict.get('title', 'Unknown')[:50]}...")

        except Exception as e:
            logger.error(f"Error processing article {url}: {e}")

        return article_dict

    def _extract_with_newspaper(self, url: str) -> tuple[str, str]:
        """
        Extract article using newspaper3k library

        Returns:
            Tuple of (cleaned_text, full_text)
        """
        try:
            article = Article(url)
            article.download()
            article.parse()

            if article.text:
                logger.debug(f"Successfully extracted with newspaper3k: {url}")
                return article.text, article.text

        except Exception as e:
            logger.debug(f"newspaper3k extraction failed for {url}: {e}")

        return '', ''

    def _extract_with_readability(self, url: str) -> tuple[str, str]:
        """
        Extract article using readability library

        Returns:
            Tuple of (cleaned_text, full_text)
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            doc = Document(response.content)
            html_content = doc.summary()

            # Convert HTML to text
            soup = BeautifulSoup(html_content, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)

            if text and len(text) > 200:
                logger.debug(f"Successfully extracted with readability: {url}")
                return text, text

        except Exception as e:
            logger.debug(f"readability extraction failed for {url}: {e}")

        return '', ''

    def _extract_manually(self, url: str) -> tuple[str, str]:
        """
        Manual content extraction as last resort

        Returns:
            Tuple of (cleaned_text, full_text)
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
                element.decompose()

            # Try to find main content
            content = None
            content_selectors = [
                'article',
                '[class*="article-body"]',
                '[class*="post-content"]',
                '[class*="entry-content"]',
                'main',
                '[role="main"]',
            ]

            for selector in content_selectors:
                content = soup.select_one(selector)
                if content:
                    break

            if not content:
                content = soup.find('body')

            if content:
                # Extract text from paragraphs
                paragraphs = content.find_all('p')
                text = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30])

                if text:
                    logger.debug(f"Successfully extracted manually: {url}")
                    return text, text

        except Exception as e:
            logger.debug(f"Manual extraction failed for {url}: {e}")

        return '', ''

    def _clean_content(self, content: str) -> str:
        """
        Clean content text

        Args:
            content: Raw content text

        Returns:
            Cleaned content
        """
        if not content:
            return ''

        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content)

        # Remove common boilerplate patterns
        patterns_to_remove = [
            r'Subscribe to our newsletter.*?(?=\n|$)',
            r'Sign up for.*?(?=\n|$)',
            r'Follow us on.*?(?=\n|$)',
            r'Share this article.*?(?=\n|$)',
            r'Copyright \d{4}.*?(?=\n|$)',
            r'All rights reserved.*?(?=\n|$)',
        ]

        for pattern in patterns_to_remove:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)

        # Trim
        content = content.strip()

        return content

    def _truncate_content(self, content: str, max_tokens: int) -> str:
        """
        Truncate content to approximately max_tokens

        Uses rough estimate: 1 token ≈ 4 characters

        Args:
            content: Content to truncate
            max_tokens: Maximum number of tokens

        Returns:
            Truncated content
        """
        max_chars = max_tokens * 4  # Rough estimate

        if len(content) <= max_chars:
            return content

        # Truncate at sentence boundary
        truncated = content[:max_chars]

        # Find last sentence ending
        last_period = max(
            truncated.rfind('.'),
            truncated.rfind('!'),
            truncated.rfind('?')
        )

        if last_period > max_chars * 0.8:  # If we found a sentence ending in last 20%
            return truncated[:last_period + 1]

        return truncated + '...'

    def _extract_date(self, url: str) -> Optional[str]:
        """
        Extract publication date from article without using AI

        Args:
            url: Article URL

        Returns:
            Date string or None
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Try meta tags
            meta_tags = [
                ('property', 'article:published_time'),
                ('property', 'og:published_time'),
                ('name', 'publish-date'),
                ('name', 'date'),
                ('name', 'publication_date'),
                ('property', 'article:modified_time'),
            ]

            for attr_name, attr_value in meta_tags:
                meta = soup.find('meta', {attr_name: attr_value})
                if meta and meta.get('content'):
                    date_str = meta.get('content')
                    parsed_date = self._parse_date_string(date_str)
                    if parsed_date:
                        return parsed_date

            # Try time tag
            time_tag = soup.find('time')
            if time_tag:
                datetime_attr = time_tag.get('datetime', '')
                if datetime_attr:
                    parsed_date = self._parse_date_string(datetime_attr)
                    if parsed_date:
                        return parsed_date

                # Try text content
                time_text = time_tag.get_text(strip=True)
                if time_text:
                    parsed_date = self._parse_date_string(time_text)
                    if parsed_date:
                        return parsed_date

            # Try JSON-LD structured data
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                import json
                try:
                    data = json.loads(json_ld.string)
                    if isinstance(data, dict):
                        date_published = data.get('datePublished') or data.get('dateCreated')
                        if date_published:
                            parsed_date = self._parse_date_string(date_published)
                            if parsed_date:
                                return parsed_date
                except:
                    pass

            # Try common date class names
            date_elements = soup.find_all(class_=re.compile(r'date|time|publish', re.I))
            for element in date_elements[:5]:  # Check first 5
                text = element.get_text(strip=True)
                if text and len(text) < 100:  # Reasonable date length
                    parsed_date = self._parse_date_string(text)
                    if parsed_date:
                        return parsed_date

        except Exception as e:
            logger.debug(f"Date extraction failed for {url}: {e}")

        return None

    def _parse_date_string(self, date_str: str) -> Optional[str]:
        """
        Parse a date string into standard format

        Args:
            date_str: Date string in various formats

        Returns:
            Standardized date string (YYYY-MM-DD HH:MM:SS) or None
        """
        try:
            parsed = dateparser.parse(date_str)
            if parsed:
                return parsed.strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass

        return None


if __name__ == '__main__':
    # Test the processor
    processor = ContentProcessor()

    test_article = {
        'title': 'Test Article',
        'url': 'https://www.ft.com/content/example',
        'source': 'Test Source'
    }

    print("Testing content processor...")
    processed = processor.process_article(test_article)
    print(f"Content length: {processed.get('content_length', 0)}")
    print(f"Truncated length: {len(processed.get('content_truncated', ''))}")
