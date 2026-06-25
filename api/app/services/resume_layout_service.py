from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping, Optional

from pydantic import BaseModel

from api.app.schemas.resume_render import ResumeContact, ResumeEntry, ResumeItem, ResumeLayout, ResumeSection
from api.app.schemas.tailoring import ProvenanceRef


SECTION_CONFIG = [
    ("profile", "PROFILE", "profile_selections"),
    ("experience", "EXPERIENCE", "experience_selections"),
    ("projects", "PROJECTS", "project_selections"),
    ("education", "EDUCATION", "education_selections"),
]
EMAIL_PATTERN = re.compile(r"[\w.\-+]+@[\w.\-]+\.\w+")
PHONE_PATTERN = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
URL_PATTERN = re.compile(r"https?://\S+")


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


def extract_contact_from_master_text(raw_text: str) -> ResumeContact:
    lines = [line.strip() for line in str(raw_text or "").splitlines() if line.strip()]
    header_lines: List[str] = []
    for line in lines:
        if line.upper().rstrip(":") in {"PROFILE", "SUMMARY OF QUALIFICATIONS", "RELEVANT EXPERIENCE"}:
            break
        header_lines.append(line)

    location = ""
    phone = ""
    email = ""
    links: List[str] = []
    for line in header_lines[1:]:
        if not location and "," in line and not URL_PATTERN.search(line) and not EMAIL_PATTERN.search(line):
            location = line
        if not phone:
            phone_match = PHONE_PATTERN.search(line)
            if phone_match:
                phone = phone_match.group(0)
        if not email:
            email_match = EMAIL_PATTERN.search(line)
            if email_match:
                email = email_match.group(0)
        links.extend(URL_PATTERN.findall(line))

    return ResumeContact(location=location, phone=phone, email=email, links=links)


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


def _canonical_profile_items(canonical_cv: Mapping[str, Any], limit: int = 3) -> List[ResumeItem]:
    items: List[ResumeItem] = []
    for index, raw_bullet in enumerate(_as_list(canonical_cv.get("profile_bullets")), start=1):
        bullet = _as_dict(raw_bullet)
        text = _clean_text(bullet.get("text"))
        if not text:
            continue
        items.append(
            ResumeItem(
                item_id=_clean_text(bullet.get("bullet_id")) or f"profile-fallback-{index}",
                text=text,
                source_section="profile",
            )
        )
        if len(items) >= limit:
            break
    return items


def _master_sections(master_payload: Mapping[str, Any], *, kind: str = "", title: str = "") -> List[Mapping[str, Any]]:
    matches: List[Mapping[str, Any]] = []
    wanted_kind = _clean_text(kind).lower()
    wanted_title = _clean_text(title).upper()
    for raw_section in _as_list(master_payload.get("sections")):
        section = _as_dict(raw_section)
        section_kind = _clean_text(section.get("kind")).lower()
        section_title = _clean_text(section.get("title")).upper()
        if wanted_kind and section_kind == wanted_kind:
            matches.append(section)
        elif wanted_title and section_title == wanted_title:
            matches.append(section)
    return matches


def _split_master_body_items(body_text: Any, limit: int) -> List[str]:
    items: List[str] = []
    for raw_line in str(body_text or "").splitlines():
        line = _clean_text(raw_line).lstrip("•-*").strip()
        if not line:
            continue
        items.append(line)
        if len(items) >= limit:
            break
    return items


def _master_profile_items(master_payload: Mapping[str, Any], limit: int = 3) -> List[ResumeItem]:
    sections = _master_sections(master_payload, kind="profile", title="PROFILE")
    if not sections:
        return []
    return [
        ResumeItem(
            item_id=f"profile-master-{index}",
            text=text,
            source_section="profile",
        )
        for index, text in enumerate(_split_master_body_items(sections[0].get("body_text"), limit), start=1)
    ]


def _canonical_skills(canonical_cv: Mapping[str, Any], limit: int = 14) -> List[str]:
    skills: List[str] = []
    seen: set[str] = set()
    sections = _as_dict(canonical_cv.get("skills_sections"))
    for values in sections.values():
        for value in _as_list(values):
            skill = _clean_text(value)
            key = skill.lower()
            if not skill or key in seen:
                continue
            seen.add(key)
            skills.append(skill)
            if len(skills) >= limit:
                return skills
    return skills


def _master_skills(master_payload: Mapping[str, Any], limit: int = 14) -> List[str]:
    sections = _master_sections(master_payload, kind="skills", title="SUMMARY OF QUALIFICATIONS")
    if not sections:
        return []
    skills: List[str] = []
    seen: set[str] = set()
    for line in _split_master_body_items(sections[0].get("body_text"), limit=8):
        for raw_skill in line.split(","):
            skill = _clean_text(raw_skill).lstrip("•-*").strip()
            key = skill.lower()
            if not skill or key in seen:
                continue
            seen.add(key)
            skills.append(skill)
            if len(skills) >= limit:
                return skills
    return skills


def _skills_section(skills: Iterable[Any]) -> Optional[ResumeSection]:
    items = [
        ResumeItem(item_id=f"skill-{index}", text=skill, source_section="skills")
        for index, skill in enumerate((_clean_text(value) for value in skills), start=1)
        if skill
    ]
    if not items:
        return None
    return ResumeSection(kind="skills", heading="SUMMARY OF QUALIFICATIONS", items=items)


def _entry_index(item_id: str) -> int:
    parts = _clean_text(item_id).split("_")
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            return 0
    return 0


def _items_for_entry(items: List[ResumeItem], index: int) -> List[ResumeItem]:
    matching = [item for item in items if _entry_index(item.item_id) == index]
    if matching:
        return matching
    return items if index == 0 else []


def _date_range(start: Any, end: Any) -> str:
    start_text = _clean_text(start)
    end_text = _clean_text(end)
    if start_text and end_text:
        return f"{start_text} - {end_text}"
    return start_text or end_text


def _experience_entries(canonical_cv: Mapping[str, Any], items: List[ResumeItem]) -> List[ResumeEntry]:
    entries: List[ResumeEntry] = []
    for index, raw_entry in enumerate(_as_list(canonical_cv.get("experience"))):
        entry = _as_dict(raw_entry)
        entry_items = _items_for_entry(items, index)
        if not entry_items:
            continue
        entries.append(
            ResumeEntry(
                entry_id=f"experience-{index + 1}",
                title=_clean_text(entry.get("role")),
                organization=_clean_text(entry.get("employer")),
                location=_clean_text(entry.get("location")),
                date_range=_date_range(entry.get("start_date"), entry.get("end_date")),
                items=entry_items,
            )
        )
    if not entries and items:
        entries.append(ResumeEntry(entry_id="experience-1", title="Experience", items=items))
    return entries


def _project_entries(canonical_cv: Mapping[str, Any], items: List[ResumeItem]) -> List[ResumeEntry]:
    entries: List[ResumeEntry] = []
    for index, raw_entry in enumerate(_as_list(canonical_cv.get("projects"))):
        entry = _as_dict(raw_entry)
        entry_items = _items_for_entry(items, index)
        if not entry_items:
            continue
        entries.append(
            ResumeEntry(
                entry_id=f"project-{index + 1}",
                title=_clean_text(entry.get("title")),
                organization=_clean_text(entry.get("institution")),
                date_range=_clean_text(entry.get("date")),
                items=entry_items,
            )
        )
    if not entries and items:
        entries.append(ResumeEntry(entry_id="project-1", title="Projects", items=items))
    return entries


def _education_entries(canonical_cv: Mapping[str, Any], items: List[ResumeItem]) -> List[ResumeEntry]:
    entries: List[ResumeEntry] = []
    for index, raw_entry in enumerate(_as_list(canonical_cv.get("education"))):
        entry = _as_dict(raw_entry)
        entry_items = _items_for_entry(items, index)
        if not entry_items:
            continue
        title_parts = [
            _clean_text(entry.get("degree")),
            _clean_text(entry.get("field_of_study")),
        ]
        entries.append(
            ResumeEntry(
                entry_id=f"education-{index + 1}",
                title=" - ".join(part for part in title_parts if part),
                organization=_clean_text(entry.get("institution")),
                date_range=_date_range(entry.get("start_date"), entry.get("end_date")),
                items=entry_items,
            )
        )
    if not entries and items:
        entries.append(ResumeEntry(entry_id="education-1", title="Education", items=items))
    return entries


def build_resume_layout(
    result_payload: Mapping[str, Any],
    *,
    owner_name: str,
    target_role: str = "",
    company_name: str = "",
    expected_keywords: Optional[List[str]] = None,
    master_payload: Optional[Mapping[str, Any]] = None,
) -> ResumeLayout:
    payload = _as_dict(result_payload)
    tailored_output = _as_dict(payload.get("tailored_output"))
    page_budget = _as_dict(payload.get("page_budget"))
    canonical_cv = _as_dict(payload.get("canonical_cv"))
    master = _as_dict(master_payload)
    contact = extract_contact_from_master_text(_clean_text(master.get("raw_text")))
    if not any([contact.location, contact.phone, contact.email, contact.links]):
        contact = ResumeContact.model_validate(_as_dict(canonical_cv.get("contact")))

    sections: List[ResumeSection] = []
    for kind, heading, selection_key in SECTION_CONFIG:
        items = _active_items(_as_list(tailored_output.get(selection_key)), kind)
        if kind == "profile" and not items:
            items = _canonical_profile_items(canonical_cv)
        if kind == "profile" and not items:
            items = _master_profile_items(master)
        if items:
            sections.append(ResumeSection(kind=kind, heading=heading, items=items))

    highlighted_skills = (
        _as_list(tailored_output.get("skills_to_highlight"))
        or _canonical_skills(canonical_cv)
        or _master_skills(master)
    )
    skills = _skills_section(highlighted_skills)
    if skills is not None:
        profile_index = next((index for index, section in enumerate(sections) if section.kind == "profile"), None)
        if profile_index is None:
            sections.insert(0, skills)
        else:
            sections.insert(profile_index + 1, skills)

    section_items = {section.kind: section.items for section in sections}
    experience_entries = _experience_entries(canonical_cv, section_items.get("experience", []))
    project_entries = _project_entries(canonical_cv, section_items.get("projects", []))
    education_entries = _education_entries(canonical_cv, section_items.get("education", []))

    max_pages = page_budget.get("max_pages", 2)
    try:
        max_pages = int(max_pages)
    except (TypeError, ValueError):
        max_pages = 2

    return ResumeLayout(
        owner_name=owner_name,
        contact=contact,
        target_role=target_role,
        company_name=company_name,
        max_pages=max_pages,
        sections=sections,
        experience_entries=experience_entries,
        project_entries=project_entries,
        education_entries=education_entries,
        expected_keywords=list(expected_keywords or []),
    )
