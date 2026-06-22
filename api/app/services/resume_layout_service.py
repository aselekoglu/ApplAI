from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

from pydantic import BaseModel

from api.app.schemas.resume_render import ResumeItem, ResumeLayout, ResumeSection
from api.app.schemas.tailoring import ProvenanceRef


SECTION_CONFIG = [
    ("profile", "PROFILE", "profile_selections"),
    ("experience", "EXPERIENCE", "experience_selections"),
    ("projects", "PROJECTS", "project_selections"),
    ("education", "EDUCATION", "education_selections"),
]


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _provenance_refs(raw_refs: Iterable[Any]) -> List[ProvenanceRef]:
    refs: List[ProvenanceRef] = []
    for raw_ref in raw_refs:
        refs.append(ProvenanceRef.model_validate(raw_ref))
    return refs


def _active_items(selections: Iterable[Any], source_section: str) -> List[ResumeItem]:
    items: List[ResumeItem] = []
    for index, raw_selection in enumerate(selections, start=1):
        selection = _as_dict(raw_selection)
        if _clean_text(selection.get("action")).lower() == "deselect":
            continue

        new_text = _clean_text(selection.get("new_text"))
        text = new_text or _clean_text(selection.get("original_text"))
        if not text:
            continue

        relevance_score = selection.get("relevance_score", 0.0)
        try:
            relevance_score = float(relevance_score)
        except (TypeError, ValueError):
            relevance_score = 0.0

        item_id = _clean_text(selection.get("bullet_id")) or f"{source_section}-{index}"
        section = _clean_text(selection.get("section")) or source_section
        items.append(
            ResumeItem(
                item_id=item_id,
                text=text,
                source_section=section,
                relevance_score=relevance_score,
                provenance=_provenance_refs(_as_list(selection.get("provenance"))),
                unsupported_claims=[
                    claim
                    for claim in (_clean_text(value) for value in _as_list(selection.get("unsupported_claims")))
                    if claim
                ],
            )
        )
    return items


def _skills_section(skills: Iterable[Any]) -> Optional[ResumeSection]:
    items = [
        ResumeItem(item_id=f"skill-{index}", text=skill, source_section="skills")
        for index, skill in enumerate((_clean_text(value) for value in skills), start=1)
        if skill
    ]
    if not items:
        return None
    return ResumeSection(kind="skills", heading="SUMMARY OF QUALIFICATIONS", items=items)


def build_resume_layout(
    result_payload: Mapping[str, Any],
    *,
    owner_name: str,
    target_role: str = "",
    company_name: str = "",
    expected_keywords: Optional[List[str]] = None,
) -> ResumeLayout:
    payload = _as_dict(result_payload)
    tailored_output = _as_dict(payload.get("tailored_output"))
    page_budget = _as_dict(payload.get("page_budget"))

    sections: List[ResumeSection] = []
    for kind, heading, selection_key in SECTION_CONFIG:
        items = _active_items(_as_list(tailored_output.get(selection_key)), kind)
        if items:
            sections.append(ResumeSection(kind=kind, heading=heading, items=items))

    skills = _skills_section(_as_list(tailored_output.get("skills_to_highlight")))
    if skills is not None:
        profile_index = next((index for index, section in enumerate(sections) if section.kind == "profile"), None)
        if profile_index is None:
            sections.insert(0, skills)
        else:
            sections.insert(profile_index + 1, skills)

    max_pages = page_budget.get("max_pages", 2)
    try:
        max_pages = int(max_pages)
    except (TypeError, ValueError):
        max_pages = 2

    return ResumeLayout(
        owner_name=owner_name,
        target_role=target_role,
        company_name=company_name,
        max_pages=max_pages,
        sections=sections,
        expected_keywords=list(expected_keywords or []),
    )
