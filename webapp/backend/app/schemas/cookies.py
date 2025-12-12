"""
Pydantic schemas for Cookie management.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class CookieStatus(str, Enum):
    """Cookie validation status."""
    ACTIVE = "active"          # Cookies validadas y funcionando
    INVALID = "invalid"        # Cookies que fallaron validación
    EXPIRED = "expired"        # Cookies expiradas
    NOT_TESTED = "not_tested"  # Cookies no validadas aún


class CookieUpload(BaseModel):
    """Schema for uploading cookies."""
    domain: str = Field(..., min_length=3, max_length=255, description="Domain for cookies (e.g., 'elpais.com')")
    cookies: List[Dict[str, Any]] = Field(..., description="Array of cookie objects from browser export")
    test_url: Optional[str] = Field(None, description="URL to test cookies (defaults to domain homepage)")
    auto_validate: bool = Field(default=True, description="Automatically validate cookies on upload")

    @validator('domain')
    def validate_domain(cls, v):
        """Clean and validate domain."""
        # Remove protocol if present
        v = v.replace('https://', '').replace('http://', '')
        # Remove www. prefix
        v = v.replace('www.', '')
        # Remove trailing slash
        v = v.rstrip('/')
        return v.lower()

    @validator('cookies')
    def validate_cookies_format(cls, v):
        """Validate cookie array format."""
        if not v or len(v) == 0:
            raise ValueError("Cookie array cannot be empty")

        # Check that each cookie has required fields
        required_fields = {'name', 'value'}
        for cookie in v:
            if not isinstance(cookie, dict):
                raise ValueError("Each cookie must be a dictionary")
            if not required_fields.issubset(cookie.keys()):
                raise ValueError(f"Each cookie must have at least: {required_fields}")

        return v


class CookieTestRequest(BaseModel):
    """Schema for testing existing cookies."""
    domain: str = Field(..., description="Domain to test")
    test_url: Optional[str] = Field(None, description="URL to test (optional)")


class CookieTestResult(BaseModel):
    """Schema for cookie test result."""
    success: bool
    status: CookieStatus
    message: str
    test_url: str
    response_size: Optional[int] = None
    error: Optional[str] = None
    tested_at: datetime


class CookieInfo(BaseModel):
    """Schema for cookie information response."""
    domain: str
    status: CookieStatus
    cookie_count: int
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    created_at: datetime
    last_tested_at: Optional[datetime] = None
    last_test_result: Optional[str] = None
    source_id: Optional[int] = Field(None, description="Associated source ID (if linked)")
    source_name: Optional[str] = Field(None, description="Associated source name")
    # Expiry information
    has_expired_cookies: bool = Field(default=False, description="Has any expired cookies")
    expiring_soon: bool = Field(default=False, description="Has cookies expiring within 7 days")
    days_until_expiry: Optional[int] = Field(None, description="Days until earliest expiry (negative if expired)")


class CookieListResponse(BaseModel):
    """Schema for list of cookies."""
    cookies: List[CookieInfo]
    total: int
