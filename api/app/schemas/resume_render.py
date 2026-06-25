from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from api.app.schemas.tailoring import ProvenanceRef


class ResumeItem(BaseModel):
    item_id: str
    text: str
    source_section: str
    relevance_score: float = 0.0
    provenance: List[ProvenanceRef] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)


class ResumeSection(BaseModel):
    kind: str
    heading: str
    items: List[ResumeItem] = Field(default_factory=list)


class ResumeContact(BaseModel):
    location: str = ""
    phone: str = ""
    email: str = ""
    links: List[str] = Field(default_factory=list)


class ResumeEntry(BaseModel):
    entry_id: str
    title: str = ""
    organization: str = ""
    location: str = ""
    date_range: str = ""
    items: List[ResumeItem] = Field(default_factory=list)


class PdfTextValidation(BaseModel):
    ats_parse_passed: bool
    extracted_text: str = ""
    missing_headings: List[str] = Field(default_factory=list)
    missing_items: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    order_passed: bool = True
    notes: List[str] = Field(default_factory=list)


class HtmlRenderResult(BaseModel):
    html_path: str
    pdf_path: str
    page_count: Optional[int] = None
    layout_passed: Optional[bool] = None
    ats_parse_passed: Optional[bool] = None
    ats_parse_notes: List[str] = Field(default_factory=list)


class ResumeLayout(BaseModel):
    owner_name: str
    contact: ResumeContact = Field(default_factory=ResumeContact)
    target_role: str = ""
    company_name: str = ""
    max_pages: int = 2
    sections: List[ResumeSection] = Field(default_factory=list)
    experience_entries: List[ResumeEntry] = Field(default_factory=list)
    project_entries: List[ResumeEntry] = Field(default_factory=list)
    education_entries: List[ResumeEntry] = Field(default_factory=list)
    expected_keywords: List[str] = Field(default_factory=list)
