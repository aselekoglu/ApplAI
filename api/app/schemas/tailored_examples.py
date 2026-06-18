from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


TailoringDecisionKind = Literal["retained", "removed", "shortened_or_reworded", "added"]


class TailoredExampleSection(BaseModel):
    heading: str
    text: str = ""


class TailoredExample(BaseModel):
    example_id: str
    source_pdf_path: str
    role_label: str
    pdf_title: Optional[str] = None
    page_count: int = Field(..., ge=0)
    extracted_text: str = ""
    section_headings: List[str] = Field(default_factory=list)
    sections: List[TailoredExampleSection] = Field(default_factory=list)
    parse_confidence: float = Field(..., ge=0.0, le=1.0)


class TailoredExamplesResponse(BaseModel):
    examples: List[TailoredExample] = Field(default_factory=list)
    count: int


class TailoringDecision(BaseModel):
    decision_type: TailoringDecisionKind
    text: str
    matched_text: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DiffClassificationRequest(BaseModel):
    master_text: str
    example_text: str
    master_source_path: str = ""
    example_source_path: str = ""


class DiffClassification(BaseModel):
    master_source_path: str = ""
    example_source_path: str = ""
    decisions: List[TailoringDecision] = Field(default_factory=list)
    retained_count: int = 0
    removed_count: int = 0
    shortened_or_reworded_count: int = 0
    added_count: int = 0
    classifier_version: str = "line-diff-v0"
