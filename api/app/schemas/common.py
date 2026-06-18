from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Human-readable error message")
    code: Optional[str] = Field(default=None, description="Optional machine-readable error code")


class HealthResponse(BaseModel):
    status: str = "ok"
