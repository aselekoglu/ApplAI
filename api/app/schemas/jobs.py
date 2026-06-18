from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


JobRecommendation = Literal["apply", "skip", "worth_20_minutes"]
JobRecordStatus = Literal["draft", "reviewed", "archived"]


class ScoreJobRequest(BaseModel):
    job_description: str = Field(..., min_length=1)
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    source_url: Optional[str] = None
    save_draft: bool = False


class ParsedJobDescription(BaseModel):
    responsibilities: List[str] = Field(default_factory=list)
    qualifications: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    seniority: str = "unspecified"
    domain: str = "general"
    location_remote_hints: List[str] = Field(default_factory=list)
    effort_signals: List[str] = Field(default_factory=list)


class EvidenceMatch(BaseModel):
    evidence_block_id: str
    score: int = Field(..., ge=0)
    matched_terms: List[str] = Field(default_factory=list)


class ScoreReport(BaseModel):
    match_score: int = Field(..., ge=0, le=100)
    recommendation: JobRecommendation
    reasons: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    top_evidence_block_ids: List[str] = Field(default_factory=list)
    evidence_matches: List[EvidenceMatch] = Field(default_factory=list)
    keyword_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    role_preference_hits: List[str] = Field(default_factory=list)
    skill_category_hits: List[str] = Field(default_factory=list)


class ScoreJobResponse(BaseModel):
    job_id: str
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    source_url: Optional[str] = None
    match_score: int = Field(..., ge=0, le=100)
    recommendation: JobRecommendation
    reasons: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    best_evidence_block_ids: List[str] = Field(default_factory=list)
    top_evidence_block_ids: List[str] = Field(default_factory=list)
    parsed_jd_summary: ParsedJobDescription = Field(default_factory=ParsedJobDescription)
    score_report: ScoreReport
    saved: bool = False
    job_record_path: Optional[str] = None


class JobRecord(BaseModel):
    job_id: str
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    source_url: Optional[str] = None
    raw_description: str = Field(..., min_length=1)
    parsed: ParsedJobDescription
    score_report: ScoreReport
    recommendation: JobRecommendation
    status: JobRecordStatus = "draft"
    created_at: str
    updated_at: str


class JobImportRequest(ScoreJobRequest):
    save_draft: bool = True


class JobListResponse(BaseModel):
    jobs: List[JobRecord] = Field(default_factory=list)
    count: int = 0
