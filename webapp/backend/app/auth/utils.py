"""
Authentication utilities for password hashing and JWT token management.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Bcrypt hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash.

    Args:
        plain_password: Plain text password
        hashed_password: Bcrypt hashed password

    Returns:
        True if password matches, False otherwise
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False


def create_access_token(data: Dict, secret_key: str, algorithm: str,
                       expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.

    Args:
        data: Token payload (should include sub, email, role)
        secret_key: JWT secret key
        algorithm: JWT algorithm (e.g., HS256)
        expires_delta: Token expiration time (default: 30 minutes)

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=30)

    to_encode.update({"exp": expire})

    try:
        encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating access token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create access token"
        )


def decode_access_token(token: str, secret_key: str, algorithm: str) -> Dict:
    """
    Decode and validate JWT token.

    Args:
        token: JWT token
        secret_key: JWT secret key (or list of keys for rotation)
        algorithm: JWT algorithm

    Returns:
        Token payload dict

    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Support multiple secret keys for rotation
    secret_keys = [secret_key] if isinstance(secret_key, str) else secret_key

    # Try each secret key (current first, then old ones)
    for idx, key in enumerate(secret_keys):
        try:
            payload = jwt.decode(token, key, algorithms=[algorithm])

            # Verify required fields
            user_id: str = payload.get("sub")
            if user_id is None:
                raise credentials_exception

            # Log if using old key (for monitoring rotation progress)
            if idx > 0:
                logger.info(f"Token validated with old secret key (index {idx})")

            return payload

        except JWTError as e:
            # If this is the last key, raise exception
            if idx == len(secret_keys) - 1:
                logger.warning(f"JWT validation error with all keys: {e}")
                raise credentials_exception
            # Otherwise, try next key
            continue
        except Exception as e:
            logger.error(f"Error decoding token: {e}")
            raise credentials_exception

    raise credentials_exception
