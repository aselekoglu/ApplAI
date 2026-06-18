# ApplAI Active TODO

Last updated: 2026-06-18

## Current Status

- [x] Sprint 0 master plan drafted.
- [x] Tailored CV examples inspected: 20 PDFs, all 2 pages, text extraction works.
- [x] Industry research added for Teal, Rezi, Huntr, Simplify, Enhancv, Resume.io, Kickresume, and AIApply.
- [x] Eve-first orchestration decision added to the master plan.
- [x] Sprint 0.5 Eve spike implemented in a separate agent window.
- [ ] Sprint 1 Career Brain + Tailored Examples is next.

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
- [ ] `npm run typecheck` in `eve/` is blocked until Eve workspace dependencies install `tsc`.

Known blocker:

- Official Eve docs currently document agent directory shape, `defineTool`, skills, and `needsApproval`, but not a stable custom workflow file API. `eve/workflows/score_job.workflow.ts` is therefore a typed local adapter until Vercel documents workflow module conventions.

## Active Sprint: Sprint 1 - Career Brain And Tailored Examples

Goal: turn Ata's master CV, skills, projects, and tailored historical PDFs into structured evidence that scoring and tailoring can use.

Recommended order:

- [ ] Review Sprint 0.5 changed files in detail before layering more work.
- [ ] Install or document Eve workspace dependencies so `npm run typecheck` can run.
- [ ] Add `CareerBrainProfile`, `EvidenceBlock`, `ExperienceRecord`, `ProjectRecord`, `SkillInventory`, and preference schemas.
- [ ] Add JSON-backed `career_brain_service`.
- [ ] Add `/career-brain` FastAPI route.
- [ ] Add tests for Career Brain seeding and profile retrieval.
- [ ] Add tailored examples schemas.
- [ ] Implement tailored PDF discovery for `docs/tailored_examples/`.
- [ ] Extract page count, PDF title, filename role label, text, and section headings.
- [ ] Add tests proving all 20 PDFs are discovered and each has `page_count == 2`.
- [ ] Add a first master-vs-example diff classifier.
- [ ] Add Eve tool contract for reading Career Brain profile.
- [ ] Add Eve tool contract for listing tailored examples.

## Near-Term Backlog

- [x] Implement first job scoring service and route.
- [x] Connect Eve `score_job` tool to Core scoring endpoint.
- [ ] Add persisted job records under `docs/jobs/`.
- [ ] Add approval service and approval event persistence.
- [ ] Expand scoring from initial keyword heuristic to Career Brain evidence scoring.
- [ ] Connect scoring results to application tracker draft records.
