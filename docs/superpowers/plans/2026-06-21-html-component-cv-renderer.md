# HTML Component CV Renderer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the final CV render path with deterministic HTML/CSS resume components that generate ATS-readable two-page PDFs while keeping DOCX as an editable compatibility output.

**Architecture:** ApplAI Core remains the source of truth for tailoring, provenance, compression, rendering, and validation. Tailoring output is converted into a structured resume layout model, rendered into real-text HTML, printed to PDF with a browser engine, then validated with page-count and PDF text-extraction gates. Eve remains a thin adapter over Core API metadata.

**Tech Stack:** Python, FastAPI, Pydantic, pdfplumber, Playwright Python, HTML/CSS print styles, existing React/Vite approval UI.

**Repository rule:** Do not commit unless Ata explicitly asks. Each task ends with a checkpoint listing changed files and verification commands instead of an automatic commit.

---

## File Structure

- Create: `api/app/schemas/resume_render.py`
  - Pydantic contracts for `ResumeLayout`, `ResumeSection`, `ResumeItem`, `PdfTextValidation`, and `HtmlRenderResult`.
- Create: `api/app/services/resume_layout_service.py`
  - Converts `TailoringResultPayload` into renderer-friendly layout sections while preserving provenance and unsupported-claim metadata.
- Create: `api/app/services/html_resume_renderer.py`
  - Renders layout models into HTML/CSS and produces PDFs with Playwright.
- Create: `api/app/services/pdf_text_validation_service.py`
  - Uses `pdfplumber` to validate extractable headings, selected bullet text, keywords, and reading order.
- Create: `api/app/templates/resume/default.html`
  - Controlled HTML document shell for final CV rendering.
- Create: `api/app/templates/resume/default.css`
  - Print-focused ATS-readable resume CSS.
- Modify: `api/app/services/export_service.py`
  - Use HTML PDF output as the final CV artifact and keep DOCX output as optional compatibility metadata.
- Modify: `api/app/schemas/tailoring.py`
  - Add render metadata fields for `html_path`, `ats_parse_passed`, and `ats_parse_notes`.
- Modify: `eve/lib/contracts.ts`
  - Add optional render metadata fields without moving logic into Eve.
- Modify: `eve/tools/render_cv.ts`
  - Pass through Core render metadata.
- Modify: `web/src/lib/types.ts`
  - Mirror new export/render metadata.
- Modify: `web/src/pages/RunsPage.tsx`
  - Display HTML/PDF render status and ATS parse status.
- Create: `tests/test_resume_layout_service.py`
  - Unit tests for layout conversion.
- Create: `tests/test_html_resume_renderer.py`
  - Unit tests for generated HTML structure and CSS constraints.
- Create: `tests/test_pdf_text_validation_service.py`
  - Unit tests for ATS extraction validation.
- Modify: `tests/test_tailoring_service.py`
  - Update export expectations from DOCX-only draft toward HTML-rendered PDF final output.

---

### Task 1: Resume Layout Model

**Files:**
- Create: `api/app/schemas/resume_render.py`
- Create: `api/app/services/resume_layout_service.py`
- Create: `tests/test_resume_layout_service.py`

- [ ] **Step 1: Write failing layout conversion tests**

Add tests that prove selected bullets, provenance, unsupported-claim flags, and section order survive conversion.

```python
from api.app.services.resume_layout_service import build_resume_layout


def test_layout_preserves_section_order_and_provenance():
    payload = {
        "tailored_output": {
            "profile_selections": [
                {
                    "bullet_id": "profile-1",
                    "section": "profile",
                    "original_text": "Built Python automation for CRM workflows.",
                    "new_text": "Built Python automation for CRM workflows.",
                    "action": "select_as_is",
                    "relevance_score": 0.9,
                    "jd_requirements_addressed": ["Python"],
                    "provenance": [{"source_type": "career_brain", "source_id": "ev-1", "source_label": "Master CV"}],
                    "unsupported_claims": [],
                }
            ],
            "experience_selections": [],
            "project_selections": [],
            "education_selections": [],
            "skills_to_highlight": ["Python", "CRM"],
        },
        "selected_evidence_block_ids": ["ev-1"],
        "page_budget": {"max_pages": 2, "estimated_words": 8},
    }

    layout = build_resume_layout(payload, owner_name="Ata Selekoglu")

    assert layout.owner_name == "Ata Selekoglu"
    assert [section.kind for section in layout.sections] == ["profile", "skills"]
    assert layout.sections[0].items[0].text == "Built Python automation for CRM workflows."
    assert layout.sections[0].items[0].provenance[0].source_id == "ev-1"
    assert layout.sections[0].items[0].unsupported_claims == []
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```powershell
py -m unittest tests.test_resume_layout_service
```

Expected: fail because `api.app.services.resume_layout_service` does not exist.

- [ ] **Step 3: Add Pydantic layout schemas**

Create `api/app/schemas/resume_render.py` with:

```python
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
    target_role: str = ""
    company_name: str = ""
    max_pages: int = 2
    sections: List[ResumeSection] = Field(default_factory=list)
    expected_keywords: List[str] = Field(default_factory=list)
```

- [ ] **Step 4: Add layout conversion service**

Create `api/app/services/resume_layout_service.py` with deterministic section ordering and no LLM calls.

```python
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from api.app.schemas.resume_render import ResumeItem, ResumeLayout, ResumeSection
from api.app.schemas.tailoring import ProvenanceRef


SECTION_CONFIG = [
    ("profile", "PROFILE", "profile_selections"),
    ("experience", "EXPERIENCE", "experience_selections"),
    ("projects", "PROJECTS", "project_selections"),
    ("education", "EDUCATION", "education_selections"),
]


def _active_items(selections: Iterable[Dict[str, Any]], source_section: str) -> List[ResumeItem]:
    items: List[ResumeItem] = []
    for selection in selections:
        if selection.get("action") == "deselect":
            continue
        text = str(selection.get("new_text") or selection.get("original_text") or "").strip()
        if not text:
            continue
        items.append(
            ResumeItem(
                item_id=str(selection.get("bullet_id") or f"{source_section}-{len(items) + 1}"),
                text=text,
                source_section=source_section,
                relevance_score=float(selection.get("relevance_score") or 0.0),
                provenance=[ProvenanceRef.model_validate(ref) for ref in selection.get("provenance", [])],
                unsupported_claims=list(selection.get("unsupported_claims") or []),
            )
        )
    return items


def build_resume_layout(
    result_payload: Dict[str, Any],
    *,
    owner_name: str,
    target_role: str = "",
    company_name: str = "",
    expected_keywords: List[str] | None = None,
) -> ResumeLayout:
    tailored = result_payload.get("tailored_output", {})
    page_budget = result_payload.get("page_budget", {})
    sections: List[ResumeSection] = []
    for kind, heading, key in SECTION_CONFIG:
        items = _active_items(tailored.get(key, []) or [], kind)
        if items:
            sections.append(ResumeSection(kind=kind, heading=heading, items=items))

    skills = [str(skill).strip() for skill in tailored.get("skills_to_highlight", []) if str(skill).strip()]
    if skills:
        sections.insert(
            1 if sections and sections[0].kind == "profile" else 0,
            ResumeSection(
                kind="skills",
                heading="SUMMARY OF QUALIFICATIONS",
                items=[
                    ResumeItem(
                        item_id=f"skill-{index + 1}",
                        text=skill,
                        source_section="skills",
                    )
                    for index, skill in enumerate(skills)
                ],
            ),
        )

    return ResumeLayout(
        owner_name=owner_name,
        target_role=target_role,
        company_name=company_name,
        max_pages=int(page_budget.get("max_pages") or 2),
        sections=sections,
        expected_keywords=expected_keywords or [],
    )
```

- [ ] **Step 5: Run the focused test**

Run:

```powershell
py -m unittest tests.test_resume_layout_service
```

Expected: pass.

- [ ] **Step 6: Checkpoint**

Record changed files and do not commit unless Ata explicitly asks.

---

### Task 2: HTML Resume Components

**Files:**
- Create: `api/app/templates/resume/default.html`
- Create: `api/app/templates/resume/default.css`
- Create: `api/app/services/html_resume_renderer.py`
- Create: `tests/test_html_resume_renderer.py`

- [ ] **Step 1: Write failing HTML renderer tests**

```python
from api.app.schemas.resume_render import ResumeItem, ResumeLayout, ResumeSection
from api.app.services.html_resume_renderer import render_resume_html


def test_html_renderer_outputs_real_text_not_images_or_canvas():
    layout = ResumeLayout(
        owner_name="Ata Selekoglu",
        sections=[
            ResumeSection(
                kind="profile",
                heading="PROFILE",
                items=[ResumeItem(item_id="p1", text="Built Python automation.", source_section="profile")],
            )
        ],
        expected_keywords=["Python"],
    )

    html = render_resume_html(layout)

    assert "Ata Selekoglu" in html
    assert "Built Python automation." in html
    assert "<canvas" not in html.lower()
    assert "<img" not in html.lower()
    assert "@page" in html
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```powershell
py -m unittest tests.test_html_resume_renderer
```

Expected: fail because `html_resume_renderer` does not exist.

- [ ] **Step 3: Add HTML/CSS render functions**

Create `api/app/services/html_resume_renderer.py` with pure string rendering using `html.escape`.

```python
from __future__ import annotations

from html import escape
from pathlib import Path

from api.app.schemas.resume_render import ResumeLayout


CSS = """
@page { size: Letter; margin: 0.48in 0.55in; }
* { box-sizing: border-box; }
body {
  font-family: Arial, Helvetica, sans-serif;
  color: #111;
  font-size: 10.2pt;
  line-height: 1.28;
  margin: 0;
}
.resume-header { border-bottom: 1px solid #222; padding-bottom: 6px; margin-bottom: 8px; }
.resume-name { font-size: 18pt; font-weight: 700; letter-spacing: 0; }
.resume-meta { font-size: 9.5pt; margin-top: 2px; }
.resume-section { break-inside: avoid; margin-top: 8px; }
.resume-section h2 {
  font-size: 10.5pt;
  margin: 0 0 4px;
  padding-bottom: 2px;
  border-bottom: 0.5px solid #999;
  letter-spacing: 0;
}
ul { margin: 0; padding-left: 16px; }
li { margin: 0 0 3px; }
.skills-list { display: block; }
"""


def render_resume_html(layout: ResumeLayout) -> str:
    sections = []
    for section in layout.sections:
        if section.kind == "skills":
            skills = ", ".join(escape(item.text) for item in section.items)
            body = f'<div class="skills-list">{skills}</div>'
        else:
            body = "<ul>" + "".join(f"<li>{escape(item.text)}</li>" for item in section.items) + "</ul>"
        sections.append(
            f'<section class="resume-section" data-section="{escape(section.kind)}">'
            f"<h2>{escape(section.heading)}</h2>{body}</section>"
        )

    role_line = " | ".join(part for part in [layout.target_role, layout.company_name] if part)
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<style>{CSS}</style></head><body>"
        "<main class=\"resume-document\">"
        "<header class=\"resume-header\">"
        f"<div class=\"resume-name\">{escape(layout.owner_name)}</div>"
        f"<div class=\"resume-meta\">{escape(role_line)}</div>"
        "</header>"
        + "".join(sections)
        + "</main></body></html>"
    )


def write_resume_html(layout: ResumeLayout, output_path: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_resume_html(layout), encoding="utf-8")
    return str(path)
```

- [ ] **Step 4: Run HTML renderer tests**

Run:

```powershell
py -m unittest tests.test_html_resume_renderer
```

Expected: pass.

- [ ] **Step 5: Checkpoint**

Record changed files and do not commit unless Ata explicitly asks.

---

### Task 3: PDF Generation And ATS Text Gate

**Files:**
- Modify: `requirements.txt`
- Modify: `api/app/services/html_resume_renderer.py`
- Create: `api/app/services/pdf_text_validation_service.py`
- Create: `tests/test_pdf_text_validation_service.py`

- [ ] **Step 1: Add dependencies**

Add Playwright Python to `requirements.txt`:

```text
playwright
```

After installing dependencies later, Chromium must be installed with:

```powershell
py -m playwright install chromium
```

- [ ] **Step 2: Write ATS validation tests with a mocked extracted text**

```python
import unittest
from unittest.mock import patch

from api.app.schemas.resume_render import ResumeItem, ResumeLayout, ResumeSection
from api.app.services.pdf_text_validation_service import validate_pdf_text


class PdfTextValidationServiceTest(unittest.TestCase):
    def test_validate_pdf_text_requires_headings_items_keywords_and_order(self):
        layout = ResumeLayout(
            owner_name="Ata Selekoglu",
            expected_keywords=["Python"],
            sections=[
                ResumeSection(
                    kind="profile",
                    heading="PROFILE",
                    items=[ResumeItem(item_id="p1", text="Built Python automation.", source_section="profile")],
                ),
                ResumeSection(
                    kind="experience",
                    heading="EXPERIENCE",
                    items=[ResumeItem(item_id="e1", text="Delivered CRM integrations.", source_section="experience")],
                ),
            ],
        )
        extracted = "Ata Selekoglu\nPROFILE\nBuilt Python automation.\nEXPERIENCE\nDelivered CRM integrations."
        with patch("api.app.services.pdf_text_validation_service.extract_pdf_text", return_value=extracted):
            result = validate_pdf_text("fake.pdf", layout)

        self.assertTrue(result.ats_parse_passed)
        self.assertEqual(result.missing_headings, [])
        self.assertEqual(result.missing_items, [])
        self.assertEqual(result.missing_keywords, [])
        self.assertTrue(result.order_passed)
```

- [ ] **Step 3: Implement PDF text validation**

Create `api/app/services/pdf_text_validation_service.py`.

```python
from __future__ import annotations

from pathlib import Path

import pdfplumber

from api.app.schemas.resume_render import PdfTextValidation, ResumeLayout


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def extract_pdf_text(pdf_path: str) -> str:
    if not Path(pdf_path).exists():
        return ""
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join((page.extract_text() or "").strip() for page in pdf.pages).strip()


def validate_pdf_text(pdf_path: str, layout: ResumeLayout) -> PdfTextValidation:
    extracted = extract_pdf_text(pdf_path)
    normalized = _normalize(extracted)

    missing_headings = [section.heading for section in layout.sections if _normalize(section.heading) not in normalized]
    expected_items = [
        item.text
        for section in layout.sections
        for item in section.items
        if section.kind != "skills"
    ]
    missing_items = [item for item in expected_items if _normalize(item) not in normalized]
    missing_keywords = [keyword for keyword in layout.expected_keywords if _normalize(keyword) not in normalized]

    cursor = -1
    order_passed = True
    for section in layout.sections:
        position = normalized.find(_normalize(section.heading))
        if position == -1:
            continue
        if position < cursor:
            order_passed = False
            break
        cursor = position

    notes = []
    if missing_headings:
        notes.append(f"Missing headings: {', '.join(missing_headings)}")
    if missing_items:
        notes.append(f"Missing selected items: {len(missing_items)}")
    if missing_keywords:
        notes.append(f"Missing keywords: {', '.join(missing_keywords)}")
    if not order_passed:
        notes.append("Section reading order did not match layout order.")
    if not notes:
        notes.append("PDF text extraction passed ATS readability checks.")

    return PdfTextValidation(
        ats_parse_passed=not missing_headings and not missing_items and not missing_keywords and order_passed,
        extracted_text=extracted,
        missing_headings=missing_headings,
        missing_items=missing_items,
        missing_keywords=missing_keywords,
        order_passed=order_passed,
        notes=notes,
    )
```

- [ ] **Step 4: Add Playwright PDF render function**

Extend `api/app/services/html_resume_renderer.py`:

```python
from playwright.sync_api import sync_playwright


def render_resume_pdf(layout: ResumeLayout, html_path: str, pdf_path: str) -> str:
    html_file = Path(write_resume_html(layout, html_path)).resolve()
    output = Path(pdf_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(html_file.as_uri(), wait_until="networkidle")
        page.pdf(path=str(output), format="Letter", print_background=True)
        browser.close()
    return str(output)
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
py -m unittest tests.test_pdf_text_validation_service tests.test_html_resume_renderer
```

Expected: pass. If Playwright browser binaries are not installed, PDF integration tests should skip with a clear message instead of failing unit-only runs.

- [ ] **Step 6: Checkpoint**

Record changed files and do not commit unless Ata explicitly asks.

---

### Task 4: Export Service Integration

**Files:**
- Modify: `api/app/schemas/tailoring.py`
- Modify: `api/app/services/export_service.py`
- Modify: `tests/test_tailoring_service.py`

- [ ] **Step 1: Write export tests for HTML PDF final output**

Add a test that patches the renderer and PDF validators so the export service can be verified without launching Chromium.

```python
from pathlib import Path
from unittest.mock import patch

from api.app.services.export_service import export_run


def test_export_uses_html_pdf_as_final_cv_artifact(self):
    pdf_path = str(Path(settings.docs_dir, "Ata_CV_Tailored_CoreCo.pdf"))
    html_path = str(Path(settings.docs_dir, "Ata_CV_Tailored_CoreCo.html"))
    Path(pdf_path).write_bytes(b"%PDF-1.4 placeholder")
    Path(html_path).write_text("<html>Ata</html>", encoding="utf-8")

    with patch("api.app.services.export_service.render_resume_pdf", return_value=pdf_path), \
         patch("api.app.services.export_service.write_resume_html", return_value=html_path), \
         patch("api.app.services.export_service._pdf_page_count", return_value=2), \
         patch("api.app.services.export_service.validate_pdf_text") as validate:
        validate.return_value.ats_parse_passed = True
        validate.return_value.notes = ["PDF text extraction passed ATS readability checks."]
        export = export_run(self.run_id)

    assert export.pdf_path == pdf_path
    assert export.page_count == 2
    assert export.layout_passed is True
```

- [ ] **Step 2: Extend export schemas**

Add optional fields to `ExportResponse` and artifact metadata in `api/app/schemas/tailoring.py`:

```python
html_path: Optional[str] = None
ats_parse_passed: Optional[bool] = None
ats_parse_notes: List[str] = Field(default_factory=list)
```

- [ ] **Step 3: Integrate HTML PDF rendering in `export_service.py`**

Implement the sequence:

```text
rehydrate workflow result
build ResumeLayout from result payload
write HTML artifact
render PDF artifact
count PDF pages
validate PDF text extraction
set layout_passed = page_count <= max_pages and ats_parse_passed
persist artifacts and layout_validation metadata
return pdf_path, html_path, page_count, layout_passed, ats_parse_passed
```

Keep the existing DOCX bridge available as a compatibility path named `docx_path`, but do not use DOCX as the final CV page-count source.

- [ ] **Step 4: Run focused export tests**

Run:

```powershell
py -m unittest tests.test_tailoring_service
```

Expected: pass with updated HTML PDF export expectations.

- [ ] **Step 5: Checkpoint**

Record changed files and do not commit unless Ata explicitly asks.

---

### Task 5: Eve And Web Metadata Pass-Through

**Files:**
- Modify: `eve/lib/contracts.ts`
- Modify: `eve/tools/render_cv.ts`
- Modify: `web/src/lib/types.ts`
- Modify: `web/src/pages/RunsPage.tsx`

- [ ] **Step 1: Update TypeScript contracts**

Add optional fields:

```ts
html_path?: string | null;
ats_parse_passed?: boolean | null;
ats_parse_notes?: string[];
```

- [ ] **Step 2: Keep Eve as a thin adapter**

Update `eve/tools/render_cv.ts` so it only returns Core metadata:

```ts
return {
  run_id: result.run_id,
  cv_path: result.cv_path,
  docx_path: input.format === "pdf" ? "" : result.docx_path ?? "",
  pdf_path: input.format === "docx" ? "" : result.pdf_path ?? "",
  html_path: result.html_path ?? "",
  page_count: result.page_count ?? null,
  layout_passed: result.layout_passed ?? null,
  ats_parse_passed: result.ats_parse_passed ?? null,
  ats_parse_notes: result.ats_parse_notes ?? [],
  artifact_ids: result.artifact_ids ?? [],
};
```

- [ ] **Step 3: Show render and ATS status in run details**

In `web/src/pages/RunsPage.tsx`, display:

```text
PDF pages: 2 / 2
Visual layout: passed
ATS text extraction: passed
```

If `ats_parse_passed` is false, show notes from `ats_parse_notes`.

- [ ] **Step 4: Run TypeScript checks**

Run:

```powershell
cd eve
npm.cmd run typecheck
cd ..\web
npm.cmd run build
```

Expected: Eve typecheck passes and web build passes.

- [ ] **Step 5: Checkpoint**

Record changed files and do not commit unless Ata explicitly asks.

---

### Task 6: Full Verification

**Files:**
- Modify: `TODO.md`
- Modify: `future_roadmap.md`
- Modify: `README.md`

- [ ] **Step 1: Run backend tests**

Run:

```powershell
py -m unittest discover -s tests -p "test_*.py"
```

Expected: pass, except private tailored-example fixture tests may fail with `0 != 20` if `docs/tailored_examples/` PDFs are absent. If absent, report that as a fixture availability issue, not a renderer regression.

- [ ] **Step 2: Run FastAPI import check**

Run:

```powershell
py -c "import api.app.main; print(api.app.main.app.title)"
```

Expected: prints the FastAPI app title without import errors.

- [ ] **Step 3: Run Eve and web checks**

Run:

```powershell
cd eve
npm.cmd test
npm.cmd run typecheck
cd ..\web
npm.cmd run build
```

Expected: all checks pass.

- [ ] **Step 4: Run whitespace check**

Run:

```powershell
git -c safe.directory=C:/Users/asele/ApplAI diff --check
```

Expected: no whitespace errors.

- [ ] **Step 5: Update docs status**

Update `TODO.md`, `future_roadmap.md`, and `README.md` to reflect implemented HTML-first rendering, ATS parse validation, and any remaining approval UI work.

- [ ] **Step 6: Final handoff**

Report:

- Files changed.
- Commands run.
- Tests/checks passed or failed.
- Any blockers.
- Whether `TODO.md` needs more status changes.
- Any architecture deviation from `docs/career-manager-sprint0-plan.md`.
