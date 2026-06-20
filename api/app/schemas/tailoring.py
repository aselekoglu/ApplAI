from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


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
    job_description: Optional[str] = Field(default=None, min_length=1)
    job_id: Optional[str] = Field(default=None, min_length=1)
    options: TailorRunOptions = Field(default_factory=TailorRunOptions)

    @model_validator(mode="after")
    def require_job_source(self) -> "TailorRunRequest":
        if not self.job_id and not self.job_description:
            raise ValueError("Either job_id or job_description is required")
        return self


class ProvenanceRef(BaseModel):
    source_type: Literal["career_brain", "job_record", "master_cv", "workflow"]
    source_id: str
    source_label: str = ""
    source_path: Optional[str] = None
    supported_text: str = ""


class SelectedEvidenceBlock(BaseModel):
    evidence_block_id: str
    source_label: str
    text: str
    score: int = 0
    matched_terms: List[str] = Field(default_factory=list)
    priority: int = 0
    provenance: List[ProvenanceRef] = Field(default_factory=list)


class Selection(BaseModel):
    bullet_id: str
    section: str
    action: str
    original_text: str
    new_text: Optional[str] = None
    rewrite_rationale: Optional[str] = None
    relevance_score: float = 0.0
    jd_requirements_addressed: List[str] = Field(default_factory=list)
    provenance: List[ProvenanceRef] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)


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
    provenance: List[ProvenanceRef] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)


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
    unsupported_claim_guard_passed: bool = True


class AtsReportPayload(BaseModel):
    jd_keywords: List[str] = Field(default_factory=list)
    covered_keywords: List[str] = Field(default_factory=list)
    gap_keywords: List[str] = Field(default_factory=list)
    added_by_tailoring: List[str] = Field(default_factory=list)
    coverage_pct: float = 0.0


class CompressionDecision(BaseModel):
    action: Literal[
        "remove_low_priority_bullets",
        "shorten_verbose_bullets",
        "reduce_project_detail",
        "compress_skills",
        "adjust_spacing_last",
    ]
    target: str
    section: str = ""
    before: str = ""
    after: str = ""
    reason: str = ""


class PageBudgetMetadata(BaseModel):
    max_pages: int = 2
    target_page_count: int = 2
    profile_bullet_budget: int = 3
    experience_bullet_budget: int = 8
    project_bullet_budget: int = 3
    education_bullet_budget: int = 2
    estimated_selected_bullets: int = 0
    estimated_words: int = 0
    compression_order: List[str] = Field(
        default_factory=lambda: [
            "remove_low_priority_bullets",
            "shorten_verbose_bullets",
            "reduce_project_detail",
            "compress_skills",
            "adjust_spacing_last",
        ]
    )
    compression_decisions: List[CompressionDecision] = Field(default_factory=list)


class LayoutValidation(BaseModel):
    max_pages: int = 2
    page_count: Optional[int] = None
    layout_passed: Optional[bool] = None
    validation_method: str = "pre_render_budget"
    notes: List[str] = Field(default_factory=list)


class ArtifactMetadata(BaseModel):
    artifact_id: str
    kind: str
    path: str
    page_count: Optional[int] = None
    layout_passed: Optional[bool] = None


class TailoringResultPayload(BaseModel):
    canonical_cv: Dict[str, Any]
    jd_analysis: Dict[str, Any]
    tailored_output: TailoredOutputPayload
    change_log: ChangeLogPayload
    qa_report: QaReportPayload
    ats_report: AtsReportPayload
    cover_letter: str = ""
    job_id: Optional[str] = None
    master_id: Optional[str] = None
    selected_evidence_block_ids: List[str] = Field(default_factory=list)
    selected_evidence: List[SelectedEvidenceBlock] = Field(default_factory=list)
    page_budget: PageBudgetMetadata = Field(default_factory=PageBudgetMetadata)
    layout_validation: LayoutValidation = Field(default_factory=LayoutValidation)
    artifacts: List[ArtifactMetadata] = Field(default_factory=list)
    approval_status: Literal["draft", "pending_review", "approved", "rejected"] = "draft"


class TailorRunResponse(BaseModel):
    run_id: str
    master_id: str
    created_at: str
    options: TailorRunOptions
    result: TailoringResultPayload
    job_id: Optional[str] = None
    selected_evidence_block_ids: List[str] = Field(default_factory=list)
    page_count: Optional[int] = None
    layout_passed: Optional[bool] = None
    artifact_ids: List[str] = Field(default_factory=list)


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
    job_id: Optional[str] = None


class ExportRequest(BaseModel):
    run_id: str


class ExportResponse(BaseModel):
    run_id: str
    cv_path: str
    cover_letter_path: str
    docs_url: Optional[str] = None
    docx_path: Optional[str] = None
    pdf_path: Optional[str] = None
    page_count: Optional[int] = None
    layout_passed: Optional[bool] = None
    artifact_ids: List[str] = Field(default_factory=list)
