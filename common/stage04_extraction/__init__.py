"""
Stage 04 Extraction - Content Extraction Utilities

Provides utilities for extracting full article content from URLs:
- XPath cache management for domain-specific selectors
- Paywall detection using LLM
- Archive.today fetching with Selenium
- Multiple extraction methods (newspaper, readability, LLM XPath discovery)
- Content cleaning and validation

Author: Newsletter Utils Team
Created: 2025-11-13
"""

from .xpath_cache import (
    load_xpath_cache,
    find_cached_xpath,
    update_xpath_cache,
    get_url_pattern,
    cleanup_xpath_cache
)

from .paywall_validator import detect_paywall_with_llm

from .archive_fetcher import fetch_archive_selenium

from .paywall_bypass import (
    fetch_without_javascript,
    fetch_with_js_disabled_selenium,
    try_paywall_bypass_strategies  # DEPRECATED: Use fetch_cascade.fetch_html_with_cascade instead
)

from .fetch_cascade import (
    fetch_with_cookies,
    fetch_direct_http,
    fetch_selenium_js_disabled,
    fetch_archive_today,
    fetch_html_with_cascade
)

from .content_validator import validate_content_quality

from .extractors import (
    extract_with_newspaper,
    extract_with_readability,
    extract_with_selector,
    extract_with_llm_xpath,
    extract_content_with_cache
)

from .content_cleaner import clean_content

__all__ = [
    # XPath cache
    'load_xpath_cache',
    'find_cached_xpath',
    'update_xpath_cache',
    'get_url_pattern',
    'cleanup_xpath_cache',
    # Paywall
    'detect_paywall_with_llm',
    # Archive
    'fetch_archive_selenium',
    # Paywall bypass (DEPRECATED)
    'fetch_without_javascript',
    'fetch_with_js_disabled_selenium',
    'try_paywall_bypass_strategies',
    # Fetch cascade (NEW - recommended)
    'fetch_with_cookies',
    'fetch_direct_http',
    'fetch_selenium_js_disabled',
    'fetch_archive_today',
    'fetch_html_with_cascade',
    # Content validation
    'validate_content_quality',
    # Extractors
    'extract_with_newspaper',
    'extract_with_readability',
    'extract_with_selector',
    'extract_with_llm_xpath',
    'extract_content_with_cache',
    # Cleaner
    'clean_content',
]
