"""
Encryption utilities for secure API key storage.
Uses Fernet (symmetric encryption) from cryptography library.
"""
import os
from cryptography.fernet import Fernet
from typing import Optional


class EncryptionManager:
    """Manages encryption and decryption of sensitive data like API keys."""

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption manager with a key.

        Args:
            encryption_key: Base64-encoded Fernet key. If None, reads from ENCRYPTION_KEY env var.
        """
        if encryption_key is None:
            encryption_key = os.getenv("ENCRYPTION_KEY")

        if not encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY environment variable must be set. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )

        self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: The string to encrypt (e.g., API key)

        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            raise ValueError("Cannot encrypt empty string")

        encrypted_bytes = self.cipher.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            encrypted_text: Base64-encoded encrypted string

        Returns:
            Original plaintext string
        """
        if not encrypted_text:
            raise ValueError("Cannot decrypt empty string")

        try:
            decrypted_bytes = self.cipher.decrypt(encrypted_text.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.

    Returns:
        Base64-encoded encryption key as string
    """
    return Fernet.generate_key().decode()


# Singleton instance
_encryption_manager: Optional[EncryptionManager] = None


def get_encryption_manager() -> EncryptionManager:
    """Get or create the singleton encryption manager instance."""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager
