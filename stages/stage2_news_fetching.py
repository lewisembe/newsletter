"""
STAGE 2: News Fetching
=======================

Purpose: Fetch news articles from all configured sources

Input: List of source dictionaries (from Stage 1)
Output: List of raw article dictionaries

This stage is completely independent and can be tested with mock sources.
"""
import logging
from typing import List, Dict, Any
from src.news_fetcher import NewsFetcher

logger = logging.getLogger(__name__)


class NewsFetchingStage:
    """Stage 2: Fetch news from sources"""

    def __init__(self, news_fetcher: NewsFetcher = None):
        """
        Initialize the stage

        Args:
            news_fetcher: Optional NewsFetcher instance.
                         If None, creates a new one.
        """
        self.news_fetcher = news_fetcher or NewsFetcher()

    def execute(self, sources: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Execute Stage 2: Fetch news from sources

        Args:
            sources: List of source dictionaries with keys:
                    - nombre: Source name
                    - url: Source URL
                    - tipo: Source type (rss, crawl, etc.)

        Returns:
            Dictionary with:
                - articles: List of article dictionaries
                - articles_by_source: Dict mapping source name to articles
                - total_articles: Total number of articles fetched
                - success: Boolean indicating success
                - error: Error message if failed
        """
        result = {
            'articles': [],
            'articles_by_source': {},
            'total_articles': 0,
            'success': False,
            'error': None
        }

        if not sources:
            result['error'] = "No sources provided"
            return result

        try:
            all_articles = []
            articles_by_source = {}

            for source in sources:
                source_name = source.get('nombre', 'Unknown')
                logger.info(f"Fetching from source: {source_name}")

                try:
                    articles = self.news_fetcher.fetch_from_source(source)
                    all_articles.extend(articles)
                    articles_by_source[source_name] = articles

                    logger.info(f"  → Fetched {len(articles)} articles from {source_name}")

                except Exception as e:
                    logger.error(f"Error fetching from {source_name}: {e}")
                    articles_by_source[source_name] = []

            result['articles'] = all_articles
            result['articles_by_source'] = articles_by_source
            result['total_articles'] = len(all_articles)
            result['success'] = True

            logger.info(f"Total articles fetched: {len(all_articles)}")

            return result

        except Exception as e:
            logger.error(f"Error in Stage 2: {e}", exc_info=True)
            result['error'] = str(e)
            return result

    def validate_output(self, output: Dict[str, Any]) -> bool:
        """
        Validate the stage output

        Args:
            output: Output dictionary from execute()

        Returns:
            True if valid, False otherwise
        """
        if not output.get('success'):
            return False

        articles = output.get('articles', [])

        # Allow empty articles (might be no new content)
        if not isinstance(articles, list):
            logger.error("Validation failed: articles is not a list")
            return False

        # Validate article structure
        required_article_keys = {'title', 'url', 'source'}
        for article in articles:
            if not all(key in article for key in required_article_keys):
                logger.error(f"Invalid article structure: {article}")
                return False

        return True


def run_stage_2(sources: List[Dict[str, str]], news_fetcher: NewsFetcher = None) -> Dict[str, Any]:
    """
    Convenience function to run Stage 2

    Args:
        sources: List of source dictionaries
        news_fetcher: Optional NewsFetcher instance

    Returns:
        Stage 2 output dictionary
    """
    stage = NewsFetchingStage(news_fetcher)
    return stage.execute(sources)


if __name__ == '__main__':
    # Test Stage 2 independently with mock sources
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("TESTING STAGE 2: News Fetching")
    print("=" * 80)

    # Mock sources for testing
    test_sources = [
        {
            'nombre': 'Financial Times',
            'url': 'https://www.ft.com/rss/home',
            'tipo': 'rss'
        }
    ]

    stage = NewsFetchingStage()
    result = stage.execute(test_sources)

    print(f"\nSuccess: {result['success']}")
    if result['success']:
        print(f"Total articles: {result['total_articles']}")
        print(f"\nArticles by source:")
        for source_name, articles in result['articles_by_source'].items():
            print(f"  {source_name}: {len(articles)} articles")

        if result['articles']:
            print(f"\nSample article:")
            article = result['articles'][0]
            print(f"  Title: {article.get('title')}")
            print(f"  Source: {article.get('source')}")
            print(f"  URL: {article.get('url')}")

        print(f"\nValidation: {'PASSED' if stage.validate_output(result) else 'FAILED'}")
    else:
        print(f"Error: {result['error']}")
