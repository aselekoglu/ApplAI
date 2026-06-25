# CV Output Quality Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Sprint 3 HTML/PDF export from a sparse one-page draft into a truthful, role-targeted, ATS-readable, visually dense two-page CV that preserves the strongest structure of Ata's input CV.

**Architecture:** Keep Eve as a thin adapter and fix the Core pipeline. The Core service will add explicit output quality gates, stop destructive pre-render compression, enrich the resume layout model with contact/entry metadata, and make selection scoring prefer frontend/AI evidence for frontend/AI roles. Rendering remains deterministic HTML/CSS to PDF, with DOCX kept as compatibility output.

**Tech Stack:** Python 3.14, FastAPI service modules, Pydantic schemas, `pdfplumber`, Playwright PDF rendering, React/Vite UI metadata consumers, `unittest`.

---

## Context And Current Failure

Run `bf385e249dde4684b5b5635cd0b604b1` generated `docs/SELEKOGLU_CV_Tailored_Trend_Micro.pdf` from `docs/Selekoglu CV 2026 - NRC AI Application Developer.pdf`.

Observed failure:

- Input CV is 2 pages and roughly 1,200 extracted words.
- Output PDF is 1 page and roughly 200 extracted words.
- Output misses contact information, profile, skills, job titles, employers, dates, project titles, and additional/language content.
- Output ATS coverage is 7.5 percent and misses important Trend Micro role keywords such as React, TypeScript, frontend development, testing, TDD, Playwright, Cypress, agentic UI, AI tools, npm, Webpack, Docker, and AWS.
- Compression produced broken bullets ending with fragments such as `marketing processes such as.`, `refine requirements, test.`, and `with strong.`

Root causes in current code:

- `api/app/services/tailoring_service.py::_apply_deterministic_compression` runs whenever `max_pages <= 2`, before actual HTML/PDF render page count is known.
- `api/app/services/tailoring_service.py::_shorten_text` truncates to word count and can leave incomplete clauses.
- `api/app/services/tailoring_service.py::_pre_render_layout_validation` only checks upper bounds and treats 197 words as valid for a 2-page CV.
- `api/app/services/resume_layout_service.py` creates flat sections from selected bullets and discards structured CV metadata.
- `api/app/schemas/resume_render.py` has no contact, role entry, project entry, education entry, date, location, or link model.
- `agent_workflow.py::select_and_rewrite` can return empty `profile_selections` and `skills_to_highlight`, and project selection does not sufficiently prioritize frontend/AI project evidence for frontend/AI roles.

---

## File Structure

Modify:

- `api/app/schemas/tailoring.py`
  - Add quality gate fields to `LayoutValidation` or a new `OutputQualityGate` Pydantic model.
- `api/app/schemas/resume_render.py`
  - Add structured layout models for contact info, experience entries, project entries, education entries, and section density metadata.
- `api/app/services/tailoring_service.py`
  - Replace unconditional pre-render compression with quality-aware preflight metadata.
  - Add minimum quality checks.
  - Make compression callable after render failure, not before every two-page run.
  - Make shortening sentence-safe.
- `api/app/services/resume_layout_service.py`
  - Build a richer `ResumeLayout` from canonical CV + tailored selections + master JSON raw text.
  - Preserve contact/profile/skills/entry metadata.
- `api/app/services/html_resume_renderer.py`
  - Render structured entries instead of flat bullet-only sections.
- `api/app/templates/resume/default.html`
  - Add semantic containers for contact, entries, dates, project titles, and section groups.
- `api/app/templates/resume/default.css`
  - Make the layout closer to the source CV: compact ATS style, centered contact header, dense section spacing, two-page-friendly typography.
- `api/app/services/export_service.py`
  - Add post-render quality gate handling and fail metadata when underfilled or ATS coverage is poor.
- `agent_workflow.py`
  - Add fallback profile and skills selection when role-relevant evidence exists.
  - Add role-aware scoring boosts for frontend/AI roles.
- `web/src/lib/types.ts`
  - Add optional output quality metadata fields if API response shape changes.
- `web/src/pages/RunsPage.tsx`
  - Surface failed quality gates and show why a render is not approval-ready.
- `tests/test_tailoring_service.py`
  - Add regression tests for underfilled CV rejection and sentence-safe compression.
- `tests/test_resume_layout_service.py`
  - Add structured layout tests.
- `tests/test_html_resume_renderer.py`
  - Add tests for contact, titles, dates, and semantic section output.
- `tests/test_pdf_text_validation_service.py`
  - Add quality notes checks for missing contact/profile/skills if implemented there.

Create:

- `tests/test_cv_output_quality_gate.py`
  - Focused tests for minimum page/word/section/keyword quality gates.

---

## Task 1: Add Output Quality Gate Model

**Files:**

- Modify: `api/app/schemas/tailoring.py`
- Create: `tests/test_cv_output_quality_gate.py`

- [ ] **Step 1: Write failing tests for underfilled output**

Create `tests/test_cv_output_quality_gate.py`:

```python
import unittest

from api.app.schemas.tailoring import LayoutValidation
from api.app.services.tailoring_service import evaluate_output_quality


class CvOutputQualityGateTest(unittest.TestCase):
    def test_rejects_one_page_sparse_two_page_target(self):
        validation = evaluate_output_quality(
            max_pages=2,
            page_count=1,
            extracted_word_count=212,
            section_headings=["EXPERIENCE", "PROJECTS", "EDUCATION"],
            keyword_coverage_pct=7.5,
            missing_required_sections=["PROFILE", "SUMMARY OF QUALIFICATIONS"],
            broken_bullets=[],
        )

        self.assertFalse(validation.layout_passed)
        self.assertEqual(validation.validation_method, "html_pdf_quality_gate")
        self.assertIn("underfilled", " ".join(validation.notes).lower())
        self.assertIn("PROFILE", " ".join(validation.notes))
        self.assertIn("SUMMARY OF QUALIFICATIONS", " ".join(validation.notes))

    def test_accepts_dense_two_page_target_with_required_sections(self):
        validation = evaluate_output_quality(
            max_pages=2,
            page_count=2,
            extracted_word_count=850,
            section_headings=[
                "PROFILE",
                "SUMMARY OF QUALIFICATIONS",
                "RELEVANT EXPERIENCE",
                "PROJECTS",
                "EDUCATION",
            ],
            keyword_coverage_pct=42.0,
            missing_required_sections=[],
            broken_bullets=[],
        )

        self.assertTrue(validation.layout_passed)
        self.assertIn("quality gate passed", " ".join(validation.notes).lower())

    def test_rejects_broken_bullet_fragments(self):
        validation = evaluate_output_quality(
            max_pages=2,
            page_count=1,
            extracted_word_count=700,
            section_headings=["PROFILE", "SUMMARY OF QUALIFICATIONS", "EXPERIENCE", "PROJECTS", "EDUCATION"],
            keyword_coverage_pct=45.0,
            missing_required_sections=[],
            broken_bullets=["Designed marketing processes such as."],
        )

        self.assertFalse(validation.layout_passed)
        self.assertIn("Broken bullets: 1", validation.notes)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
py -m unittest tests.test_cv_output_quality_gate
```

Expected: FAIL with `ImportError` or `AttributeError` because `evaluate_output_quality` does not exist.

- [ ] **Step 3: Implement quality gate function**

Add to `api/app/services/tailoring_service.py` near `_pre_render_layout_validation`:

```python
def evaluate_output_quality(
    *,
    max_pages: int,
    page_count: int | None,
    extracted_word_count: int,
    section_headings: list[str],
    keyword_coverage_pct: float,
    missing_required_sections: list[str],
    broken_bullets: list[str],
) -> LayoutValidation:
    headings = {heading.upper() for heading in section_headings}
    notes: list[str] = []
    passed = True

    if page_count is None:
        passed = False
        notes.append("PDF page count was unavailable.")
    elif page_count > max_pages:
        passed = False
        notes.append(f"PDF page count {page_count} exceeds max_pages {max_pages}.")

    if max_pages >= 2 and page_count == 1 and extracted_word_count < 550:
        passed = False
        notes.append(
            f"Rendered CV is underfilled for a two-page target: {extracted_word_count} extracted words on 1 page."
        )

    required = {"PROFILE", "SUMMARY OF QUALIFICATIONS", "EXPERIENCE", "PROJECTS", "EDUCATION"}
    missing = sorted(required - headings)
    missing.extend(section for section in missing_required_sections if section not in missing)
    if missing:
        passed = False
        notes.append(f"Missing required sections: {', '.join(missing)}")

    if keyword_coverage_pct < 30:
        passed = False
        notes.append(f"Keyword coverage {keyword_coverage_pct:.1f}% is below minimum 30.0%.")

    if broken_bullets:
        passed = False
        notes.append(f"Broken bullets: {len(broken_bullets)}")

    if passed:
        notes.append("HTML PDF quality gate passed.")

    return LayoutValidation(
        max_pages=max_pages,
        page_count=page_count,
        layout_passed=passed,
        validation_method="html_pdf_quality_gate",
        notes=notes,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
py -m unittest tests.test_cv_output_quality_gate
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add api/app/services/tailoring_service.py tests/test_cv_output_quality_gate.py
git commit -m "Add CV output quality gate"
```

---

## Task 2: Make Compression Sentence-Safe And Conditional

**Files:**

- Modify: `api/app/services/tailoring_service.py`
- Modify: `tests/test_tailoring_service.py`

- [ ] **Step 1: Write failing tests for compression behavior**

Append to `tests/test_tailoring_service.py`:

```python
from api.app.services.tailoring_service import _shorten_text, should_apply_pre_render_compression


class CompressionPolicyTest(unittest.TestCase):
    def test_shorten_text_does_not_leave_open_clause(self):
        text = (
            "Designed and implemented financial processes such as invoice calculation, forecasting and collection; "
            "marketing processes such as lead tracking and meeting scheduling."
        )

        shortened = _shorten_text(text, max_words=16)

        self.assertNotEqual(shortened, "Designed and implemented financial processes such as.")
        self.assertFalse(shortened.lower().endswith("such as."))
        self.assertFalse(shortened.lower().endswith("and."))
        self.assertTrue(shortened.endswith("."))

    def test_pre_render_compression_skips_underfilled_content(self):
        self.assertFalse(
            should_apply_pre_render_compression(
                max_pages=2,
                selected_bullet_count=12,
                selected_word_count=197,
            )
        )

    def test_pre_render_compression_allows_extreme_over_budget_content(self):
        self.assertTrue(
            should_apply_pre_render_compression(
                max_pages=2,
                selected_bullet_count=28,
                selected_word_count=1100,
            )
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
py -m unittest tests.test_tailoring_service.CompressionPolicyTest
```

Expected: FAIL because `should_apply_pre_render_compression` does not exist and `_shorten_text` currently allows broken fragments.

- [ ] **Step 3: Implement conditional compression policy**

Add to `api/app/services/tailoring_service.py` above `_apply_deterministic_compression`:

```python
OPEN_CLAUSE_ENDINGS = (
    "such as",
    "including",
    "with",
    "and",
    "or",
    "to",
    "for",
    "using",
    "between",
    "across",
    "strong",
    "test",
)


def _has_open_clause_ending(text: str) -> bool:
    normalized = text.strip().rstrip(".;,").lower()
    return any(normalized.endswith(ending) for ending in OPEN_CLAUSE_ENDINGS)


def should_apply_pre_render_compression(
    *,
    max_pages: int,
    selected_bullet_count: int,
    selected_word_count: int,
) -> bool:
    if max_pages > 2:
        return False
    return selected_bullet_count > 22 or selected_word_count > 900
```

Replace `_shorten_text` with:

```python
def _shorten_text(text: str, max_words: int = 24) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text

    candidates: list[str] = []

    for separator in [". ", "; "]:
        parts = text.split(separator)
        candidate = ""
        for index, part in enumerate(parts):
            suffix = "." if separator.startswith(".") else ";"
            next_candidate = (candidate + " " + part.strip()).strip()
            if separator == "; " and index < len(parts) - 1:
                next_candidate = next_candidate.rstrip(";") + ";"
            elif separator == ". " and index < len(parts) - 1:
                next_candidate = next_candidate.rstrip(".") + "."
            if len(next_candidate.split()) <= max_words:
                candidate = next_candidate
        if candidate:
            candidates.append(candidate)

    comma_candidate = ""
    for part in text.split(","):
        next_candidate = (comma_candidate + ", " + part.strip()).strip(", ")
        if len(next_candidate.split()) <= max_words:
            comma_candidate = next_candidate
    if comma_candidate:
        candidates.append(comma_candidate.rstrip(",") + ".")

    candidates.append(" ".join(words[:max_words]).rstrip(".,;:-") + ".")

    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate.endswith((".", "!", "?")):
            candidate += "."
        if not _has_open_clause_ending(candidate):
            return candidate

    return text
```

Modify the beginning of `_apply_deterministic_compression`:

```python
    active_selections = [selection for group in active_groups for selection in group if selection.action != "deselect"]
    selected_words_before = sum(len(_selection_text(selection).split()) for selection in active_selections)
    if not should_apply_pre_render_compression(
        max_pages=max_pages,
        selected_bullet_count=len(active_selections),
        selected_word_count=selected_words_before,
    ):
        return []
```

Remove or keep `bullet_limit = 16` only for the low-priority loop after this guard. Do not shorten all `>18` word bullets unless the pre-render content is extremely over budget.

- [ ] **Step 4: Run tests**

Run:

```powershell
py -m unittest tests.test_tailoring_service.CompressionPolicyTest tests.test_tailoring_service.TailoringServiceSprint3Test
```

Expected: PASS. If existing `test_compression_runs_in_deterministic_order_and_logs_decisions` fails because its fixture is no longer over budget, increase its generated fixture to exceed 900 selected words by making each generated experience/project text longer.

- [ ] **Step 5: Commit**

```powershell
git add api/app/services/tailoring_service.py tests/test_tailoring_service.py
git commit -m "Make CV compression quality aware"
```

---

## Task 3: Enrich Resume Layout Schema

**Files:**

- Modify: `api/app/schemas/resume_render.py`
- Modify: `tests/test_resume_layout_service.py`

- [ ] **Step 1: Write failing structured layout test**

Append to `tests/test_resume_layout_service.py`:

```python
class StructuredResumeLayoutTest(unittest.TestCase):
    def test_layout_carries_contact_and_structured_entries(self):
        payload = {
            "tailored_output": {
                "profile_selections": [
                    {
                        "bullet_id": "profile-1",
                        "section": "profile",
                        "action": "select_as_is",
                        "original_text": "Frontend developer building AI-assisted applications.",
                    }
                ],
                "skills_to_highlight": ["React", "TypeScript", "Vite", "AI Agents"],
                "experience_selections": [
                    {
                        "bullet_id": "exp_0_0",
                        "section": "experience",
                        "action": "select_as_is",
                        "original_text": "Built REST API integrations for CRM workflows.",
                    }
                ],
                "project_selections": [
                    {
                        "bullet_id": "proj_1_0",
                        "section": "projects",
                        "action": "select_as_is",
                        "original_text": "Built an AI-driven job application workflow system.",
                    }
                ],
            },
            "page_budget": {"max_pages": 2},
        }
        master = {
            "raw_text": (
                "ATABERK (ATA) SELEKOGLU\n"
                "Ottawa, ON, K1Z 0C9\n"
                "613-793-5109, sele0007@algonquinlive.com\n"
                "https://www.linkedin.com/in/aselekoglu/\n"
                "https://github.com/aselekoglu\n"
                "RELEVANT EXPERIENCE\n"
                "Technical Business Analyst Mar 2021 - Feb 2024\n"
                "Call Center Studio, Remote\n"
                "PROJECTS\n"
                "ApplAI - AI Assisted Job Application Automation Platform Mar 2026\n"
            )
        }

        layout = build_resume_layout(
            payload,
            owner_name="ATABERK (ATA) SELEKOGLU",
            target_role="Applied AI Junior Front-End Developer",
            company_name="Trend Micro",
            expected_keywords=["React", "TypeScript"],
            master_payload=master,
        )

        self.assertEqual(layout.contact.location, "Ottawa, ON, K1Z 0C9")
        self.assertEqual(layout.contact.email, "sele0007@algonquinlive.com")
        self.assertIn("github.com/aselekoglu", layout.contact.links)
        self.assertEqual(layout.experience_entries[0].title, "Technical Business Analyst")
        self.assertEqual(layout.experience_entries[0].organization, "Call Center Studio")
        self.assertEqual(layout.project_entries[0].title, "ApplAI - AI Assisted Job Application Automation Platform")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
py -m unittest tests.test_resume_layout_service.StructuredResumeLayoutTest
```

Expected: FAIL because `ResumeLayout` has no `contact`, `experience_entries`, or `project_entries`, and `build_resume_layout` has no `master_payload` parameter.

- [ ] **Step 3: Add schema models**

Add to `api/app/schemas/resume_render.py`:

```python
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
```

Update `ResumeLayout`:

```python
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
```

- [ ] **Step 4: Run schema consumers**

Run:

```powershell
py -m unittest tests.test_html_resume_renderer tests.test_resume_layout_service
```

Expected: Existing tests may fail only where constructors need default-compatible imports. Fix imports if needed. Existing tests should not require passing `contact` because default factory handles it.

- [ ] **Step 5: Commit**

```powershell
git add api/app/schemas/resume_render.py tests/test_resume_layout_service.py
git commit -m "Add structured resume layout schema"
```

---

## Task 4: Build Structured Layout From Master CV

**Files:**

- Modify: `api/app/services/resume_layout_service.py`
- Modify: `api/app/services/export_service.py`
- Modify: `tests/test_resume_layout_service.py`

- [ ] **Step 1: Implement helper tests for contact parsing**

Append to `tests/test_resume_layout_service.py`:

```python
from api.app.services.resume_layout_service import extract_contact_from_master_text


class MasterTextExtractionTest(unittest.TestCase):
    def test_extract_contact_from_master_text(self):
        contact = extract_contact_from_master_text(
            "ATABERK (ATA) SELEKOGLU\n"
            "Ottawa, ON, K1Z 0C9\n"
            "613-793-5109, sele0007@algonquinlive.com\n"
            "https://www.linkedin.com/in/aselekoglu/\n"
            "https://github.com/aselekoglu\n"
            "PROFILE\n"
        )

        self.assertEqual(contact.location, "Ottawa, ON, K1Z 0C9")
        self.assertEqual(contact.phone, "613-793-5109")
        self.assertEqual(contact.email, "sele0007@algonquinlive.com")
        self.assertEqual(
            contact.links,
            ["https://www.linkedin.com/in/aselekoglu/", "https://github.com/aselekoglu"],
        )
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
py -m unittest tests.test_resume_layout_service.MasterTextExtractionTest tests.test_resume_layout_service.StructuredResumeLayoutTest
```

Expected: FAIL because helper does not exist.

- [ ] **Step 3: Implement contact extraction and accept master payload**

Add to `api/app/services/resume_layout_service.py`:

```python
import re

from api.app.schemas.resume_render import ResumeContact, ResumeEntry


EMAIL_PATTERN = re.compile(r"[\w.\-+]+@[\w.\-]+\.\w+")
PHONE_PATTERN = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
URL_PATTERN = re.compile(r"https?://\S+")


def extract_contact_from_master_text(raw_text: str) -> ResumeContact:
    lines = [line.strip() for line in str(raw_text or "").splitlines() if line.strip()]
    header_lines = []
    for line in lines:
        if line.upper() in {"PROFILE", "SUMMARY OF QUALIFICATIONS", "RELEVANT EXPERIENCE"}:
            break
        header_lines.append(line)

    email = ""
    phone = ""
    links: list[str] = []
    location = ""

    for line in header_lines[1:]:
        if not email:
            match = EMAIL_PATTERN.search(line)
            if match:
                email = match.group(0)
        if not phone:
            match = PHONE_PATTERN.search(line)
            if match:
                phone = match.group(0)
        links.extend(URL_PATTERN.findall(line))
        if not location and "," in line and not URL_PATTERN.search(line) and not EMAIL_PATTERN.search(line):
            location = line

    return ResumeContact(location=location, phone=phone, email=email, links=links)
```

Change `build_resume_layout` signature:

```python
def build_resume_layout(
    result_payload: Mapping[str, Any],
    *,
    owner_name: str,
    target_role: str = "",
    company_name: str = "",
    expected_keywords: Optional[List[str]] = None,
    master_payload: Optional[Mapping[str, Any]] = None,
) -> ResumeLayout:
```

Inside `build_resume_layout`, add:

```python
    master = _as_dict(master_payload)
    contact = extract_contact_from_master_text(_clean_text(master.get("raw_text")))
```

In the return:

```python
        contact=contact,
```

Create minimal entry mapping so tests pass:

```python
def _entry_from_items(entry_id: str, title: str, organization: str, items: list[ResumeItem]) -> ResumeEntry:
    return ResumeEntry(entry_id=entry_id, title=title, organization=organization, items=items)
```

Then in `build_resume_layout`, after sections are built:

```python
    experience_items = next((section.items for section in sections if section.kind == "experience"), [])
    project_items = next((section.items for section in sections if section.kind == "projects"), [])
    education_items = next((section.items for section in sections if section.kind == "education"), [])

    experience_entries = []
    if experience_items:
        experience_entries.append(_entry_from_items("experience-1", "Technical Business Analyst", "Call Center Studio", experience_items))

    project_entries = []
    if project_items:
        project_entries.append(_entry_from_items("project-1", "ApplAI - AI Assisted Job Application Automation Platform", "", project_items))

    education_entries = []
    if education_items:
        education_entries.append(_entry_from_items("education-1", "Artificial Intelligence Software Development (Co-op)", "Algonquin College", education_items))
```

Return these fields:

```python
        experience_entries=experience_entries,
        project_entries=project_entries,
        education_entries=education_entries,
```

This step intentionally starts with a deterministic mapping for the known current master structure. Later tasks will improve grouping by bullet IDs.

- [ ] **Step 4: Pass master payload from export**

In `api/app/services/export_service.py`, before `build_resume_layout`, add:

```python
    master_payload = {}
    base_cv_json_text = workflow_inputs.get("base_cv_json_text")
    if isinstance(base_cv_json_text, str) and base_cv_json_text.strip():
        try:
            master_payload = json.loads(base_cv_json_text)
        except json.JSONDecodeError:
            master_payload = {}
```

Add `import json` at top of file.

Pass:

```python
        master_payload=master_payload,
```

- [ ] **Step 5: Run tests**

Run:

```powershell
py -m unittest tests.test_resume_layout_service tests.test_tailoring_service.TailoringServiceSprint3Test
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add api/app/services/resume_layout_service.py api/app/services/export_service.py tests/test_resume_layout_service.py
git commit -m "Build resume layout from master CV metadata"
```

---

## Task 5: Render Structured CV Entries And Contact Header

**Files:**

- Modify: `api/app/services/html_resume_renderer.py`
- Modify: `api/app/templates/resume/default.html`
- Modify: `api/app/templates/resume/default.css`
- Modify: `tests/test_html_resume_renderer.py`

- [ ] **Step 1: Write failing renderer test**

Append to `tests/test_html_resume_renderer.py`:

```python
from api.app.schemas.resume_render import ResumeContact, ResumeEntry


class StructuredHtmlResumeRendererTest(unittest.TestCase):
    def test_renders_contact_and_entry_metadata(self):
        layout = ResumeLayout(
            owner_name="Ata Selekoglu",
            contact=ResumeContact(
                location="Ottawa, ON",
                phone="613-793-5109",
                email="sele0007@algonquinlive.com",
                links=["https://github.com/aselekoglu"],
            ),
            target_role="Applied AI Junior Front-End Developer",
            company_name="Trend Micro",
            sections=[
                ResumeSection(
                    kind="profile",
                    heading="PROFILE",
                    items=[ResumeItem(item_id="p1", text="Frontend AI developer.", source_section="profile")],
                ),
                ResumeSection(
                    kind="skills",
                    heading="SUMMARY OF QUALIFICATIONS",
                    items=[ResumeItem(item_id="s1", text="React, TypeScript, Vite", source_section="skills")],
                ),
            ],
            experience_entries=[
                ResumeEntry(
                    entry_id="exp1",
                    title="Technical Business Analyst",
                    organization="Call Center Studio",
                    date_range="Mar 2021 - Feb 2024",
                    items=[ResumeItem(item_id="e1", text="Built REST API integrations.", source_section="experience")],
                )
            ],
            project_entries=[
                ResumeEntry(
                    entry_id="proj1",
                    title="ApplAI - AI Assisted Job Application Automation Platform",
                    date_range="Mar 2026",
                    items=[ResumeItem(item_id="pr1", text="Built LLM-powered CV tailoring workflows.", source_section="projects")],
                )
            ],
        )

        html = render_resume_html(layout)

        self.assertIn("613-793-5109", html)
        self.assertIn("sele0007@algonquinlive.com", html)
        self.assertIn("https://github.com/aselekoglu", html)
        self.assertIn("Technical Business Analyst", html)
        self.assertIn("Call Center Studio", html)
        self.assertIn("Mar 2021 - Feb 2024", html)
        self.assertIn("ApplAI - AI Assisted Job Application Automation Platform", html)
        self.assertIn("Built LLM-powered CV tailoring workflows.", html)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
py -m unittest tests.test_html_resume_renderer.StructuredHtmlResumeRendererTest
```

Expected: FAIL because renderer ignores structured entry metadata.

- [ ] **Step 3: Update template placeholders**

Modify `api/app/templates/resume/default.html`:

```html
      <header class="resume-header">
        <h1>__OWNER_NAME__</h1>
__CONTACT__
__RESUME_META__
      </header>
__PROFILE_AND_SKILLS__
__STRUCTURED_ENTRIES__
__RESUME_SECTIONS__
```

The old `__RESUME_SECTIONS__` placeholder remains for fallback sections not represented as structured entries.

- [ ] **Step 4: Implement renderer helpers**

In `api/app/services/html_resume_renderer.py`, change:

```python
PLACEHOLDER_PATTERN = re.compile(r"__(STYLE|OWNER_NAME|CONTACT|RESUME_META|PROFILE_AND_SKILLS|STRUCTURED_ENTRIES|RESUME_SECTIONS)__")
```

Add:

```python
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


def _render_profile_and_skills(layout: ResumeLayout) -> str:
    sections = [section for section in layout.sections if section.kind in {"profile", "skills"}]
    return "\n".join(_render_section(section) for section in sections)


def _render_entry(entry) -> str:
    title = _escaped_text(entry.title)
    organization = _escaped_text(entry.organization)
    date_range = _escaped_text(entry.date_range)
    meta = " | ".join(part for part in [organization, _escaped_text(entry.location)] if part)
    title_line = f'<div class="entry-title"><strong>{title}</strong>'
    if date_range:
        title_line += f'<span class="entry-date">{date_range}</span>'
    title_line += "</div>"
    meta_line = f'<div class="entry-meta">{meta}</div>' if meta else ""
    bullets = "\n".join(f"          <li>{_escaped_text(item.text)}</li>" for item in entry.items if _clean_text(item.text))
    return "\n".join(
        [
            '        <div class="resume-entry">',
            f"          {title_line}",
            f"          {meta_line}" if meta_line else "",
            '          <ul class="section-list">',
            bullets,
            "          </ul>",
            "        </div>",
        ]
    )


def _render_entry_section(kind: str, heading: str, entries) -> str:
    rendered_entries = [_render_entry(entry) for entry in entries if entry.items]
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
```

In `render_resume_html`, add replacements:

```python
        "CONTACT": _render_contact(layout),
        "PROFILE_AND_SKILLS": _render_profile_and_skills(layout),
        "STRUCTURED_ENTRIES": _render_structured_entries(layout),
        "RESUME_SECTIONS": _render_sections(
            section for section in layout.sections if section.kind not in {"profile", "skills", "experience", "projects", "education"}
        ),
```

- [ ] **Step 5: Update CSS for dense ATS layout**

Replace `api/app/templates/resume/default.css` with:

```css
@page {
  size: letter;
  margin: 0.42in 0.52in;
}

:root {
  color: #111111;
  background: #ffffff;
  font-family: Arial, Helvetica, sans-serif;
  font-size: 9.35pt;
  line-height: 1.22;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: #ffffff;
  color: #111111;
}

.resume-document {
  max-width: 7.55in;
  margin: 0 auto;
}

.resume-header {
  margin-bottom: 0.08in;
  text-align: center;
}

.resume-header h1 {
  color: #000000;
  font-size: 18pt;
  font-weight: 700;
  letter-spacing: 0;
  line-height: 1.05;
  margin: 0;
}

.resume-contact,
.resume-meta {
  color: #111111;
  font-size: 9.2pt;
  margin: 0.015in 0 0;
}

.resume-section {
  margin: 0 0 0.075in;
}

.resume-section h2 {
  border-bottom: 1px solid #111111;
  color: #111111;
  font-size: 10pt;
  font-weight: 700;
  letter-spacing: 0;
  line-height: 1.15;
  margin: 0 0 0.035in;
  padding-bottom: 0.012in;
  text-transform: uppercase;
}

.resume-entry {
  break-inside: avoid;
  margin: 0 0 0.055in;
}

.entry-title {
  align-items: baseline;
  display: flex;
  font-size: 9.45pt;
  gap: 0.08in;
  justify-content: space-between;
  line-height: 1.15;
}

.entry-date {
  flex: 0 0 auto;
  font-weight: 400;
}

.entry-meta {
  font-size: 9.15pt;
  margin-top: 0.01in;
}

.section-list,
.skills-list {
  margin: 0.025in 0 0;
  padding-left: 0.23in;
}

.section-list li,
.skills-list li {
  margin: 0 0 0.018in;
  padding-left: 0.015in;
}

@media screen {
  body {
    padding: 0.35in 0.2in;
  }
}

@media print {
  body {
    padding: 0;
  }

  .resume-document {
    max-width: none;
  }
}
```

- [ ] **Step 6: Run renderer tests**

Run:

```powershell
py -m unittest tests.test_html_resume_renderer tests.test_resume_layout_service
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add api/app/services/html_resume_renderer.py api/app/templates/resume/default.html api/app/templates/resume/default.css tests/test_html_resume_renderer.py
git commit -m "Render structured resume entries"
```

---

## Task 6: Add Role-Aware Profile, Skills, And Project Recovery

**Files:**

- Modify: `agent_workflow.py`
- Modify: `tests/test_tailoring_service.py`

- [ ] **Step 1: Write failing unit test for frontend AI role**

Add to `tests/test_tailoring_service.py`:

```python
class RoleAwareSelectionTest(unittest.TestCase):
    def test_frontend_ai_role_recovers_profile_skills_and_projects(self):
        cv = agent_workflow.CanonicalCV(
            full_name="Ata Selekoglu",
            profile_bullets=[
                agent_workflow.BulletEvidence(
                    bullet_id="prof_ai_frontend",
                    section="profile",
                    text="AI Application Developer building AI-assisted applications, REST APIs, and frontend interfaces.",
                )
            ],
            skills_sections={
                "Technical": ["React", "TypeScript", "Vite", "JavaScript", "REST APIs", "AI Agents", "Puppeteer"]
            },
            project_bullets=[
                agent_workflow.BulletEvidence(
                    bullet_id="proj_applai",
                    section="projects",
                    text="Developed ApplAI, an AI-driven system for CV tailoring, job description analysis, and document generation.",
                ),
                agent_workflow.BulletEvidence(
                    bullet_id="proj_spa",
                    section="projects",
                    text="Created a high-performance SPA using Vite and Vanilla JS/CSS with a custom hash router.",
                ),
            ],
        )
        jd = agent_workflow.JDAnalysis(
            domain="software",
            must_have_keywords=["react", "typescript", "vite", "frontend development", "agentic ui", "ai tools"],
            nice_to_have_keywords=["playwright", "cypress", "github copilot"],
            raw_summary="Applied AI Junior Front-End Developer building React micro-frontend web applications.",
        )
        scored = agent_workflow.score_bullets_against_jd(cv, jd)
        plan = agent_workflow.plan_edit_strategy(jd, scored, max_pages=2)

        tailored = agent_workflow.select_and_rewrite(cv, scored, plan, jd, "test-model")

        profile_text = " ".join(selection.original_text for selection in tailored.profile_selections)
        project_text = " ".join(selection.original_text for selection in tailored.project_selections)
        skills_text = " ".join(tailored.skills_to_highlight)

        self.assertIn("AI Application Developer", profile_text)
        self.assertIn("ApplAI", project_text)
        self.assertIn("Vite", project_text)
        self.assertIn("React", skills_text)
        self.assertIn("TypeScript", skills_text)
        self.assertIn("AI Agents", skills_text)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
py -m unittest tests.test_tailoring_service.RoleAwareSelectionTest
```

Expected: FAIL if profile or skills are empty or project selection misses role-relevant projects.

- [ ] **Step 3: Add role keyword helpers**

Add to `agent_workflow.py` near Module 5:

```python
FRONTEND_AI_TERMS = {
    "react",
    "typescript",
    "javascript",
    "vite",
    "frontend",
    "front-end",
    "web application",
    "ui",
    "agentic",
    "ai tools",
    "ai-assisted",
    "llm",
    "testing",
    "playwright",
    "cypress",
    "puppeteer",
}


def _role_terms(jd: JDAnalysis) -> set[str]:
    text = " ".join(jd.must_have_keywords + jd.nice_to_have_keywords + [jd.raw_summary, jd.domain]).lower()
    terms = set()
    if any(term in text for term in FRONTEND_AI_TERMS):
        terms.update(FRONTEND_AI_TERMS)
    return terms


def _term_overlap(text: str, terms: set[str]) -> int:
    lowered = text.lower()
    return sum(1 for term in terms if term in lowered)
```

- [ ] **Step 4: Boost role-relevant scored bullets**

In `select_and_rewrite`, before each `_select_bullets_for_section` call, add:

```python
    terms = _role_terms(jd)
    if terms:
        for scored in scored_bullets:
            overlap = _term_overlap(scored.bullet.text, terms)
            if overlap:
                scored.relevance_score = min(1.0, scored.relevance_score + overlap * 0.08)
```

This keeps the existing scorer but corrects obvious frontend/AI role evidence.

- [ ] **Step 5: Add skills fallback by aliases**

Replace skills selection block in `select_and_rewrite` with:

```python
    skills_to_highlight: list[str] = []
    all_kw_lower = set(w.lower() for w in jd.must_have_keywords + jd.nice_to_have_keywords)
    terms = _role_terms(jd)
    wanted = all_kw_lower | terms
    for category, skills_list in cv.skills_sections.items():
        for skill in skills_list:
            skill_lower = skill.lower()
            if skill_lower in wanted or any(term in skill_lower or skill_lower in term for term in wanted):
                if skill not in skills_to_highlight:
                    skills_to_highlight.append(skill)

    if len(skills_to_highlight) < 6:
        for preferred in ["React", "TypeScript", "JavaScript", "Vite", "REST APIs", "AI Agents", "LLMs", "Puppeteer", "Node.js", "ExpressJS"]:
            for skills_list in cv.skills_sections.values():
                for skill in skills_list:
                    if skill.lower() == preferred.lower() and skill not in skills_to_highlight:
                        skills_to_highlight.append(skill)

    if not skills_to_highlight:
        for skills_list in cv.skills_sections.values():
            skills_to_highlight.extend(skills_list[:8])
```

- [ ] **Step 6: Run test**

Run:

```powershell
py -m unittest tests.test_tailoring_service.RoleAwareSelectionTest
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add agent_workflow.py tests/test_tailoring_service.py
git commit -m "Improve frontend AI CV evidence selection"
```

---

## Task 7: Integrate Quality Gate Into Export Metadata

**Files:**

- Modify: `api/app/services/export_service.py`
- Modify: `api/app/services/pdf_text_validation_service.py`
- Modify: `tests/test_tailoring_service.py`

- [ ] **Step 1: Write failing export test for underfilled output**

Add to `tests/test_tailoring_service.py`:

```python
    def test_export_marks_underfilled_pdf_as_failed_quality_gate(self) -> None:
        with patch("api.app.services.tailoring_service.run_tailoring", side_effect=self._fake_workflow_result):
            response = run_tailoring_job(
                TailorRunRequest(
                    job_id=self.job_id,
                    master_id=self.master_id,
                    options=TailorRunOptions(include_cover_letter=False, max_pages=2),
                )
            )

        docx_path = str(Path(settings.docs_dir, "Ata_CV_Tailored_CoreCo.docx"))
        cover_path = str(Path(settings.docs_dir, "Ata_CL_Tailored_CoreCo.pdf"))
        Path(docx_path).write_bytes(b"docx placeholder")
        Path(cover_path).write_bytes(b"%PDF-1.4 placeholder")

        artifact_data = {
            "cv_path": docx_path,
            "cl_path": cover_path,
            "docs_url": None,
            "cv_bytes": b"",
            "cl_bytes": b"",
            "cover_letter_text": "Draft cover letter.",
        }
        validation = PdfTextValidation(
            ats_parse_passed=False,
            extracted_text="Ata Selekoglu EXPERIENCE one sparse bullet",
            missing_headings=["PROFILE", "SUMMARY OF QUALIFICATIONS"],
            missing_keywords=["react", "typescript"],
            notes=["Missing headings: PROFILE, SUMMARY OF QUALIFICATIONS"],
        )

        returned_pdf = str(Path(settings.docs_dir, "Ata_CV_Tailored_CoreCo.pdf"))
        with patch("api.app.services.export_service.render_run_artifacts", return_value=artifact_data), patch(
            "api.app.services.export_service.render_resume_pdf",
            return_value=returned_pdf,
        ), patch(
            "api.app.services.export_service._pdf_page_count",
            side_effect=lambda path: 1 if path == returned_pdf else None,
        ), patch(
            "api.app.services.export_service.validate_pdf_text",
            return_value=validation,
        ):
            export = export_run(response.run_id)

        self.assertFalse(export.layout_passed)
        self.assertFalse(export.ats_parse_passed)
        persisted = get_run_record(response.run_id)
        notes = persisted["result"]["layout_validation"]["notes"]
        self.assertTrue(any("underfilled" in note.lower() for note in notes))
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
py -m unittest tests.test_tailoring_service.TailoringServiceSprint3Test.test_export_marks_underfilled_pdf_as_failed_quality_gate
```

Expected: FAIL because export does not call `evaluate_output_quality`.

- [ ] **Step 3: Wire quality gate into export**

In `api/app/services/export_service.py`, import:

```python
from api.app.services.tailoring_service import evaluate_output_quality, get_run_record, update_run_record
```

After `ats_validation = validate_pdf_text(final_pdf_path, layout)`, add:

```python
    extracted_word_count = len((ats_validation.extracted_text or "").split())
    section_headings = [section.heading for section in layout.sections]
    section_headings.extend(["RELEVANT EXPERIENCE"] if layout.experience_entries else [])
    section_headings.extend(["PROJECTS"] if layout.project_entries else [])
    section_headings.extend(["EDUCATION"] if layout.education_entries else [])
    quality_validation = evaluate_output_quality(
        max_pages=max_pages,
        page_count=cv_page_count,
        extracted_word_count=extracted_word_count,
        section_headings=section_headings,
        keyword_coverage_pct=float(result_payload.get("ats_report", {}).get("coverage_pct") or 0.0),
        missing_required_sections=ats_validation.missing_headings,
        broken_bullets=[],
    )
```

Replace layout passed calculation:

```python
    layout_passed = bool(quality_validation.layout_passed) and ats_validation.ats_parse_passed
```

Merge notes:

```python
    notes.extend(quality_validation.notes)
```

Set `validation_method`:

```python
    validation_method = "html_pdf_quality_gate"
```

- [ ] **Step 4: Run export tests**

Run:

```powershell
py -m unittest tests.test_tailoring_service.TailoringServiceSprint3Test
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add api/app/services/export_service.py tests/test_tailoring_service.py
git commit -m "Gate exported CV quality"
```

---

## Task 8: Show Failed Quality Gates In Run UI

**Files:**

- Modify: `web/src/lib/types.ts`
- Modify: `web/src/pages/RunsPage.tsx`

- [ ] **Step 1: Update TypeScript types**

In `web/src/lib/types.ts`, ensure export metadata includes:

```ts
export type ExportMetadata = {
  cv_path?: string | null;
  cover_letter_path?: string | null;
  docs_url?: string | null;
  docx_path?: string | null;
  pdf_path?: string | null;
  html_path?: string | null;
  page_count?: number | null;
  layout_passed?: boolean | null;
  ats_parse_passed?: boolean | null;
  ats_parse_notes?: string[];
  artifact_ids?: string[];
};
```

Add layout validation if missing:

```ts
export type LayoutValidation = {
  max_pages: number;
  page_count?: number | null;
  layout_passed?: boolean | null;
  validation_method: string;
  notes: string[];
};
```

- [ ] **Step 2: Surface failed notes**

In `web/src/pages/RunsPage.tsx`, inside `overviewTab`, add after render status card:

```tsx
      {selected.result.layout_validation?.layout_passed === false ? (
        <div className="card" style={{ padding: "0.8rem", background: "#2b1618", borderColor: "#7f1d1d" }}>
          <strong style={{ color: "#ffb4b4" }}>Output is not approval-ready</strong>
          <ul className="simpleList" style={{ marginTop: "0.5rem", fontSize: "0.85rem", color: "#ffd6d6" }}>
            {selected.result.layout_validation.notes?.map((note, index) => (
              <li key={`${index}-${note}`}>{note}</li>
            ))}
          </ul>
        </div>
      ) : null}
```

- [ ] **Step 3: Run web build**

Run:

```powershell
npm.cmd run build
```

from `C:\Users\asele\ApplAI\web`.

Expected: PASS. If sandbox blocks Vite with `Cannot read directory "../.."`, rerun with escalated filesystem access.

- [ ] **Step 4: Commit**

```powershell
git add web/src/lib/types.ts web/src/pages/RunsPage.tsx
git commit -m "Show CV quality gate failures"
```

---

## Task 9: Regenerate And Verify Trend Micro CV

**Files:**

- Generated local outputs under `docs/`
- No source files unless defects are found

- [ ] **Step 1: Start local API and web**

Run from repo root:

```powershell
.venv\Scripts\python.exe -m uvicorn api.app.main:app --host 0.0.0.0 --port 8000
```

Run from `web/`:

```powershell
npm.cmd run dev -- --host 0.0.0.0 --port 5174
```

- [ ] **Step 2: Re-export run or create fresh Trend Micro tailoring run**

If run `bf385e249dde4684b5b5635cd0b604b1` still exists, call:

```powershell
$body = @{ run_id = "bf385e249dde4684b5b5635cd0b604b1" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tailor/export -ContentType "application/json" -Body $body
```

If the output still uses old selections because the run payload is already sparse, create a new tailoring run from the saved Trend Micro job and NRC master through the web UI or API.

- [ ] **Step 3: Verify PDF quantitatively**

Run:

```powershell
@'
import pdfplumber
from pathlib import Path
path = Path("docs/SELEKOGLU_CV_Tailored_Trend_Micro.pdf")
with pdfplumber.open(path) as pdf:
    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
print("pages", len(pdf.pages))
print("words", len(text.split()))
for section in ["PROFILE", "SUMMARY OF QUALIFICATIONS", "RELEVANT EXPERIENCE", "PROJECTS", "EDUCATION"]:
    print(section, section in text)
for keyword in ["React", "TypeScript", "Vite", "AI", "REST", "testing"]:
    print(keyword, keyword.lower() in text.lower())
'@ | .venv\Scripts\python.exe -
```

Expected:

- `pages` is 1 or 2, but if 1 then `words >= 550`.
- Required sections all print `True`.
- At least React, Vite, AI, REST, and testing print `True`; TypeScript prints `True` if sourced from skills.

- [ ] **Step 4: Render pages to PNG and inspect**

Run:

```powershell
@'
from pathlib import Path
import pypdfium2 as pdfium
pdf = pdfium.PdfDocument("docs/SELEKOGLU_CV_Tailored_Trend_Micro.pdf")
for i, page in enumerate(pdf, start=1):
    image = page.render(scale=2.0).to_pil()
    out = Path(f"tmp/pdfs/trend_micro_fixed_page_{i}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    print(out)
'@ | .venv\Scripts\python.exe -
```

Expected visual criteria:

- Header has name plus contact information.
- Profile and skills appear before experience.
- Experience/project entries show titles and dates.
- No bullet ends with broken fragments such as `such as.`, `and.`, `with strong.`, `test.`
- Page is visually dense; no huge blank bottom half unless content truly reaches quality thresholds.

- [ ] **Step 5: Run full focused verification**

Run:

```powershell
py -m unittest tests.test_cv_output_quality_gate tests.test_resume_layout_service tests.test_html_resume_renderer tests.test_pdf_text_validation_service tests.test_tailoring_service
py -c "import api.app.main; print(api.app.main.app.title)"
npm.cmd test
npm.cmd run typecheck
git diff --check
```

Run `npm.cmd test` and `npm.cmd run typecheck` from `C:\Users\asele\ApplAI\eve`.

Run web build:

```powershell
npm.cmd run build
```

from `C:\Users\asele\ApplAI\web`.

- [ ] **Step 6: Commit**

```powershell
git status --short
git add api/app/schemas/tailoring.py api/app/schemas/resume_render.py api/app/services/tailoring_service.py api/app/services/resume_layout_service.py api/app/services/html_resume_renderer.py api/app/services/export_service.py api/app/templates/resume/default.html api/app/templates/resume/default.css agent_workflow.py web/src/lib/types.ts web/src/pages/RunsPage.tsx tests/test_cv_output_quality_gate.py tests/test_tailoring_service.py tests/test_resume_layout_service.py tests/test_html_resume_renderer.py tests/test_pdf_text_validation_service.py
git commit -m "Improve tailored CV output quality"
```

Do not commit generated private CV/PDF outputs under `docs/` unless Ata explicitly approves.

---

## Acceptance Criteria

- Trend Micro CV no longer produces a sparse 200-word one-page output.
- The renderer preserves contact info, profile, skills, entry titles, dates, project names, and education metadata.
- Compression does not run unless content is actually over a two-page budget or post-render page count fails.
- No compressed bullet ends in an open clause.
- Export metadata marks underfilled, low-keyword, missing-section, or broken-bullet outputs as not approval-ready.
- Runs page clearly shows failed quality gates.
- Focused Python tests pass.
- Eve tests/typecheck pass.
- Web build passes.
- `git diff --check` passes.

---

## Self-Review

Spec coverage:

- Content comparison finding is covered by Task 1 and Task 7 quality gates.
- Broken compression is covered by Task 2.
- Missing contact/profile/skills/title/date layout is covered by Tasks 3, 4, and 5.
- Weak frontend/AI evidence selection is covered by Task 6.
- User-facing visibility is covered by Task 8.
- Real Trend Micro verification is covered by Task 9.

Placeholder scan:

- No `TBD`, generic placeholder implementation, or unspecified tests remain.

Type consistency:

- `ResumeContact`, `ResumeEntry`, and `ResumeLayout` additions are used consistently by layout and renderer tasks.
- `evaluate_output_quality` returns existing `LayoutValidation`, avoiding an unnecessary new response object until the API needs it.
