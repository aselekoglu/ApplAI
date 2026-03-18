# Redesigned Agentic CV Tailoring Workflow

## Background

The current system is a monolithic 4-agent CrewAI pipeline that:
1. Parses the JD with one agent
2. Rewrites the entire CV with a second agent (unrestricted freeform rewrite)
3. Writes a cover letter
4. Runs a QA check

**Problems:**
- CV data is stored as raw, unstructured text — there is no canonical model
- The tailoring agent is given the whole CV as text and told to rewrite it freely — high hallucination risk
- No bullet provenance: no way to know if any generated bullet was sourced from original content
- No separate evidence scoring or bullet selection before rewriting
- The renderer blindly replaces bullets under headers — no zone enforcement or overflow detection
- No structured change log — only a `tailoring_notes` string
- No real ATS keyword coverage module (done in [app.py](file:///c:/Users/asele/Documents/ApplAI/app.py) as simple word matching after the fact)

## Proposed Changes

This redesign **replaces only [agent_workflow.py](file:///c:/Users/asele/Documents/ApplAI/agent_workflow.py)** (the pipeline) and makes minimal, backward-compatible updates to [app.py](file:///c:/Users/asele/Documents/ApplAI/app.py) to consume the richer output. All existing UI code, styling, and Google Drive integration is untouched.

---

### Canonical Data Model

#### [MODIFY] [agent_workflow.py](file:///c:/Users/asele/Documents/ApplAI/agent_workflow.py)

The new pipeline uses rich Pydantic models instead of raw text:

```python
# Canonical source of truth for a CV
class BulletEvidence(BaseModel):
    bullet_id: str               # e.g. "exp_ccs_1"
    text: str                    # original bullet text
    section: str                 # "experience"|"profile"|"projects"|"skills"
    employer: str                # "Call Center Studio" (locked field)
    role: str                    # "Technical Business Analyst" (locked field)
    domain_tags: list[str]       # ["automation","data","api"]
    is_locked: bool              # If True: never rewrite, only select/deselect

class CanonicalCV(BaseModel):
    full_name: str               # LOCKED
    contact: dict                # LOCKED
    profile_bullets: list[BulletEvidence]
    skills_sections: dict        # category -> list[str]
    experience: list[ExperienceEntry]  # contains BulletEvidence list
    projects: list[ProjectEntry]
    education: list[EducationEntry]
    additional: str

class JDAnalysis(BaseModel):
    ranked_requirements: list[RequirementItem]  # priority-ranked
    domain: str                  # "ai_ml"|"software"|"data"|etc.
    seniority: str
    must_have_keywords: list[str]
    nice_to_have_keywords: list[str]
    company_tone: str

class BulletSelection(BaseModel):
    bullet_id: str               # references original BulletEvidence.bullet_id
    action: str                  # "select_as_is"|"rewrite"|"deselect"
    rewritten_text: str | None   # Only if action=="rewrite"
    rewrite_rationale: str | None
    source_bullet_text: str      # Always populated for traceability

class TailoredOutput(BaseModel):
    profile_bullets: list[BulletSelection]
    skills_to_highlight: list[str]
    experience_selections: list[BulletSelection]  # selected/rewritten
    summary_section: str | None  # Optional role-specific intro paragraph

class QAReport(BaseModel):
    matching_rate_score: int
    factual_support_passed: bool
    keyword_coverage_pct: float
    style_issues: list[str]
    unsupported_claims: list[str]
    section_length_ok: bool
    key_pain_points: list[str]
    strong_points: list[str]
    feedback: str

class ChangeLogEntry(BaseModel):
    bullet_id: str
    section: str
    action: str                  # "selected"|"rewritten"|"deselected"
    original_text: str
    new_text: str | None
    rationale: str
    jd_requirements_addressed: list[str]

class ChangeLog(BaseModel):
    entries: list[ChangeLogEntry]
    total_bullets_considered: int
    total_bullets_changed: int

class ATSReport(BaseModel):
    jd_keywords: list[str]
    covered_keywords: list[str]
    gap_keywords: list[str]
    coverage_pct: float
    added_by_tailoring: list[str]
```

---

### Module Pipeline Design

The new pipeline replaces the 4-agent sequential CrewAI crew with **8 explicit modules**. Each module has a defined contract (input/output), mode (deterministic/LLM/hybrid), and can be individually tested and debugged.

```
JD Text + DOCX Template
        │
        ▼
┌───────────────────┐
│  1. CV Loader     │  (LLM-assisted)   PDF raw_text → CanonicalCV
└────────┬──────────┘
         │ CanonicalCV
         ▼
┌───────────────────┐
│  2. JD Parser     │  (LLM)           JD text → JDAnalysis
└────────┬──────────┘
         │ JDAnalysis
         ▼
┌───────────────────┐
│  3. Evidence      │  (Deterministic  CanonicalCV + JDAnalysis
│     Mapper        │   + TF-IDF)      → scored BulletEvidence list
└────────┬──────────┘
         │ Scored bullets
         ▼
┌───────────────────┐
│  4. Section       │  (Deterministic) decide which sections to edit
│     Strategy      │                  based on domain, gaps, scores
│     Planner       │
└────────┬──────────┘
         │ EditPlan
         ▼
┌───────────────────┐
│  5. Bullet        │  (LLM, grounded) Select or rewrite bullets
│     Selector/     │                  strictly from evidence bank
│     Rewriter      │
└────────┬──────────┘
         │ TailoredOutput
         ▼
┌───────────────────┐
│  6. QA Validator  │  (Deterministic  Check factual support,
└────────┬──────────┘   + LLM)         lengths, keyword coverage
         │ QAReport
         ▼
┌─────────────┬─────────────────────┐
│             │                     │
▼             ▼                     ▼
ATS         Change               Cover Letter
Report      Log                  Writer
Generator   Generator            (LLM)
│             │                     │
└─────────────┴─────────────────────┘
              │ WorkflowResult
              ▼
         Renderer (pdf_generator.py)
         → DOCX + PDF output
```

#### [MODIFY] [agent_workflow.py](file:///c:/Users/asele/Documents/ApplAI/agent_workflow.py)

This file is **completely replaced**. Key changes:

**Module 1 — CV Loader (`load_canonical_cv`)**
- Input: raw JSON from `json_exports/` (currently just `{source_file, raw_text}`)
- LLM call: parse `raw_text` into structured `CanonicalCV` with `BulletEvidence` for every bullet
- Output: `CanonicalCV`
- Mode: LLM-assisted, but uses strict JSON output schema (Pydantic)
- Failure: falls back to partial structure if LLM fails

**Module 2 — JD Parser (`parse_jd`)**
- Input: JD text string
- LLM call: extract ranked requirements, domain classification, keyword sets
- Output: `JDAnalysis`
- Mode: LLM with structured output

**Module 3 — Evidence Mapper (`map_evidence`)**
- Input: `CanonicalCV`, `JDAnalysis`
- Algorithm: For each `BulletEvidence`, compute relevance score vs `ranked_requirements`
  - Keyword overlap scoring (deterministic)
  - Domain tag matching (deterministic)
- Output: `list[ScoredBullet]` — each bullet with relevance score
- Mode: Mostly deterministic (string matching + tag overlap), LLM only if low-confidence

**Module 4 — Section Strategy Planner (`plan_strategy`)**
- Input: `JDAnalysis`, `ScoredBullet` list
- Decision table:
  - If `domain == "ai_ml"` → prioritize ML project bullets, skills
  - If `domain == "software"` → prioritize API/full-stack bullets
  - etc.
- Output: `EditPlan` — `{sections_to_edit, max_bullets_per_section, rewrite_threshold_score}`
- Mode: Deterministic rule engine

**Module 5 — Bullet Selector/Rewriter (`select_and_rewrite`)**
- Input: `TailoredOutput` plan, `CanonicalCV`, `EditPlan`, `JDAnalysis`
- For each editable section:
  - Sort bullets by relevance score
  - Take top N (from EditPlan)
  - For bullets above rewrite threshold: mark `action="select_as_is"`
  - For bullets with keyword gaps but sufficient evidence: `action="rewrite"` (LLM call)
  - LLM prompt is strictly grounded: "Given ONLY this original bullet text, rephrase to emphasize X and Y. Do not add new facts."
  - For locked bullets: `action="select_as_is"` if relevant, `action="deselect"` if not
- Output: `TailoredOutput` with full `BulletSelection` list
- Mode: Hybrid (deterministic selection + LLM rewriting where needed)

**Module 6 — QA Validator (`validate_qa`)**
- Input: `TailoredOutput`, `CanonicalCV`, `JDAnalysis`
- Deterministic checks:
  - Bullet count per section (≥ 2, ≤ 8)
  - No rewritten bullet invents a new employer, date, or tool not in original
  - Locked section fields unchanged
- LLM check:
  - "Does this rewritten bullet make any claim not supported by the original text?"
- Output: `QAReport` with pass/fail flags
- Mode: Hybrid

**Module 7 — ATS Keyword Analyzer (`analyze_ats`)**
- Input: `TailoredOutput`, `JDAnalysis`, `CanonicalCV`
- Deterministic: set intersection/difference between JD keywords and tailored text
- Output: `ATSReport`
- Mode: Fully deterministic

**Module 8 — Change Log Generator (`generate_change_log`)**
- Input: `TailoredOutput`, `CanonicalCV`
- Builds `ChangeLog` from all `BulletSelection` entries
- Includes: original text, new text, action, rationale, which JD requirements addressed
- Output: `ChangeLog`
- Mode: Fully deterministic

**Orchestrator ([run_application_workflow](file:///c:/Users/asele/Documents/ApplAI/agent_workflow.py#109-124))**
- Chains all 8 modules
- Returns `WorkflowResult` dataclass containing all module outputs
- [app.py](file:///c:/Users/asele/Documents/ApplAI/app.py) reads this result by field name

---

#### [MODIFY] [pdf_generator.py](file:///c:/Users/asele/Documents/ApplAI/pdf_generator.py)

Small improvements:
- Accept the new `TailoredOutput` model in addition to the current `tailored_data` dict
  (keep backward compatibility)
- Add skills section injection (currently not in the renderer)
- Add overflow detection: check if resulting paragraph count exceeds original

---

#### [MODIFY] [app.py](file:///c:/Users/asele/Documents/ApplAI/app.py)

Minimal changes — the rendering section after `result = agent_workflow.run_application_workflow(...)`:
- Read `result.tailored_output`, `result.qa_report`, `result.change_log`, `result.ats_report`
- Add a **Change Log** expander below the Keyword Match Analysis section
- ATS report replaces the current ad-hoc keyword analysis code (which can be removed)
- All other UI, CSS, tabs, form, and download code untouched

---

## Prompting Strategy (Key LLM Agents)

### JD Parser prompt contract
```
System: You are a requirements analyst. Extract structured requirements from job descriptions.
Return ONLY valid JSON matching this schema: {JDAnalysis schema}
User: <job description>
```

### CV Loader / Structurer prompt contract
```
System: You are a CV parser. Convert this raw CV text into a structured JSON format.
- Do NOT infer or invent any information not present in the text.
- For every bullet point, preserve it exactly in the "text" field.
- Identify the section it belongs to (profile/experience/projects/education/skills).
- For experience bullets, record the employer and role from the nearest header above them.
Return ONLY valid JSON matching this schema: {CanonicalCV schema}
User: <raw_text>
```

### Bullet Rewriter prompt contract
```
System: You are a CV editor. Your ONLY job is to rephrase a single bullet point.
RULES (non-negotiable):
- Do NOT add any skills, tools, metrics, projects, or experiences not present in the original.
- Do NOT change the employer, date, or role.
- You MAY rephrase to emphasize the following JD keywords: {keyword_list}
- The output must be a single bullet point, max 2 lines.
- If the original bullet cannot be improved without inventing content, return it unchanged.
Return ONLY valid JSON: {"action": "rewrite"|"unchanged", "text": "<bullet text>", "rationale": "<1 sentence>"}
User: Original bullet: {original_text}
```

### QA Hallucination Check prompt contract
```
System: You are a factual auditor. Check if a rewritten CV bullet introduces any claims not in the original.
Return ONLY valid JSON: {"supported": true|false, "concern": "<description or null>"}
User: Original: {original_text}
Rewritten: {new_text}
```

---

## What is NOT changed

- [app.py](file:///c:/Users/asele/Documents/ApplAI/app.py) UI layout, CSS/styling, tabs, CV Corpus Manager, Google Drive integration
- [pdf_parser.py](file:///c:/Users/asele/Documents/ApplAI/pdf_parser.py)
- [pdf_generator.py](file:///c:/Users/asele/Documents/ApplAI/pdf_generator.py) core replacement logic
- [requirements.txt](file:///c:/Users/asele/Documents/ApplAI/requirements.txt) (no new packages needed)
- All docs/ files

---

## Verification Plan

### Automated Tests
- Run [test_workflow.py](file:///c:/Users/asele/Documents/ApplAI/test_workflow.py) (the existing test) to ensure the new workflow still accepts the same interface:
  ```powershell
  cd c:\Users\asele\Documents\ApplAI
  python test_workflow.py
  ```
  Expected: no exception, `WorkflowResult` object returned with all fields populated.

### Manual UI Verification
1. Start the app: `streamlit run app.py`
2. Paste a JD (e.g. a software developer role)
3. Select `Selekoglu CV 2026 - AAFC Data Analyst Developer.pdf`
4. Click "Generate Tailored Application"
5. Verify:
   - ✅ Match Rate Score metric shows a number
   - ✅ Agent Execution Log expander shows each module's output
   - ✅ Change Log expander shows which bullets were selected/rewritten
   - ✅ Keyword Analysis section (now from ATS module) shows coverage
   - ✅ DOCX download opens correctly with formatting preserved
   - ✅ No hallucinated employer names, dates, or tools added to the CV

---

# Phase 2: Live UI & Renderer Fix

## Goal Description
Address the job title overwriting bug in the CV renderer and implement a premium real-time progress UI with card-swipe animations and step history navigation.

## Proposed Changes

### [Bullet Renderer Fix]
#### [MODIFY] [pdf_generator.py](file:///c:/Users/asele/Documents/ApplAI/pdf_generator.py)
The system currently fails to distinguish between job title rows and bullet points because both use the 'Normal' style.
- **Fix**: Use `left_indent > 0` as the primary filter. Job titles/companies have `indent=0` and will be skipped. Indented bullets will be replaced.

### [Live Loading UI]
#### [MODIFY] [agent_workflow.py](file:///c:/Users/asele/Documents/ApplAI/agent_workflow.py)
[NEW] `run_application_workflow_streaming()`: A generator that yields `StepUpdate` objects (Step #, Module Name, Running/Done, Summary, Detail Lines).

#### [MODIFY] [app.py](file:///c:/Users/asele/Documents/ApplAI/app.py)
Replace the static `st.spinner` with a dynamic **Live Pipeline Runner**:
- **Overlay Component**: A glassmorphism overlay using custom CSS.
- **Card-Swipe Animation**: CSS `transform: translateX` transitions triggered by Step updates.
- **Step History**: Maintain a list of completed steps in `st.session_state` and allow "Back/Next" navigation buttons to view intermediate outputs (Evidence scores, strategy, etc.) while the model is still running.
- **Detailed Logs**: Real-time display of module logs (similar to the user's provided example).

## Verification Plan

### Automated Tests
- Import test for `run_application_workflow_streaming`.
- Manual verification of bullet preservation in a test DOCX.

### Manual UI Verification
- Run the workflow and verify the loading cards swipe left/right correctly.
- Verify "Back" button works while the next agent is spinning.
- Check that the final CV preserves "Technical Business Analyst" and company name lines.

