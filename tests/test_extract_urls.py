"""
Unit tests for Stage 01: Extract URLs
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import csv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib.util

# Load the module directly
spec = importlib.util.spec_from_file_location(
    "extract_urls",
    Path(__file__).parent.parent / "stages" / "01_extract_urls.py"
)
extract_urls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract_urls)


class TestLoadSources:
    """Tests for load_sources function."""

    def test_load_sources_success(self, tmp_path):
        """Test loading sources from valid YAML file."""
        # Create temporary config file
        config_file = tmp_path / "sources.yml"
        config_file.write_text("""
sources:
  - id: test1
    name: Test Source 1
    url: https://test1.com
    selectors:
      - "a.link"
    enabled: true
  - id: test2
    name: Test Source 2
    url: https://test2.com
    selectors:
      - "a"
    enabled: false
""")

        sources = extract_urls.load_sources(str(config_file))

        assert len(sources) == 1
        assert sources[0]['id'] == 'test1'
        assert sources[0]['enabled'] is True

    def test_load_sources_file_not_found(self):
        """Test handling of missing config file."""
        sources = extract_urls.load_sources("nonexistent.yml")
        assert sources == []


class TestExtractUrlsFromSource:
    """Tests for extract_urls_from_source function."""

    @patch('extract_urls.filter_news_urls')
    def test_extract_urls_success(self, mock_filter):
        """Test successful URL extraction from a source."""
        # Mock Selenium driver
        mock_driver = Mock()
        mock_driver.get_page.return_value = True
        mock_driver.extract_links.return_value = [
            {'url': 'https://test.com/article1', 'title': 'Article 1'},
            {'url': 'https://test.com/article2', 'title': 'Article 2'}
        ]

        # Mock LLM filter
        mock_filter.return_value = [
            {'url': 'https://test.com/article1', 'title': 'Article 1'}
        ]

        # Mock LLM client
        mock_llm = Mock()

        source = {
            'id': 'test',
            'name': 'Test Source',
            'url': 'https://test.com',
            'selectors': ['a.link']
        }

        urls = extract_urls.extract_urls_from_source(source, mock_driver, mock_llm)

        assert len(urls) == 1
        assert urls[0]['url'] == 'https://test.com/article1'
        assert urls[0]['source'] == 'https://test.com'
        assert urls[0]['source_id'] == 'test'

        mock_driver.get_page.assert_called_once_with('https://test.com')
        mock_driver.extract_links.assert_called_once()

    def test_extract_urls_page_load_failed(self):
        """Test handling when page fails to load."""
        mock_driver = Mock()
        mock_driver.get_page.return_value = False

        mock_llm = Mock()

        source = {
            'id': 'test',
            'name': 'Test Source',
            'url': 'https://test.com',
            'selectors': ['a']
        }

        urls = extract_urls.extract_urls_from_source(source, mock_driver, mock_llm)

        assert urls == []


class TestSaveUrlsToCsv:
    """Tests for save_urls_to_csv function."""

    def test_save_csv_success(self, tmp_path):
        """Test saving URLs to CSV file."""
        output_file = tmp_path / "test_urls.csv"

        urls = [
            {
                'url': 'https://test.com/1',
                'title': 'Test Article 1',
                'source': 'https://test.com',
                'content_type': 'contenido_noticia',
                'extracted_at': '2025-11-09T10:00:00'
            },
            {
                'url': 'https://test.com/2',
                'title': 'Test Article 2',
                'source': 'https://test.com',
                'content_type': 'contenido_otros',
                'extracted_at': '2025-11-09T10:00:00'
            }
        ]

        extract_urls.save_urls_to_csv(urls, str(output_file))

        # Verify file exists and has correct content
        assert output_file.exists()

        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]['url'] == 'https://test.com/1'
        assert rows[0]['title'] == 'Test Article 1'
        assert rows[0]['content_type'] == 'contenido_noticia'
        assert rows[1]['url'] == 'https://test.com/2'
        assert rows[1]['content_type'] == 'contenido_otros'

    def test_save_csv_with_all_content_types(self, tmp_path):
        """Test saving URLs with all 3 new content types."""
        output_file = tmp_path / "test_urls_all_types.csv"

        urls = [
            {
                'url': 'https://test.com/news',
                'title': 'Breaking News',
                'source': 'https://test.com',
                'content_type': 'contenido_noticia',
                'extracted_at': '2025-11-09T10:00:00'
            },
            {
                'url': 'https://test.com/opinion',
                'title': 'Opinion Column',
                'source': 'https://test.com',
                'content_type': 'contenido_otros',
                'extracted_at': '2025-11-09T10:00:00'
            },
            {
                'url': 'https://test.com/nav',
                'title': 'Navigation',
                'source': 'https://test.com',
                'content_type': 'no_contenido',
                'extracted_at': '2025-11-09T10:00:00'
            }
        ]

        extract_urls.save_urls_to_csv(urls, str(output_file))

        # Verify all content types are preserved
        assert output_file.exists()

        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            rows = list(reader)

        assert len(rows) == 3
        content_types = [row['content_type'] for row in rows]
        assert 'contenido_noticia' in content_types
        assert 'contenido_otros' in content_types
        assert 'no_contenido' in content_types


class TestMain:
    """Tests for main function."""

    @patch('extract_urls.create_driver_from_env')
    @patch('extract_urls.LLMClient')
    @patch('extract_urls.load_sources')
    @patch('extract_urls.save_urls_to_csv')
    def test_main_success(
        self,
        mock_save,
        mock_load_sources,
        mock_llm_class,
        mock_driver_factory,
        tmp_path
    ):
        """Test successful execution of main function."""
        # Mock sources
        mock_load_sources.return_value = [
            {
                'id': 'test',
                'name': 'Test Source',
                'url': 'https://test.com',
                'selectors': ['a']
            }
        ]

        # Mock Selenium driver
        mock_driver = MagicMock()
        mock_driver.get_page.return_value = True
        mock_driver.extract_links.return_value = [
            {'url': 'https://test.com/article', 'title': 'Test'}
        ]
        mock_driver_factory.return_value.__enter__.return_value = mock_driver

        # Mock LLM client
        mock_llm = Mock()
        mock_llm_class.return_value = mock_llm

        # Mock filter_news_urls to return the links
        with patch('extract_urls.filter_news_urls') as mock_filter:
            mock_filter.return_value = [
                {'url': 'https://test.com/article', 'title': 'Test'}
            ]

            # Run main
            exit_code = extract_urls.main(run_date='2025-11-09')

        assert exit_code == 0
        mock_save.assert_called_once()

    @patch('extract_urls.load_sources')
    def test_main_no_sources(self, mock_load_sources):
        """Test main function when no sources are configured."""
        mock_load_sources.return_value = []

        exit_code = extract_urls.main(run_date='2025-11-09')

        assert exit_code == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
