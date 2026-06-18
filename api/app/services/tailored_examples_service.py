from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, List, Optional

import pdfplumber

from api.app.config import settings
from api.app.schemas.tailored_examples import (
    DiffClassification,
    TailoredExample,
    TailoredExampleSection,
    TailoringDecision,
)


KNOWN_SECTION_HEADINGS = {
    "PROFILE",
    "SUMMARY",
    "SUMMARY OF QUALIFICATIONS",
    "HIGHLIGHTS OF QUALIFICATIONS",
    "SKILLS",
    "TECHNICAL SKILLS",
    "EXPERIENCE",
    "RELEVANT EXPERIENCE",
    "WORK EXPERIENCE",
    "PROJECTS",
    "EDUCATION",
    "CERTIFICATIONS",
    "ADDITIONAL",
    "ADDITIONAL EXPERIENCE",
    "OTHER EXPERIENCE",
    "VOLUNTEER EXPERIENCE",
}


def tailored_examples_dir() -> Path:
    return Path(settings.tailored_examples_dir)


def discover_tailored_example_pdfs(root: Optional[Path] = None) -> List[Path]:
    examples_root = root or tailored_examples_dir()
    if not examples_root.exists():
        return []
    return sorted(path for path in examples_root.glob("*.pdf") if path.is_file())


def role_label_from_filename(path: Path) -> str:
    label = path.stem
    label = re.sub(r"^Selekoglu CV\s+", "", label, flags=re.IGNORECASE)
    label = re.sub(r"^\d{4}(?:\.\d{2})?\s*-\s*", "", label).strip()
    label = re.sub(r"\s+", " ", label).strip()
    return label or path.stem


def example_id_from_path(path: Path) -> str:
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^a-z0-9]+", "_", path.stem.lower()).strip("_")
    return f"tailored_{slug}_{digest}"


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def extract_section_headings_from_text(text: str) -> List[str]:
    headings: List[str] = []
    seen = set()
    for raw_line in text.splitlines():
        line = _clean_line(raw_line).strip(":")
        canonical = line.upper()
        if canonical in KNOWN_SECTION_HEADINGS and canonical not in seen:
            headings.append(canonical)
            seen.add(canonical)
    return headings


def extract_sections(text: str) -> List[TailoredExampleSection]:
    headings = set(extract_section_headings_from_text(text))
    sections: List[TailoredExampleSection] = []
    current_heading = ""
    current_lines: List[str] = []

    for raw_line in text.splitlines():
        line = _clean_line(raw_line)
        canonical = line.strip(":").upper()
        if canonical in headings:
            if current_heading:
                sections.append(TailoredExampleSection(heading=current_heading, text="\n".join(current_lines).strip()))
            current_heading = canonical
            current_lines = []
        elif current_heading:
            current_lines.append(line)

    if current_heading:
        sections.append(TailoredExampleSection(heading=current_heading, text="\n".join(current_lines).strip()))
    return sections


def _parse_confidence(page_count: int, text: str, title: Optional[str], headings: List[str], sections: List[TailoredExampleSection]) -> float:
    score = 0.0
    if text.strip():
        score += 0.35
    if page_count > 0:
        score += 0.2
    if title:
        score += 0.1
    if headings:
        score += min(0.2, len(headings) * 0.04)
    if sections:
        score += min(0.15, len(sections) * 0.03)
    return round(min(score, 1.0), 2)


def parse_tailored_example_pdf(path: Path) -> TailoredExample:
    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        metadata = pdf.metadata or {}
        title = metadata.get("Title")
        text = "\n".join((page.extract_text() or "").strip() for page in pdf.pages).strip()

    headings = extract_section_headings_from_text(text)
    sections = extract_sections(text)
    return TailoredExample(
        example_id=example_id_from_path(path),
        source_pdf_path=_relative_path(path),
        role_label=role_label_from_filename(path),
        pdf_title=str(title).strip() if title else None,
        page_count=page_count,
        extracted_text=text,
        section_headings=headings,
        sections=sections,
        parse_confidence=_parse_confidence(page_count, text, str(title).strip() if title else None, headings, sections),
    )


def list_tailored_examples(root: Optional[Path] = None, role_label: Optional[str] = None) -> List[TailoredExample]:
    examples = [parse_tailored_example_pdf(path) for path in discover_tailored_example_pdfs(root)]
    if role_label:
        needle = role_label.lower()
        examples = [example for example in examples if needle in example.role_label.lower()]
    return examples


def _normalized_lines(text: str) -> List[str]:
    lines = []
    for raw_line in text.splitlines():
        line = _clean_line(raw_line)
        if len(line) < 8:
            continue
        if line.upper() in KNOWN_SECTION_HEADINGS:
            continue
        lines.append(line)
    return lines


def _best_match(line: str, candidates: Iterable[str]) -> tuple[str, float]:
    best_line = ""
    best_ratio = 0.0
    for candidate in candidates:
        ratio = SequenceMatcher(None, line.lower(), candidate.lower()).ratio()
        if ratio > best_ratio:
            best_line = candidate
            best_ratio = ratio
    return best_line, best_ratio


def classify_master_example_diff(
    master_text: str,
    example_text: str,
    master_source_path: str = "",
    example_source_path: str = "",
) -> DiffClassification:
    master_lines = _normalized_lines(master_text)
    example_lines = _normalized_lines(example_text)
    master_lookup = {line.lower(): line for line in master_lines}
    example_lookup = {line.lower(): line for line in example_lines}

    decisions: List[TailoringDecision] = []
    matched_master_lines = set()

    for line in example_lines:
        key = line.lower()
        if key in master_lookup:
            matched_master_lines.add(key)
            decisions.append(TailoringDecision(decision_type="retained", text=line, matched_text=master_lookup[key], confidence=1.0))
            continue

        matched_line, ratio = _best_match(line, master_lines)
        if ratio >= 0.72:
            matched_master_lines.add(matched_line.lower())
            decisions.append(
                TailoringDecision(
                    decision_type="shortened_or_reworded",
                    text=line,
                    matched_text=matched_line,
                    confidence=round(ratio, 2),
                )
            )
        else:
            decisions.append(TailoringDecision(decision_type="added", text=line, confidence=0.5))

    for line in master_lines:
        if line.lower() not in matched_master_lines and line.lower() not in example_lookup:
            decisions.append(TailoringDecision(decision_type="removed", text=line, confidence=0.75))

    return DiffClassification(
        master_source_path=master_source_path,
        example_source_path=example_source_path,
        decisions=decisions,
        retained_count=sum(1 for decision in decisions if decision.decision_type == "retained"),
        removed_count=sum(1 for decision in decisions if decision.decision_type == "removed"),
        shortened_or_reworded_count=sum(1 for decision in decisions if decision.decision_type == "shortened_or_reworded"),
        added_count=sum(1 for decision in decisions if decision.decision_type == "added"),
    )
