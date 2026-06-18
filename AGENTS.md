# ApplAI Agent Coordination Guide

This file is the first stop for any agent working in this repository.

## Project Mission

ApplAI is being rebuilt from an AI job application board into a private AI Career Manager for Ata Selekoglu.

The product goal is to help Ata find, score, prepare, approve, and track job applications for software, AI, automation, technical analyst, and business-tech roles.

V1 must remain human-in-the-loop:

- Agents may discover, score, draft, tailor, render, summarize, and recommend.
- Agents must not submit applications, publish posts, send messages, or mark an application as ready-to-submit without explicit approval.

## Source Of Truth

Read these files before implementation:

1. `docs/career-manager-sprint0-plan.md`
2. `TODO.md`
3. `future_roadmap.md`
4. `README.md`

If these conflict, prefer `docs/career-manager-sprint0-plan.md` for architecture and `TODO.md` for current execution status.

## Architecture Decision

ApplAI is moving to an Eve-first orchestration model.

- Eve owns durable workflows, approvals, schedules, subagents, channels, evals, and agent behavior.
- ApplAI Core services own Career Brain, job scoring, tailored example parsing, CV tailoring contracts, DOCX/PDF rendering, exports, and tracker persistence.
- Do not bury career domain logic inside Eve prompts.
- Eve tools should call typed Core API endpoints first.
- Keep existing Python/FastAPI CV parsing and rendering operational.
- Do not delete Streamlit, FastAPI, React/Vite, CV parsing, or rendering paths unless a later plan explicitly says so.

## Current Build Target

Current active build target:

`Sprint 3 - CV Tailoring Engine`

Sprint 0.5 has been implemented:

- `eve/` workspace exists.
- `POST /jobs/score` exists in Core API.
- Eve `score_job` calls Core first.
- Approval policy tests exist.
- `eve/workflows/score_job.workflow.ts` is a typed local adapter.

Known Eve blocker:

- Official Eve docs currently document the agent directory shape, `defineTool`, skills, and `needsApproval`, but not a stable custom workflow file API.
- Keep workflow files as typed local adapters until Vercel documents runtime conventions.
- `npm run typecheck` in `eve/` passes after dependency setup.
- Eve `0.11.4` declares Node `>=24`; use Node 24+ before relying on runtime execution beyond static typechecking.

Sprint 1 has been implemented:

- Career Brain schemas and JSON-backed service exist.
- `GET/PUT /career-brain` exists.
- Tailored examples schemas and importer exist.
- All 20 PDFs under `docs/tailored_examples/` are discovered and parse as two pages in tests.
- First master-vs-example diff classifier scaffold exists.
- Eve tools exist for reading Career Brain and listing tailored examples.

Sprint 2 has been implemented:

- Local persisted job records under `docs/jobs/` exist; generated JSON stays ignored.
- `POST /jobs/import`, `GET /jobs`, and `GET /jobs/{job_id}` exist.
- Job parsing extracts responsibilities, qualifications, keywords, seniority, domain, location/remote hints, and effort signals.
- Scoring loads Career Brain evidence and returns evidence matches, missing keywords, concerns, and `apply` / `skip` / `worth_20_minutes`.
- Eve `score_job` remains a thin Core API adapter.

Expected Sprint 3 vertical slice:

First vertical slice implemented:

1. Saved `JobRecord` + Career Brain evidence feed into the CV tailoring pipeline.
2. Evidence selection starts from scored job evidence matches.
3. Selected/reworded bullets and change-log entries carry provenance metadata.
4. Unsupported-claim guard metadata flags unsupported introduced terms.
5. Page-budget metadata and compression-loop order are recorded before render.
6. Export metadata returns artifact IDs/paths and conditional page-count/layout validation when a CV PDF path exists.
7. Eve `tailor_cv` and `render_cv` remain thin Core API adapters.
8. Tests cover saved-job tailoring, evidence selection, provenance, unsupported-claim flagging, layout metadata, and draft approval boundary.

Remaining Sprint 3 focus:

1. Make CV PDF generation/page-count validation unconditional, or clearly separate DOCX-only draft render from PDF validation.
2. Turn compression-loop metadata into a deterministic content reduction pass.
3. Add a user-facing diff/approval screen before any ready-to-submit state.
4. Broaden QA around provenance quality, generated artifacts, and application tracker boundaries.

## Working Rules

- Check `git status --short` before editing.
- Treat existing modified/untracked files as user-owned unless you created them in the current task.
- Use `rg` / `rg --files` for repo search.
- Keep edits tightly scoped to the active task.
- Do not commit unless Ata explicitly asks.
- Do not move private CV data or generated profile data outside local ignored paths.
- Prefer tests around service boundaries and approval policy over broad snapshot tests.

## Handoff Requirements

Every implementation agent should report:

- Files changed.
- Commands run.
- Tests/checks passed or failed.
- Any blockers.
- Whether `TODO.md` needs status changes.
- Any architecture deviation from `docs/career-manager-sprint0-plan.md`.

If a task is blocked because Eve SDK/API details are unclear, document:

- what was attempted,
- official docs checked,
- exact missing package/API detail,
- safest scaffold left behind.

## Privacy Rules

Private/local data paths:

- `docs/tailored_examples/`
- `docs/career_brain/`
- `docs/jobs/`
- `docs/applications/`
- generated DOCX/PDF outputs under `docs/`

Do not upload, publish, or expose these paths externally without explicit approval.
