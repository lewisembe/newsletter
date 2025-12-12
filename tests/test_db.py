"""
Unit tests for SQLite Database Manager (common/db.py)

Tests cover:
- Database initialization
- CRUD operations
- UNIQUE constraint enforcement
- Timestamp tracking (extracted_at + last_extracted_at)
- Batch upsert with deduplication
- Query operations (by date, content type)
- Statistics and reporting

Author: Newsletter Utils Team
Created: 2025-11-10
"""

import pytest
import os
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.postgres_db import PostgreSQLURLDatabase


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")

    db = PostgreSQLURLDatabase(db_path)
    db.init_db()

    yield db

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_url_data():
    """Sample URL data for testing"""
    return {
        'url': 'https://example.com/article-123',
        'title': 'Test Article',
        'source': 'https://example.com',
        'content_type': 'contenido',
        'content_subtype': 'noticia',
        'classification_method': 'regex_rule',
        'rule_name': 'example_articles'
    }


class TestDatabaseInitialization:
    """Test database initialization and schema creation"""

    def test_init_creates_tables(self, temp_db):
        """Test that init_db creates all required tables"""
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()

            # Check urls table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='urls'")
            assert cursor.fetchone() is not None

            # Check processing_logs table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processing_logs'")
            assert cursor.fetchone() is not None

    def test_init_creates_indices(self, temp_db):
        """Test that init_db creates all required indices"""
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()

            # Get all indices
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indices = {row[0] for row in cursor.fetchall()}

            # Check critical indices exist
            required_indices = {
                'idx_url', 'idx_extracted_at', 'idx_last_extracted_at',
                'idx_content_type', 'idx_source', 'idx_extracted_content'
            }

            assert required_indices.issubset(indices)

    def test_init_drop_existing(self):
        """Test that init_db with drop_existing=True removes old data"""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test.db")

        try:
            db = PostgreSQLURLDatabase(db_path)
            db.init_db()

            # Add test data
            db.add_url({
                'url': 'https://example.com/test',
                'title': 'Test',
                'source': 'https://example.com',
                'content_type': 'contenido',
                'classification_method': 'llm_api'
            })

            # Verify data exists
            assert db.get_stats()['total_urls'] == 1

            # Reinitialize with drop_existing=True
            db.init_db(drop_existing=True)

            # Verify data is gone
            assert db.get_stats()['total_urls'] == 0

        finally:
            shutil.rmtree(temp_dir)


class TestCRUDOperations:
    """Test Create, Read, Update, Delete operations"""

    def test_add_url_success(self, temp_db, sample_url_data):
        """Test adding a new URL"""
        row_id = temp_db.add_url(sample_url_data)

        assert row_id is not None
        assert row_id > 0

    def test_add_url_duplicate_fails(self, temp_db, sample_url_data):
        """Test that adding duplicate URL returns None"""
        # Add first time
        row_id1 = temp_db.add_url(sample_url_data)
        assert row_id1 is not None

        # Add second time (duplicate)
        row_id2 = temp_db.add_url(sample_url_data)
        assert row_id2 is None

    def test_add_url_sets_timestamps(self, temp_db, sample_url_data):
        """Test that add_url sets extracted_at and last_extracted_at"""
        before = datetime.now(timezone.utc)
        temp_db.add_url(sample_url_data)
        after = datetime.now(timezone.utc)

        url_data = temp_db.get_url(sample_url_data['url'])

        # Parse timestamps
        extracted_at = datetime.fromisoformat(url_data['extracted_at'].replace('Z', '+00:00'))
        last_extracted_at = datetime.fromisoformat(url_data['last_extracted_at'].replace('Z', '+00:00'))

        # Check timestamps are within reasonable range
        assert before <= extracted_at <= after
        assert before <= last_extracted_at <= after

        # Check both timestamps are equal for new URLs
        assert url_data['extracted_at'] == url_data['last_extracted_at']

    def test_get_url_success(self, temp_db, sample_url_data):
        """Test retrieving a URL by its URL string"""
        temp_db.add_url(sample_url_data)

        retrieved = temp_db.get_url(sample_url_data['url'])

        assert retrieved is not None
        assert retrieved['url'] == sample_url_data['url']
        assert retrieved['title'] == sample_url_data['title']
        assert retrieved['content_type'] == sample_url_data['content_type']

    def test_get_url_not_found(self, temp_db):
        """Test that get_url returns None for non-existent URL"""
        result = temp_db.get_url('https://nonexistent.com/article')

        assert result is None

    def test_update_url_success(self, temp_db, sample_url_data):
        """Test updating an existing URL"""
        temp_db.add_url(sample_url_data)

        # Update title
        success = temp_db.update_url(sample_url_data['url'], {'title': 'Updated Title'})

        assert success is True

        # Verify update
        updated = temp_db.get_url(sample_url_data['url'])
        assert updated['title'] == 'Updated Title'

    def test_update_url_not_found(self, temp_db):
        """Test updating non-existent URL returns False"""
        success = temp_db.update_url('https://nonexistent.com/article', {'title': 'Test'})

        assert success is False

    def test_get_all_urls(self, temp_db):
        """Test retrieving all URLs"""
        # Add multiple URLs
        for i in range(5):
            temp_db.add_url({
                'url': f'https://example.com/article-{i}',
                'title': f'Article {i}',
                'source': 'https://example.com',
                'content_type': 'contenido',
                'classification_method': 'regex_rule'
            })

        all_urls = temp_db.get_all_urls()

        assert len(all_urls) == 5

    def test_get_all_urls_with_limit(self, temp_db):
        """Test retrieving URLs with limit"""
        # Add multiple URLs
        for i in range(10):
            temp_db.add_url({
                'url': f'https://example.com/article-{i}',
                'title': f'Article {i}',
                'source': 'https://example.com',
                'content_type': 'contenido',
                'classification_method': 'regex_rule'
            })

        limited_urls = temp_db.get_all_urls(limit=3)

        assert len(limited_urls) == 3


class TestBatchUpsert:
    """Test batch upsert operations with deduplication"""

    def test_batch_upsert_all_new(self, temp_db):
        """Test batch upsert with all new URLs"""
        urls = [
            {
                'url': f'https://example.com/article-{i}',
                'title': f'Article {i}',
                'source': 'https://example.com',
                'content_type': 'contenido',
                'classification_method': 'regex_rule'
            }
            for i in range(5)
        ]

        stats = temp_db.batch_upsert(urls)

        assert stats['inserted'] == 5
        assert stats['updated'] == 0
        assert stats['errors'] == 0

    def test_batch_upsert_all_duplicates(self, temp_db):
        """Test batch upsert with all duplicate URLs"""
        urls = [
            {
                'url': f'https://example.com/article-{i}',
                'title': f'Article {i}',
                'source': 'https://example.com',
                'content_type': 'contenido',
                'classification_method': 'regex_rule'
            }
            for i in range(5)
        ]

        # Insert first time
        temp_db.batch_upsert(urls)

        # Insert again (all duplicates)
        stats = temp_db.batch_upsert(urls)

        assert stats['inserted'] == 0
        assert stats['updated'] == 5
        assert stats['errors'] == 0

    def test_batch_upsert_mixed(self, temp_db):
        """Test batch upsert with mix of new and duplicate URLs"""
        # Add 3 URLs initially
        initial_urls = [
            {
                'url': f'https://example.com/article-{i}',
                'title': f'Article {i}',
                'source': 'https://example.com',
                'content_type': 'contenido',
                'classification_method': 'regex_rule'
            }
            for i in range(3)
        ]

        temp_db.batch_upsert(initial_urls)

        # Batch upsert with 2 duplicates + 2 new
        mixed_urls = [
            initial_urls[0],  # Duplicate
            initial_urls[1],  # Duplicate
            {
                'url': 'https://example.com/article-new-1',
                'title': 'New Article 1',
                'source': 'https://example.com',
                'content_type': 'contenido',
                'classification_method': 'llm_api'
            },
            {
                'url': 'https://example.com/article-new-2',
                'title': 'New Article 2',
                'source': 'https://example.com',
                'content_type': 'contenido',
                'classification_method': 'llm_api'
            }
        ]

        stats = temp_db.batch_upsert(mixed_urls)

        assert stats['inserted'] == 2
        assert stats['updated'] == 2
        assert stats['errors'] == 0

    def test_batch_upsert_preserves_extracted_at(self, temp_db):
        """Test that batch upsert preserves original extracted_at for duplicates"""
        original_time = '2025-11-09T10:00:00Z'

        # Add URL with specific extracted_at
        temp_db.add_url({
            'url': 'https://example.com/article-1',
            'title': 'Original Title',
            'source': 'https://example.com',
            'content_type': 'contenido',
            'classification_method': 'regex_rule',
            'extracted_at': original_time,
            'last_extracted_at': original_time
        })

        # Batch upsert same URL (simulating re-extraction)
        temp_db.batch_upsert([
            {
                'url': 'https://example.com/article-1',
                'title': 'Updated Title',
                'source': 'https://example.com',
                'content_type': 'contenido',
                'classification_method': 'regex_rule'
            }
        ])

        # Verify extracted_at is preserved
        updated_url = temp_db.get_url('https://example.com/article-1')

        # extracted_at should be original
        assert updated_url['extracted_at'] == original_time

        # last_extracted_at should be updated (newer)
        assert updated_url['last_extracted_at'] != original_time


class TestQueryOperations:
    """Test query operations (by date, content type, etc.)"""

    def test_get_urls_by_date(self, temp_db):
        """Test retrieving URLs by extraction date"""
        target_date = '2025-11-10'

        # Add URLs with different dates
        temp_db.add_url({
            'url': 'https://example.com/article-1',
            'title': 'Article 1',
            'source': 'https://example.com',
            'content_type': 'contenido',
            'classification_method': 'regex_rule',
            'extracted_at': '2025-11-10T08:00:00Z'
        })

        temp_db.add_url({
            'url': 'https://example.com/article-2',
            'title': 'Article 2',
            'source': 'https://example.com',
            'content_type': 'contenido',
            'classification_method': 'regex_rule',
            'extracted_at': '2025-11-11T08:00:00Z'
        })

        # Query by date
        results = temp_db.get_urls_by_date(target_date)

        assert len(results) == 1
        assert results[0]['url'] == 'https://example.com/article-1'

    def test_get_urls_by_date_with_content_type_filter(self, temp_db):
        """Test retrieving URLs by date and content type"""
        target_date = '2025-11-10'

        # Add URLs with same date but different content types
        temp_db.add_url({
            'url': 'https://example.com/article-1',
            'title': 'Article 1',
            'source': 'https://example.com',
            'content_type': 'contenido',
            'classification_method': 'regex_rule',
            'extracted_at': f'{target_date}T08:00:00Z'
        })

        temp_db.add_url({
            'url': 'https://example.com/nav-1',
            'title': 'Navigation',
            'source': 'https://example.com',
            'content_type': 'no_contenido',
            'classification_method': 'regex_rule',
            'extracted_at': f'{target_date}T08:00:00Z'
        })

        # Query by date and content type
        results = temp_db.get_urls_by_date(target_date, content_type='contenido')

        assert len(results) == 1
        assert results[0]['content_type'] == 'contenido'

    def test_get_content_urls(self, temp_db):
        """Test get_content_urls convenience method"""
        target_date = '2025-11-10'

        # Add mix of content types
        temp_db.add_url({
            'url': 'https://example.com/article-1',
            'title': 'Article 1',
            'source': 'https://example.com',
            'content_type': 'contenido',
            'classification_method': 'regex_rule',
            'extracted_at': f'{target_date}T08:00:00Z'
        })

        temp_db.add_url({
            'url': 'https://example.com/nav-1',
            'title': 'Navigation',
            'source': 'https://example.com',
            'content_type': 'no_contenido',
            'classification_method': 'regex_rule',
            'extracted_at': f'{target_date}T08:00:00Z'
        })

        # Query content URLs
        results = temp_db.get_content_urls(target_date)

        assert len(results) == 1
        assert results[0]['content_type'] == 'contenido'


class TestStatistics:
    """Test statistics and reporting"""

    def test_get_stats_empty_db(self, temp_db):
        """Test statistics on empty database"""
        stats = temp_db.get_stats()

        assert stats['total_urls'] == 0
        assert stats['contenido_count'] == 0
        assert stats['no_contenido_count'] == 0
        assert stats['sources_count'] == 0
        assert stats['date_range'] is None

    def test_get_stats_with_data(self, temp_db):
        """Test statistics with data"""
        # Add URLs with different content types and sources
        urls = [
            {
                'url': 'https://source1.com/article-1',
                'title': 'Article 1',
                'source': 'https://source1.com',
                'content_type': 'contenido',
                'classification_method': 'regex_rule'
            },
            {
                'url': 'https://source1.com/article-2',
                'title': 'Article 2',
                'source': 'https://source1.com',
                'content_type': 'contenido',
                'classification_method': 'regex_rule'
            },
            {
                'url': 'https://source2.com/nav-1',
                'title': 'Navigation',
                'source': 'https://source2.com',
                'content_type': 'no_contenido',
                'classification_method': 'regex_rule'
            }
        ]

        temp_db.batch_upsert(urls)

        stats = temp_db.get_stats()

        assert stats['total_urls'] == 3
        assert stats['contenido_count'] == 2
        assert stats['no_contenido_count'] == 1
        assert stats['sources_count'] == 2
        assert stats['date_range'] is not None


class TestContentTypeConstraints:
    """Test CHECK constraints on content_type and other fields"""

    def test_invalid_content_type_fails(self, temp_db):
        """Test that invalid content_type values are rejected"""
        with pytest.raises(Exception):  # sqlite3.IntegrityError
            temp_db.add_url({
                'url': 'https://example.com/article-1',
                'title': 'Article 1',
                'source': 'https://example.com',
                'content_type': 'invalid_type',  # Invalid
                'classification_method': 'regex_rule'
            })

    def test_valid_content_subtypes(self, temp_db):
        """Test that valid content_subtype values are accepted"""
        # Test 'noticia'
        temp_db.add_url({
            'url': 'https://example.com/article-1',
            'title': 'Article 1',
            'source': 'https://example.com',
            'content_type': 'contenido',
            'content_subtype': 'noticia',
            'classification_method': 'regex_rule'
        })

        # Test 'otros'
        temp_db.add_url({
            'url': 'https://example.com/article-2',
            'title': 'Article 2',
            'source': 'https://example.com',
            'content_type': 'contenido',
            'content_subtype': 'otros',
            'classification_method': 'regex_rule'
        })

        # Test NULL (optional)
        temp_db.add_url({
            'url': 'https://example.com/article-3',
            'title': 'Article 3',
            'source': 'https://example.com',
            'content_type': 'contenido',
            'content_subtype': None,
            'classification_method': 'regex_rule'
        })

        assert temp_db.get_stats()['total_urls'] == 3


class TestProcessingLogs:
    """Test processing logs functionality"""

    def test_log_processing(self, temp_db):
        """Test logging processing events"""
        temp_db.log_processing(
            stage='01_extract_urls',
            event_type='success',
            message='Completed successfully',
            stats={'urls_extracted': 100},
            source='elpais'
        )

        # Verify log was created
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM processing_logs WHERE stage = '01_extract_urls'")
            row = cursor.fetchone()

            assert row is not None
            assert row['event_type'] == 'success'
            assert row['source'] == 'elpais'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
