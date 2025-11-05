#!/usr/bin/env python3
"""
Newsletter Bot - Main Pipeline
Orchestrates the entire newsletter generation process
"""
import logging
from datetime import datetime
import sys

from config import settings
from src.google_sheets import GoogleSheetsClient
from src.news_fetcher import NewsFetcher
from src.content_processor import ContentProcessor
from src.archive_service import ArchiveService
from src.deduplicator import create_deduplicator
from src.openai_client import OpenAIClient

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
    """Main pipeline for newsletter generation"""

    def __init__(self):
        """Initialize all components"""
        logger.info("=" * 80)
        logger.info("NEWSLETTER BOT - STARTING")
        logger.info("=" * 80)

        # Validate configuration
        settings.validate_config()

        # Initialize components
        self.sheets_client = GoogleSheetsClient()
        self.news_fetcher = NewsFetcher()
        self.content_processor = ContentProcessor()
        self.archive_service = ArchiveService()
        self.openai_client = OpenAIClient()

        # Initialize deduplicator with existing articles
        self.deduplicator = create_deduplicator(self.sheets_client)

        logger.info("All components initialized successfully")

    def run(self):
        """Execute the complete pipeline"""
        try:
            start_time = datetime.now()
            logger.info(f"Pipeline started at {start_time}")

            # Step 1: Get active sources
            logger.info("\n" + "=" * 80)
            logger.info("STEP 1: Fetching active news sources")
            logger.info("=" * 80)
            sources = self.sheets_client.get_active_sources()

            if not sources:
                logger.error("No active sources found. Please add sources to the Google Sheet.")
                return

            logger.info(f"Found {len(sources)} active sources")

            # Step 2: Get available topics
            logger.info("\n" + "=" * 80)
            logger.info("STEP 2: Loading predefined topics")
            logger.info("=" * 80)
            topics = self.sheets_client.get_topic_names()

            if not topics:
                logger.error("No topics found. Please add topics to the Google Sheet.")
                return

            logger.info(f"Found {len(topics)} topics: {', '.join(topics)}")

            # Step 3: Fetch articles from all sources
            logger.info("\n" + "=" * 80)
            logger.info("STEP 3: Fetching articles from sources")
            logger.info("=" * 80)
            all_articles = []

            for source in sources:
                source_name = source.get('nombre', 'Unknown')
                logger.info(f"Fetching from: {source_name}")

                articles = self.news_fetcher.fetch_from_source(source)
                all_articles.extend(articles)

                logger.info(f"  → Fetched {len(articles)} articles from {source_name}")

            logger.info(f"Total articles fetched: {len(all_articles)}")

            if not all_articles:
                logger.warning("No articles fetched. Exiting.")
                return

            # Step 4: Filter duplicates
            logger.info("\n" + "=" * 80)
            logger.info("STEP 4: Filtering duplicate articles")
            logger.info("=" * 80)
            unique_articles = self.deduplicator.filter_duplicates(all_articles)
            logger.info(f"Unique articles after deduplication: {len(unique_articles)}")

            if not unique_articles:
                logger.info("No new articles to process. Exiting.")
                return

            # Step 5: Process content for each article
            logger.info("\n" + "=" * 80)
            logger.info("STEP 5: Processing article content")
            logger.info("=" * 80)
            processed_articles = []

            for i, article in enumerate(unique_articles[:settings.MAX_ARTICLES_PER_DAY], 1):
                logger.info(f"Processing article {i}/{len(unique_articles[:settings.MAX_ARTICLES_PER_DAY])}: {article.get('title', 'Unknown')[:50]}...")

                # Process content
                processed_article = self.content_processor.process_article(article)

                # Create archive link
                logger.info(f"  → Creating archive link...")
                archive_url = self.archive_service.create_archive_link(article.get('url', ''))
                processed_article['url_sin_paywall'] = archive_url

                # Generate content hash
                content_hash = self.deduplicator.get_content_hash(
                    processed_article.get('content_truncated', '')
                )
                processed_article['hash_contenido'] = content_hash

                processed_articles.append(processed_article)

            logger.info(f"Processed {len(processed_articles)} articles")

            # Step 6: Classify articles by topic
            logger.info("\n" + "=" * 80)
            logger.info("STEP 6: Classifying articles by topic using OpenAI")
            logger.info("=" * 80)
            classified_articles = self.openai_client.classify_articles_batch(
                processed_articles,
                topics
            )

            # Log classification results
            for article in classified_articles:
                logger.info(f"  → '{article.get('title', 'Unknown')[:40]}' → {article.get('tema', 'Unknown')}")

            # Step 7: Save processed articles to Google Sheets
            logger.info("\n" + "=" * 80)
            logger.info("STEP 7: Saving processed articles to Google Sheets")
            logger.info("=" * 80)

            articles_to_save = []
            for article in classified_articles:
                articles_to_save.append({
                    'fecha_publicacion': article.get('published_date', ''),
                    'titulo': article.get('title', ''),
                    'fuente': article.get('source', ''),
                    'tema': article.get('tema', ''),
                    'contenido_completo': article.get('content', ''),  # Full content
                    'contenido_truncado': article.get('content_truncated', ''),  # Truncated for classification
                    'url_original': article.get('url', ''),
                    'url_sin_paywall': article.get('url_sin_paywall', ''),
                    'hash_contenido': article.get('hash_contenido', '')
                })

            self.sheets_client.add_processed_articles_batch(articles_to_save)
            logger.info(f"Saved {len(articles_to_save)} articles to Google Sheets")

            # Step 8: Generate newsletter
            logger.info("\n" + "=" * 80)
            logger.info("STEP 8: Generating newsletter using OpenAI")
            logger.info("=" * 80)
            newsletter_content = self.openai_client.generate_newsletter(
                classified_articles,
                topics
            )

            # Step 9: Save newsletter to Google Sheets
            logger.info("\n" + "=" * 80)
            logger.info("STEP 9: Saving newsletter to Google Sheets")
            logger.info("=" * 80)

            topics_covered = ', '.join(set(a.get('tema', '') for a in classified_articles))

            self.sheets_client.add_newsletter(
                contenido=newsletter_content,
                num_articulos=len(classified_articles),
                temas_cubiertos=topics_covered
            )

            logger.info("Newsletter saved successfully!")

            # Summary
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.info("\n" + "=" * 80)
            logger.info("PIPELINE COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            logger.info(f"Duration: {duration:.2f} seconds")
            logger.info(f"Articles processed: {len(classified_articles)}")
            logger.info(f"Topics covered: {topics_covered}")
            logger.info(f"Newsletter saved to Google Sheet")
            logger.info("=" * 80)

            # Print newsletter preview
            print("\n" + "=" * 80)
            print("NEWSLETTER PREVIEW")
            print("=" * 80)
            print(newsletter_content[:1000])
            if len(newsletter_content) > 1000:
                print("\n... (truncated, see Google Sheet for full content)")
            print("=" * 80)

        except Exception as e:
            logger.error(f"Pipeline failed with error: {e}", exc_info=True)
            raise


def main():
    """Main entry point"""
    try:
        pipeline = NewsletterPipeline()
        pipeline.run()
    except KeyboardInterrupt:
        logger.info("\nPipeline interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
