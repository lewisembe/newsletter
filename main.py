#!/usr/bin/env python3
"""
Newsletter Bot - Refactored Main Pipeline
==========================================

This refactored version uses independent stages that can be tested
and improved separately.

Each stage:
- Has clear input/output contracts
- Can be run independently
- Has validation
- Is fully documented
"""
import logging
import sys
from datetime import datetime
from typing import Dict, Any

from config import settings

# Import all stages
from stages.stage1_source_loading import SourceLoadingStage
from stages.stage2_news_fetching import NewsFetchingStage
from stages.stage3_content_processing import ContentProcessingStage
from stages.stage4_deduplication import DeduplicationStage
from stages.stage5_classification import ClassificationStage
from stages.stage6_newsletter_generation import NewsletterGenerationStage
from stages.stage7_persistence import PersistenceStage

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class NewsletterPipeline:
    """Refactored newsletter generation pipeline using independent stages"""

    def __init__(self):
        """Initialize the pipeline with all stages"""
        logger.info("=" * 80)
        logger.info("NEWSLETTER BOT - REFACTORED PIPELINE")
        logger.info("=" * 80)

        # Validate configuration
        settings.validate_config()

        # Initialize stages
        self.stage1 = SourceLoadingStage()
        self.stage2 = NewsFetchingStage()
        self.stage3 = ContentProcessingStage()
        self.stage4 = DeduplicationStage()
        self.stage5 = ClassificationStage()
        self.stage6 = NewsletterGenerationStage()
        self.stage7 = PersistenceStage()

        logger.info("All stages initialized successfully")

    def run(self) -> Dict[str, Any]:
        """
        Execute the complete pipeline

        Returns:
            Dictionary with pipeline results and statistics
        """
        pipeline_result = {
            'success': False,
            'stages_completed': [],
            'stages_failed': [],
            'total_articles_fetched': 0,
            'total_articles_processed': 0,
            'total_duplicates_removed': 0,
            'total_articles_classified': 0,
            'newsletter_generated': False,
            'data_saved': False,
            'duration_seconds': 0,
            'error': None
        }

        start_time = datetime.now()

        try:
            # STAGE 1: Source Loading
            logger.info("\n" + "=" * 80)
            logger.info("STAGE 1: Loading Sources and Topics")
            logger.info("=" * 80)

            stage1_result = self.stage1.execute()

            if not stage1_result['success']:
                pipeline_result['error'] = f"Stage 1 failed: {stage1_result['error']}"
                pipeline_result['stages_failed'].append('Stage 1')
                return pipeline_result

            if not self.stage1.validate_output(stage1_result):
                pipeline_result['error'] = "Stage 1 validation failed"
                pipeline_result['stages_failed'].append('Stage 1')
                return pipeline_result

            pipeline_result['stages_completed'].append('Stage 1')

            sources = stage1_result['sources']
            topics = stage1_result['topics']

            logger.info(f"✓ Loaded {len(sources)} sources and {len(topics)} topics")

            # STAGE 2: News Fetching
            logger.info("\n" + "=" * 80)
            logger.info("STAGE 2: Fetching News from Sources")
            logger.info("=" * 80)

            stage2_result = self.stage2.execute(sources)

            if not stage2_result['success']:
                pipeline_result['error'] = f"Stage 2 failed: {stage2_result['error']}"
                pipeline_result['stages_failed'].append('Stage 2')
                return pipeline_result

            if not self.stage2.validate_output(stage2_result):
                pipeline_result['error'] = "Stage 2 validation failed"
                pipeline_result['stages_failed'].append('Stage 2')
                return pipeline_result

            pipeline_result['stages_completed'].append('Stage 2')
            pipeline_result['total_articles_fetched'] = stage2_result['total_articles']

            articles = stage2_result['articles']

            logger.info(f"✓ Fetched {len(articles)} articles")

            if not articles:
                logger.info("No articles fetched. Pipeline complete.")
                pipeline_result['success'] = True
                return pipeline_result

            # STAGE 3: Content Processing
            logger.info("\n" + "=" * 80)
            logger.info("STAGE 3: Processing Article Content")
            logger.info("=" * 80)

            stage3_result = self.stage3.execute(articles)

            if not stage3_result['success']:
                pipeline_result['error'] = f"Stage 3 failed: {stage3_result['error']}"
                pipeline_result['stages_failed'].append('Stage 3')
                return pipeline_result

            if not self.stage3.validate_output(stage3_result):
                pipeline_result['error'] = "Stage 3 validation failed"
                pipeline_result['stages_failed'].append('Stage 3')
                return pipeline_result

            pipeline_result['stages_completed'].append('Stage 3')
            pipeline_result['total_articles_processed'] = stage3_result['total_processed']

            processed_articles = stage3_result['processed_articles']

            logger.info(f"✓ Processed {len(processed_articles)} articles")

            # STAGE 4: Deduplication
            logger.info("\n" + "=" * 80)
            logger.info("STAGE 4: Filtering Duplicate Articles")
            logger.info("=" * 80)

            stage4_result = self.stage4.execute(processed_articles)

            if not stage4_result['success']:
                pipeline_result['error'] = f"Stage 4 failed: {stage4_result['error']}"
                pipeline_result['stages_failed'].append('Stage 4')
                return pipeline_result

            if not self.stage4.validate_output(stage4_result):
                pipeline_result['error'] = "Stage 4 validation failed"
                pipeline_result['stages_failed'].append('Stage 4')
                return pipeline_result

            pipeline_result['stages_completed'].append('Stage 4')
            pipeline_result['total_duplicates_removed'] = stage4_result['duplicates_removed']

            unique_articles = stage4_result['unique_articles']

            logger.info(f"✓ {stage4_result['duplicates_removed']} duplicates removed, {len(unique_articles)} unique articles")

            if not unique_articles:
                logger.info("No new articles to process. Pipeline complete.")
                pipeline_result['success'] = True
                return pipeline_result

            # STAGE 5: Classification
            logger.info("\n" + "=" * 80)
            logger.info("STAGE 5: Classifying Articles by Topic")
            logger.info("=" * 80)

            stage5_result = self.stage5.execute(unique_articles, topics)

            if not stage5_result['success']:
                pipeline_result['error'] = f"Stage 5 failed: {stage5_result['error']}"
                pipeline_result['stages_failed'].append('Stage 5')
                return pipeline_result

            if not self.stage5.validate_output(stage5_result):
                pipeline_result['error'] = "Stage 5 validation failed"
                pipeline_result['stages_failed'].append('Stage 5')
                return pipeline_result

            pipeline_result['stages_completed'].append('Stage 5')
            pipeline_result['total_articles_classified'] = stage5_result['total_classified']

            classified_articles = stage5_result['classified_articles']
            classification_stats = stage5_result['classification_stats']

            logger.info(f"✓ Classified {len(classified_articles)} articles:")
            for topic, count in classification_stats.items():
                logger.info(f"    {topic}: {count}")

            # STAGE 6: Newsletter Generation
            logger.info("\n" + "=" * 80)
            logger.info("STAGE 6: Generating Newsletter")
            logger.info("=" * 80)

            stage6_result = self.stage6.execute(classified_articles, topics)

            if not stage6_result['success']:
                pipeline_result['error'] = f"Stage 6 failed: {stage6_result['error']}"
                pipeline_result['stages_failed'].append('Stage 6')
                return pipeline_result

            if not self.stage6.validate_output(stage6_result):
                pipeline_result['error'] = "Stage 6 validation failed"
                pipeline_result['stages_failed'].append('Stage 6')
                return pipeline_result

            pipeline_result['stages_completed'].append('Stage 6')
            pipeline_result['newsletter_generated'] = True

            newsletter_content = stage6_result['newsletter_content']
            topics_covered = stage6_result['topics_covered']

            logger.info(f"✓ Newsletter generated: {stage6_result['word_count']} words")

            # STAGE 7: Data Persistence
            logger.info("\n" + "=" * 80)
            logger.info("STAGE 7: Saving Data to Google Sheets")
            logger.info("=" * 80)

            stage7_result = self.stage7.execute(
                classified_articles,
                newsletter_content,
                topics_covered
            )

            if not stage7_result['success']:
                pipeline_result['error'] = f"Stage 7 failed: {stage7_result['error']}"
                pipeline_result['stages_failed'].append('Stage 7')
                return pipeline_result

            if not self.stage7.validate_output(stage7_result):
                pipeline_result['error'] = "Stage 7 validation failed"
                pipeline_result['stages_failed'].append('Stage 7')
                return pipeline_result

            pipeline_result['stages_completed'].append('Stage 7')
            pipeline_result['data_saved'] = True

            logger.info(f"✓ Saved {stage7_result['articles_saved']} articles and newsletter")

            # Pipeline completed successfully
            pipeline_result['success'] = True
            end_time = datetime.now()
            pipeline_result['duration_seconds'] = (end_time - start_time).total_seconds()

            # Print summary
            self._print_summary(pipeline_result, stage6_result)

            return pipeline_result

        except Exception as e:
            logger.error(f"Pipeline failed with unexpected error: {e}", exc_info=True)
            pipeline_result['error'] = str(e)
            return pipeline_result

    def _print_summary(self, pipeline_result: Dict[str, Any], stage6_result: Dict[str, Any]):
        """Print pipeline execution summary"""
        logger.info("\n" + "=" * 80)
        logger.info("PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"Duration: {pipeline_result['duration_seconds']:.2f} seconds")
        logger.info(f"Stages completed: {', '.join(pipeline_result['stages_completed'])}")
        logger.info(f"Articles fetched: {pipeline_result['total_articles_fetched']}")
        logger.info(f"Articles processed: {pipeline_result['total_articles_processed']}")
        logger.info(f"Duplicates removed: {pipeline_result['total_duplicates_removed']}")
        logger.info(f"Articles classified: {pipeline_result['total_articles_classified']}")
        logger.info(f"Newsletter word count: {stage6_result['word_count']}")
        logger.info(f"Topics covered: {', '.join(stage6_result['topics_covered'])}")
        logger.info("=" * 80)

        # Print newsletter preview
        print("\n" + "=" * 80)
        print("NEWSLETTER PREVIEW")
        print("=" * 80)
        newsletter_content = stage6_result['newsletter_content']
        print(newsletter_content[:1000])
        if len(newsletter_content) > 1000:
            print("\n... (truncated, see Google Sheet for full content)")
        print("=" * 80)


def main():
    """Main entry point"""
    try:
        pipeline = NewsletterPipeline()
        result = pipeline.run()

        if not result['success']:
            logger.error(f"Pipeline failed: {result['error']}")
            if result['stages_failed']:
                logger.error(f"Failed stages: {', '.join(result['stages_failed'])}")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nPipeline interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
