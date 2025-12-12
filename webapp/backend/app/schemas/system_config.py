"""
Pydantic schemas for system configuration.
"""
from pydantic import BaseModel, Field


class SystemConfigUpdate(BaseModel):
    newsletter_execution_mode: str = Field(..., description="Execution mode: 'sequential' or 'parallel'")
    newsletter_max_parallel: int = Field(..., ge=1, le=10, description="Max parallel executions")


class SystemConfigResponse(BaseModel):
    newsletter_execution_mode: str
    newsletter_max_parallel: int
