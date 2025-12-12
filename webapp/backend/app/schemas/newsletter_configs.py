"""
Pydantic schemas for newsletter configurations.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class NewsletterConfigBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, description="Unique newsletter name")
    display_name: Optional[str] = Field(None, max_length=255, description="Human-readable name")
    description: Optional[str] = Field(None, description="Newsletter description")
    visibility: str = Field(default='private', pattern="^(public|private)$", description="Newsletter visibility")
    source_ids: List[int] = Field(default_factory=list, description="List of source IDs")
    category_ids: List[str] = Field(default_factory=list, description="List of category IDs (strings)")
    articles_count: int = Field(default=20, ge=5, le=100, description="Number of articles to rank")
    ranker_method: str = Field(default='level_scoring', description="Ranking method")
    output_format: str = Field(default='markdown', description="Output format")
    template_name: str = Field(default='default', description="Template name")
    skip_paywall_check: bool = Field(default=False, description="Skip paywall check")
    related_window_days: int = Field(default=365, ge=0, description="Related articles window in days")
    is_active: bool = Field(default=True, description="Whether config is active")
    api_key_id: int = Field(..., description="Primary API key ID (required, uses user's API keys with optional fallback)")
    enable_fallback: bool = Field(default=True, description="Enable automatic fallback to user's other API keys")


class NewsletterConfigCreate(NewsletterConfigBase):
    pass


class NewsletterConfigUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = Field(
        default=None,
        pattern="^(public|private)$",
        description="Newsletter visibility"
    )
    source_ids: Optional[List[int]] = None
    category_ids: Optional[List[str]] = None
    articles_count: Optional[int] = None
    ranker_method: Optional[str] = None
    output_format: Optional[str] = None
    template_name: Optional[str] = None
    skip_paywall_check: Optional[bool] = None
    related_window_days: Optional[int] = None
    is_active: Optional[bool] = None
    api_key_id: Optional[int] = None
    enable_fallback: Optional[bool] = None


class NewsletterConfigResponse(BaseModel):
    id: int
    name: str
    display_name: Optional[str]
    description: Optional[str]
    visibility: str
    source_ids: List[int]
    category_ids: List[str]
    articles_count: int
    ranker_method: str
    output_format: str
    template_name: str
    skip_paywall_check: bool
    related_window_days: int
    is_active: bool
    api_key_id: Optional[int] = None  # Made optional for backwards compatibility
    enable_fallback: bool
    created_by_user_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    # Enriched fields (computed)
    source_count: Optional[int] = None
    categories: Optional[List[str]] = None

    class Config:
        from_attributes = True
