from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


EvidenceKind = Literal["profile", "experience", "project", "education", "skill", "preference", "approved_note"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class EvidenceBlock(BaseModel):
    block_id: str = Field(..., min_length=1)
    kind: EvidenceKind
    text: str = Field(..., min_length=1)
    source_label: str = Field(..., min_length=1)
    source_path: Optional[str] = None
    provenance: List[str] = Field(default_factory=list)
    relevance_tags: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    skill_categories: List[str] = Field(default_factory=list)
    ats_keywords: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    priority: int = Field(default=3, ge=1, le=5)
    truth_constraints: List[str] = Field(default_factory=list)
    length_estimate: int = Field(default=0, ge=0)


class ExperienceRecord(BaseModel):
    experience_id: str = Field(..., min_length=1)
    employer: str = ""
    role: str = ""
    start_date: str = ""
    end_date: str = ""
    location: str = ""
    evidence_block_ids: List[str] = Field(default_factory=list)


class ProjectRecord(BaseModel):
    project_id: str = Field(..., min_length=1)
    title: str = ""
    summary: str = ""
    technologies: List[str] = Field(default_factory=list)
    links: List[str] = Field(default_factory=list)
    evidence_block_ids: List[str] = Field(default_factory=list)
    pr_asset_status: Literal["not_started", "draft", "approved"] = "not_started"


class SkillInventory(BaseModel):
    categories: Dict[str, List[str]] = Field(default_factory=dict)
    aliases: Dict[str, List[str]] = Field(default_factory=dict)
    role_relevance: Dict[str, List[str]] = Field(default_factory=dict)


class RolePreferences(BaseModel):
    preferred_roles: List[str] = Field(default_factory=list)
    target_companies: List[str] = Field(default_factory=list)
    preferred_locations: List[str] = Field(default_factory=list)
    work_authorization_notes: str = ""
    avoid_roles: List[str] = Field(default_factory=list)


class WritingPreferences(BaseModel):
    tone: str = "clear, direct, evidence-backed"
    max_pages: int = Field(default=2, ge=1, le=3)
    bullet_style: str = "concise impact-first bullets"
    banned_claims: List[str] = Field(default_factory=list)
    preferred_terms: List[str] = Field(default_factory=list)


class CareerBrainProfile(BaseModel):
    schema_version: str = "1.0"
    owner: str = "Ata Selekoglu"
    source_masters: List[str] = Field(default_factory=list)
    role_preferences: RolePreferences = Field(default_factory=RolePreferences)
    writing_preferences: WritingPreferences = Field(default_factory=WritingPreferences)
    skills: SkillInventory = Field(default_factory=SkillInventory)
    evidence_blocks: List[EvidenceBlock] = Field(default_factory=list)
    experiences: List[ExperienceRecord] = Field(default_factory=list)
    projects: List[ProjectRecord] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class CareerBrainUpdateResponse(BaseModel):
    profile: CareerBrainProfile
    path: str
