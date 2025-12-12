"""
XPath Cache Manager

Manages caching of XPath/CSS selectors for content extraction by domain.
Reduces LLM API calls by reusing discovered selectors for the same domain.

Author: Newsletter Utils Team
Created: 2025-11-13
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timezone
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def get_url_pattern(url: str) -> str:
    """
    Extract domain pattern from URL for cache matching.

    Includes section path if present (e.g., /news, /economia) for more specific matching.

    Examples:
        https://www.bbc.com/news/articles/xyz → www.bbc.com/news
        https://elpais.com/economia/2025/... → elpais.com/economia
        https://www.ft.com/content/abc → www.ft.com/content
        https://example.com/article → example.com

    Args:
        url: Full URL string

    Returns:
        Domain pattern string for matching
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc  # www.bbc.com

        # Get path parts
        path_parts = parsed.path.strip('/').split('/')

        # Include first path segment if it looks like a section (not an ID/slug)
        if path_parts and path_parts[0]:
            section = path_parts[0]
            # Include section if it's not numeric and reasonably short (likely a section)
            if not section.isdigit() and len(section) <= 20 and not any(c in section for c in ['-', '_']):
                return f"{domain}/{section}"

        return domain

    except Exception as e:
        logger.warning(f"Failed to parse URL pattern from {url}: {e}")
        return urlparse(url).netloc  # Fallback to domain only


def load_xpath_cache(cache_path: str = "config/xpath_cache.yml") -> Dict:
    """
    Load XPath cache from YAML file.

    Args:
        cache_path: Path to cache YAML file

    Returns:
        Dictionary mapping URL patterns to selector configurations
    """
    cache_file = Path(cache_path)

    if not cache_file.exists():
        logger.info(f"XPath cache not found at {cache_path}, starting with empty cache")
        return {}

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache = yaml.safe_load(f) or {}

        logger.info(f"Loaded XPath cache: {len(cache)} entries from {cache_path}")
        return cache

    except Exception as e:
        logger.error(f"Failed to load XPath cache from {cache_path}: {e}")
        return {}


def find_cached_xpath(url: str, cache: Dict) -> Optional[Dict]:
    """
    Find matching XPath selector from cache for a URL.

    Tries multiple matching strategies in order of specificity:
    1. Exact pattern match (domain/section)
    2. Domain-only match (fallback)

    Args:
        url: URL to find selector for
        cache: Loaded XPath cache dictionary

    Returns:
        Selector configuration dict if found, None otherwise
    """
    if not cache:
        return None

    pattern = get_url_pattern(url)

    # Try exact match first (most specific)
    if pattern in cache:
        logger.debug(f"Found exact cache match for pattern: {pattern}")
        return cache[pattern]

    # Try domain-only match (fallback)
    domain = pattern.split('/')[0]
    if domain in cache and domain != pattern:
        logger.debug(f"Found domain cache match: {domain} for pattern {pattern}")
        return cache[domain]

    logger.debug(f"No cache match found for {pattern}")
    return None


def update_xpath_cache(
    url: str,
    selector: str,
    selector_type: str,
    confidence: int,
    success: bool,
    cache_path: str = "config/xpath_cache.yml"
) -> None:
    """
    Update XPath cache with extraction result.

    If pattern exists, updates success/fail stats.
    If pattern is new, creates new cache entry.

    Args:
        url: URL that was extracted
        selector: CSS selector or XPath used
        selector_type: 'css' or 'xpath'
        confidence: Confidence score (0-100) from LLM
        success: Whether extraction succeeded
        cache_path: Path to cache file
    """
    try:
        # Load existing cache
        cache_file = Path(cache_path)
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = yaml.safe_load(f) or {}
        else:
            cache = {}

        pattern = get_url_pattern(url)
        now = datetime.now(timezone.utc).isoformat()

        if pattern in cache:
            # Update existing entry
            entry = cache[pattern]
            entry['last_used_at'] = now

            if success:
                entry['success_count'] = entry.get('success_count', 0) + 1
            else:
                entry['fail_count'] = entry.get('fail_count', 0) + 1

            total = entry['success_count'] + entry['fail_count']
            entry['success_rate'] = round(entry['success_count'] / total, 2) if total > 0 else 0.0

            logger.info(
                f"Updated cache for {pattern}: "
                f"success_rate={entry['success_rate']} "
                f"({entry['success_count']}/{total})"
            )

        else:
            # Create new entry
            cache[pattern] = {
                'url_pattern': pattern,
                'content_selector': selector,
                'selector_type': selector_type,
                'confidence': confidence,
                'discovered_at': now,
                'last_used_at': now,
                'success_count': 1 if success else 0,
                'fail_count': 0 if success else 1,
                'success_rate': 1.0 if success else 0.0
            }

            logger.info(f"Added new cache entry for {pattern}: selector={selector}")

        # Save cache
        with open(cache_file, 'w', encoding='utf-8') as f:
            yaml.dump(
                cache,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=True
            )

    except Exception as e:
        logger.error(f"Failed to update XPath cache: {e}")


def cleanup_xpath_cache(
    cache_path: str = "config/xpath_cache.yml",
    min_success_rate: float = 0.5,
    min_attempts: int = 5
) -> int:
    """
    Remove low-performing entries from cache.

    Removes entries with:
    - Success rate < min_success_rate AND attempts >= min_attempts

    This prevents accumulation of outdated or broken selectors.

    Args:
        cache_path: Path to cache file
        min_success_rate: Minimum success rate to keep (0.0-1.0)
        min_attempts: Minimum attempts before considering removal

    Returns:
        Number of entries removed
    """
    try:
        cache_file = Path(cache_path)

        if not cache_file.exists():
            logger.info("No cache file to clean up")
            return 0

        with open(cache_file, 'r', encoding='utf-8') as f:
            cache = yaml.safe_load(f) or {}

        before = len(cache)

        # Filter entries
        cleaned_cache = {}
        for pattern, entry in cache.items():
            total_attempts = entry.get('success_count', 0) + entry.get('fail_count', 0)
            success_rate = entry.get('success_rate', 0)

            # Keep if:
            # - High success rate, OR
            # - Not enough attempts yet to judge
            if success_rate >= min_success_rate or total_attempts < min_attempts:
                cleaned_cache[pattern] = entry
            else:
                logger.info(
                    f"Removing low-performing entry: {pattern} "
                    f"(success_rate={success_rate}, attempts={total_attempts})"
                )

        after = len(cleaned_cache)
        removed = before - after

        if removed > 0:
            # Save cleaned cache
            with open(cache_file, 'w', encoding='utf-8') as f:
                yaml.dump(
                    cleaned_cache,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=True
                )

            logger.info(f"Cache cleanup: removed {removed} entries ({before} → {after})")
        else:
            logger.info(f"Cache cleanup: no entries removed ({before} entries)")

        return removed

    except Exception as e:
        logger.error(f"Cache cleanup failed: {e}")
        return 0
