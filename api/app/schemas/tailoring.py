from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TailorRunOptions(BaseModel):
    model_name: str = "gemini-2.5-flash"
    company_name: str = ""
    job_title: str = ""
    quick_mode: bool = False
    include_cover_letter: bool = True
    include_ats: bool = True
    include_qa: bool = True
    allow_experience_rewrites: bool = False
    allow_education_rewrites: bool = False
    max_pages: int = Field(default=2, ge=1, le=3)


class TailorRunRequest(BaseModel):
    master_id: str
    job_description: str = Field(..., min_length=1)
    options: TailorRunOptions = Field(default_factory=TailorRunOptions)


class Selection(BaseModel):
    bullet_id: str
    section: str
    action: str
    original_text: str
    new_text: Optional[str] = None
    rewrite_rationale: Optional[str] = None
    relevance_score: float = 0.0
    jd_requirements_addressed: List[str] = Field(default_factory=list)


class TailoredOutputPayload(BaseModel):
    profile_selections: List[Selection] = Field(default_factory=list)
    skills_to_highlight: List[str] = Field(default_factory=list)
    experience_selections: List[Selection] = Field(default_factory=list)
    project_selections: List[Selection] = Field(default_factory=list)
    education_selections: List[Selection] = Field(default_factory=list)
    summary_section: Optional[str] = None


class ChangeLogEntryPayload(BaseModel):
    bullet_id: str
    section: str
    action: str
    original_text: str
    new_text: Optional[str] = None
    rationale: str = ""
    jd_requirements_addressed: List[str] = Field(default_factory=list)


class ChangeLogPayload(BaseModel):
    entries: List[ChangeLogEntryPayload] = Field(default_factory=list)
    total_bullets_considered: int = 0
    total_bullets_changed: int = 0
    total_bullets_rewritten: int = 0
    total_bullets_deselected: int = 0


class QaReportPayload(BaseModel):
    matching_rate_score: int = 0
    factual_support_passed: bool = True
    keyword_coverage_pct: float = 0.0
    style_issues: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    section_length_ok: bool = True
    key_pain_points: List[str] = Field(default_factory=list)
    strong_points: List[str] = Field(default_factory=list)
    feedback: str = ""


class AtsReportPayload(BaseModel):
    jd_keywords: List[str] = Field(default_factory=list)
    covered_keywords: List[str] = Field(default_factory=list)
    gap_keywords: List[str] = Field(default_factory=list)
    added_by_tailoring: List[str] = Field(default_factory=list)
    coverage_pct: float = 0.0


class TailoringResultPayload(BaseModel):
    canonical_cv: Dict[str, Any]
    jd_analysis: Dict[str, Any]
    tailored_output: TailoredOutputPayload
    change_log: ChangeLogPayload
    qa_report: QaReportPayload
    ats_report: AtsReportPayload
    cover_letter: str = ""


class TailorRunResponse(BaseModel):
    run_id: str
    master_id: str
    created_at: str
    options: TailorRunOptions
    result: TailoringResultPayload


class RunSummary(BaseModel):
    run_id: str
    master_id: str
    created_at: str
    model_name: str
    company_name: str = ""
    job_title: str = ""


class RunDetailResponse(BaseModel):
    run_id: str
    master_id: str
    created_at: str
    options: TailorRunOptions
    result: TailoringResultPayload
    exports: Optional[Dict[str, Any]] = None


class ExportRequest(BaseModel):
    run_id: str


class ExportResponse(BaseModel):
    run_id: str
    cv_path: str
    cover_letter_path: str
    docs_url: Optional[str] = None
