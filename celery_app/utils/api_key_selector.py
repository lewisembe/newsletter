"""
API Key selection utility for Celery tasks.
Supports manual selection or automatic round-robin rotation.
"""
import logging

logger = logging.getLogger(__name__)


def select_api_key(db, api_key_id=None):
    """
    Select API key: manual or round-robin.

    Args:
        db: PostgreSQLURLDatabase instance
        api_key_id: ID específico (None = rotación automática)

    Returns:
        dict con datos de API key o None si no hay keys disponibles
    """
    if api_key_id:
        # Selección manual
        logger.info(f"Using manually selected API key: {api_key_id}")
        return db.get_api_key_by_id(api_key_id)

    # Rotación round-robin: API key menos usada (usage_count)
    active_keys = db.get_all_api_keys(user_id=None, include_inactive=False)

    if not active_keys:
        logger.error("No active API keys available")
        return None

    # Ordenar por usage_count ASC, last_used_at ASC (nulls first)
    sorted_keys = sorted(
        active_keys,
        key=lambda k: (k['usage_count'], k['last_used_at'] or '1970-01-01')
    )

    selected = sorted_keys[0]
    logger.info(f"Auto-selected API key (round-robin): {selected['alias']} (usage: {selected['usage_count']})")

    return db.get_api_key_by_id(selected['id'])
