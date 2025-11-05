"""
STAGE 3: Content Processing
============================

Purpose: Process and clean article content, create archive links

Input: List of raw article dictionaries (from Stage 2)
Output: List of processed article dictionaries with:
  - Cleaned and full content
  - Truncated content for classification
  - Archive links (paywall-free)
  - Content hashes

This stage is completely independent and can be tested with mock articles.
"""
import logging
from typing import List, Dict, Any
from src.content_processor import ContentProcessor
from src.archive_service import ArchiveService
from src.deduplicator import Deduplicator

logger = logging.getLogger(__name__)


class ContentProcessingStage:
    """Stage 3: Process content and create archive links"""

    def __init__(
        self,
        content_processor: ContentProcessor = None,
        archive_service: ArchiveService = None,
        deduplicator: Deduplicator = None
    ):
        """
        Initialize the stage

        Args:
            content_processor: Optional ContentProcessor instance
            archive_service: Optional ArchiveService instance
            deduplicator: Optional Deduplicator instance
        """
        self.content_processor = content_processor or ContentProcessor()
        self.archive_service = archive_service or ArchiveService()
        self.deduplicator = deduplicator or Deduplicator()

    def execute(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute Stage 3: Process article content

        Args:
            articles: List of raw article dictionaries from Stage 2

        Returns:
            Dictionary with:
                - processed_articles: List of processed article dictionaries
                - total_processed: Number of articles processed
                - success: Boolean indicating success
                - error: Error message if failed
        """
        result = {
            'processed_articles': [],
            'total_processed': 0,
            'success': False,
            'error': None
        }

        if not articles:
            logger.warning("No articles provided for processing")
            result['success'] = True  # Not an error, just empty
            return result

        try:
            processed_articles = []

            for i, article in enumerate(articles, 1):
                title = article.get('title', 'Unknown')[:50]
                logger.info(f"Processing article {i}/{len(articles)}: {title}...")

                try:
                    # Process content (extract, clean, truncate)
                    processed_article = self.content_processor.process_article(article)

                    # Create archive link
                    url = processed_article.get('url', '')
                    if url:
                        archive_url = self.archive_service.create_archive_link(url)
                        processed_article['url_sin_paywall'] = archive_url
                    else:
                        processed_article['url_sin_paywall'] = ''

                    # Generate content hash for deduplication
                    content_for_hash = processed_article.get('content_truncated', '')
                    content_hash = self.deduplicator.get_content_hash(content_for_hash)
                    processed_article['hash_contenido'] = content_hash

                    processed_articles.append(processed_article)

                except Exception as e:
                    logger.error(f"Error processing article '{title}': {e}")
                    continue

            result['processed_articles'] = processed_articles
            result['total_processed'] = len(processed_articles)
            result['success'] = True

            logger.info(f"Successfully processed {len(processed_articles)} articles")

            return result

        except Exception as e:
            logger.error(f"Error in Stage 3: {e}", exc_info=True)
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

        articles = output.get('processed_articles', [])

        # Allow empty articles
        if not isinstance(articles, list):
            logger.error("Validation failed: processed_articles is not a list")
            return False

        # Validate article structure
        required_keys = {
            'title', 'url', 'source', 'content', 'content_truncated',
            'url_sin_paywall', 'hash_contenido'
        }

        for article in articles:
            if not all(key in article for key in required_keys):
                missing = required_keys - set(article.keys())
                logger.error(f"Invalid article structure. Missing keys: {missing}")
                return False

            # Validate content exists
            if not article.get('content'):
                logger.warning(f"Article '{article.get('title')}' has empty content")

        return True


def run_stage_3(
    articles: List[Dict[str, Any]],
    content_processor: ContentProcessor = None,
    archive_service: ArchiveService = None,
    deduplicator: Deduplicator = None
) -> Dict[str, Any]:
    """
    Convenience function to run Stage 3

    Args:
        articles: List of raw article dictionaries
        content_processor: Optional ContentProcessor instance
        archive_service: Optional ArchiveService instance
        deduplicator: Optional Deduplicator instance

    Returns:
        Stage 3 output dictionary
    """
    stage = ContentProcessingStage(content_processor, archive_service, deduplicator)
    return stage.execute(articles)


if __name__ == '__main__':
    # Test Stage 3 independently with mock articles
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("TESTING STAGE 3: Content Processing")
    print("=" * 80)

    # Mock articles for testing
    test_articles = [
        {
            'title': 'Test Article 1',
            'url': 'https://example.com/article1',
            'source': 'Test Source',
            'published_date': '2025-11-05',
            'summary': 'Test summary',
            'content': 'Test content'
        }
    ]

    stage = ContentProcessingStage()
    result = stage.execute(test_articles)

    print(f"\nSuccess: {result['success']}")
    if result['success']:
        print(f"Total processed: {result['total_processed']}")

        if result['processed_articles']:
            print(f"\nSample processed article:")
            article = result['processed_articles'][0]
            print(f"  Title: {article.get('title')}")
            print(f"  Content length: {article.get('content_length', 0)}")
            print(f"  Truncated length: {len(article.get('content_truncated', ''))}")
            print(f"  Archive URL: {article.get('url_sin_paywall', '')[:60]}...")
            print(f"  Hash: {article.get('hash_contenido', '')[:16]}...")

        print(f"\nValidation: {'PASSED' if stage.validate_output(result) else 'FAILED'}")
    else:
        print(f"Error: {result['error']}")
