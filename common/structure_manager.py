"""
Manager for source structure (CSS selectors) configuration.
Handles loading, saving, and caching of auto-generated CSS selectors per source.
"""

import yaml
import logging
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

STRUCTURE_FILE = "config/source_structure.yml"


def load_source_structure(source_id: str) -> Optional[Dict]:
    """
    Load structure configuration for a specific source.

    Args:
        source_id: Source identifier (e.g., "elconfidencial")

    Returns:
        Dict with 'selectors' and 'generated_date' or None if not found
    """
    structure_path = Path(STRUCTURE_FILE)

    if not structure_path.exists():
        logger.debug(f"Structure file does not exist: {STRUCTURE_FILE}")
        return None

    try:
        with open(structure_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        sources = data.get('sources', [])

        for source in sources:
            if source.get('id') == source_id:
                logger.info(f"Found cached structure for {source_id} (generated: {source.get('generated_date')})")
                return {
                    'selectors': source.get('selectors', []),
                    'generated_date': source.get('generated_date')
                }

        logger.debug(f"No cached structure found for {source_id}")
        return None

    except Exception as e:
        logger.error(f"Error loading structure for {source_id}: {e}")
        return None


def save_source_structure(source_id: str, selectors: List[str]):
    """
    Save or update structure configuration for a source.

    Args:
        source_id: Source identifier
        selectors: List of CSS selectors
    """
    structure_path = Path(STRUCTURE_FILE)

    # Ensure config directory exists
    structure_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data
    if structure_path.exists():
        try:
            with open(structure_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error loading existing structure file: {e}")
            data = {}
    else:
        data = {}

    # Initialize sources list if not exists
    if 'sources' not in data:
        data['sources'] = []

    # Find and update or append
    source_found = False
    for source in data['sources']:
        if source.get('id') == source_id:
            source['selectors'] = selectors
            source['generated_date'] = datetime.now().isoformat()
            source_found = True
            logger.info(f"Updated structure for {source_id}")
            break

    if not source_found:
        data['sources'].append({
            'id': source_id,
            'generated_date': datetime.now().isoformat(),
            'selectors': selectors
        })
        logger.info(f"Created new structure for {source_id}")

    # Save back to file
    try:
        with open(structure_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        logger.debug(f"Saved structure to {STRUCTURE_FILE}")
    except Exception as e:
        logger.error(f"Error saving structure file: {e}")
        raise


def structure_exists(source_id: str) -> bool:
    """
    Check if structure exists for a source.

    Args:
        source_id: Source identifier

    Returns:
        True if structure exists, False otherwise
    """
    structure = load_source_structure(source_id)
    return structure is not None and len(structure.get('selectors', [])) > 0


def get_selectors(source_id: str) -> List[str]:
    """
    Get selectors for a source.

    Args:
        source_id: Source identifier

    Returns:
        List of CSS selectors, or empty list if not found
    """
    structure = load_source_structure(source_id)
    if structure:
        return structure.get('selectors', [])
    return []
