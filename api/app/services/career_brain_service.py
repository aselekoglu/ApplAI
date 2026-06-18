from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List, Optional

from api.app.config import settings
from api.app.schemas.career_brain import CareerBrainProfile, EvidenceBlock, SkillInventory, utc_now_iso


DEFAULT_ROLE_PREFERENCES = [
    "Software Developer",
    "AI Automation Developer",
    "Technical Analyst",
    "Business Systems Analyst",
    "Data Analyst",
]

DEFAULT_SKILL_CATEGORIES = {
    "programming": ["Python", "JavaScript", "TypeScript", "Java", "Kotlin", "SQL"],
    "web": ["FastAPI", "React", "Vite", "REST APIs", "HTML", "CSS"],
    "automation": ["Google Apps Script", "workflow automation", "document automation"],
    "data": ["data analysis", "ETL", "reporting", "PostgreSQL"],
    "ai": ["LLMs", "Gemini", "prompting", "AI-assisted workflows"],
}


def career_brain_dir() -> Path:
    return Path(settings.career_brain_dir)


def career_brain_profile_path() -> Path:
    return career_brain_dir() / "profile.json"


def _slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or fallback


def _iter_master_payloads() -> Iterable[tuple[Path, dict]]:
    exports_dir = Path(settings.json_exports_dir)
    if not exports_dir.exists():
        return []

    payloads: List[tuple[Path, dict]] = []
    for path in sorted(exports_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            payloads.append((path, payload))
    return payloads


def _evidence_from_master(path: Path, payload: dict) -> List[EvidenceBlock]:
    source_label = str(payload.get("source_file") or payload.get("source_pdf") or path.name)
    raw_text = str(payload.get("raw_text") or "").strip()
    sections = payload.get("sections")
    blocks: List[EvidenceBlock] = []

    if isinstance(sections, list):
        for index, section in enumerate(sections, start=1):
            if not isinstance(section, dict):
                continue
            title = str(section.get("title") or section.get("kind") or f"section {index}").strip()
            text = str(section.get("body_text") or section.get("text") or "").strip()
            if not text:
                continue
            blocks.append(
                EvidenceBlock(
                    block_id=f"master_{path.stem}_{index}",
                    kind="profile",
                    text=text,
                    source_label=f"{source_label}: {title}",
                    source_path=str(path),
                    provenance=[str(path)],
                    relevance_tags=[_slug(title, "section")],
                    priority=3,
                    truth_constraints=["Use only as sourced career evidence; do not inflate scope, dates, or metrics."],
                    length_estimate=len(text),
                )
            )

    if not blocks and raw_text:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", raw_text) if p.strip()]
        for index, paragraph in enumerate(paragraphs[:24], start=1):
            blocks.append(
                EvidenceBlock(
                    block_id=f"master_{path.stem}_{index}",
                    kind="profile",
                    text=paragraph,
                    source_label=source_label,
                    source_path=str(path),
                    provenance=[str(path)],
                    priority=3,
                    truth_constraints=["Use only as sourced career evidence; do not inflate scope, dates, or metrics."],
                    length_estimate=len(paragraph),
                )
            )
    return blocks


def default_career_brain_profile() -> CareerBrainProfile:
    source_masters: List[str] = []
    evidence_blocks: List[EvidenceBlock] = []
    for path, payload in _iter_master_payloads():
        source_masters.append(str(path))
        evidence_blocks.extend(_evidence_from_master(path, payload))

    if not evidence_blocks:
        seed_text = (
            "Software developer and technical business analyst profile seed. "
            "Replace or enrich this with reviewed master CV evidence before using it for final application materials."
        )
        evidence_blocks.append(
            EvidenceBlock(
                block_id="seed_profile_summary",
                kind="profile",
                text=seed_text,
                source_label="ApplAI default seed",
                provenance=["generated seed pending reviewed master CV import"],
                relevance_tags=["seed"],
                priority=1,
                truth_constraints=["Do not use as final source evidence until replaced by reviewed local CV/profile data."],
                length_estimate=len(seed_text),
            )
        )

    return CareerBrainProfile(
        source_masters=source_masters,
        role_preferences={"preferred_roles": DEFAULT_ROLE_PREFERENCES},
        skills=SkillInventory(categories=DEFAULT_SKILL_CATEGORIES),
        evidence_blocks=evidence_blocks,
    )


def ensure_career_brain_profile() -> CareerBrainProfile:
    path = career_brain_profile_path()
    if path.exists():
        return load_career_brain_profile(path)

    profile = default_career_brain_profile()
    save_career_brain_profile(profile, path)
    return profile


def load_career_brain_profile(path: Optional[Path] = None) -> CareerBrainProfile:
    profile_path = path or career_brain_profile_path()
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    return CareerBrainProfile.model_validate(payload)


def save_career_brain_profile(profile: CareerBrainProfile, path: Optional[Path] = None) -> str:
    profile_path = path or career_brain_profile_path()
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = profile.model_copy(update={"updated_at": utc_now_iso()})
    tmp_path = profile_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(normalized.model_dump(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp_path.replace(profile_path)
    return str(profile_path)


def update_career_brain_profile(profile: CareerBrainProfile) -> tuple[CareerBrainProfile, str]:
    path = save_career_brain_profile(profile)
    return load_career_brain_profile(), path
