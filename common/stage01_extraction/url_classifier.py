"""
URL classification utilities using regex rules.

This module provides functions to classify URLs using cached regex patterns,
with fallback to LLM classification for URLs that don't match any rules.
"""

import os
import re
import json
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import yaml
from datetime import datetime

logger = logging.getLogger(__name__)


class RuleBasedClassifier:
    """Classifier that uses regex rules to categorize URLs."""

    def __init__(
        self,
        rules_path: str = "config/url_classification_rules.yml",
        cached_urls_path: str = "config/cached_no_content_urls.yml"
    ):
        """
        Initialize the rule-based classifier.

        Args:
            rules_path: Path to the YAML file containing classification rules
            cached_urls_path: Path to the YAML file with cached no_contenido URLs
        """
        self.rules_path = rules_path
        self.cached_urls_path = cached_urls_path
        self.rules = None
        self.global_rules = []
        self.source_rules = {}
        self.cached_no_content_urls = {}  # Dict[source_domain, Set[url]]
        self.load_rules()
        self.load_cached_urls()

    def load_rules(self) -> bool:
        """
        Load classification rules from YAML file.

        Returns:
            True if rules were loaded successfully, False otherwise
        """
        try:
            rules_file = Path(self.rules_path)

            if not rules_file.exists():
                logger.warning(f"Rules file not found: {self.rules_path}")
                return False

            with open(rules_file, 'r', encoding='utf-8') as f:
                self.rules = yaml.safe_load(f)

            # Extract global rules
            self.global_rules = self.rules.get('global_rules', [])

            # Extract per-source rules
            sources_config = self.rules.get('sources', {})
            for source_domain, config in sources_config.items():
                self.source_rules[source_domain] = config.get('rules', [])

            total_global = len(self.global_rules)
            total_source = sum(len(rules) for rules in self.source_rules.values())

            logger.info(f"Loaded {total_global} global rules and {total_source} source-specific rules from {self.rules_path}")

            return True

        except Exception as e:
            logger.error(f"Failed to load rules from {self.rules_path}: {e}")
            return False

    def load_cached_urls(self) -> bool:
        """
        Load cached no_contenido URLs from YAML file.

        Returns:
            True if cached URLs were loaded successfully, False otherwise
        """
        try:
            cached_file = Path(self.cached_urls_path)

            if not cached_file.exists():
                logger.info(f"Cached URLs file not found: {self.cached_urls_path} (will be created on first update)")
                return False

            with open(cached_file, 'r', encoding='utf-8') as f:
                cached_data = yaml.safe_load(f)

            # Extract URLs by source
            sources_data = cached_data.get('sources', {})
            for source_domain, config in sources_data.items():
                urls_list = config.get('urls', [])
                # Store as set for fast lookup
                self.cached_no_content_urls[source_domain] = set(urls_list)

            total_cached = sum(len(urls) for urls in self.cached_no_content_urls.values())
            logger.info(f"Loaded {total_cached} cached no_contenido URLs from {self.cached_urls_path}")

            return True

        except Exception as e:
            logger.error(f"Failed to load cached URLs from {self.cached_urls_path}: {e}")
            return False

    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from URL for source-specific rule matching.

        Args:
            url: Full URL

        Returns:
            Domain (e.g., 'ft.com', 'bbc.com')
        """
        # Simple domain extraction - match common patterns
        match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if match:
            return match.group(1)
        return ""

    def has_rules_for_source(self, source_id: str) -> bool:
        """
        Check if rules exist for a specific source.

        Args:
            source_id: Source identifier (e.g., 'elconfidencial', 'bbc', 'ft')

        Returns:
            True if source-specific rules exist, False otherwise
        """
        if not self.rules or not self.source_rules:
            return False

        # Check for exact match
        if source_id in self.source_rules and len(self.source_rules[source_id]) > 0:
            return True

        # Check for domain variations (e.g., 'ft' vs 'ft.com')
        for source_key in self.source_rules.keys():
            if source_id in source_key or source_key in source_id:
                if len(self.source_rules[source_key]) > 0:
                    return True

        return False

    def classify_url(self, url: str, title: str = "") -> Optional[Tuple[str, str]]:
        """
        Classify a single URL using regex rules (LEVEL 1: content_type only).

        Priority order:
        1. Check cached no_contenido URLs (fastest)
        2. Try global regex rules (for universal patterns like live blogs, podcasts)
        3. Try source-specific regex rules
        4. Return None (fallback to LLM)

        Args:
            url: URL to classify
            title: Title of the link (optional, for context)

        Returns:
            Tuple of (content_type, rule_name) if matched, None otherwise
            content_type will be either 'contenido' or 'no_contenido'
        """
        # Extract domain for source-specific lookups
        domain = self._extract_domain(url)

        # Check both full domain and shortened versions (bbc.com -> bbc)
        possible_keys = [domain]
        if '.' in domain:
            base = domain.split('.')[0]
            possible_keys.append(base)

        # PRIORITY 1: Check cached no_contenido URLs (instant lookup)
        for key in possible_keys:
            if key in self.cached_no_content_urls:
                if url in self.cached_no_content_urls[key]:
                    logger.debug(f"URL found in cached no_contenido list: {url}")
                    return ('no_contenido', 'cached_url')

        # PRIORITY 2 & 3: Try regex rules
        if not self.rules:
            return None

        # PRIORITY 2: Try global rules FIRST (for universal patterns like live/podcast)
        for rule in self.global_rules:
            pattern = rule.get('pattern', '')
            content_type = rule.get('content_type', '')
            rule_name = rule.get('name', 'unnamed_rule')

            try:
                if re.search(pattern, url, re.IGNORECASE):
                    logger.debug(f"URL matched global rule '{rule_name}': {url}")
                    return (content_type, rule_name)
            except re.error as e:
                logger.warning(f"Invalid regex pattern in rule '{rule_name}': {e}")
                continue

        # PRIORITY 3: Try source-specific rules
        for key in possible_keys:
            if key in self.source_rules:
                for rule in self.source_rules[key]:
                    pattern = rule.get('pattern', '')
                    content_type = rule.get('content_type', '')
                    rule_name = rule.get('name', 'unnamed_rule')

                    try:
                        if re.search(pattern, url, re.IGNORECASE):
                            logger.debug(f"URL matched source rule '{rule_name}': {url}")
                            return (content_type, rule_name)
                    except re.error as e:
                        logger.warning(f"Invalid regex pattern in rule '{rule_name}': {e}")
                        continue

        # No match found
        return None

    def classify_batch(
        self,
        links: List[Dict[str, str]]
    ) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        """
        Classify a batch of URLs, separating matched from unmatched.

        Args:
            links: List of dicts with 'url' and 'title' keys

        Returns:
            Tuple of (classified_links, unclassified_links)
            - classified_links: Links with 'content_type', 'classification_method', 'rule_name' added
            - unclassified_links: Links that didn't match any rule
        """
        classified = []
        unclassified = []

        for link in links:
            url = link.get('url', '')
            title = link.get('title', '')

            result = self.classify_url(url, title)

            if result:
                content_type, rule_name = result
                # Add classification metadata
                classified_link = link.copy()
                classified_link['content_type'] = content_type
                classified_link['content_subtype'] = None  # Will be set by LLM later if needed
                classified_link['classification_method'] = 'regex_rule'
                classified_link['rule_name'] = rule_name
                classified.append(classified_link)
            else:
                unclassified.append(link)

        return classified, unclassified


def _extract_pattern_from_url(url: str, content_type: str) -> Optional[str]:
    """
    Extract a simple regex pattern from a single URL.

    Converts concrete components to regex:
    - Dates: YYYY-MM-DD → 20[0-9]{2}-[0-9]{2}-[0-9]{2}
    - Timestamps: YYYYMMDDHHMMSS → 20[0-9]{12}
    - Numeric IDs: _1234567 → _[0-9]+
    - Slugs: /some-article-title/ → /[^/]+/

    Args:
        url: URL to extract pattern from
        content_type: 'contenido' or 'no_contenido'

    Returns:
        Regex pattern string, or None if no pattern can be extracted
    """
    try:
        # Start with the URL
        pattern = url

        # Replace timestamps (14 digit dates: YYYYMMDDHHMMSS)
        pattern = re.sub(r'20[0-9]{12}', r'20[0-9]{12}', pattern)

        # Replace dates (YYYY-MM-DD, DD-MM-YYYY, YYYY/MM/DD)
        pattern = re.sub(r'20[0-9]{2}[-/][0-9]{2}[-/][0-9]{2}', r'20[0-9]{2}[-/][0-9]{2}[-/][0-9]{2}', pattern)
        pattern = re.sub(r'[0-9]{2}[-/][0-9]{2}[-/]20[0-9]{2}', r'[0-9]{2}[-/][0-9]{2}[-/]20[0-9]{2}', pattern)

        # Replace numeric IDs at end (7+ digits) - do this FIRST
        pattern = re.sub(r'_[0-9]{7,}', r'_[0-9]+', pattern)
        pattern = re.sub(r'/[0-9]{7,}/?$', r'/[0-9]+/?$', pattern)

        # Replace slug before _[0-9]+ pattern (article title before numeric ID)
        # Example: /article-title_123/ → /[^/]+_[0-9]+/
        pattern = re.sub(r'/[a-z0-9]+-[a-z0-9-]+_\[0-9\]\+', r'/[^/]+_[0-9]+', pattern, flags=re.IGNORECASE)

        # Replace ALL remaining slugs with hyphens or underscores (iteratively)
        # This catches: /por-las-esquinas/, /cafe-society/, /casa_inglesa/, etc.
        prev_pattern = ""
        max_iterations = 10
        iteration = 0
        while prev_pattern != pattern and iteration < max_iterations:
            prev_pattern = pattern
            # Replace path segments with hyphens/underscores
            pattern = re.sub(r'/[a-z0-9_]+-[a-z0-9_-]+/', r'/[^/]+/', pattern, flags=re.IGNORECASE)
            pattern = re.sub(r'/[a-z0-9_]+_[a-z0-9_-]+/', r'/[^/]+/', pattern, flags=re.IGNORECASE)
            iteration += 1

        # Escape special regex characters that we want to keep literal
        for char in ['.', '?', '(', ')']:
            pattern = pattern.replace(char, '\\' + char)

        # Make protocol optional
        pattern = pattern.replace('https://', r'https?://')
        pattern = pattern.replace('http://', r'https?://')

        # Make trailing slash optional
        if pattern.endswith('/'):
            pattern = pattern[:-1] + '/?'

        # Anchor to start
        if not pattern.startswith('^'):
            pattern = '^' + pattern

        # Add end anchor if not present
        if not pattern.endswith('$') and not pattern.endswith('/?$'):
            pattern = pattern + '$'

        return pattern

    except Exception as e:
        logger.debug(f"Could not extract pattern from {url}: {e}")
        return None


def _normalize_patterns_with_llm(
    pattern_groups: Dict[str, Dict],
    llm_client,
    model: str = "gpt-4o-mini",
    batch_size: int = 40
) -> Dict[str, Dict]:
    """
    Use LLM to normalize similar patterns into canonical forms using batched processing.

    Processes patterns in small batches, then recursively deduplicates the results
    if still too many normalized patterns remain.

    Args:
        pattern_groups: Dict mapping pattern to metadata
        llm_client: LLM client for API calls
        model: Model to use
        batch_size: Number of patterns per batch (default 40)

    Returns:
        Dict mapping normalized_pattern to metadata (with merged example_urls)
    """
    patterns_list = list(pattern_groups.keys())
    total_patterns = len(patterns_list)

    # If few patterns, process directly
    if total_patterns <= batch_size:
        return _normalize_single_batch(patterns_list, pattern_groups, llm_client, model)

    # Process in batches
    logger.info(f"Processing {total_patterns} patterns in batches of {batch_size}")

    all_normalized = {}
    for i in range(0, total_patterns, batch_size):
        batch = patterns_list[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_patterns + batch_size - 1) // batch_size

        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} patterns)")

        # Create pattern_groups dict for this batch
        batch_groups = {p: pattern_groups[p] for p in batch if p in pattern_groups}

        # Normalize this batch
        normalized_batch = _normalize_single_batch(batch, batch_groups, llm_client, model)

        # Merge results
        all_normalized.update(normalized_batch)

    logger.info(f"After batch processing: {total_patterns} patterns → {len(all_normalized)} normalized patterns")

    # Recursive deduplication if still too many patterns
    if len(all_normalized) > batch_size:
        logger.info(f"Still {len(all_normalized)} patterns, applying recursive normalization")
        return _normalize_patterns_with_llm(all_normalized, llm_client, model, batch_size)

    return all_normalized


def _normalize_single_batch(
    patterns_list: List[str],
    pattern_groups: Dict[str, Dict],
    llm_client,
    model: str = "gpt-4o-mini"
) -> Dict[str, Dict]:
    """
    Normalize a single batch of patterns using LLM.

    Args:
        patterns_list: List of pattern strings to normalize
        pattern_groups: Dict mapping patterns to their metadata
        llm_client: LLM client for API calls
        model: Model to use

    Returns:
        Dict mapping normalized_pattern to metadata
    """

    system_prompt = """Eres un experto en análisis de patrones regex.

Tu tarea es agrupar patrones regex que son VARIACIONES del mismo patrón estructural.

Ejemplos de patrones que DEBEN agruparse:
- ^https://www.bbc.com/news/articles/cx2n5k8n1nko/?$
- ^https://www.bbc.com/news/articles/c0lg5j3j3j0o/?$
→ Patrón normalizado: ^https://www\\.bbc\\.com/news/articles/[^/]+/?$

- ^https://www.ft.com/content/abc-def-123/?$
- ^https://www.ft.com/content/xyz-ghi-456/?$
→ Patrón normalizado: ^https://www\\.ft\\.com/content/[^/]+/?$

Reglas:
1. Agrupa patrones que solo difieren en slugs/IDs específicos
2. Reemplaza componentes variables con clases genéricas: [^/]+, [a-z0-9-]+, etc.
3. ESCAPA caracteres especiales de regex (. → \\.)
4. NO agrupes patrones con estructura diferente (diferente número de path segments, query strings diferentes, etc.)
5. IMPORTANTE: En el campo "reason", usa SOLO texto ASCII simple sin caracteres especiales

Responde ÚNICAMENTE con JSON válido sin caracteres especiales en strings:
{
  "groups": [
    {
      "normalized_pattern": "pattern_regex",
      "original_patterns": ["pattern1", "pattern2"],
      "reason": "brief explanation in simple text"
    }
  ]
}"""

    user_prompt = f"""Analiza estos {len(patterns_list)} patrones regex y agrúpalos por similitud estructural:

{json.dumps(patterns_list, ensure_ascii=False, indent=2)}

Agrupa los patrones que son variaciones del mismo patrón estructural y genera UN patrón normalizado por grupo.
IMPORTANTE: Asegúrate de devolver JSON válido sin strings sin cerrar."""

    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = llm_client.call(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=0.1 if attempt == 0 else 0.0,  # Lower temp on retry
                max_tokens=4000,
                response_format={"type": "json_object"},
                stage="01",
                operation="normalize_patterns",
                run_date=None
            )

            # Try to parse JSON
            result = json.loads(response)

            # Successfully parsed, process groups
            groups = result.get('groups', [])

            # Build normalized pattern groups
            normalized_groups = {}

            for group in groups:
                normalized_pattern = group.get('normalized_pattern', '')
                original_patterns = group.get('original_patterns', [])
                reason = group.get('reason', '')

                if not normalized_pattern or not original_patterns:
                    continue

                # Merge all example URLs from original patterns
                merged_urls = []
                content_types = []

                for orig_pattern in original_patterns:
                    if orig_pattern in pattern_groups:
                        merged_urls.extend(pattern_groups[orig_pattern]['example_urls'])
                        content_types.append(pattern_groups[orig_pattern]['content_type'])

                # Use most common content_type
                content_type = max(set(content_types), key=content_types.count) if content_types else 'contenido'

                normalized_groups[normalized_pattern] = {
                    'pattern': normalized_pattern,
                    'content_type': content_type,
                    'example_urls': merged_urls,
                    'reason': reason
                }

            logger.info(f"LLM normalized {len(pattern_groups)} patterns into {len(normalized_groups)} groups")
            return normalized_groups

        except json.JSONDecodeError as e:
            if attempt < max_retries - 1:
                logger.warning(f"JSON parse error on attempt {attempt + 1}/{max_retries}: {e}. Retrying with stricter prompt...")
                # Reduce number of patterns on retry
                patterns_list = patterns_list[:len(patterns_list) // 2]
                user_prompt = f"""Analiza estos {len(patterns_list)} patrones regex (reducidos para evitar errores):

{json.dumps(patterns_list, ensure_ascii=False, indent=2)}

Agrupa los patrones. CRÍTICO: Devuelve JSON válido bien formado."""
                continue
            else:
                logger.error(f"Failed to normalize patterns with LLM after {max_retries} attempts: {e}")
                # Fallback: return original groups
                return pattern_groups

        except Exception as e:
            logger.error(f"Unexpected error normalizing patterns with LLM: {e}")
            return pattern_groups

    # Should not reach here
    return pattern_groups


def _deduplicate_and_validate_patterns(
    patterns_by_url: List[Tuple[str, str, str]],
    all_urls: List[Dict[str, str]],
    min_coverage: int = 3,
    llm_client = None,
    model: str = "gpt-4o-mini"
) -> List[Dict]:
    """
    Deduplicate patterns and validate coverage.

    If deduplication ratio is poor (>80% unique patterns), uses LLM
    to normalize similar patterns.

    Args:
        patterns_by_url: List of (url, pattern, content_type) tuples
        all_urls: All URLs from source for validation
        min_coverage: Minimum number of URLs a pattern must match
        llm_client: Optional LLM client for pattern normalization
        model: Model to use for normalization

    Returns:
        List of validated pattern dicts
    """
    # Group by pattern
    pattern_groups = {}
    for url, pattern, content_type in patterns_by_url:
        if pattern not in pattern_groups:
            pattern_groups[pattern] = {
                'pattern': pattern,
                'content_type': content_type,
                'example_urls': []
            }
        pattern_groups[pattern]['example_urls'].append(url)

    initial_unique = len(pattern_groups)
    logger.info(f"Generated {len(patterns_by_url)} individual patterns, reduced to {initial_unique} unique patterns")

    # Check deduplication ratio
    dedup_ratio = initial_unique / len(patterns_by_url) if len(patterns_by_url) > 0 else 0

    # If poor deduplication (>80% patterns are unique) and we have LLM client, normalize
    if dedup_ratio > 0.8 and initial_unique > 10 and llm_client:
        logger.info(f"Low deduplication ratio ({dedup_ratio:.1%}), using LLM to normalize patterns")
        pattern_groups = _normalize_patterns_with_llm(pattern_groups, llm_client, model)
    else:
        logger.info(f"Good deduplication ratio ({dedup_ratio:.1%}), skipping LLM normalization")

    # Validate each pattern
    validated = []
    for pattern_str, group in pattern_groups.items():
        try:
            compiled = re.compile(pattern_str, re.IGNORECASE)

            # Count matches in all URLs
            matches = []
            types_found = {}
            for url_dict in all_urls:
                if compiled.search(url_dict['url']):
                    matches.append(url_dict)
                    url_type = url_dict.get('content_type', 'unknown')
                    types_found[url_type] = types_found.get(url_type, 0) + 1

            match_count = len(matches)

            # Check coverage threshold
            if match_count < min_coverage:
                logger.debug(f"Pattern rejected: only {match_count} matches (min: {min_coverage})")
                continue

            # Check consistency (70% of matches should be same type)
            if types_found:
                dominant_type = max(types_found.items(), key=lambda x: x[1])[0]
                dominant_count = types_found[dominant_type]
                consistency = (dominant_count / match_count * 100) if match_count > 0 else 0

                if consistency < 70.0:
                    logger.debug(f"Pattern rejected: only {consistency:.1f}% consistent (need 70%)")
                    continue

                # Use dominant type
                final_type = dominant_type
            else:
                final_type = group['content_type']

            # Generate descriptive name
            name = f"{final_type}_{len(validated)+1}"
            if '_[0-9]+' in pattern_str or '/[0-9]+' in pattern_str:
                name = f"{final_type}_articulos_con_id"
            elif '20[0-9]{12}' in pattern_str:
                name = f"{final_type}_articulos_timestamp"
            elif '20[0-9]{2}' in pattern_str:
                name = f"{final_type}_articulos_fechados"
            elif '/[^/]+/' in pattern_str:
                name = f"{final_type}_con_slug"

            coverage_pct = (match_count / len(all_urls) * 100) if len(all_urls) > 0 else 0

            validated.append({
                'name': name,
                'pattern': pattern_str,
                'content_type': final_type,
                'confidence': 'high' if match_count > 10 else 'medium',
                'examples': match_count,
                'coverage_percentage': round(coverage_pct, 2),
                'type_consistency': round(consistency, 2),
                'sample_urls': [m['url'] for m in matches[:3]]
            })

            logger.info(f"Validated pattern: {match_count} matches ({coverage_pct:.1f}% coverage) → {final_type}")

        except re.error as e:
            logger.warning(f"Invalid pattern {pattern_str}: {e}")
            continue

    return validated


def discover_patterns_from_urls(
    urls_by_source: Dict[str, List[Dict[str, str]]],
    llm_client,
    model: str = "gpt-4o-mini",
    min_coverage: int = 3,
    min_coverage_percentage: float = 0.0
) -> Tuple[Dict, Dict[str, List[str]]]:
    """
    Discover regex patterns by extracting individual patterns from each URL,
    then deduplicating and validating coverage.

    Uses LLM for normalization when deduplication ratio is poor (>80% unique patterns).

    Args:
        urls_by_source: Dict mapping source_domain to list of URL dicts
        llm_client: LLM client for pattern normalization
        model: Model to use for normalization
        min_coverage: Minimum number of URLs a pattern must match
        min_coverage_percentage: Not used in this implementation

    Returns:
        Tuple of (discovered_rules_dict, no_contenido_urls_by_source)
    """
    logger.info(f"Starting pattern discovery for {len(urls_by_source)} sources (individual extraction + dedup)")

    discovered_rules = {
        "version": "1.0",
        "last_updated": datetime.now().isoformat(),
        "global_rules": [],
        "sources": {}
    }

    # Collect no_contenido URLs for caching
    no_contenido_urls_by_source = {}

    for source_domain, urls in urls_by_source.items():
        logger.info(f"Processing {len(urls)} URLs from {source_domain}")

        # Separate by content_type
        contenido_urls = [u for u in urls if u.get('content_type') == 'contenido']
        no_contenido_urls = [u for u in urls if u.get('content_type') == 'no_contenido']

        logger.info(f"  - {len(contenido_urls)} contenido URLs")
        logger.info(f"  - {len(no_contenido_urls)} no_contenido URLs")

        # Generate pattern for each contenido URL
        patterns_by_url = []
        for url_dict in contenido_urls:
            url = url_dict['url']
            pattern = _extract_pattern_from_url(url, 'contenido')
            if pattern:
                patterns_by_url.append((url, pattern, 'contenido'))

        logger.info(f"  - Generated {len(patterns_by_url)} patterns from contenido URLs")

        # Deduplicate and validate (with optional LLM normalization)
        validated_patterns = _deduplicate_and_validate_patterns(
            patterns_by_url,
            urls,
            min_coverage=min_coverage,
            llm_client=llm_client,
            model=model
        )

        # Add to results
        if validated_patterns:
            discovered_rules["sources"][source_domain] = {
                "rules": validated_patterns
            }
            logger.info(f"Discovered {len(validated_patterns)} valid patterns for {source_domain}")
        else:
            logger.warning(f"No valid patterns found for {source_domain}")

        # Cache ALL no_contenido URLs
        if no_contenido_urls:
            no_contenido_urls_by_source[source_domain] = [u['url'] for u in no_contenido_urls]
            logger.info(f"Cached {len(no_contenido_urls)} no_contenido URLs for {source_domain}")

    # Log summary
    total_cached = sum(len(urls) for urls in no_contenido_urls_by_source.values())
    logger.info(f"Collected {total_cached} no_contenido URLs across {len(no_contenido_urls_by_source)} sources for caching")

    return discovered_rules, no_contenido_urls_by_source


def save_rules_to_yaml(rules: Dict, output_path: str = "config/url_classification_rules.yml"):
    """
    Save discovered rules to YAML file, merging with existing rules.

    Only updates/adds rules for sources present in the input dict.
    Preserves rules for sources not included in the input.

    Args:
        rules: Rules dict in YAML-compatible format
        output_path: Path to output YAML file
    """
    try:
        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Load existing rules if file exists
        existing_rules = {}
        if Path(output_path).exists():
            try:
                with open(output_path, 'r', encoding='utf-8') as f:
                    existing_rules = yaml.safe_load(f) or {}
                logger.info(f"Loaded existing rules from {output_path}")
            except Exception as e:
                logger.warning(f"Could not load existing rules (will create new file): {e}")
                existing_rules = {}

        # Merge rules: preserve existing sources not in new rules
        merged_rules = {
            "version": rules.get("version", "1.0"),
            "last_updated": rules.get("last_updated", datetime.now().isoformat()),
            "global_rules": rules.get("global_rules", existing_rules.get("global_rules", [])),
            "sources": existing_rules.get("sources", {}).copy()  # Start with existing sources
        }

        # Update/add sources from new rules
        new_sources = rules.get("sources", {})
        for source_id, source_config in new_sources.items():
            merged_rules["sources"][source_id] = source_config
            logger.info(f"Updated rules for source: {source_id}")

        # Write merged rules
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(merged_rules, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        total_sources = len(merged_rules["sources"])
        updated_sources = len(new_sources)
        logger.info(f"Rules saved to {output_path} ({updated_sources} sources updated, {total_sources} total)")

    except Exception as e:
        logger.error(f"Failed to save rules to {output_path}: {e}")
        raise


def save_cached_no_content_urls(
    urls_by_source: Dict[str, List[str]],
    output_path: str = "config/cached_no_content_urls.yml"
):
    """
    Save cached no_contenido URLs to YAML file, merging with existing cache.

    Only updates/adds cache for sources present in the input dict.
    Preserves cache for sources not included in the input.

    Args:
        urls_by_source: Dict mapping source_domain to list of no_contenido URLs
        output_path: Path to output YAML file
    """
    try:
        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Load existing cached URLs if file exists
        existing_cache = {}
        if Path(output_path).exists():
            try:
                with open(output_path, 'r', encoding='utf-8') as f:
                    existing_data = yaml.safe_load(f) or {}
                    existing_cache = existing_data.get("sources", {})
                logger.info(f"Loaded existing cached URLs from {output_path}")
            except Exception as e:
                logger.warning(f"Could not load existing cached URLs (will create new file): {e}")
                existing_cache = {}

        # Build merged structure
        cached_data = {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "sources": existing_cache.copy()  # Start with existing cache
        }

        # Update/add sources from new cache
        for source_domain, urls_list in urls_by_source.items():
            # Deduplicate and sort for readability
            unique_urls = sorted(set(urls_list))
            cached_data["sources"][source_domain] = {
                "urls": unique_urls,
                "count": len(unique_urls),
                "last_updated": datetime.now().isoformat()
            }
            logger.info(f"Updated cached URLs for source: {source_domain} ({len(unique_urls)} URLs)")

        # Save to YAML
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(cached_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        total_sources = len(cached_data["sources"])
        updated_sources = len(urls_by_source)
        total_urls = sum(source["count"] for source in cached_data["sources"].values())
        logger.info(f"Saved cached URLs to {output_path} ({updated_sources} sources updated, {total_sources} total, {total_urls} URLs)")

    except Exception as e:
        logger.error(f"Failed to save cached URLs to {output_path}: {e}")
        raise


def get_classification_stats(links: List[Dict[str, str]]) -> Dict:
    """
    Calculate statistics about classification methods used.

    Args:
        links: List of classified links

    Returns:
        Dict with statistics
    """
    stats = {
        "total": len(links),
        "by_method": {},
        "by_category": {},
        "regex_coverage_pct": 0.0
    }

    for link in links:
        method = link.get('classification_method', 'unknown')
        category = link.get('content_type', 'unknown')

        stats["by_method"][method] = stats["by_method"].get(method, 0) + 1
        stats["by_category"][category] = stats["by_category"].get(category, 0) + 1

    # Calculate regex coverage
    regex_count = stats["by_method"].get("regex_rule", 0)
    cached_count = stats["by_method"].get("cached_url", 0)
    total_non_llm = regex_count + cached_count
    if stats["total"] > 0:
        stats["regex_coverage_pct"] = (total_non_llm / stats["total"]) * 100

    return stats
