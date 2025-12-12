"""
Pydantic schemas for Sources management.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SourceBase(BaseModel):
    """Base schema for Source."""
    name: str = Field(..., min_length=2, max_length=255, description="Unique source identifier")
    display_name: str = Field(..., min_length=2, max_length=255, description="Display name")
    base_url: str = Field(..., description="Base URL for scraping")
    language: str = Field(default='es', max_length=10, description="Language code (es, en, fr)")
    description: Optional[str] = Field(None, description="Source description")
    is_active: bool = Field(default=True, description="Active status")
    priority: int = Field(default=1, ge=0, le=100, description="Priority level (1=highest)")
    notes: Optional[str] = Field(None, description="Internal notes")


class SourceCreate(SourceBase):
    """Schema for creating a new source."""
    pass


class SourceUpdate(BaseModel):
    """Schema for updating a source."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    display_name: Optional[str] = Field(None, min_length=2, max_length=255)
    base_url: Optional[str] = None
    language: Optional[str] = Field(None, max_length=10)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=0, le=100)
    notes: Optional[str] = None


class SourceResponse(SourceBase):
    """Schema for source response."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SourceListItem(BaseModel):
    """Schema for source list item (minimal)."""
    id: int
    name: str
    display_name: str
    base_url: str
    language: str
    is_active: bool
    priority: int

    class Config:
        from_attributes = True
