"""
Pydantic schemas for categories management.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class CategoryBase(BaseModel):
    """Base category schema with common fields."""
    id: str = Field(..., description="Unique category identifier")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Category description")
    consolidates: List[str] = Field(default_factory=list, description="Predecessor category IDs")
    examples: List[str] = Field(default_factory=list, description="Example strings")


class CategoryCreate(BaseModel):
    """Schema for creating a new category."""
    id: str = Field(..., min_length=1, max_length=50, description="Unique category identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    description: str = Field(..., min_length=1, max_length=500, description="Category description")
    consolidates: List[str] = Field(default_factory=list, description="Predecessor category IDs")
    examples: List[str] = Field(default_factory=list, description="Example strings")


class CategoryUpdate(BaseModel):
    """Schema for updating an existing category."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="New display name")
    description: Optional[str] = Field(None, min_length=1, max_length=500, description="New description")
    consolidates: Optional[List[str]] = Field(None, description="New predecessor category IDs")
    examples: Optional[List[str]] = Field(None, description="New example strings")


class CategoryResponse(CategoryBase):
    """Schema for category response with timestamps."""
    created_at: datetime
    updated_at: datetime
    url_count: Optional[int] = Field(None, description="Number of URLs in this category")

    class Config:
        from_attributes = True


class CategoryListItem(BaseModel):
    """Simplified category schema for list views."""
    id: str
    name: str
    description: str
    url_count: int = Field(default=0, description="Number of URLs in this category")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReclassificationRequest(BaseModel):
    """Schema for triggering reclassification."""
    category_ids: List[str] = Field(..., description="Category IDs that were modified")
    reclassify_all: bool = Field(default=True, description="If True, reclassify ALL URLs (not just affected ones)")


class ReclassificationJobResponse(BaseModel):
    """Schema for reclassification job status."""
    id: int
    triggered_by: int
    category_ids: List[str]
    status: str = Field(..., description="Job status: pending, running, completed, failed")
    total_urls: int
    processed_urls: int
    failed_urls: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CategoryStatsResponse(BaseModel):
    """Schema for category statistics."""
    total_categories: int
    total_urls_categorized: int
    urls_by_category: dict[str, int]
