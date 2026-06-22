from __future__ import annotations

import re
from pathlib import Path
from typing import List

from api.app.schemas.resume_render import PdfTextValidation, ResumeLayout

try:
    import pdfplumber
except ImportError:  # pragma: no cover - dependency availability is environment-specific.
    pdfplumber = None


SUCCESS_NOTE = "PDF text extraction passed ATS readability checks."


def _normalize(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _contains_normalized_term(normalized_text: str, term: str) -> bool:
    normalized_term = _normalize(term)
    if not normalized_term:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None


def extract_pdf_text(pdf_path: str) -> str:
    path = Path(pdf_path)
    if not path.exists():
        return ""
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is required to extract PDF text.")

    with pdfplumber.open(path) as pdf:
        page_text = [(page.extract_text() or "").strip() for page in pdf.pages]
    return "\n".join(text for text in page_text if text).strip()


def _expected_non_skill_items(layout: ResumeLayout) -> List[str]:
    return [
        item.text
        for section in layout.sections
        if _normalize(section.kind) != "skills"
        for item in section.items
        if _normalize(item.text)
    ]


def _section_order_passed(layout: ResumeLayout, normalized_text: str) -> bool:
    cursor = -1
    for section in layout.sections:
        heading = _normalize(section.heading)
        if not heading:
            continue
        position = normalized_text.find(heading, cursor + 1)
        if position == -1:
            if heading in normalized_text:
                return False
            continue
        cursor = position
    return True


def validate_pdf_text(pdf_path: str, layout: ResumeLayout) -> PdfTextValidation:
    extracted_text = extract_pdf_text(pdf_path)
    normalized_text = _normalize(extracted_text)
    owner_name_missing = bool(_normalize(layout.owner_name)) and not _contains_normalized_term(
        normalized_text, layout.owner_name
    )

    missing_headings = [
        section.heading
        for section in layout.sections
        if _normalize(section.heading) and _normalize(section.heading) not in normalized_text
    ]
    missing_items = [
        item_text
        for item_text in _expected_non_skill_items(layout)
        if _normalize(item_text) not in normalized_text
    ]
    missing_keywords = [
        keyword
        for keyword in layout.expected_keywords
        if _normalize(keyword) and not _contains_normalized_term(normalized_text, keyword)
    ]
    order_passed = _section_order_passed(layout, normalized_text)

    notes: List[str] = []
    if owner_name_missing:
        notes.append(f"Owner name missing from extracted text: {layout.owner_name}")
    if missing_headings:
        notes.append(f"Missing headings: {', '.join(missing_headings)}")
    if missing_items:
        notes.append(f"Missing selected items: {len(missing_items)}")
    if missing_keywords:
        notes.append(f"Missing keywords: {', '.join(missing_keywords)}")
    if not order_passed:
        notes.append("Section reading order did not match layout order.")
    if not notes:
        notes.append(SUCCESS_NOTE)

    return PdfTextValidation(
        ats_parse_passed=(
            not owner_name_missing
            and not missing_headings
            and not missing_items
            and not missing_keywords
            and order_passed
        ),
        extracted_text=extracted_text,
        missing_headings=missing_headings,
        missing_items=missing_items,
        missing_keywords=missing_keywords,
        order_passed=order_passed,
        notes=notes,
    )
