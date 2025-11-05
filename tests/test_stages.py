"""
Example unit tests for Newsletter Bot stages

Run with: pytest tests/
"""
import pytest
from stages.stage4_deduplication import DeduplicationStage
from src.deduplicator import Deduplicator


class TestDeduplicationStage:
    """Test Stage 4: Deduplication"""

    def test_duplicate_url_detection(self):
        """Test that duplicate URLs are detected"""
        deduplicator = Deduplicator()
        stage = DeduplicationStage(deduplicator)

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
                'title': 'Article 1 Duplicate',
                'url': 'https://example.com/article1',  # Same URL
                'source': 'Test',
                'content': 'Content 1',
                'content_truncated': 'Content 1',
                'hash_contenido': 'hash1'
            }
        ]

        result = stage.execute(test_articles)

        assert result['success'] == True
        assert result['duplicates_removed'] == 1
        assert result['total_output'] == 1
        assert len(result['unique_articles']) == 1

    def test_unique_articles(self):
        """Test that unique articles are not filtered"""
        deduplicator = Deduplicator()
        stage = DeduplicationStage(deduplicator)

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
                'url': 'https://example.com/article2',  # Different URL
                'source': 'Test',
                'content': 'Content 2',
                'content_truncated': 'Content 2',
                'hash_contenido': 'hash2'
            }
        ]

        result = stage.execute(test_articles)

        assert result['success'] == True
        assert result['duplicates_removed'] == 0
        assert result['total_output'] == 2
        assert len(result['unique_articles']) == 2

    def test_validation(self):
        """Test that output validation works"""
        deduplicator = Deduplicator()
        stage = DeduplicationStage(deduplicator)

        test_articles = [
            {
                'title': 'Article 1',
                'url': 'https://example.com/article1',
                'source': 'Test',
                'content': 'Content 1',
                'content_truncated': 'Content 1',
                'hash_contenido': 'hash1'
            }
        ]

        result = stage.execute(test_articles)

        assert stage.validate_output(result) == True


# TODO: Add more test classes for other stages
# class TestSourceLoadingStage:
#     pass
#
# class TestNewsFetchingStage:
#     pass
#
# class TestContentProcessingStage:
#     pass
#
# class TestClassificationStage:
#     pass
#
# class TestNewsletterGenerationStage:
#     pass
#
# class TestPersistenceStage:
#     pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
