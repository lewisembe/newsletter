"""
STAGE 5: Article Classification
================================

Purpose: Classify articles into predefined topics using OpenAI

Input:
  - articles: List of unique articles (from Stage 4)
  - topics: List of topic names (from Stage 1)

Output: List of articles with 'tema' field added

This stage is completely independent and can be tested with mock data.
"""
import logging
from typing import List, Dict, Any
from src.openai_client import OpenAIClient

logger = logging.getLogger(__name__)


class ClassificationStage:
    """Stage 5: Classify articles by topic"""

    def __init__(self, openai_client: OpenAIClient = None):
        """
        Initialize the stage

        Args:
            openai_client: Optional OpenAIClient instance
        """
        self.openai_client = openai_client or OpenAIClient()

    def execute(
        self,
        articles: List[Dict[str, Any]],
        topics: List[str]
    ) -> Dict[str, Any]:
        """
        Execute Stage 5: Classify articles by topic

        Args:
            articles: List of unique article dictionaries
            topics: List of available topic names

        Returns:
            Dictionary with:
                - classified_articles: List of articles with 'tema' field
                - classification_stats: Dict mapping topics to article counts
                - total_classified: Number of articles classified
                - success: Boolean indicating success
                - error: Error message if failed
        """
        result = {
            'classified_articles': [],
            'classification_stats': {},
            'total_classified': 0,
            'success': False,
            'error': None
        }

        if not articles:
            logger.info("No articles to classify")
            result['success'] = True
            return result

        if not topics:
            result['error'] = "No topics provided for classification"
            return result

        try:
            logger.info(f"Classifying {len(articles)} articles into {len(topics)} topics...")

            # Classify each article
            classified_articles = self.openai_client.classify_articles_batch(
                articles,
                topics
            )

            # Generate statistics
            classification_stats = {}
            for article in classified_articles:
                topic = article.get('tema', 'Unknown')
                classification_stats[topic] = classification_stats.get(topic, 0) + 1

            result['classified_articles'] = classified_articles
            result['classification_stats'] = classification_stats
            result['total_classified'] = len(classified_articles)
            result['success'] = True

            logger.info("Classification complete:")
            for topic, count in classification_stats.items():
                logger.info(f"  {topic}: {count} articles")

            return result

        except Exception as e:
            logger.error(f"Error in Stage 5: {e}", exc_info=True)
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

        articles = output.get('classified_articles', [])

        # Validate that all articles have 'tema' field
        for article in articles:
            if 'tema' not in article:
                logger.error(f"Article missing 'tema' field: {article.get('title')}")
                return False

            if not article.get('tema'):
                logger.error(f"Article has empty 'tema': {article.get('title')}")
                return False

        # Validate statistics match
        stats = output.get('classification_stats', {})
        total_in_stats = sum(stats.values())
        total_articles = len(articles)

        if total_in_stats != total_articles:
            logger.error(
                f"Validation failed: Stats don't match. "
                f"Stats total: {total_in_stats}, Articles: {total_articles}"
            )
            return False

        return True


def run_stage_5(
    articles: List[Dict[str, Any]],
    topics: List[str],
    openai_client: OpenAIClient = None
) -> Dict[str, Any]:
    """
    Convenience function to run Stage 5

    Args:
        articles: List of unique articles
        topics: List of topic names
        openai_client: Optional OpenAIClient instance

    Returns:
        Stage 5 output dictionary
    """
    stage = ClassificationStage(openai_client)
    return stage.execute(articles, topics)


if __name__ == '__main__':
    # Test Stage 5 independently with mock articles
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("TESTING STAGE 5: Classification")
    print("=" * 80)

    # Mock articles and topics for testing
    test_articles = [
        {
            'title': 'Fed Raises Interest Rates',
            'content_truncated': 'The Federal Reserve raised interest rates by 0.5%...',
            'url': 'https://example.com/fed'
        },
        {
            'title': 'New AI Technology Released',
            'content_truncated': 'A groundbreaking AI system was announced today...',
            'url': 'https://example.com/ai'
        }
    ]

    test_topics = ['Economía y Finanzas', 'Tecnología', 'Política']

    stage = ClassificationStage()
    result = stage.execute(test_articles, test_topics)

    print(f"\nSuccess: {result['success']}")
    if result['success']:
        print(f"Total classified: {result['total_classified']}")
        print(f"\nClassification breakdown:")
        for topic, count in result['classification_stats'].items():
            print(f"  {topic}: {count}")

        print(f"\nSample classified article:")
        if result['classified_articles']:
            article = result['classified_articles'][0]
            print(f"  Title: {article.get('title')}")
            print(f"  Tema: {article.get('tema')}")

        print(f"\nValidation: {'PASSED' if stage.validate_output(result) else 'FAILED'}")
    else:
        print(f"Error: {result['error']}")
