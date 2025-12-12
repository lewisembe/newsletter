"""
Pydantic schemas for authentication endpoints.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional


# ============================================
# REQUEST SCHEMAS
# ============================================

class UserRegister(BaseModel):
    """Schema for user registration."""
    nombre: str = Field(..., min_length=2, max_length=255, description="User's name")
    email: EmailStr = Field(..., description="User's email")
    password: str = Field(..., min_length=8, max_length=100, description="User's password (min 8 characters)")

    @field_validator('nombre')
    @classmethod
    def nombre_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Name cannot be empty or whitespace')
        return v.strip()


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr = Field(..., description="User's email")
    password: str = Field(..., description="User's password")
    remember_me: bool = Field(default=False, description="Keep session active for 30 days")


class UserProfileUpdate(BaseModel):
    """Schema for updating user profile."""
    nombre: Optional[str] = Field(None, min_length=2, max_length=255, description="New name")
    current_password: Optional[str] = Field(None, min_length=8, description="Current password (required to change password)")
    new_password: Optional[str] = Field(None, min_length=8, max_length=100, description="New password")

    @field_validator('nombre')
    @classmethod
    def nombre_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError('Name cannot be empty or whitespace')
        return v.strip() if v else None


class UserRoleUpdate(BaseModel):
    """Schema for updating user role (admin only)."""
    role: str = Field(..., pattern="^(user|enterprise)$", description="New role (user or enterprise)")


# ============================================
# RESPONSE SCHEMAS
# ============================================

class Token(BaseModel):
    """Schema for token response."""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Schema for user response (public data)."""
    id: int
    nombre: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserListItem(BaseModel):
    """Schema for user list item (admin view)."""
    id: int
    nombre: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
