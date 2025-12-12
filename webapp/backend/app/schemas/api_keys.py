"""
Pydantic schemas for API key management.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator


class APIKeyCreate(BaseModel):
    """Schema for creating a new API key."""

    alias: str = Field(..., min_length=1, max_length=255, description="Human-readable identifier for the API key")
    api_key: str = Field(..., min_length=20, description="OpenAI API key to encrypt and store")
    notes: Optional[str] = Field(None, description="Optional notes about this API key")
    use_as_fallback: bool = Field(True, description="Whether this API key can be used as fallback when primary key runs out of credits")

    @validator("alias")
    def validate_alias(cls, v):
        """Validate alias format."""
        if not v.strip():
            raise ValueError("Alias cannot be empty or whitespace")
        return v.strip()

    @validator("api_key")
    def validate_api_key(cls, v):
        """Validate API key format (basic check for OpenAI format)."""
        if not v.startswith("sk-"):
            raise ValueError("API key must start with 'sk-'")
        return v


class APIKeyUpdate(BaseModel):
    """Schema for updating an existing API key."""

    alias: Optional[str] = Field(None, min_length=1, max_length=255)
    api_key: Optional[str] = Field(None, min_length=20)
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    use_as_fallback: Optional[bool] = None

    @validator("alias")
    def validate_alias(cls, v):
        """Validate alias format if provided."""
        if v is not None and not v.strip():
            raise ValueError("Alias cannot be empty or whitespace")
        return v.strip() if v else v

    @validator("api_key")
    def validate_api_key(cls, v):
        """Validate API key format if provided."""
        if v is not None and not v.startswith("sk-"):
            raise ValueError("API key must start with 'sk-'")
        return v


class APIKeyResponse(BaseModel):
    """Schema for API key response (never exposes actual key)."""

    id: int
    alias: str
    user_id: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime]
    usage_count: int
    notes: Optional[str]
    key_preview: str = Field(..., description="First 7 characters of the key (sk-xxx...)")
    use_as_fallback: bool

    class Config:
        from_attributes = True


class APIKeyList(BaseModel):
    """Schema for list of API keys."""

    total: int
    api_keys: list[APIKeyResponse]


class APIKeyTestRequest(BaseModel):
    """Schema for testing an API key."""

    alias: str = Field(..., description="Alias of the API key to test")


class APIKeyTestResponse(BaseModel):
    """Schema for API key test result."""

    success: bool
    message: str
    model_available: Optional[str] = Field(None, description="Available model if test succeeded")
    has_credits: Optional[bool] = Field(None, description="Whether the API key has available credits")
    error_code: Optional[str] = Field(None, description="Error code if test failed (e.g., 'insufficient_quota')")
