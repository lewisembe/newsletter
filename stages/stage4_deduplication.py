"""
STAGE 4: Deduplication
=======================

Purpose: Filter out duplicate articles

Input: List of processed article dictionaries (from Stage 3)
Output: List of unique articles (duplicates removed)

This stage is completely independent and can be tested with mock articles.
"""
import logging
from typing import List, Dict, Any, Set
from src.deduplicator import Deduplicator, create_deduplicator
from src.google_sheets import GoogleSheetsClient

logger = logging.getLogger(__name__)


class DeduplicationStage:
    """Stage 4: Remove duplicate articles"""

    def __init__(
        self,
        deduplicator: Deduplicator = None,
        sheets_client: GoogleSheetsClient = None
    ):
        """
        Initialize the stage

        Args:
            deduplicator: Optional Deduplicator instance.
                         If None, creates one with existing articles from sheets_client
            sheets_client: Optional GoogleSheetsClient for loading existing articles
        """
        if deduplicator is None:
            self.deduplicator = create_deduplicator(sheets_client)
        else:
            self.deduplicator = deduplicator

    def execute(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute Stage 4: Filter duplicate articles

        Args:
            articles: List of processed article dictionaries

        Returns:
            Dictionary with:
                - unique_articles: List of unique articles
                - duplicates_removed: Number of duplicates filtered
                - total_input: Total input articles
                - total_output: Total unique articles
                - success: Boolean indicating success
                - error: Error message if failed
        """
        result = {
            'unique_articles': [],
            'duplicates_removed': 0,
            'total_input': len(articles),
            'total_output': 0,
            'success': False,
            'error': None
        }

        if not articles:
            logger.info("No articles to deduplicate")
            result['success'] = True
            return result

        try:
            logger.info(f"Deduplicating {len(articles)} articles...")

            # Filter duplicates
            unique_articles = self.deduplicator.filter_duplicates(articles)

            result['unique_articles'] = unique_articles
            result['duplicates_removed'] = len(articles) - len(unique_articles)
            result['total_output'] = len(unique_articles)
            result['success'] = True

            logger.info(
                f"Filtered {result['duplicates_removed']} duplicates, "
                f"{result['total_output']} unique articles remain"
            )

            return result

        except Exception as e:
            logger.error(f"Error in Stage 4: {e}", exc_info=True)
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

        # Check that counts are consistent
        total_input = output.get('total_input', 0)
        total_output = output.get('total_output', 0)
        duplicates_removed = output.get('duplicates_removed', 0)

        if total_input != total_output + duplicates_removed:
            logger.error(
                f"Validation failed: Counts don't match. "
                f"Input: {total_input}, Output: {total_output}, Duplicates: {duplicates_removed}"
            )
            return False

        return True


def run_stage_4(
    articles: List[Dict[str, Any]],
    deduplicator: Deduplicator = None,
    sheets_client: GoogleSheetsClient = None
) -> Dict[str, Any]:
    """
    Convenience function to run Stage 4

    Args:
        articles: List of processed articles
        deduplicator: Optional Deduplicator instance
        sheets_client: Optional GoogleSheetsClient instance

    Returns:
        Stage 4 output dictionary
    """
    stage = DeduplicationStage(deduplicator, sheets_client)
    return stage.execute(articles)


if __name__ == '__main__':
    # Test Stage 4 independently with mock articles
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("TESTING STAGE 4: Deduplication")
    print("=" * 80)

    # Mock articles for testing (including duplicates)
    test_articles = [
        {
            'title': 'Article 1',
            'url': 'https://example.com/article1',
            'source': 'Test',
            'content': 'Content 1',
            'content_truncated': 'Content 1',
            'hash_contenido': 'hash1'
        },
        {
            'title': 'Article 2',
            'url': 'https://example.com/article2',
            'source': 'Test',
            'content': 'Content 2',
            'content_truncated': 'Content 2',
            'hash_contenido': 'hash2'
        },
        {
            'title': 'Article 1 Duplicate',
            'url': 'https://example.com/article1',  # Same URL
            'source': 'Test',
            'content': 'Content 1',
            'content_truncated': 'Content 1',
            'hash_contenido': 'hash1'
        }
    ]

    # Create deduplicator without existing articles
    deduplicator = Deduplicator()
    stage = DeduplicationStage(deduplicator)

    result = stage.execute(test_articles)

    print(f"\nSuccess: {result['success']}")
    if result['success']:
        print(f"Total input: {result['total_input']}")
        print(f"Duplicates removed: {result['duplicates_removed']}")
        print(f"Unique articles: {result['total_output']}")

        print(f"\nValidation: {'PASSED' if stage.validate_output(result) else 'FAILED'}")
    else:
        print(f"Error: {result['error']}")
