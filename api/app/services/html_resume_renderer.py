from __future__ import annotations

import re
from html import escape
from pathlib import Path
from typing import Dict, Iterable, List

from api.app.schemas.resume_render import ResumeEntry, ResumeLayout, ResumeSection

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - exercised when optional browser deps are absent.
    sync_playwright = None


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "resume"
DEFAULT_TEMPLATE_PATH = TEMPLATE_DIR / "default.html"
DEFAULT_CSS_PATH = TEMPLATE_DIR / "default.css"
PLACEHOLDER_PATTERN = re.compile(
    r"__(STYLE|OWNER_NAME|CONTACT|RESUME_META|PROFILE_AND_SKILLS|STRUCTURED_ENTRIES|RESUME_SECTIONS)__"
)


def _read_template_asset(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _clean_text(value: str) -> str:
    return str(value or "").strip()


def _escaped_text(value: str) -> str:
    return escape(_clean_text(value), quote=True)


def _render_metadata(layout: ResumeLayout) -> str:
    target_role = _clean_text(layout.target_role)
    company_name = _clean_text(layout.company_name)
    if target_role and company_name:
        return f"{_escaped_text(target_role)} | {_escaped_text(company_name)}"
    if target_role:
        return _escaped_text(target_role)
    if company_name:
        return _escaped_text(company_name)
    return ""


def _render_contact(layout: ResumeLayout) -> str:
    parts = [
        _escaped_text(layout.contact.location),
        _escaped_text(layout.contact.phone),
        _escaped_text(layout.contact.email),
        *[_escaped_text(link) for link in layout.contact.links],
    ]
    parts = [part for part in parts if part]
    if not parts:
        return ""
    return f'      <p class="resume-contact">{" | ".join(parts)}</p>'


def _render_items(section: ResumeSection) -> str:
    items: List[str] = []
    for item in section.items:
        text = _escaped_text(item.text)
        if not text:
            continue
        items.append(f"          <li>{text}</li>")
    return "\n".join(items)


def _render_section(section: ResumeSection) -> str:
    heading = _escaped_text(section.heading)
    if not heading:
        return ""

    kind = escape(_clean_text(section.kind).lower().replace(" ", "-"), quote=True)
    items_html = _render_items(section)
    if not items_html:
        return ""

    list_class = "skills-list" if kind == "skills" else "section-list"
    return "\n".join(
        [
            f'      <section class="resume-section resume-section-{kind}">',
            f"        <h2>{heading}</h2>",
            f'        <ul class="{list_class}">',
            items_html,
            "        </ul>",
            "      </section>",
        ]
    )


def _render_sections(sections: Iterable[ResumeSection]) -> str:
    rendered_sections = [section_html for section in sections if (section_html := _render_section(section))]
    return "\n".join(rendered_sections)


def _render_profile_and_skills(layout: ResumeLayout) -> str:
    sections = [section for section in layout.sections if section.kind in {"profile", "skills"}]
    return "\n".join(_render_section(section) for section in sections)


def _render_entry(entry: ResumeEntry) -> str:
    title = _escaped_text(entry.title)
    organization = _escaped_text(entry.organization)
    location = _escaped_text(entry.location)
    date_range = _escaped_text(entry.date_range)
    meta = " | ".join(part for part in [organization, location] if part)
    title_html = f'<div class="entry-title"><strong>{title}</strong>'
    if date_range:
        title_html += f'<span class="entry-date">{date_range}</span>'
    title_html += "</div>"
    meta_html = f'<div class="entry-meta">{meta}</div>' if meta else ""
    items_html = "\n".join(
        f"          <li>{_escaped_text(item.text)}</li>"
        for item in entry.items
        if _clean_text(item.text)
    )
    if not items_html:
        return ""
    lines = [
        '        <div class="resume-entry">',
        f"          {title_html}",
    ]
    if meta_html:
        lines.append(f"          {meta_html}")
    lines.extend(
        [
            '          <ul class="section-list">',
            items_html,
            "          </ul>",
            "        </div>",
        ]
    )
    return "\n".join(lines)


def _render_entry_section(kind: str, heading: str, entries: Iterable[ResumeEntry]) -> str:
    rendered_entries = [entry_html for entry in entries if (entry_html := _render_entry(entry))]
    if not rendered_entries:
        return ""
    return "\n".join(
        [
            f'      <section class="resume-section resume-section-{kind}">',
            f"        <h2>{_escaped_text(heading)}</h2>",
            *rendered_entries,
            "      </section>",
        ]
    )


def _render_structured_entries(layout: ResumeLayout) -> str:
    return "\n".join(
        section
        for section in [
            _render_entry_section("experience", "RELEVANT EXPERIENCE", layout.experience_entries),
            _render_entry_section("projects", "PROJECTS", layout.project_entries),
            _render_entry_section("education", "EDUCATION", layout.education_entries),
        ]
        if section
    )


def render_resume_html(layout: ResumeLayout) -> str:
    """Render a ResumeLayout into deterministic, ATS-readable HTML."""
    template = _read_template_asset(DEFAULT_TEMPLATE_PATH)
    css = _read_template_asset(DEFAULT_CSS_PATH)
    metadata = _render_metadata(layout)
    metadata_html = f'      <p class="resume-meta">{metadata}</p>' if metadata else ""
    replacements: Dict[str, str] = {
        "STYLE": css,
        "OWNER_NAME": _escaped_text(layout.owner_name),
        "CONTACT": _render_contact(layout),
        "RESUME_META": metadata_html,
        "PROFILE_AND_SKILLS": _render_profile_and_skills(layout),
        "STRUCTURED_ENTRIES": _render_structured_entries(layout),
        "RESUME_SECTIONS": _render_sections(
            section
            for section in layout.sections
            if section.kind not in {"profile", "skills", "experience", "projects", "education"}
        ),
    }

    return PLACEHOLDER_PATTERN.sub(lambda match: replacements[match.group(1)], template)


def write_resume_html(layout: ResumeLayout, output_path: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_resume_html(layout), encoding="utf-8")
    return str(path)


def render_resume_pdf(layout: ResumeLayout, html_path: str, pdf_path: str) -> str:
    if sync_playwright is None:
        raise RuntimeError("Playwright is required to render resume PDFs. Install playwright and Chromium first.")

    html_file = Path(write_resume_html(layout, html_path)).resolve()
    output = Path(pdf_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(html_file.as_uri(), wait_until="networkidle")
            page.pdf(path=str(output), format="Letter", print_background=True)
        finally:
            browser.close()

    return str(output)
