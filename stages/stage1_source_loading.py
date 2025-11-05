"""
STAGE 1: Source Loading
========================

Purpose: Load active news sources and predefined topics from Google Sheets

Input: Google Sheets credentials
Output: Dictionary with:
  - sources: List[Dict] - Active news sources
  - topics: List[str] - Topic names for classification

This stage is completely independent and can be tested standalone.
"""
import logging
from typing import Dict, List, Any
from src.google_sheets import GoogleSheetsClient

logger = logging.getLogger(__name__)


class SourceLoadingStage:
    """Stage 1: Load sources and topics from Google Sheets"""

    def __init__(self, sheets_client: GoogleSheetsClient = None):
        """
        Initialize the stage

        Args:
            sheets_client: Optional GoogleSheetsClient instance.
                          If None, creates a new one.
        """
        self.sheets_client = sheets_client or GoogleSheetsClient()

    def execute(self) -> Dict[str, Any]:
        """
        Execute Stage 1: Load sources and topics

        Returns:
            Dictionary with:
                - sources: List of active source dictionaries
                - topics: List of topic names
                - topic_details: List of full topic dictionaries
                - success: Boolean indicating success
                - error: Error message if failed
        """
        result = {
            'sources': [],
            'topics': [],
            'topic_details': [],
            'success': False,
            'error': None
        }

        try:
            # Load active sources
            logger.info("Loading active news sources from Google Sheets...")
            sources = self.sheets_client.get_active_sources()

            if not sources:
                logger.warning("No active sources found")
                result['error'] = "No active sources found in Google Sheets"
                return result

            result['sources'] = sources
            logger.info(f"Loaded {len(sources)} active sources")

            # Load topics
            logger.info("Loading predefined topics from Google Sheets...")
            topic_details = self.sheets_client.get_all_topics()

            if not topic_details:
                logger.warning("No topics found")
                result['error'] = "No topics found in Google Sheets"
                return result

            topics = self.sheets_client.get_topic_names()
            result['topics'] = topics
            result['topic_details'] = topic_details
            logger.info(f"Loaded {len(topics)} topics")

            result['success'] = True
            return result

        except Exception as e:
            logger.error(f"Error in Stage 1: {e}", exc_info=True)
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

        if not output.get('sources'):
            logger.error("Validation failed: No sources in output")
            return False

        if not output.get('topics'):
            logger.error("Validation failed: No topics in output")
            return False

        # Validate source structure
        required_source_keys = {'nombre', 'url', 'tipo'}
        for source in output['sources']:
            if not all(key in source for key in required_source_keys):
                logger.error(f"Invalid source structure: {source}")
                return False

        return True


def run_stage_1(sheets_client: GoogleSheetsClient = None) -> Dict[str, Any]:
    """
    Convenience function to run Stage 1

    Args:
        sheets_client: Optional GoogleSheetsClient instance

    Returns:
        Stage 1 output dictionary
    """
    stage = SourceLoadingStage(sheets_client)
    return stage.execute()


if __name__ == '__main__':
    # Test Stage 1 independently
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("TESTING STAGE 1: Source Loading")
    print("=" * 80)

    stage = SourceLoadingStage()
    result = stage.execute()

    print(f"\nSuccess: {result['success']}")
    if result['success']:
        print(f"Sources loaded: {len(result['sources'])}")
        print(f"Topics loaded: {len(result['topics'])}")
        print(f"\nSources:")
        for source in result['sources']:
            print(f"  - {source.get('nombre')} ({source.get('tipo')})")
        print(f"\nTopics:")
        for topic in result['topics']:
            print(f"  - {topic}")

        print(f"\nValidation: {'PASSED' if stage.validate_output(result) else 'FAILED'}")
    else:
        print(f"Error: {result['error']}")
