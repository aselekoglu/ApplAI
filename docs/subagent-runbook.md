# Subagent runbook (ApplAI)

Use this when you want **parallel, bounded work** instead of one monolithic agent pass. In Cursor, that means the lead agent **spawns multiple subagent tasks in a single message** (e.g. explore / general-purpose), each with a **narrow scope, explicit paths, and a fixed deliverable**.

---

## Method (same as dual-stack migration)

1. **Split by surface** — no two subagents should edit the same files in the same pass.
2. **Read-only first** — prefer `explore` + `readonly` when the goal is a map or a plan; use write-capable agents only when implementation is clear.
3. **One merge owner** — the parent applies diffs or resolves conflicts after all subagents return; subagents do not “coordinate” with each other.
4. **Verify in the prompt** — each subagent block ends with **exact commands** to run before reporting done.

---

## How to make *your* commands more specific

Vague → **specific** (fill the bracketed bits):

| Weak | Strong |
|------|--------|
| “Finish the project” | “**API only**: add `PUT /masters/{id}` that calls `finalize_master` with `overwrite=True`; touch only `api/app/routes/masters.py` and `master_service.py`; run `python -m compileall api`.” |
| “Polish the UI” | “**Web only**: `web/src/pages/MastersPage.tsx` + `web/src/styles.css`; add empty-state copy and a loading skeleton; do not change `api/`; run `cd web && npm run build`.” |
| “Fix CORS” | “**Config only**: `api/app/config.py` — add `http://127.0.0.1:4173` to default `APPLAI_CORS_ORIGINS`; update `README.md` one line; no route logic changes.” |

Always include:

- **Paths** (directories or files).
- **Out of scope** (what not to touch).
- **Definition of done** (one sentence).
- **Verification** (commands below).

---

## Copy-paste: parent message (parallel batch)

Send **one** user message with **three** Task blocks (adjust names if your client labels them differently). Each block is self-contained.

### Subagent A — API slice

```text
You are the API subagent for repo ApplAI (Python FastAPI under api/app/).

Scope: ONLY files under api/ (prefer api/app/routes/, api/app/services/, api/app/schemas/, api/app/adapters/, api/app/config.py).

Task: [DESCRIBE: e.g. add endpoint X, fix schema Y, align service Z with master_cv]

Out of scope: web/, Streamlit app.py, unrelated refactors.

Deliverable: Minimal diff; list files changed.

Before done, run from repo root:
  python3 -m compileall api
  PYTHONPATH=. python3 -c "from api.app.main import app; print('ok', app.title)"

Report: summary, file list, any follow-ups for the merge agent.
```

### Subagent B — Web slice

```text
You are the Web subagent for ApplAI (Vite + React + TS under web/).

Scope: ONLY web/src/ and web/package.json / web/vite.config.ts if needed.

Task: [DESCRIBE: e.g. new route, form validation, api-client method]

Out of scope: api/, Python, Streamlit.

Deliverable: Minimal diff; list files changed.

Before done, run:
  cd web && npm run build

Report: summary, file list, how to manually verify in the browser (URL + clicks).
```

### Subagent C — Integration / hygiene

```text
You are the Integration subagent for ApplAI.

Scope: README.md, web/.env.example, .gitignore, docs/*.md (not generated docs/), cross-stack wiring only.

Task: [DESCRIBE: e.g. document ports 5173/8000, env vars, run order]

Out of scope: business logic in agent_workflow.py, large UI rewrites.

Deliverable: Doc-only or tiny config edits; list files changed.

Report: exact “start dev” sequence for a new clone.
```

**Parent after return:** merge conflicts, run full smoke (API + `npm run build`), one commit message.

---

## Copy-paste: single deep subagent (exploration)

Use when you do not know where logic lives.

```text
explore agent, readonly, thoroughness: medium.

Repository: ApplAI root.

Question: [e.g. Where is tailoring run persisted and loaded for GET /tailor/runs?]

Return: bullet list of file:line references, 1 short data-flow sentence, and suggested owner (api vs web vs core) for the actual fix.
```

---

## ApplAI-specific verification cheatsheet

| Layer | Command |
|-------|---------|
| API | `PYTHONPATH=. ./.venv/bin/python -m uvicorn api.app.main:app --reload` then open `/docs` |
| API import | `PYTHONPATH=. python3 -c "from api.app.main import app"` |
| Web | `cd web && npm run build` |
| Core workflow | `python3 test_workflow.py` (needs env / keys as today) |

---

## When *not* to split

- One file, &lt; ~50 lines of change.
- You need atomic behavior across API + web (then use **one** agent or run API first, then web in sequence).

---

## Optional: your “master command” template

Keep a note in your scratchpad and only swap bracketed segments:

```text
Use the subagent runbook in docs/subagent-runbook.md.

Spawn 3 parallel subagents (API / Web / Integration) with the tasks below. I will merge.

API: [one sentence, files under api/]
Web: [one sentence, files under web/]
Integration: [one sentence, docs + env + readme]

Global constraints: Python 3.x, no new deps unless justified, small diffs.
```

This keeps your commands **specific** without rewriting the whole runbook each time.
