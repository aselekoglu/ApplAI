# ApplAI Active TODO

Last updated: 2026-06-18

## Current Status

- [x] Sprint 0 master plan drafted.
- [x] Tailored CV examples inspected: 20 PDFs, all 2 pages, text extraction works.
- [x] Industry research added for Teal, Rezi, Huntr, Simplify, Enhancv, Resume.io, Kickresume, and AIApply.
- [x] Eve-first orchestration decision added to the master plan.
- [x] Sprint 0.5 Eve spike implemented in a separate agent window.
- [x] Sprint 1 Career Brain + Tailored Examples foundation implemented.
- [x] Sprint 2 Job Intake + Career Brain-backed Scoring vertical slice implemented.
- [ ] Sprint 3 CV Tailoring Engine first vertical slice is implemented; broader approval UI/render hardening remains.

## Completed Sprint: Sprint 0.5 - Eve Spike And Boundary Proof

Owner: external implementation agent in another window.

Goal: prove Eve can orchestrate ApplAI workflows without moving core career logic into Eve.

Checklist:

- [x] Inspect current repo structure and git status.
- [x] Read `docs/career-manager-sprint0-plan.md`.
- [x] Create `eve/` workspace skeleton.
- [x] Add `eve/instructions.md`.
- [x] Add `eve/skills/approval_policy.md`.
- [x] Add minimal skills for Career Brain, job scoring, and CV tailoring.
- [x] Add tool contract stubs for:
  - [x] `score_job`
  - [x] `tailor_cv`
  - [x] `render_cv`
  - [x] `save_application`
  - [x] `approve_artifact`
- [x] Implement or scaffold `score_job` as a thin adapter over a Core API endpoint.
- [x] Add a minimal `score_job.workflow.ts`.
- [x] Ensure workflow pauses before state-changing follow-up actions.
- [x] Add or expose Core API job scoring endpoint.
- [x] Add approval policy tests where feasible.
- [x] Run focused verification commands.
- [x] Report changed files, tests, and blockers.

Acceptance criteria:

- [x] Existing FastAPI app still imports/runs.
- [x] Existing Streamlit, FastAPI, React/Vite, CV parsing, and rendering code remains intact.
- [x] `eve/` workspace exists with instructions, tools, workflow, and approval policy.
- [x] `score_job` path is implemented or scaffolded with exact blocker notes.
- [x] No submit/publish/send/upload/ready-to-submit action can run without approval.
- [x] Private data stays local.

Verification reported by implementation agent:

- [x] `python3 -m unittest discover -s tests -p 'test_*.py'` passed.
- [x] `python3 -c "import api.app.main; print(api.app.main.app.title)"` passed.
- [x] FastAPI `POST /jobs/score` smoke returned `200`, recommendation `apply`, score `96`.
- [x] `npm test` in `eve/` passed approval policy tests.
- [x] `npm run typecheck` in `eve/` now passes after Sprint 1 dependency setup.

Known blocker:

- Official Eve docs currently document agent directory shape, `defineTool`, skills, and `needsApproval`, but not a stable custom workflow file API. `eve/workflows/score_job.workflow.ts` is therefore a typed local adapter until Vercel documents workflow module conventions.

Runtime caveat:

- Eve `0.11.4` declares Node `>=24`; the current shell is Node `v22.22.3`, so runtime work should use Node 24+ even though static typecheck passes.

## Completed Sprint: Sprint 1 - Career Brain And Tailored Examples

Goal: turn Ata's master CV, skills, projects, and tailored historical PDFs into structured evidence that scoring and tailoring can use.

Recommended order:

- [x] Review Sprint 0.5 changed files in detail before layering more work.
- [x] Install or document Eve workspace dependencies so `npm run typecheck` can run.
- [x] Add `CareerBrainProfile`, `EvidenceBlock`, `ExperienceRecord`, `ProjectRecord`, `SkillInventory`, and preference schemas.
- [x] Add JSON-backed `career_brain_service`.
- [x] Add `/career-brain` FastAPI route.
- [x] Add tests for Career Brain seeding and profile retrieval.
- [x] Add tailored examples schemas.
- [x] Implement tailored PDF discovery for `docs/tailored_examples/`.
- [x] Extract page count, PDF title, filename role label, text, and section headings.
- [x] Add tests proving all 20 PDFs are discovered and each has `page_count == 2`.
- [x] Add a first master-vs-example diff classifier.
- [x] Add Eve tool contract for reading Career Brain profile.
- [x] Add Eve tool contract for listing tailored examples.

Sprint 1 verification notes:

- [x] `python3 -m unittest discover -s tests -p 'test_*.py'` passed.
- [x] `python3 -c "import api.app.main; print(api.app.main.app.title)"` passed.
- [x] `npm test` in `eve/` passed approval policy tests.
- [x] `npm run typecheck` in `eve/` passed after installing Eve dependencies.
- [ ] Eve runtime execution still needs Node `>=24`; local verification used Node `v22.22.3`, which prints npm `EBADENGINE` warnings for `eve@0.11.4`.
- [x] No private PDF-derived JSON was generated or committed; tailored examples parse on demand from local PDFs.

## Completed Sprint: Sprint 2 - Job Intake And Career Brain-backed Scoring

Goal: upgrade the first keyword-only scoring path into a persisted job intake and evidence-aware scoring workflow.

Recommended order:

- [x] Review Sprint 1 changed files before layering more work.
- [x] Add `docs/jobs/` local persistence service for job records.
- [x] Add `JobRecord` persistence fields for raw JD, company, title, source URL, parsed requirements, score report, recommendation, and timestamps.
- [x] Extend `POST /jobs/score` or add `POST /jobs/import` so scored jobs can be saved as drafts.
- [x] Parse job descriptions into responsibilities, qualifications, keywords, seniority, domain, location/remote hints, and effort signals.
- [x] Load Career Brain evidence blocks during scoring.
- [x] Score JD requirements against evidence blocks, role preferences, technologies, and skill categories.
- [x] Return top evidence block IDs and missing evidence/keyword gaps.
- [x] Keep recommendations limited to `apply`, `skip`, or `worth_20_minutes`.
- [x] Update Eve `score_job` contract/adapter if Core response shape changes.
- [x] Add tests for persisted job records and Career Brain-backed evidence scoring.
- [x] Keep `npm test` and `npm run typecheck` passing in `eve/`.
- [x] Do not introduce submit/publish/send/upload/ready-to-submit actions without approval.

Sprint 2 verification notes:

- [x] `python3 -m unittest discover -s tests -p 'test_*.py'` passed.
- [x] `python3 -c "import api.app.main; print(api.app.main.app.title)"` passed.
- [x] `npm test` in `eve/` passed.
- [x] `npm run typecheck` in `eve/` passed.
- [x] `git diff --check` passed.
- [x] Generated job records remain local JSON under ignored `docs/jobs/*.json`; only `docs/jobs/.gitkeep` is tracked.

## Active Sprint: Sprint 3 - CV Tailoring Engine

Goal: generate a truthful, role-specific, two-page CV from a saved job record and Career Brain evidence.

Recommended order:

- [x] Review Sprint 2 changed files before layering more work.
- [x] Connect existing tailoring service to saved `JobRecord` inputs.
- [x] Load Career Brain evidence blocks during tailoring.
- [x] Build evidence selection from scored job evidence matches before rewriting.
- [x] Ensure each selected/reworded bullet carries source provenance.
- [x] Add an unsupported-claim guard that rejects claims without source support.
- [x] Add deterministic page-budget metadata before render.
- [x] Add render page-count validation for PDF outputs where the current render path exposes a CV PDF path.
- [x] Add compression loop ordering: remove low-priority bullets, shorten verbose bullets, reduce project detail, compress skills, adjust spacing last.
- [x] Return CV artifact IDs/paths, `page_count`, `layout_passed`, ATS report, QA report, and change log.
- [x] Keep Eve `tailor_cv` and `render_cv` as thin Core API adapters and update contracts if response shape changes.
- [x] Add tests for provenance, unsupported-claim prevention, page count/compression behavior, and approval boundary.
- [x] Keep `python3 -m unittest discover -s tests -p 'test_*.py'`, FastAPI import, `npm test`, `npm run typecheck`, and `git diff --check` passing.

Sprint 3 first-slice verification notes:

- [x] `python3 -m unittest discover -s tests -p 'test_*.py'` passed.
- [x] `python3 -c "import api.app.main; print(api.app.main.app.title)"` passed.
- [x] `npm test` in `eve/` passed.
- [x] `npm run typecheck` in `eve/` passed.
- [x] `git diff --check` passed.
- [ ] Current CV render path still writes DOCX for the CV; PDF page-count validation is conditional and will activate when a CV PDF export path is available.

## Near-Term Backlog

- [x] Implement first job scoring service and route.
- [x] Connect Eve `score_job` tool to Core scoring endpoint.
- [x] Implement Career Brain Pydantic schemas.
- [x] Implement JSON-backed Career Brain service.
- [x] Add `/career-brain` FastAPI route.
- [x] Implement tailored examples importer for `docs/tailored_examples/`.
- [x] Add tests for PDF discovery, page count, heading extraction, and master-vs-example diff.
- [x] Add persisted job records under `docs/jobs/`.
- [ ] Add approval service and approval event persistence.
- [x] Expand scoring from initial keyword heuristic to Career Brain evidence scoring.
- [x] Connect scoring results to draft job records.
- [ ] Connect approved scoring results to application tracker draft records.
- [ ] Feed saved jobs and Career Brain evidence into CV tailoring.
- [ ] Add two-page validation and compression loop.
