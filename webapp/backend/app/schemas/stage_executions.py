from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date

# ============================================================================
# EXECUTION SCHEMAS
# ============================================================================

class ExecutionTriggerRequest(BaseModel):
    """Request to trigger manual execution."""
    api_key_id: int
    source_names: Optional[List[str]] = None
    use_fallback: bool = True  # Enable fallback by default

class ExecutionHistoryCreate(BaseModel):
    """Schema for creating execution history record."""
    stage_name: str
    execution_date: date
    trigger_type: str  # "manual" or "scheduled"
    api_key_id: int
    source_filter: Optional[List[str]] = None
    schedule_id: Optional[int] = None

class ExecutionHistoryUpdate(BaseModel):
    """Schema for updating execution history."""
    status: Optional[str] = None
    celery_task_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    urls_extracted: Optional[int] = None
    urls_failed: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    error_message: Optional[str] = None

class ExecutionHistoryResponse(BaseModel):
    """Schema for execution history response."""
    id: int
    schedule_id: Optional[int] = None
    schedule_name: Optional[str] = None
    execution_type: str  # "manual" or "scheduled"
    stage_name: str
    status: str
    api_key_id: Optional[int] = None
    api_key_alias: Optional[str] = None
    api_keys_used: Optional[List[int]] = None  # Array of API key IDs used (primary + fallbacks)
    parameters: Optional[dict] = None
    celery_task_id: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_items: int = 0
    processed_items: int = 0
    updated_items: int = 0
    failed_items: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    cost_eur: float = 0.0
    error_message: Optional[str] = None
    log_file: Optional[str] = None
    duration_seconds: Optional[int] = None

    class Config:
        from_attributes = True

# ============================================================================
# EXECUTION DETAIL SCHEMAS
# ============================================================================

class URLDetail(BaseModel):
    """Schema for individual URL detail."""
    id: int
    url: str
    title: Optional[str] = None
    source: str
    content_type: Optional[str] = None
    content_subtype: Optional[str] = None
    categoria_tematica: Optional[str] = None
    classification_method: Optional[str] = None
    rule_name: Optional[str] = None
    extracted_at: datetime
    last_extracted_at: Optional[datetime] = None

class SourceStats(BaseModel):
    """Statistics per source."""
    source: str
    total_urls: int
    content_urls: int
    non_content_urls: int
    categorized_urls: int

class CategoryStats(BaseModel):
    """Statistics per category."""
    categoria_tematica: str
    url_count: int

class ExecutionDetailResponse(BaseModel):
    """Detailed execution information including URLs and statistics."""
    execution: ExecutionHistoryResponse
    urls: List[URLDetail]
    stats_by_source: List[SourceStats]
    stats_by_category: List[CategoryStats]
    total_urls: int

    class Config:
        from_attributes = True

# ============================================================================
# SCHEDULE SCHEMAS
# ============================================================================

class ScheduledExecutionCreate(BaseModel):
    """Schema for creating scheduled execution."""
    name: str = Field(..., min_length=3, max_length=100)
    cron_expression: str
    api_key_id: int
    execution_target: str = Field(default="01_extract_urls")
    newsletter_config_id: Optional[int] = None
    source_filter: Optional[List[str]] = None
    trigger_on_stage1_ready: bool = False
    is_active: bool = True

class ScheduledExecutionUpdate(BaseModel):
    """Schema for updating scheduled execution."""
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    cron_expression: Optional[str] = None
    api_key_id: Optional[int] = None
    execution_target: Optional[str] = None
    newsletter_config_id: Optional[int] = None
    source_filter: Optional[List[str]] = None
    trigger_on_stage1_ready: Optional[bool] = None
    is_active: Optional[bool] = None

class ScheduledExecutionResponse(BaseModel):
    """Schema for scheduled execution response."""
    id: int
    name: str
    cron_expression: str
    api_key_id: int
    execution_target: str
    newsletter_config_id: Optional[int] = None
    source_filter: Optional[List[str]] = None
    trigger_on_stage1_ready: bool = False
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        extra = "ignore"  # Ignore extra fields from database (stage_name, parameters, etc.)

# ============================================================================
# DASHBOARD SCHEMAS
# ============================================================================

class DashboardSystemStatus(BaseModel):
    """System status for dashboard."""
    has_running_execution: bool
    last_execution: Optional[ExecutionHistoryResponse] = None

class DashboardExecutionStats(BaseModel):
    """Aggregated execution statistics."""
    total_executions: int
    completed: int
    failed: int
    running: int
    pending: int
    success_rate: float
    total_cost_usd: float
    total_tokens: int

class DashboardResourceCounts(BaseModel):
    """Resource counts for dashboard."""
    total_users: int
    active_users: int
    total_sources: int
    active_sources: int
    active_schedules: int
    total_api_keys: int

class DashboardStageCostBreakdown(BaseModel):
    """Cost breakdown by stage."""
    stage_name: str
    total_cost_usd: float
    total_tokens: int
    executions: int
    avg_cost_per_execution: float

class DashboardResponse(BaseModel):
    """Complete dashboard data response."""
    system_status: DashboardSystemStatus
    recent_executions: List[ExecutionHistoryResponse]
    execution_stats: DashboardExecutionStats
    resource_counts: DashboardResourceCounts
    cost_by_stage: List[DashboardStageCostBreakdown]
