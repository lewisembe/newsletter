from typing import List, Optional, Any
from pydantic import BaseModel, Field


class PromptBase(BaseModel):
    name: str
    stage: str
    operation: str
    scope: str
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    placeholders: List[str] = Field(default_factory=list)
    response_format: Optional[Any] = None
    default_model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    batch_size: Optional[int] = None
    status: str
    version: int
    notes: Optional[str] = None


class PromptResponse(PromptBase):
    id: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class PromptUpdate(BaseModel):
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    placeholders: Optional[List[str]] = None
    response_format: Optional[Any] = None
    default_model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    batch_size: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class PromptTestResponse(BaseModel):
    prompt_id: str
    stage: str
    operation: str
    received_payload: Any
    note: str
