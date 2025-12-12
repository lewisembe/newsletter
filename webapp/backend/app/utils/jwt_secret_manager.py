import hashlib
import logging
from typing import List

from app.config import settings
from common.encryption import get_encryption_manager
from common.postgres_db import PostgreSQLURLDatabase

logger = logging.getLogger(__name__)

TABLE_NAME = "jwt_secret_history"


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def ensure_history_table(db: PostgreSQLURLDatabase) -> None:
    """Create history table if it does not exist."""
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id SERIAL PRIMARY KEY,
                secret_encrypted TEXT NOT NULL,
                secret_hash TEXT NOT NULL UNIQUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()


def store_secret_if_missing(db: PostgreSQLURLDatabase, secret: str) -> bool:
    """
    Persist the given secret if it is not already recorded (by hash).

    Returns True if inserted, False if it already existed.
    """
    secret_hash = _hash_secret(secret)
    encryptor = get_encryption_manager()

    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT 1 FROM {TABLE_NAME} WHERE secret_hash = %s",
            (secret_hash,),
        )
        if cur.fetchone():
            return False

        encrypted = encryptor.encrypt(secret)
        cur.execute(
            f"""
            INSERT INTO {TABLE_NAME} (secret_encrypted, secret_hash)
            VALUES (%s, %s)
            """,
            (encrypted, secret_hash),
        )
        conn.commit()
        return True


def _get_recent_encrypted_secrets(db: PostgreSQLURLDatabase, limit: int) -> List[str]:
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT secret_encrypted
            FROM {TABLE_NAME}
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return [row["secret_encrypted"] for row in rows]


def ensure_current_secret_logged(db: PostgreSQLURLDatabase) -> None:
    """
    Record the current JWT secret in history (idempotent).
    """
    try:
        ensure_history_table(db)
        stored = store_secret_if_missing(db, settings.JWT_SECRET_KEY)
        if stored:
            logger.info("Stored current JWT secret in history table")
    except Exception as exc:
        logger.error("Could not store current JWT secret: %s", exc)


def get_jwt_validation_keys(
    db: PostgreSQLURLDatabase,
    max_keys: int = 2,
) -> List[str]:
    """
    Build an ordered list of JWT secrets (current + recent) for token validation.
    """
    try:
        ensure_history_table(db)
        store_secret_if_missing(db, settings.JWT_SECRET_KEY)

        encrypted_secrets = _get_recent_encrypted_secrets(db, max_keys)
        decryptor = get_encryption_manager()

        keys: List[str] = []
        for encrypted in encrypted_secrets:
            try:
                secret = decryptor.decrypt(encrypted)
                if secret not in keys:
                    keys.append(secret)
            except Exception as exc:
                logger.warning("Failed to decrypt stored JWT secret: %s", exc)

        # Always ensure the current key is first
        if settings.JWT_SECRET_KEY not in keys:
            keys.insert(0, settings.JWT_SECRET_KEY)

        return keys[:max_keys]
    except Exception as exc:
        logger.error("Falling back to current JWT secret due to error: %s", exc)
        return [settings.JWT_SECRET_KEY]
