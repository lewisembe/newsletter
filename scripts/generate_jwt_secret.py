#!/usr/bin/env python3
"""
Generate a new secure JWT secret key for rotation.

Usage:
    python scripts/generate_jwt_secret.py

Output:
    Prints a new secure random secret suitable for JWT_SECRET_KEY
"""

import secrets
import sys


def generate_jwt_secret(length: int = 32) -> str:
    """
    Generate a cryptographically secure random secret key.

    Args:
        length: Length in bytes (default: 32 bytes = 256 bits)

    Returns:
        URL-safe base64-encoded secret string
    """
    return secrets.token_urlsafe(length)


def main():
    print("=" * 60)
    print("🔐 JWT Secret Key Generator")
    print("=" * 60)
    print()

    # Generate new secret
    new_secret = generate_jwt_secret()

    print("New JWT Secret:")
    print("-" * 60)
    print(new_secret)
    print("-" * 60)
    print()

    print("📋 Instructions:")
    print()
    print("1. Copy the secret above")
    print("2. Edit .env file:")
    print()
    print("   # Move current JWT_SECRET_KEY to JWT_SECRET_KEY_OLD")
    print("   JWT_SECRET_KEY=" + new_secret)
    print("   JWT_SECRET_KEY_OLD=<your_current_jwt_secret_key>")
    print()
    print("3. Restart backend:")
    print("   docker-compose restart backend")
    print()
    print("4. Monitor rotation progress:")
    print("   docker-compose logs backend | grep 'old secret key'")
    print()
    print("5. After 30+ days, remove JWT_SECRET_KEY_OLD from .env")
    print()
    print("⚠️  SECURITY NOTES:")
    print("- Never commit .env to git")
    print("- Store old secret until all users have re-authenticated")
    print("- Rotate secrets regularly (recommended: every 90 days)")
    print()
    print("See JWT_ROTATION.md for detailed instructions")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(0)
