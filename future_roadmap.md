# ApplAI Future Roadmap

Last updated: 2026-06-18

This roadmap tracks the build sequence after the Eve-first architecture decision.

## Guiding Principles

- Human approval is mandatory before submit, publish, send, upload, or ready-to-submit actions.
- Eve orchestrates workflows; ApplAI Core owns deterministic career logic.
- Career Brain is the source of truth.
- CV generation must be provenance-backed, truthful, ATS-friendly, and capped at two pages.
- Private CV/application data stays local unless explicitly approved.

## Phase 0 - Architecture And Research

Status: mostly complete.

Completed:

- Repo assessment.
- Resume builder industry research.
- ATS, rendering, and CV truthfulness research.
- Tailored examples inventory.
- Eve-first orchestration decision.
- Master plan in `docs/career-manager-sprint0-plan.md`.

Remaining:

- Keep plan updated as implementation discovers real Eve SDK constraints.

## Phase 0.5 - Eve Spike And Boundary Proof

Status: implemented.

Purpose:

- Prove Eve can orchestrate ApplAI without absorbing core domain logic.
- Establish tool/workflow/approval conventions.

Deliverables:

- `eve/` workspace: delivered.
- Eve instructions and approval policy: delivered.
- Minimal tool contracts: delivered for `score_job`, `tailor_cv`, `render_cv`, `save_application`, and `approve_artifact`.
- `score_job` workflow: delivered as a typed local adapter.
- Core API endpoint for job scoring: delivered as `POST /jobs/score`.
- Verification notes: recorded in `TODO.md`.

Exit criteria:

- Existing app behavior is preserved.
- Eve `score_job` can call Core API.
- Approval gate is explicit and tested.

Known blocker:

- Vercel Eve public docs do not yet show a stable custom workflow file API. Keep workflow files as typed local adapters until Vercel documents runtime conventions.

Runtime caveat:

- Eve `0.11.4` declares Node `>=24`. Static typecheck passes after Sprint 1 dependency setup, but Eve runtime work should use Node 24+.

## Phase 1 - Career Brain And Tailored Examples

Status: implemented.

Purpose:

- Convert Ata's profile, CV, skills, projects, and historical tailored CVs into structured evidence.

Core work:

- Career Brain schema: delivered.
- Evidence blocks with provenance and truth constraints: delivered in schema.
- Project, skill, experience, and preference records: delivered in schema.
- Tailored examples importer for `docs/tailored_examples/`: delivered.
- Master-vs-tailored diff scaffold: delivered.
- Core API routes for profile and examples: delivered.
- Eve tools for profile/example retrieval: delivered.
- Eve TypeScript dependency setup: delivered; Node 24 remains runtime caveat.

Exit criteria:

- Career Brain can be loaded and updated.
- All 20 tailored PDFs can be parsed into local metadata.
- Historical examples can inform role-family calibration.

## Phase 2 - Job Intake And Scoring

Status: next active phase.

Purpose:

- Turn pasted job descriptions into actionable apply/skip decisions.

Core work:

- Job record schema and local JSON persistence.
- JD parser for requirements, responsibilities, qualifications, keywords, seniority, and domain.
- Hybrid scoring: keyword, semantic, role fit, seniority, location, work authorization, career value, effort.
- Recommendation output: `apply`, `skip`, or `worth_20_minutes`.
- Eve `score_job` tool connected to real scoring service. The first Core endpoint now exists; this phase upgrades it from keyword heuristic to Career Brain-backed evidence scoring.
- Evidence matching should use Career Brain evidence blocks and return top evidence block IDs plus missing keyword/evidence gaps.
- Scored jobs should be saved as draft records under `docs/jobs/`.

Exit criteria:

- A pasted JD produces a saved job record, score report, missing keywords, concerns, and recommended positioning.

## Phase 3 - CV Tailoring Engine

Purpose:

- Generate a truthful, role-specific, two-page CV from Career Brain evidence.

Core work:

- Evidence selection before rewriting.
- Grounded rewrite/compression only from source material.
- Provenance for every selected or rewritten bullet.
- Two-page render validation.
- Compression loop before spacing tweaks.
- Diff and approval screen.
- Eve `tailor_cv` and `render_cv` tools.

Exit criteria:

- Generated CV has DOCX/PDF outputs, page count <= 2, provenance, ATS report, QA report, and approval status.

## Phase 4 - Cover Letter And Application Packet

Purpose:

- Package everything needed to apply with minimal friction.

Core work:

- Cover letter generation.
- Recruiter notes.
- Interview prep notes.
- Application packet workflow.
- Approval-gated ready-to-submit state.

Exit criteria:

- For an approved job, ApplAI can produce a complete draft packet and save it to the tracker.

## Phase 5 - Application Tracker

Purpose:

- Track applications and reduce follow-up friction.

Core work:

- Application statuses.
- Follow-up dates and reminders.
- Weekly progress summary.
- Outcome tracking.
- Eve scheduled follow-up workflow.

Exit criteria:

- Ata can see current applications, stale follow-ups, and next actions.

## Phase 6 - Personal PR Agent

Purpose:

- Turn Ata's projects into visibility assets.

Core work:

- LinkedIn post drafts.
- GitHub README suggestions.
- Portfolio case studies.
- Recruiter-friendly summaries.
- Interview talking points.
- Approval-gated publish/send workflows.

Exit criteria:

- Each major project has reusable marketing/interview assets.

## Phase 7 - Hermes / Telegram Integration

Purpose:

- Expose key workflows through Telegram or Hermes without bypassing approvals.

Decision to make:

- Hermes remains VPS interface and calls Eve/Core APIs.
- Hermes becomes an Eve channel wrapper.
- Eve becomes primary channel runtime and Hermes is retired or narrowed.

Candidate commands:

- `/jobs_today`
- `/review_job`
- `/tailor_cv`
- `/generate_cover_letter`
- `/approve_application`
- `/reject_job`
- `/followups`
- `/linkedin_post`
- `/project_summary`
- `/weekly_report`

Exit criteria:

- Telegram/Hermes can trigger summaries and approvals while preserving the same approval policy as the web app.

## Parking Lot

- Full job scraping.
- Auto-apply.
- Browser automation for external application forms.
- Multi-user SaaS architecture.
- Postgres migration.
- Public productization.

These are intentionally deferred until the personal MVP works reliably.
