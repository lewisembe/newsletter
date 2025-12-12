"""
Pydantic schemas for newsletter executions.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field


class NewsletterExecutionTriggerRequest(BaseModel):
    newsletter_config_id: int = Field(..., description="Newsletter configuration ID")
    run_date: date = Field(..., description="Execution date")
    api_key_id: Optional[int] = Field(None, description="Optional API key ID")
    force: bool = Field(default=False, description="Force re-execution")


class StageExecutionResponse(BaseModel):
    id: int
    stage_number: int
    stage_name: str
    status: str
    items_processed: int = 0
    items_successful: int = 0
    items_failed: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    stage_metadata: Optional[Dict[str, Any]]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class NewsletterExecutionResponse(BaseModel):
    id: int
    newsletter_config_id: Optional[int]
    newsletter_config_name: Optional[str]
    schedule_id: Optional[int]
    execution_type: str
    status: str
    run_date: date
    api_key_id: Optional[int] = None
    api_key_alias: Optional[str] = None
    total_stages: int
    completed_stages: int
    failed_stages: int
    total_urls_processed: int
    total_urls_ranked: int
    total_urls_with_content: int
    newsletter_generated: bool
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int = 0
    total_cost_usd: float
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    error_message: Optional[str]
    celery_task_id: Optional[str]

    class Config:
        from_attributes = True


class NewsletterExecutionDetailResponse(BaseModel):
    execution: NewsletterExecutionResponse
    stages: List[StageExecutionResponse]
    output_files: Optional[Dict[str, str]]
