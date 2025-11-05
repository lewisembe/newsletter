"""
STAGE 7: Data Persistence
==========================

Purpose: Save processed articles and newsletter to Google Sheets

Input:
  - classified_articles: List of classified articles (from Stage 5)
  - newsletter_content: Generated newsletter (from Stage 6)
  - topics_covered: List of topics covered

Output: Confirmation of saved data

This stage is completely independent and can be tested with mock data.
"""
import logging
from typing import List, Dict, Any
from src.google_sheets import GoogleSheetsClient

logger = logging.getLogger(__name__)


class PersistenceStage:
    """Stage 7: Save data to Google Sheets"""

    def __init__(self, sheets_client: GoogleSheetsClient = None):
        """
        Initialize the stage

        Args:
            sheets_client: Optional GoogleSheetsClient instance
        """
        self.sheets_client = sheets_client or GoogleSheetsClient()

    def execute(
        self,
        classified_articles: List[Dict[str, Any]],
        newsletter_content: str,
        topics_covered: List[str]
    ) -> Dict[str, Any]:
        """
        Execute Stage 7: Save to Google Sheets

        Args:
            classified_articles: List of classified articles
            newsletter_content: Generated newsletter content
            topics_covered: List of topics covered

        Returns:
            Dictionary with:
                - articles_saved: Number of articles saved
                - newsletter_saved: Boolean indicating newsletter saved
                - success: Boolean indicating success
                - error: Error message if failed
        """
        result = {
            'articles_saved': 0,
            'newsletter_saved': False,
            'success': False,
            'error': None
        }

        try:
            # Save articles
            if classified_articles:
                logger.info(f"Saving {len(classified_articles)} articles to Google Sheets...")

                articles_to_save = []
                for article in classified_articles:
                    articles_to_save.append({
                        'fecha_publicacion': article.get('published_date', ''),
                        'titulo': article.get('title', ''),
                        'fuente': article.get('source', ''),
                        'tema': article.get('tema', ''),
                        'contenido_completo': article.get('content', ''),
                        'contenido_truncado': article.get('content_truncated', ''),
                        'url_original': article.get('url', ''),
                        'url_sin_paywall': article.get('url_sin_paywall', ''),
                        'hash_contenido': article.get('hash_contenido', '')
                    })

                self.sheets_client.add_processed_articles_batch(articles_to_save)
                result['articles_saved'] = len(articles_to_save)
                logger.info(f"Saved {len(articles_to_save)} articles")

            # Save newsletter
            if newsletter_content:
                logger.info("Saving newsletter to Google Sheets...")

                topics_str = ', '.join(topics_covered) if topics_covered else 'N/A'

                self.sheets_client.add_newsletter(
                    contenido=newsletter_content,
                    num_articulos=len(classified_articles),
                    temas_cubiertos=topics_str
                )

                result['newsletter_saved'] = True
                logger.info("Newsletter saved successfully")

            result['success'] = True
            return result

        except Exception as e:
            logger.error(f"Error in Stage 7: {e}", exc_info=True)
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

        # If articles were provided, they should be saved
        articles_saved = output.get('articles_saved', 0)
        if articles_saved < 0:
            logger.error("Validation failed: Negative articles_saved count")
            return False

        return True


def run_stage_7(
    classified_articles: List[Dict[str, Any]],
    newsletter_content: str,
    topics_covered: List[str],
    sheets_client: GoogleSheetsClient = None
) -> Dict[str, Any]:
    """
    Convenience function to run Stage 7

    Args:
        classified_articles: List of classified articles
        newsletter_content: Newsletter content
        topics_covered: List of topics covered
        sheets_client: Optional GoogleSheetsClient instance

    Returns:
        Stage 7 output dictionary
    """
    stage = PersistenceStage(sheets_client)
    return stage.execute(classified_articles, newsletter_content, topics_covered)


if __name__ == '__main__':
    # Test Stage 7 with mock data (won't actually save without real sheets_client)
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("TESTING STAGE 7: Data Persistence")
    print("=" * 80)
    print("Note: This test requires a real Google Sheets connection")
    print("=" * 80)

    test_articles = [
        {
            'title': 'Test Article',
            'content': 'Full content',
            'content_truncated': 'Truncated',
            'tema': 'Test Topic',
            'url': 'https://example.com',
            'url_sin_paywall': 'https://archive.ph/example',
            'source': 'Test',
            'published_date': '2025-11-05',
            'hash_contenido': 'testhash123'
        }
    ]

    test_newsletter = "# Test Newsletter\n\nThis is a test."
    test_topics = ['Test Topic']

    try:
        stage = PersistenceStage()
        result = stage.execute(test_articles, test_newsletter, test_topics)

        print(f"\nSuccess: {result['success']}")
        if result['success']:
            print(f"Articles saved: {result['articles_saved']}")
            print(f"Newsletter saved: {result['newsletter_saved']}")
            print(f"\nValidation: {'PASSED' if stage.validate_output(result) else 'FAILED'}")
        else:
            print(f"Error: {result['error']}")
    except Exception as e:
        print(f"Test failed (expected without real credentials): {e}")
