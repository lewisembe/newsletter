"""
Configuration settings for Newsletter Utils FastAPI backend.

Loads environment variables from .env file.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # Security
    SECRET_KEY: str
    JWT_SECRET_KEY: str
    JWT_SECRET_KEY_OLD: str = ""  # Optional: previous JWT secret for rotation
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REMEMBER_ME_EXPIRE_DAYS: int = 30  # Extended session for "Remember Me"
    COOKIE_SECURE: bool = True  # Send cookies only over HTTPS
    COOKIE_SAMESITE: str = "lax"  # lax | none | strict
    COOKIE_DOMAIN: str | None = None  # e.g. ".example.com" in production

    @property
    def jwt_secret_keys(self) -> List[str]:
        """Return list of valid JWT secret keys (current + old for rotation)"""
        keys = [self.JWT_SECRET_KEY]
        if self.JWT_SECRET_KEY_OLD:
            keys.append(self.JWT_SECRET_KEY_OLD)
        return keys

    # CORS - accepts comma-separated string
    CORS_ORIGINS: str = "http://localhost:3000"

    # Admin
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS string into list"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def cookie_samesite(self) -> str:
        """Normalize samesite value to lowercase expected by FastAPI"""
        value = (self.COOKIE_SAMESITE or "lax").lower()
        if value not in {"lax", "none", "strict"}:
            return "lax"
        return value

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
