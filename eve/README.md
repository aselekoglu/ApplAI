# ApplAI Eve Spike

This workspace is the Sprint 0.5 Eve orchestration boundary. The goal is to keep ApplAI Core portable and call the existing FastAPI service before adding any agent-native business logic.

## Current status

- `tools/score_job.ts` is the first working thin adapter. It calls `POST /jobs/score` on the Core API.
- `tools/tailor_cv.ts`, `tools/render_cv.ts`, `tools/save_application.ts`, and `tools/approve_artifact.ts` define the first contracts and approval boundaries.
- `workflows/score_job.workflow.ts` is a minimal local workflow adapter. It scores a pasted job description and returns one of `apply`, `skip`, or `worth_20_minutes`.
- The workflow does not perform state-changing follow-up actions. Saving, ready-to-submit transitions, publishing, sending, uploading, and external submission are explicitly approval-gated.

## SDK blocker

Official Vercel Eve docs confirm the agent directory shape, Markdown instructions/skills, TypeScript tools via `defineTool`, and `needsApproval` on tools. The public docs do not yet show a stable custom workflow file API beyond schedules/evals/tool files, so `workflows/score_job.workflow.ts` is intentionally written as a typed local adapter. Once Eve exposes or documents workflow module conventions, wire this file into the runtime without moving the scoring logic into Eve prompts.

## Local run assumptions

Set `APPLAI_CORE_API_URL` if the FastAPI Core API is not running at `http://127.0.0.1:8000`.
