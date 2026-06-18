from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


JobRecommendation = Literal["apply", "skip", "worth_20_minutes"]


class ScoreJobRequest(BaseModel):
    job_description: str = Field(..., min_length=1)
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    source_url: Optional[str] = None


class ScoreJobResponse(BaseModel):
    job_id: str
    match_score: int = Field(..., ge=0, le=100)
    recommendation: JobRecommendation
    reasons: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    best_evidence_block_ids: List[str] = Field(default_factory=list)
