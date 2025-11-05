"""
STAGE 6: Newsletter Generation
===============================

Purpose: Generate an elegant newsletter from classified articles

Input: List of classified articles (from Stage 5)
Output: Generated newsletter content (Markdown/HTML)

This stage is completely independent and can be tested with mock articles.
"""
import logging
from typing import List, Dict, Any
from src.openai_client import OpenAIClient

logger = logging.getLogger(__name__)


class NewsletterGenerationStage:
    """Stage 6: Generate newsletter from articles"""

    def __init__(self, openai_client: OpenAIClient = None):
        """
        Initialize the stage

        Args:
            openai_client: Optional OpenAIClient instance
        """
        self.openai_client = openai_client or OpenAIClient()

    def execute(
        self,
        classified_articles: List[Dict[str, Any]],
        topics: List[str]
    ) -> Dict[str, Any]:
        """
        Execute Stage 6: Generate newsletter

        Args:
            classified_articles: List of articles with 'tema' field
            topics: List of topic names for organization

        Returns:
            Dictionary with:
                - newsletter_content: Generated newsletter (Markdown/HTML)
                - word_count: Approximate word count
                - topics_covered: List of topics included
                - article_count: Number of articles included
                - success: Boolean indicating success
                - error: Error message if failed
        """
        result = {
            'newsletter_content': '',
            'word_count': 0,
            'topics_covered': [],
            'article_count': 0,
            'success': False,
            'error': None
        }

        if not classified_articles:
            logger.warning("No articles provided for newsletter generation")
            result['error'] = "No articles to generate newsletter from"
            result['success'] = True  # Not a failure, just empty
            return result

        try:
            logger.info(f"Generating newsletter from {len(classified_articles)} articles...")

            # Generate newsletter
            newsletter_content = self.openai_client.generate_newsletter(
                classified_articles,
                topics
            )

            # Extract topics covered
            topics_covered = list(set(a.get('tema', '') for a in classified_articles))
            topics_covered = [t for t in topics_covered if t]  # Remove empty

            result['newsletter_content'] = newsletter_content
            result['word_count'] = len(newsletter_content.split())
            result['topics_covered'] = topics_covered
            result['article_count'] = len(classified_articles)
            result['success'] = True

            logger.info(f"Newsletter generated successfully:")
            logger.info(f"  Word count: {result['word_count']}")
            logger.info(f"  Topics covered: {', '.join(topics_covered)}")
            logger.info(f"  Articles included: {result['article_count']}")

            return result

        except Exception as e:
            logger.error(f"Error in Stage 6: {e}", exc_info=True)
            result['error'] = str(e)
            return result

    def validate_output(self, output: Dict[str, Any]) -> bool:
        """
        Validate the stage output with enhanced checks for new format

        Args:
            output: Output dictionary from execute()

        Returns:
            True if valid, False otherwise
        """
        if not output.get('success'):
            return False

        newsletter_content = output.get('newsletter_content', '')
        article_count = output.get('article_count', 0)
        word_count = output.get('word_count', 0)

        # If there were articles, newsletter should have content
        if article_count > 0:
            if not newsletter_content or len(newsletter_content) < 100:
                logger.error("Validation failed: Newsletter content too short")
                return False

            # Check minimum word count (800 words for quality content)
            if word_count < 800:
                logger.warning(f"Newsletter has {word_count} words, recommended minimum is 800")
                # Don't fail, just warn

            # Check for executive summary marker
            if '🎯' not in newsletter_content and 'RESUMEN EJECUTIVO' not in newsletter_content.upper():
                logger.warning("Newsletter may be missing executive summary section")
                # Don't fail, just warn

            # Check for main content section
            if '📰' not in newsletter_content and 'HISTORIA COMPLETA' not in newsletter_content.upper():
                logger.warning("Newsletter may be missing main content section")
                # Don't fail, just warn

        return True


def run_stage_6(
    classified_articles: List[Dict[str, Any]],
    topics: List[str],
    openai_client: OpenAIClient = None
) -> Dict[str, Any]:
    """
    Convenience function to run Stage 6

    Args:
        classified_articles: List of classified articles
        topics: List of topic names
        openai_client: Optional OpenAIClient instance

    Returns:
        Stage 6 output dictionary
    """
    stage = NewsletterGenerationStage(openai_client)
    return stage.execute(classified_articles, topics)


if __name__ == '__main__':
    # Test Stage 6 independently with mock articles
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("TESTING STAGE 6: Newsletter Generation")
    print("=" * 80)

    # Mock classified articles for testing
    test_articles = [
        {
            'title': 'Fed Raises Interest Rates',
            'content': 'Full article content about Fed rates...',
            'content_truncated': 'The Federal Reserve raised rates...',
            'tema': 'Economía y Finanzas',
            'url': 'https://example.com/fed',
            'url_sin_paywall': 'https://archive.ph/fed',
            'source': 'Test Source',
            'published_date': '2025-11-05'
        }
    ]

    test_topics = ['Economía y Finanzas', 'Tecnología']

    stage = NewsletterGenerationStage()
    result = stage.execute(test_articles, test_topics)

    print(f"\nSuccess: {result['success']}")
    if result['success']:
        print(f"Word count: {result['word_count']}")
        print(f"Topics covered: {', '.join(result['topics_covered'])}")
        print(f"Articles included: {result['article_count']}")

        if result['newsletter_content']:
            print(f"\nNewsletter preview (first 500 chars):")
            print(result['newsletter_content'][:500])
            print("...")

        print(f"\nValidation: {'PASSED' if stage.validate_output(result) else 'FAILED'}")
    else:
        print(f"Error: {result['error']}")
