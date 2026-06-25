# AI Task Queue And Gemini Interactions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a durable ApplAI AI task queue and Arpa-style Q panel so long-running AI work runs in the background, stays inspectable, and opens completed results in the right review screen.

**Architecture:** Keep ApplAI Core responsible for job scoring, CV tailoring, rendering, artifact paths, and approval state. Add a small local queue layer in Core that persists task records under `docs/ai_tasks/`, runs task handlers in background threads, and exposes queue state through typed FastAPI endpoints. The React web app mirrors Arpa Meal Planner's Q UX, but it reads durable task state from Core instead of holding jobs only in memory.

**Tech Stack:** FastAPI, Pydantic, JSON persistence, Python `concurrent.futures`, Google GenAI Python SDK `google-genai>=2.3.0`, React 18, TypeScript, Vite.

---

## Source Notes

Arpa Meal Planner reference inspected at `C:\Users\asele\Documents\arpa-meal-planner\arpa-meal-planner`:

- `src/context/AiJobQueueContext.tsx`: in-memory AI job wrapper with `running | done | error`, local minimized state, auto-removal for completed non-restorable jobs, provider/model labels, and `buildRestore`.
- `src/components/AiJobQueuePanel.tsx`: sticky top-right queue card, minimized pill, running spinner, done/error rows, dismiss, clear done, and click-to-open completed results.
- `src/lib/ai-job-nav-state.ts`: route-state restore payloads used to reopen a completed AI result in the relevant editor.
- AI call sites such as `src/components/AddMealModal.tsx`, `src/components/GeneratePlanModal.tsx`, and `src/pages/GroceryList.tsx`: wrap async work as `runWithAiJob(meta, asyncFn)`.

Gemini docs checked on 2026-06-23:

- Interactions API is GA and recommended for new Gemini work: https://ai.google.dev/gemini-api/docs/interactions-overview
- Interactions support observable steps, server-side state, and `background=true`, but default storage keeps interactions for 55 days on paid tier and 1 day on free tier unless `store=false`.
- `store=false` is incompatible with `background=true` and prevents `previous_interaction_id`.
- Python SDK support for Interactions API requires `google-genai` package from `2.3.0` onward.
- Text generation uses `client.interactions.create(model=..., input=...)`, and streaming uses `stream=True`: https://ai.google.dev/gemini-api/docs/text-generation

Privacy decision:

- For ApplAI private CV/JD data, default Gemini calls must use `store=false`.
- Do not use Gemini `background=true` for private CV/JD content unless Ata explicitly approves Gemini-side storage.
- ApplAI's background Q should be local/durable under `docs/ai_tasks/`, not delegated to Gemini background execution.

## File Structure

Create:

- `api/app/schemas/ai_tasks.py`: Pydantic queue task records, request/response DTOs, status/kind/result types.
- `api/app/services/ai_task_service.py`: JSON persistence, task creation, status transitions, event append, handler dispatch, background executor lifecycle.
- `api/app/services/gemini_interactions_service.py`: Gemini Interactions API wrapper with private-by-default `store=false`.
- `api/app/routes/ai_tasks.py`: queue endpoints for create/list/get/cancel and typed aliases for tailoring/export tasks.
- `tests/test_ai_task_service.py`: unit tests for durable task persistence and state transitions.
- `tests/test_ai_task_routes.py`: FastAPI route tests with handlers mocked to avoid real Gemini calls.
- `tests/test_gemini_interactions_service.py`: SDK-call contract tests with fake client.
- `web/src/features/ai-tasks/AiTaskQueueContext.tsx`: polling queue context and helper to create tasks.
- `web/src/features/ai-tasks/AiTaskQueuePanel.tsx`: Arpa-inspired queue panel adapted to ApplAI visual system.
- `web/src/features/ai-tasks/ai-task-restore.ts`: route mapping for completed tasks.
- `web/src/features/ai-tasks/ai-task-labels.ts`: display labels for task kind/status.
- `web/src/features/ai-tasks/useAiTaskSubmit.ts`: typed helper for page actions that create background tasks.

Modify:

- `requirements.txt`: add `google-genai>=2.3.0`.
- `api/app/config.py`: add `ai_tasks_subdir`, `gemini_default_model`, and `ai_task_max_workers`.
- `api/app/main.py`: include `ai_tasks_router`.
- `api/app/services/tailoring_service.py`: reuse existing `run_tailoring_job`, `export_run`, and run record update paths from queue handlers without changing core behavior.
- `api/app/routes/tailoring.py`: keep current synchronous endpoints for compatibility; add no queue logic here beyond sharing schemas.
- `web/src/app/App.tsx`: wrap layout in `AiTaskQueueProvider`.
- `web/src/components/AppLayout.tsx`: render `AiTaskQueuePanel` near the top of `<main>`.
- `web/src/lib/api-client.ts`: add AI task endpoint calls.
- `web/src/lib/types.ts`: add AI task types and optional task metadata on result types if needed.
- `web/src/pages/TailoringPage.tsx`: replace blocking `Run tailoring` and `Export` actions with queue-backed task creation.
- `web/src/pages/RunsPage.tsx`: queue `rerun` and `export` actions; open selected run when completed.
- `web/src/styles.css`: add compact queue panel styles that match ApplAI's dark utility UI.
- `TODO.md`: after implementation passes, add a Sprint 3/3.2 note that AI tasks now run through a durable local queue.

Do not modify:

- Eve tool contracts except for a later follow-up after the Core queue is stable.
- Private generated files under `docs/career_brain/`, `docs/jobs/`, `docs/runs/`, or generated CV/PDF paths except through normal test fixtures.

## Data Contract

`AiTaskRecord` persisted at `docs/ai_tasks/<task_id>.json`:

```python
{
    "task_id": "task_...",
    "kind": "tailor_cv",
    "status": "queued",
    "title": "Tailor CV",
    "related_label": "Company - Role",
    "created_at": "2026-06-23T12:00:00+00:00",
    "updated_at": "2026-06-23T12:00:00+00:00",
    "started_at": None,
    "finished_at": None,
    "input": {"master_id": "master", "job_id": "job_123", "options": {}},
    "result": None,
    "error": None,
    "events": [
        {"created_at": "2026-06-23T12:00:00+00:00", "level": "info", "message": "Queued task."}
    ],
    "restore": None,
    "approval_required_before_apply": False,
}
```

Supported initial `kind` values:

- `score_job`: scores and optionally saves a draft job record.
- `tailor_cv`: creates a draft tailoring run.
- `render_cv`: exports/render artifacts for a run.
- `rerun_tailoring`: creates a new draft run from a historical run.
- `gemini_interaction`: low-level smoke/admin task for Interactions API connectivity; not exposed as a primary UI action.

Status values:

- `queued`: persisted and waiting for the local worker.
- `running`: handler started.
- `succeeded`: handler returned a result and restore target.
- `failed`: handler raised an exception.
- `cancelled`: cancellation accepted before handler start.

Restore mapping:

- `tailor_cv` -> `{ "path": "/runs", "state": { "selectedRunId": "<run_id>" } }`
- `render_cv` -> `{ "path": "/runs", "state": { "selectedRunId": "<run_id>", "showExports": true } }`
- `rerun_tailoring` -> `{ "path": "/runs", "state": { "selectedRunId": "<new_run_id>" } }`
- `score_job` -> future Jobs page; for now `{ "path": "/tailoring", "state": { "jobId": "<job_id>" } }`

## Task 1: Backend Task Schemas

**Files:**

- Create: `api/app/schemas/ai_tasks.py`
- Test: `tests/test_ai_task_service.py`

- [ ] **Step 1: Write schema tests**

Add this to `tests/test_ai_task_service.py`:

```python
import unittest

from api.app.schemas.ai_tasks import AiTaskCreateRequest, AiTaskRecord


class AiTaskSchemaTest(unittest.TestCase):
    def test_create_request_requires_known_kind(self):
        payload = AiTaskCreateRequest(
            kind="tailor_cv",
            title="Tailor CV",
            related_label="NRC - AI Analyst",
            input={"master_id": "master", "job_id": "job_abc"},
        )

        self.assertEqual(payload.kind, "tailor_cv")
        self.assertEqual(payload.input["master_id"], "master")

    def test_record_defaults_to_queued(self):
        record = AiTaskRecord.new(
            kind="render_cv",
            title="Render CV",
            related_label="Trend Micro",
            input={"run_id": "run_123"},
        )

        self.assertTrue(record.task_id.startswith("task_"))
        self.assertEqual(record.status, "queued")
        self.assertIsNone(record.result)
        self.assertEqual(record.events[0].message, "Queued task.")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
py -m unittest tests.test_ai_task_service.AiTaskSchemaTest -v
```

Expected: fail with `ModuleNotFoundError: No module named 'api.app.schemas.ai_tasks'`.

- [ ] **Step 3: Add schemas**

Create `api/app/schemas/ai_tasks.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


AiTaskKind = Literal[
    "score_job",
    "tailor_cv",
    "render_cv",
    "rerun_tailoring",
    "gemini_interaction",
]
AiTaskStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
AiTaskEventLevel = Literal["info", "warning", "error"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AiTaskEvent(BaseModel):
    created_at: str = Field(default_factory=utc_now)
    level: AiTaskEventLevel = "info"
    message: str


class AiTaskRestoreTarget(BaseModel):
    path: str
    state: Dict[str, Any] = Field(default_factory=dict)


class AiTaskCreateRequest(BaseModel):
    kind: AiTaskKind
    title: str
    related_label: str = ""
    input: Dict[str, Any] = Field(default_factory=dict)


class AiTaskRecord(BaseModel):
    task_id: str
    kind: AiTaskKind
    status: AiTaskStatus = "queued"
    title: str
    related_label: str = ""
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    input: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    events: List[AiTaskEvent] = Field(default_factory=list)
    restore: Optional[AiTaskRestoreTarget] = None
    approval_required_before_apply: bool = False

    @classmethod
    def new(cls, *, kind: AiTaskKind, title: str, related_label: str = "", input: Dict[str, Any] | None = None) -> "AiTaskRecord":
        now = utc_now()
        return cls(
            task_id=f"task_{uuid4().hex}",
            kind=kind,
            title=title,
            related_label=related_label,
            created_at=now,
            updated_at=now,
            input=input or {},
            events=[AiTaskEvent(created_at=now, message="Queued task.")],
        )


class AiTaskListResponse(BaseModel):
    tasks: List[AiTaskRecord] = Field(default_factory=list)
    count: int = 0
```

- [ ] **Step 4: Run schema tests**

Run:

```powershell
py -m unittest tests.test_ai_task_service.AiTaskSchemaTest -v
```

Expected: pass.

## Task 2: Durable Queue Service

**Files:**

- Create: `api/app/services/ai_task_service.py`
- Modify: `api/app/config.py`
- Test: `tests/test_ai_task_service.py`

- [ ] **Step 1: Add service tests**

Append this to `tests/test_ai_task_service.py` above the `if __name__ == "__main__"` block:

```python
import tempfile
from pathlib import Path
from unittest.mock import patch

from api.app.services import ai_task_service


class AiTaskServiceTest(unittest.TestCase):
    def test_create_persists_task_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_task_service, "tasks_dir", return_value=Path(tmp)):
                record = ai_task_service.create_task(
                    kind="tailor_cv",
                    title="Tailor CV",
                    related_label="NRC",
                    input={"master_id": "master"},
                    enqueue=False,
                )

                saved = Path(tmp, f"{record.task_id}.json")
                self.assertTrue(saved.exists())
                loaded = ai_task_service.get_task(record.task_id)
                self.assertEqual(loaded.status, "queued")
                self.assertEqual(loaded.input["master_id"], "master")

    def test_mark_succeeded_sets_restore_and_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_task_service, "tasks_dir", return_value=Path(tmp)):
                record = ai_task_service.create_task(
                    kind="render_cv",
                    title="Render CV",
                    input={"run_id": "run_1"},
                    enqueue=False,
                )

                updated = ai_task_service.mark_task_succeeded(
                    record.task_id,
                    result={"run_id": "run_1"},
                    restore_path="/runs",
                    restore_state={"selectedRunId": "run_1"},
                )

                self.assertEqual(updated.status, "succeeded")
                self.assertEqual(updated.result["run_id"], "run_1")
                self.assertEqual(updated.restore.path, "/runs")

    def test_cancel_queued_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_task_service, "tasks_dir", return_value=Path(tmp)):
                record = ai_task_service.create_task(
                    kind="tailor_cv",
                    title="Tailor CV",
                    input={},
                    enqueue=False,
                )

                cancelled = ai_task_service.cancel_task(record.task_id)

                self.assertEqual(cancelled.status, "cancelled")
                self.assertEqual(cancelled.events[-1].message, "Cancelled before start.")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
py -m unittest tests.test_ai_task_service -v
```

Expected: fail because `api.app.services.ai_task_service` does not exist.

- [ ] **Step 3: Add config fields**

Modify `api/app/config.py`:

```python
@dataclass
class Settings:
    docs_dir: str = field(default_factory=lambda: os.getenv("APPLAI_DOCS_DIR", "docs"))
    runs_subdir: str = field(default_factory=lambda: os.getenv("APPLAI_RUNS_SUBDIR", "runs"))
    ai_tasks_subdir: str = field(default_factory=lambda: os.getenv("APPLAI_AI_TASKS_SUBDIR", "ai_tasks"))
    default_model: str = field(default_factory=lambda: os.getenv("APPLAI_DEFAULT_MODEL", "gemini-2.5-flash"))
    gemini_default_model: str = field(default_factory=lambda: os.getenv("APPLAI_GEMINI_DEFAULT_MODEL", os.getenv("APPLAI_DEFAULT_MODEL", "gemini-2.5-flash")))
    ai_task_max_workers: int = field(default_factory=lambda: int(os.getenv("APPLAI_AI_TASK_MAX_WORKERS", "1")))
```

Add property:

```python
    @property
    def ai_tasks_dir(self) -> str:
        return os.path.join(self.docs_dir, self.ai_tasks_subdir)
```

- [ ] **Step 4: Implement queue service**

Create `api/app/services/ai_task_service.py`:

```python
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, List

from api.app.config import settings
from api.app.schemas.ai_tasks import AiTaskKind, AiTaskRecord, AiTaskRestoreTarget, AiTaskStatus, AiTaskEvent, utc_now


TaskHandler = Callable[[AiTaskRecord], tuple[Dict[str, Any], AiTaskRestoreTarget | None]]

_executor = ThreadPoolExecutor(max_workers=max(1, settings.ai_task_max_workers))
_lock = Lock()
_handlers: Dict[str, TaskHandler] = {}


def tasks_dir() -> Path:
    return Path(settings.ai_tasks_dir)


def ensure_tasks_dir() -> None:
    tasks_dir().mkdir(parents=True, exist_ok=True)


def task_path(task_id: str) -> Path:
    safe = "".join(ch for ch in task_id if ch.isalnum() or ch in "._-")
    if not safe:
        raise ValueError("task_id must contain safe filename characters")
    return tasks_dir() / f"{safe}.json"


def save_task(record: AiTaskRecord) -> AiTaskRecord:
    ensure_tasks_dir()
    task_path(record.task_id).write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return record


def get_task(task_id: str) -> AiTaskRecord:
    path = task_path(task_id)
    if not path.exists():
        raise FileNotFoundError(f"AI task '{task_id}' was not found")
    return AiTaskRecord.model_validate_json(path.read_text(encoding="utf-8"))


def list_tasks(limit: int = 50) -> List[AiTaskRecord]:
    ensure_tasks_dir()
    tasks: List[AiTaskRecord] = []
    for path in sorted(tasks_dir().glob("*.json"), reverse=True):
        try:
            tasks.append(AiTaskRecord.model_validate_json(path.read_text(encoding="utf-8")))
        except Exception:
            continue
        if len(tasks) >= limit:
            break
    return tasks


def register_task_handler(kind: AiTaskKind, handler: TaskHandler) -> None:
    _handlers[kind] = handler


def _append_event(record: AiTaskRecord, message: str, level: str = "info") -> AiTaskRecord:
    record.events.append(AiTaskEvent(message=message, level=level))  # type: ignore[arg-type]
    record.updated_at = utc_now()
    return record


def update_task_status(task_id: str, status: AiTaskStatus, message: str) -> AiTaskRecord:
    with _lock:
        record = get_task(task_id)
        record.status = status
        record.updated_at = utc_now()
        if status == "running":
            record.started_at = record.started_at or record.updated_at
        if status in {"succeeded", "failed", "cancelled"}:
            record.finished_at = record.updated_at
        _append_event(record, message, "error" if status == "failed" else "info")
        return save_task(record)


def mark_task_succeeded(task_id: str, *, result: Dict[str, Any], restore_path: str | None = None, restore_state: Dict[str, Any] | None = None) -> AiTaskRecord:
    with _lock:
        record = get_task(task_id)
        record.status = "succeeded"
        record.result = result
        record.restore = AiTaskRestoreTarget(path=restore_path, state=restore_state or {}) if restore_path else None
        record.error = None
        record.updated_at = utc_now()
        record.finished_at = record.updated_at
        _append_event(record, "Task completed.")
        return save_task(record)


def mark_task_failed(task_id: str, error: str) -> AiTaskRecord:
    with _lock:
        record = get_task(task_id)
        record.status = "failed"
        record.error = error
        record.updated_at = utc_now()
        record.finished_at = record.updated_at
        _append_event(record, error, "error")
        return save_task(record)


def cancel_task(task_id: str) -> AiTaskRecord:
    with _lock:
        record = get_task(task_id)
        if record.status != "queued":
            raise ValueError("Only queued tasks can be cancelled")
        record.status = "cancelled"
        record.updated_at = utc_now()
        record.finished_at = record.updated_at
        _append_event(record, "Cancelled before start.")
        return save_task(record)


def create_task(*, kind: AiTaskKind, title: str, related_label: str = "", input: Dict[str, Any] | None = None, enqueue: bool = True) -> AiTaskRecord:
    record = AiTaskRecord.new(kind=kind, title=title, related_label=related_label, input=input or {})
    save_task(record)
    if enqueue:
        _executor.submit(run_task, record.task_id)
    return record


def run_task(task_id: str) -> AiTaskRecord:
    current = get_task(task_id)
    if current.status == "cancelled":
        return current
    handler = _handlers.get(current.kind)
    if handler is None:
        return mark_task_failed(task_id, f"No handler registered for task kind: {current.kind}")
    update_task_status(task_id, "running", "Task started.")
    try:
        result, restore = handler(get_task(task_id))
        return mark_task_succeeded(
            task_id,
            result=result,
            restore_path=restore.path if restore else None,
            restore_state=restore.state if restore else None,
        )
    except Exception as exc:
        return mark_task_failed(task_id, str(exc))
```

- [ ] **Step 5: Run service tests**

Run:

```powershell
py -m unittest tests.test_ai_task_service -v
```

Expected: pass.

## Task 3: Queue Handlers For Existing Core Workflows

**Files:**

- Modify: `api/app/services/ai_task_service.py`
- Test: `tests/test_ai_task_service.py`

- [ ] **Step 1: Add handler tests with mocks**

Append:

```python
class AiTaskHandlerTest(unittest.TestCase):
    def test_tailor_handler_returns_run_restore(self):
        from api.app.schemas.ai_tasks import AiTaskRestoreTarget

        fake_response = type("TailorResponse", (), {"model_dump": lambda self: {"run_id": "run_abc"}, "run_id": "run_abc"})()

        with patch("api.app.services.ai_task_service.run_tailoring_job", return_value=fake_response):
            record = AiTaskRecord.new(
                kind="tailor_cv",
                title="Tailor CV",
                input={"master_id": "master", "job_description": "JD", "options": {"model_name": "gemini-2.5-flash"}},
            )

            result, restore = ai_task_service.handle_tailor_cv(record)

            self.assertEqual(result["run_id"], "run_abc")
            self.assertIsInstance(restore, AiTaskRestoreTarget)
            self.assertEqual(restore.state["selectedRunId"], "run_abc")

    def test_render_handler_returns_run_restore(self):
        fake_export = type("ExportResponse", (), {"model_dump": lambda self: {"run_id": "run_abc", "pdf_path": "docs/out.pdf"}})()

        with patch("api.app.services.ai_task_service.export_run", return_value=fake_export):
            record = AiTaskRecord.new(kind="render_cv", title="Render CV", input={"run_id": "run_abc"})

            result, restore = ai_task_service.handle_render_cv(record)

            self.assertEqual(result["pdf_path"], "docs/out.pdf")
            self.assertTrue(restore.state["showExports"])
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
py -m unittest tests.test_ai_task_service.AiTaskHandlerTest -v
```

Expected: fail because handler functions are missing.

- [ ] **Step 3: Add handlers and register them**

Append to `api/app/services/ai_task_service.py`:

```python
from api.app.schemas.jobs import JobImportRequest, ScoreJobRequest
from api.app.schemas.tailoring import ExportRequest, TailorRunOptions, TailorRunRequest
from api.app.services.export_service import export_run
from api.app.services.job_scoring_service import score_job
from api.app.services.tailoring_service import rerun_tailoring_job, run_tailoring_job


def _label_from_input(payload: Dict[str, Any]) -> str:
    company = str(payload.get("company_name") or "").strip()
    role = str(payload.get("job_title") or "").strip()
    return " - ".join(part for part in [company, role] if part)


def handle_score_job(record: AiTaskRecord) -> tuple[Dict[str, Any], AiTaskRestoreTarget | None]:
    request = ScoreJobRequest.model_validate(record.input)
    response = score_job(request)
    return response.model_dump(), AiTaskRestoreTarget(path="/tailoring", state={"jobId": response.job_id})


def handle_tailor_cv(record: AiTaskRecord) -> tuple[Dict[str, Any], AiTaskRestoreTarget | None]:
    options = TailorRunOptions.model_validate(record.input.get("options") or {})
    request = TailorRunRequest(
        master_id=str(record.input.get("master_id") or ""),
        job_id=record.input.get("job_id"),
        job_description=record.input.get("job_description"),
        options=options,
    )
    response = run_tailoring_job(request)
    return response.model_dump(), AiTaskRestoreTarget(path="/runs", state={"selectedRunId": response.run_id})


def handle_render_cv(record: AiTaskRecord) -> tuple[Dict[str, Any], AiTaskRestoreTarget | None]:
    request = ExportRequest.model_validate(record.input)
    response = export_run(request.run_id)
    return response.model_dump(), AiTaskRestoreTarget(path="/runs", state={"selectedRunId": response.run_id, "showExports": True})


def handle_rerun_tailoring(record: AiTaskRecord) -> tuple[Dict[str, Any], AiTaskRestoreTarget | None]:
    run_id = str(record.input.get("run_id") or "")
    if not run_id:
        raise ValueError("run_id is required")
    response = rerun_tailoring_job(run_id)
    return response.model_dump(), AiTaskRestoreTarget(path="/runs", state={"selectedRunId": response.run_id})


register_task_handler("score_job", handle_score_job)
register_task_handler("tailor_cv", handle_tailor_cv)
register_task_handler("render_cv", handle_render_cv)
register_task_handler("rerun_tailoring", handle_rerun_tailoring)
```

- [ ] **Step 4: Run handler tests**

Run:

```powershell
py -m unittest tests.test_ai_task_service -v
```

Expected: pass.

## Task 4: Gemini Interactions Wrapper

**Files:**

- Modify: `requirements.txt`
- Create: `api/app/services/gemini_interactions_service.py`
- Test: `tests/test_gemini_interactions_service.py`

- [ ] **Step 1: Add SDK dependency**

Append to `requirements.txt` if it is not already present:

```text
google-genai>=2.3.0
```

- [ ] **Step 2: Add wrapper tests**

Create `tests/test_gemini_interactions_service.py`:

```python
import unittest
from unittest.mock import MagicMock, patch

from api.app.services.gemini_interactions_service import GeminiInteractionRequest, create_text_interaction


class GeminiInteractionsServiceTest(unittest.TestCase):
    def test_private_default_uses_store_false(self):
        fake_interaction = MagicMock()
        fake_interaction.id = "interaction_1"
        fake_interaction.output_text = "hello"
        fake_interaction.model_dump.return_value = {"id": "interaction_1", "output_text": "hello"}
        fake_client = MagicMock()
        fake_client.interactions.create.return_value = fake_interaction

        with patch("api.app.services.gemini_interactions_service.genai.Client", return_value=fake_client):
            result = create_text_interaction(
                GeminiInteractionRequest(
                    input="hello",
                    model="gemini-2.5-flash",
                    system_instruction="Be concise.",
                )
            )

        fake_client.interactions.create.assert_called_once()
        kwargs = fake_client.interactions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gemini-2.5-flash")
        self.assertEqual(kwargs["input"], "hello")
        self.assertFalse(kwargs["store"])
        self.assertNotIn("background", kwargs)
        self.assertEqual(result["output_text"], "hello")

    def test_rejects_background_when_store_false(self):
        with self.assertRaises(ValueError):
            create_text_interaction(
                GeminiInteractionRequest(
                    input="private JD",
                    background=True,
                    store=False,
                )
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```powershell
py -m unittest tests.test_gemini_interactions_service -v
```

Expected: fail because the service file does not exist.

- [ ] **Step 4: Implement Gemini wrapper**

Create `api/app/services/gemini_interactions_service.py`:

```python
from __future__ import annotations

from typing import Any, Dict, Optional

from google import genai
from pydantic import BaseModel, Field

from api.app.config import settings


class GeminiInteractionRequest(BaseModel):
    input: str = Field(..., min_length=1)
    model: str = ""
    system_instruction: str = ""
    temperature: Optional[float] = None
    thinking_level: Optional[str] = None
    previous_interaction_id: Optional[str] = None
    store: bool = False
    background: bool = False


def _generation_config(request: GeminiInteractionRequest) -> Dict[str, Any] | None:
    config: Dict[str, Any] = {}
    if request.temperature is not None:
        config["temperature"] = request.temperature
    if request.thinking_level:
        config["thinking_level"] = request.thinking_level
    return config or None


def create_text_interaction(request: GeminiInteractionRequest) -> Dict[str, Any]:
    if request.background and not request.store:
        raise ValueError("Gemini background execution requires store=true; keep private ApplAI CV/JD tasks on the local queue.")

    client = genai.Client()
    kwargs: Dict[str, Any] = {
        "model": request.model.strip() or settings.gemini_default_model,
        "input": request.input,
        "store": request.store,
    }
    if request.system_instruction:
        kwargs["system_instruction"] = request.system_instruction
    if request.previous_interaction_id:
        kwargs["previous_interaction_id"] = request.previous_interaction_id
    if request.background:
        kwargs["background"] = True
    generation_config = _generation_config(request)
    if generation_config:
        kwargs["generation_config"] = generation_config

    interaction = client.interactions.create(**kwargs)
    if hasattr(interaction, "model_dump"):
        payload = interaction.model_dump()
    else:
        payload = {"id": getattr(interaction, "id", ""), "output_text": getattr(interaction, "output_text", "")}
    payload["output_text"] = getattr(interaction, "output_text", payload.get("output_text", ""))
    return payload
```

- [ ] **Step 5: Run wrapper tests**

Run:

```powershell
py -m unittest tests.test_gemini_interactions_service -v
```

Expected: pass.

## Task 5: AI Task API Routes

**Files:**

- Create: `api/app/routes/ai_tasks.py`
- Modify: `api/app/main.py`
- Modify: `web/src/lib/api-client.ts`
- Modify: `web/src/lib/types.ts`
- Test: `tests/test_ai_task_routes.py`

- [ ] **Step 1: Add route tests**

Create `tests/test_ai_task_routes.py`:

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app.main import app
from api.app.services import ai_task_service


class AiTaskRoutesTest(unittest.TestCase):
    def test_create_and_get_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_task_service, "tasks_dir", return_value=Path(tmp)):
                with patch.object(ai_task_service, "run_task", return_value=None):
                    client = TestClient(app)
                    created = client.post(
                        "/ai-tasks",
                        json={
                            "kind": "tailor_cv",
                            "title": "Tailor CV",
                            "related_label": "NRC",
                            "input": {"master_id": "master", "job_description": "JD"},
                        },
                    )

                    self.assertEqual(created.status_code, 201)
                    task_id = created.json()["task_id"]
                    fetched = client.get(f"/ai-tasks/{task_id}")
                    self.assertEqual(fetched.status_code, 200)
                    self.assertEqual(fetched.json()["kind"], "tailor_cv")

    def test_list_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_task_service, "tasks_dir", return_value=Path(tmp)):
                ai_task_service.create_task(kind="render_cv", title="Render CV", input={"run_id": "run_1"}, enqueue=False)
                client = TestClient(app)
                response = client.get("/ai-tasks")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["count"], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
py -m unittest tests.test_ai_task_routes -v
```

Expected: fail because `/ai-tasks` routes are not registered.

- [ ] **Step 3: Add route module**

Create `api/app/routes/ai_tasks.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from api.app.schemas.ai_tasks import AiTaskCreateRequest, AiTaskListResponse, AiTaskRecord
from api.app.services.ai_task_service import cancel_task, create_task, get_task, list_tasks

router = APIRouter(prefix="/ai-tasks", tags=["ai-tasks"])


@router.post("", response_model=AiTaskRecord, status_code=status.HTTP_201_CREATED)
def create_ai_task(payload: AiTaskCreateRequest) -> AiTaskRecord:
    return create_task(
        kind=payload.kind,
        title=payload.title,
        related_label=payload.related_label,
        input=payload.input,
    )


@router.get("", response_model=AiTaskListResponse)
def list_ai_tasks(limit: int = 50) -> AiTaskListResponse:
    tasks = list_tasks(limit=max(1, min(limit, 200)))
    return AiTaskListResponse(tasks=tasks, count=len(tasks))


@router.get("/{task_id}", response_model=AiTaskRecord)
def get_ai_task(task_id: str) -> AiTaskRecord:
    try:
        return get_task(task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{task_id}/cancel", response_model=AiTaskRecord)
def cancel_ai_task(task_id: str) -> AiTaskRecord:
    try:
        return cancel_task(task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
```

- [ ] **Step 4: Register router**

Modify `api/app/main.py` imports:

```python
from api.app.routes.ai_tasks import router as ai_tasks_router
```

Add include before `app.mount`:

```python
app.include_router(ai_tasks_router)
```

- [ ] **Step 5: Add TypeScript API types**

Add to `web/src/lib/types.ts`:

```ts
export type AiTaskKind =
  | "score_job"
  | "tailor_cv"
  | "render_cv"
  | "rerun_tailoring"
  | "gemini_interaction";

export type AiTaskStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface AiTaskRestoreTarget {
  path: string;
  state: Record<string, unknown>;
}

export interface AiTaskEvent {
  created_at: string;
  level: "info" | "warning" | "error";
  message: string;
}

export interface AiTaskRecord {
  task_id: string;
  kind: AiTaskKind;
  status: AiTaskStatus;
  title: string;
  related_label: string;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  input: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  error?: string | null;
  events: AiTaskEvent[];
  restore?: AiTaskRestoreTarget | null;
  approval_required_before_apply: boolean;
}

export interface AiTaskListResponse {
  tasks: AiTaskRecord[];
  count: number;
}
```

Modify `web/src/lib/api-client.ts` imports and client:

```ts
  AiTaskKind,
  AiTaskListResponse,
  AiTaskRecord,
```

Add methods:

```ts
  async createAiTask(payload: {
    kind: AiTaskKind;
    title: string;
    related_label?: string;
    input: Record<string, unknown>;
  }): Promise<AiTaskRecord> {
    return request<AiTaskRecord>("/ai-tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  async listAiTasks(): Promise<AiTaskListResponse> {
    return request<AiTaskListResponse>("/ai-tasks");
  },
  async getAiTask(taskId: string): Promise<AiTaskRecord> {
    return request<AiTaskRecord>(`/ai-tasks/${encodeURIComponent(taskId)}`);
  },
  async cancelAiTask(taskId: string): Promise<AiTaskRecord> {
    return request<AiTaskRecord>(`/ai-tasks/${encodeURIComponent(taskId)}/cancel`, {
      method: "POST",
    });
  },
```

- [ ] **Step 6: Run route and type checks**

Run:

```powershell
py -m unittest tests.test_ai_task_routes -v
npm.cmd run build
```

Expected: route tests pass; web build may fail until frontend queue files are added in later tasks. Record the exact failure if it is only missing imports from upcoming tasks.

## Task 6: Frontend Queue Context

**Files:**

- Create: `web/src/features/ai-tasks/AiTaskQueueContext.tsx`
- Create: `web/src/features/ai-tasks/ai-task-labels.ts`
- Modify: `web/src/app/App.tsx`

- [ ] **Step 1: Add labels helper**

Create `web/src/features/ai-tasks/ai-task-labels.ts`:

```ts
import type { AiTaskKind, AiTaskStatus } from "../../lib/types";

export function aiTaskKindLabel(kind: AiTaskKind): string {
  const labels: Record<AiTaskKind, string> = {
    score_job: "Score job",
    tailor_cv: "Tailor CV",
    render_cv: "Render CV",
    rerun_tailoring: "Rerun tailoring",
    gemini_interaction: "Gemini interaction",
  };
  return labels[kind];
}

export function aiTaskStatusLabel(status: AiTaskStatus): string {
  const labels: Record<AiTaskStatus, string> = {
    queued: "Queued",
    running: "Running",
    succeeded: "Done",
    failed: "Failed",
    cancelled: "Cancelled",
  };
  return labels[status];
}
```

- [ ] **Step 2: Add context**

Create `web/src/features/ai-tasks/AiTaskQueueContext.tsx`:

```tsx
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type PropsWithChildren } from "react";
import { apiClient } from "../../lib/api-client";
import type { AiTaskKind, AiTaskRecord } from "../../lib/types";

const MINIMIZED_KEY = "applaiAiTaskQueueMinimized";
const POLL_MS = 2500;

interface CreateAiTaskInput {
  kind: AiTaskKind;
  title: string;
  related_label?: string;
  input: Record<string, unknown>;
}

interface AiTaskQueueContextValue {
  tasks: AiTaskRecord[];
  isMinimized: boolean;
  isPolling: boolean;
  setMinimized: (value: boolean) => void;
  refreshTasks: () => Promise<void>;
  createTask: (payload: CreateAiTaskInput) => Promise<AiTaskRecord>;
  dismissLocalTask: (taskId: string) => void;
  cancelTask: (taskId: string) => Promise<void>;
  clearFinishedLocal: () => void;
}

const AiTaskQueueContext = createContext<AiTaskQueueContextValue | null>(null);

function hasActiveTasks(tasks: AiTaskRecord[]) {
  return tasks.some((task) => task.status === "queued" || task.status === "running");
}

export function AiTaskQueueProvider({ children }: PropsWithChildren) {
  const [tasks, setTasks] = useState<AiTaskRecord[]>([]);
  const [hiddenTaskIds, setHiddenTaskIds] = useState<Set<string>>(() => new Set());
  const [isPolling, setIsPolling] = useState(false);
  const pollRef = useRef<number | null>(null);
  const [isMinimized, setMinimizedState] = useState(() => {
    try {
      return localStorage.getItem(MINIMIZED_KEY) === "true";
    } catch {
      return false;
    }
  });

  const visibleTasks = useMemo(
    () => tasks.filter((task) => !hiddenTaskIds.has(task.task_id)),
    [tasks, hiddenTaskIds],
  );

  const refreshTasks = useCallback(async () => {
    setIsPolling(true);
    try {
      const response = await apiClient.listAiTasks();
      setTasks(response.tasks);
    } finally {
      setIsPolling(false);
    }
  }, []);

  useEffect(() => {
    void refreshTasks();
  }, [refreshTasks]);

  useEffect(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (!hasActiveTasks(tasks)) return;
    pollRef.current = window.setInterval(() => {
      void refreshTasks();
    }, POLL_MS);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [tasks, refreshTasks]);

  const setMinimized = useCallback((value: boolean) => {
    setMinimizedState(value);
    try {
      localStorage.setItem(MINIMIZED_KEY, String(value));
    } catch {
      // localStorage is optional.
    }
  }, []);

  const createTask = useCallback(
    async (payload: CreateAiTaskInput) => {
      const task = await apiClient.createAiTask(payload);
      setHiddenTaskIds((prev) => {
        const next = new Set(prev);
        next.delete(task.task_id);
        return next;
      });
      await refreshTasks();
      return task;
    },
    [refreshTasks],
  );

  const dismissLocalTask = useCallback((taskId: string) => {
    setHiddenTaskIds((prev) => new Set(prev).add(taskId));
  }, []);

  const clearFinishedLocal = useCallback(() => {
    setHiddenTaskIds((prev) => {
      const next = new Set(prev);
      for (const task of tasks) {
        if (task.status === "succeeded" || task.status === "failed" || task.status === "cancelled") {
          next.add(task.task_id);
        }
      }
      return next;
    });
  }, [tasks]);

  const cancelTask = useCallback(
    async (taskId: string) => {
      await apiClient.cancelAiTask(taskId);
      await refreshTasks();
    },
    [refreshTasks],
  );

  const value = useMemo(
    () => ({
      tasks: visibleTasks,
      isMinimized,
      isPolling,
      setMinimized,
      refreshTasks,
      createTask,
      dismissLocalTask,
      cancelTask,
      clearFinishedLocal,
    }),
    [visibleTasks, isMinimized, isPolling, setMinimized, refreshTasks, createTask, dismissLocalTask, cancelTask, clearFinishedLocal],
  );

  return <AiTaskQueueContext.Provider value={value}>{children}</AiTaskQueueContext.Provider>;
}

export function useAiTaskQueue(): AiTaskQueueContextValue {
  const ctx = useContext(AiTaskQueueContext);
  if (!ctx) {
    throw new Error("useAiTaskQueue must be used within AiTaskQueueProvider");
  }
  return ctx;
}
```

- [ ] **Step 3: Wrap app**

Modify `web/src/app/App.tsx`:

```tsx
import { AiTaskQueueProvider } from "../features/ai-tasks/AiTaskQueueContext";
```

Wrap routes:

```tsx
export function App() {
  return (
    <AiTaskQueueProvider>
      <AppLayout>
        <Routes>
          <Route path="/" element={<Navigate to="/masters" replace />} />
          <Route path="/masters" element={<MastersPage />} />
          <Route path="/masters/:masterId" element={<MasterEditorPage />} />
          <Route path="/tailoring" element={<TailoringPage />} />
          <Route path="/runs" element={<RunsPage />} />
        </Routes>
      </AppLayout>
    </AiTaskQueueProvider>
  );
}
```

- [ ] **Step 4: Run typecheck/build**

Run:

```powershell
cd web
npm.cmd run build
```

Expected: build passes unless the panel import from the next task has already been added.

## Task 7: Arpa-Style Queue Panel

**Files:**

- Create: `web/src/features/ai-tasks/AiTaskQueuePanel.tsx`
- Create: `web/src/features/ai-tasks/ai-task-restore.ts`
- Modify: `web/src/components/AppLayout.tsx`
- Modify: `web/src/styles.css`

- [ ] **Step 1: Add restore helper**

Create `web/src/features/ai-tasks/ai-task-restore.ts`:

```ts
import type { AiTaskRecord } from "../../lib/types";

export function canOpenAiTask(task: AiTaskRecord): boolean {
  return task.status === "succeeded" && Boolean(task.restore?.path);
}
```

- [ ] **Step 2: Add panel component**

Create `web/src/features/ai-tasks/AiTaskQueuePanel.tsx`:

```tsx
import { useNavigate } from "react-router-dom";
import { canOpenAiTask } from "./ai-task-restore";
import { aiTaskStatusLabel } from "./ai-task-labels";
import { useAiTaskQueue } from "./AiTaskQueueContext";

function statusClass(status: string) {
  if (status === "succeeded") return "aiTaskIcon aiTaskIcon--done";
  if (status === "failed" || status === "cancelled") return "aiTaskIcon aiTaskIcon--error";
  return "aiTaskIcon aiTaskIcon--running";
}

export function AiTaskQueuePanel() {
  const navigate = useNavigate();
  const { tasks, isMinimized, setMinimized, dismissLocalTask, clearFinishedLocal, cancelTask } = useAiTaskQueue();

  if (tasks.length === 0) return null;

  const activeCount = tasks.filter((task) => task.status === "queued" || task.status === "running").length;
  const hasFinished = tasks.some((task) => task.status === "succeeded" || task.status === "failed" || task.status === "cancelled");

  function openTask(taskId: string) {
    const task = tasks.find((item) => item.task_id === taskId);
    if (!task || !canOpenAiTask(task) || !task.restore) return;
    navigate(task.restore.path, { state: task.restore.state });
    dismissLocalTask(task.task_id);
  }

  if (isMinimized) {
    return (
      <div className="aiTaskQueueDock">
        <button
          type="button"
          className="aiTaskQueuePill"
          onClick={() => setMinimized(false)}
          aria-label={`AI queue: ${activeCount} active, ${tasks.length} total. Expand queue.`}
        >
          <span className="aiTaskSpark">AI</span>
          <span>Q</span>
          <strong>{activeCount > 0 ? activeCount : tasks.length}</strong>
          <span aria-hidden="true">v</span>
        </button>
      </div>
    );
  }

  return (
    <div className="aiTaskQueueDock">
      <section className="aiTaskQueuePanel" aria-label="AI task queue">
        <header className="aiTaskQueueHeader">
          <div className="row">
            <span className="aiTaskSpark">AI</span>
            <strong>Q</strong>
            {activeCount > 0 ? <span className="pill">{activeCount} active</span> : null}
          </div>
          <div className="row">
            {hasFinished ? (
              <button type="button" className="linkButton" onClick={clearFinishedLocal}>
                Clear done
              </button>
            ) : null}
            <button type="button" className="linkButton" onClick={() => setMinimized(true)} aria-label="Minimize AI queue">
              ^
            </button>
          </div>
        </header>

        <ul className="aiTaskQueueList">
          {tasks.map((task) => {
            const openable = canOpenAiTask(task);
            const body = (
              <>
                <span className={statusClass(task.status)} aria-hidden="true" />
                <span className="aiTaskQueueBody">
                  <strong>{task.title}</strong>
                  {task.related_label ? <small>{task.related_label}</small> : null}
                  <small>{aiTaskStatusLabel(task.status)}</small>
                  {openable ? <small className="aiTaskOpenHint">Click to open result</small> : null}
                  {task.error ? <small className="error">{task.error}</small> : null}
                  {task.status === "running" || task.status === "queued" ? <span className="aiTaskProgress"><span /></span> : null}
                </span>
              </>
            );

            return (
              <li key={task.task_id} className="aiTaskQueueItem">
                {openable ? (
                  <button type="button" className="aiTaskQueueRow" onClick={() => openTask(task.task_id)}>
                    {body}
                  </button>
                ) : (
                  <div className="aiTaskQueueRow">{body}</div>
                )}
                {task.status === "queued" ? (
                  <button type="button" className="aiTaskDismiss" onClick={() => void cancelTask(task.task_id)} aria-label="Cancel queued task">
                    x
                  </button>
                ) : (
                  <button type="button" className="aiTaskDismiss" onClick={() => dismissLocalTask(task.task_id)} aria-label="Dismiss task">
                    x
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Render panel in layout**

Modify `web/src/components/AppLayout.tsx`:

```tsx
import { AiTaskQueuePanel } from "../features/ai-tasks/AiTaskQueuePanel";
```

Render inside `<main className="page">` before `{children}`:

```tsx
      <main className="page">
        <AiTaskQueuePanel />
        {children}
      </main>
```

- [ ] **Step 4: Add styles**

Append to `web/src/styles.css`:

```css
.aiTaskQueueDock {
  position: sticky;
  top: 0.75rem;
  z-index: 40;
  display: flex;
  justify-content: flex-end;
  margin-bottom: 0.75rem;
  pointer-events: none;
}

.aiTaskQueuePill,
.aiTaskQueuePanel {
  pointer-events: auto;
  border: 1px solid #344154;
  background: rgba(18, 24, 32, 0.96);
  color: #e6e9ef;
  box-shadow: 0 14px 36px rgba(0, 0, 0, 0.32);
  backdrop-filter: blur(14px);
}

.aiTaskQueuePill {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  border-radius: 999px;
  padding: 0.45rem 0.75rem;
}

.aiTaskQueuePanel {
  width: min(24rem, 100%);
  overflow: hidden;
  border-radius: 12px;
}

.aiTaskQueueHeader,
.aiTaskQueueRow {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}

.aiTaskQueueHeader {
  justify-content: space-between;
  padding: 0.75rem 0.85rem;
  border-bottom: 1px solid #263040;
}

.aiTaskSpark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.65rem;
  height: 1.65rem;
  border-radius: 999px;
  background: #213e67;
  color: #a9d0ff;
  font-size: 0.72rem;
  font-weight: 700;
}

.aiTaskQueueList {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: min(50vh, 22rem);
  overflow-y: auto;
}

.aiTaskQueueItem {
  position: relative;
  border-top: 1px solid #263040;
}

.aiTaskQueueItem:first-child {
  border-top: 0;
}

.aiTaskQueueRow {
  width: 100%;
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 0.75rem 2.4rem 0.75rem 0.85rem;
  text-align: left;
}

button.aiTaskQueueRow:hover {
  background: #182130;
}

.aiTaskQueueBody {
  display: grid;
  gap: 0.12rem;
  min-width: 0;
}

.aiTaskQueueBody small {
  color: #8ea0b8;
}

.aiTaskOpenHint {
  color: #8ab4ff !important;
  font-weight: 600;
}

.aiTaskDismiss {
  position: absolute;
  top: 0.55rem;
  right: 0.55rem;
  width: 1.7rem;
  height: 1.7rem;
  padding: 0;
  border-radius: 999px;
}

.aiTaskIcon {
  position: relative;
  width: 1.75rem;
  height: 1.75rem;
  flex: 0 0 1.75rem;
  border-radius: 999px;
  border: 2px solid #415a7a;
}

.aiTaskIcon--running::after {
  content: "";
  position: absolute;
  inset: -2px;
  border-radius: inherit;
  border: 2px solid transparent;
  border-top-color: #8ab4ff;
  animation: aiTaskSpin 0.9s linear infinite;
}

.aiTaskIcon--done {
  border-color: #5bd4a8;
  background: #14382d;
}

.aiTaskIcon--error {
  border-color: #ff9f9f;
  background: #3b1f27;
}

.aiTaskProgress {
  display: block;
  width: 100%;
  height: 0.25rem;
  overflow: hidden;
  border-radius: 999px;
  background: #263040;
}

.aiTaskProgress span {
  display: block;
  width: 38%;
  height: 100%;
  border-radius: inherit;
  background: #8ab4ff;
  animation: aiTaskSlide 1.1s ease-in-out infinite;
}

@keyframes aiTaskSpin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes aiTaskSlide {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(280%);
  }
}
```

- [ ] **Step 5: Run web build**

Run:

```powershell
cd web
npm.cmd run build
```

Expected: pass.

## Task 8: Wire Tailoring And Runs To The Queue

**Files:**

- Create: `web/src/features/ai-tasks/useAiTaskSubmit.ts`
- Modify: `web/src/pages/TailoringPage.tsx`
- Modify: `web/src/pages/RunsPage.tsx`

- [ ] **Step 1: Add submit helper**

Create `web/src/features/ai-tasks/useAiTaskSubmit.ts`:

```ts
import { useAiTaskQueue } from "./AiTaskQueueContext";
import type { TailorRunOptions } from "../../lib/types";

export function useAiTaskSubmit() {
  const { createTask } = useAiTaskQueue();

  return {
    queueTailoring(input: { master_id: string; job_description?: string; job_id?: string; options: TailorRunOptions }) {
      const related = [input.options.company_name, input.options.job_title].filter(Boolean).join(" - ");
      return createTask({
        kind: "tailor_cv",
        title: "Tailor CV",
        related_label: related || input.master_id,
        input: input as unknown as Record<string, unknown>,
      });
    },
    queueRender(run_id: string, related_label = "") {
      return createTask({
        kind: "render_cv",
        title: "Render CV",
        related_label,
        input: { run_id },
      });
    },
    queueRerun(run_id: string, related_label = "") {
      return createTask({
        kind: "rerun_tailoring",
        title: "Rerun tailoring",
        related_label,
        input: { run_id },
      });
    },
  };
}
```

- [ ] **Step 2: Queue TailoringPage run/export actions**

Modify `web/src/pages/TailoringPage.tsx`:

```tsx
import { useAiTaskSubmit } from "../features/ai-tasks/useAiTaskSubmit";
```

Inside component:

```tsx
const { queueTailoring, queueRender } = useAiTaskSubmit();
```

Replace the body of `handleRun` with:

```tsx
async function handleRun() {
  setError("");
  setBusy(true);
  try {
    const task = await queueTailoring({
      master_id: masterId,
      job_description: jobDescription,
      options,
    });
    setRunResult(null);
    setError(`Queued ${task.title}. Open the Q panel for progress.`);
  } catch (err) {
    setError((err as Error).message);
  } finally {
    setBusy(false);
  }
}
```

Replace export handler so completed existing run exports through Q:

```tsx
async function handleExport() {
  if (!runResult) return;
  setError("");
  setBusy(true);
  try {
    const task = await queueRender(runResult.run_id, options.job_title || runResult.run_id);
    setError(`Queued ${task.title}.`);
  } catch (err) {
    setError((err as Error).message);
  } finally {
    setBusy(false);
  }
}
```

- [ ] **Step 3: Queue RunsPage rerun/export actions**

Modify `web/src/pages/RunsPage.tsx`:

```tsx
import { useAiTaskSubmit } from "../features/ai-tasks/useAiTaskSubmit";
```

Inside component:

```tsx
const { queueRender, queueRerun } = useAiTaskSubmit();
```

Change export action:

```tsx
async function exportSelected() {
  if (!selected) return;
  setError("");
  setBusy(true);
  try {
    const label = selected.options.job_title || selected.options.company_name || selected.run_id;
    await queueRender(selected.run_id, label);
  } catch (err) {
    setError((err as Error).message);
  } finally {
    setBusy(false);
  }
}
```

Change rerun action:

```tsx
async function rerunSelected() {
  if (!selected) return;
  setError("");
  setBusy(true);
  try {
    const label = selected.options.job_title || selected.options.company_name || selected.run_id;
    await queueRerun(selected.run_id, label);
  } catch (err) {
    setError((err as Error).message);
  } finally {
    setBusy(false);
  }
}
```

- [ ] **Step 4: Run web build**

Run:

```powershell
cd web
npm.cmd run build
```

Expected: pass.

## Task 9: Runs Page Restore State

**Files:**

- Modify: `web/src/pages/RunsPage.tsx`
- Test manually through browser after local servers are running.

- [ ] **Step 1: Read location state in RunsPage**

Add import:

```tsx
import { useLocation } from "react-router-dom";
```

Add helper type:

```ts
type RunsLocationState = {
  selectedRunId?: string;
  showExports?: boolean;
};
```

Inside component:

```tsx
const location = useLocation();
```

After runs load, select the restored run:

```tsx
useEffect(() => {
  const state = location.state as RunsLocationState | null;
  if (!state?.selectedRunId) return;
  void selectRun(state.selectedRunId);
}, [location.state]);
```

- [ ] **Step 2: Confirm no infinite loop**

Run:

```powershell
cd web
npm.cmd run build
```

Expected: TypeScript passes. If dependency warnings appear, they must not hide TypeScript errors.

## Task 10: Verification And Handoff

**Files:**

- Modify: `TODO.md`
- Optional create: `docs/superpowers/plans/2026-06-23-ai-task-queue-and-gemini-interactions-results.md` only if implementation notes are lengthy.

- [ ] **Step 1: Run backend focused tests**

Run:

```powershell
py -m unittest tests.test_ai_task_service tests.test_ai_task_routes tests.test_gemini_interactions_service -v
```

Expected: pass.

- [ ] **Step 2: Run existing Sprint 3 focused tests**

Run:

```powershell
py -m unittest tests.test_tailoring_service tests.test_resume_layout_service tests.test_html_resume_renderer -v
```

Expected: pass. If this fails because of existing dirty worktree changes unrelated to queue files, stop and report exact failures before editing user-owned files.

- [ ] **Step 3: Run FastAPI import smoke**

Run:

```powershell
py -c "import api.app.main; print(api.app.main.app.title)"
```

Expected output:

```text
ApplAI API
```

- [ ] **Step 4: Run web build**

Run:

```powershell
cd web
npm.cmd run build
```

Expected: pass.

- [ ] **Step 5: Run Eve checks**

Run:

```powershell
cd eve
npm.cmd test
npm.cmd run typecheck
```

Expected: pass. Node version warnings for Eve `0.11.4` are acceptable if the same warning is already present and typecheck passes.

- [ ] **Step 6: Run diff whitespace check**

Run:

```powershell
git diff --check
```

Expected: no output.

- [ ] **Step 7: Manual local smoke**

Start API:

```powershell
py -m uvicorn api.app.main:app --reload
```

Start web:

```powershell
cd web
npm.cmd run dev
```

Manual checks:

- Open `http://127.0.0.1:5173/tailoring`.
- Queue a tailoring task with a small test JD.
- Confirm Q panel appears with one active task.
- Confirm task transitions to done or failed without blocking the page.
- Click the completed task and confirm `/runs` opens.
- Queue render/export from a run and confirm clicking completed task reopens the run detail.
- Refresh browser and confirm recent tasks reload from `/ai-tasks`.

- [ ] **Step 8: Update TODO.md status**

Add under Sprint 3 continuation notes or Sprint 3.2:

```markdown
- [x] AI task queue plan implemented: Core persists AI tasks under `docs/ai_tasks/`, React shows an Arpa-style Q panel, and tailoring/render/rerun tasks run in the background.
- [x] Gemini Interactions API wrapper added with private-by-default `store=false`; local queue remains the background execution layer for private CV/JD data.
```

## Self-Review

Spec coverage:

- Gemini Interactions API is included through a private-by-default Core wrapper.
- AI-related task backgrounding is implemented through a durable local queue.
- A visible Q system is implemented in React and based on the Arpa Meal Planner UX.
- Existing ApplAI source-of-truth boundaries are preserved: Eve remains thin, Core owns domain logic, approval remains required before ready-to-submit.

Risk controls:

- Existing synchronous endpoints remain for compatibility.
- The first queue only handles Core-local tasks; no external submit/send/publish actions are introduced.
- Private CV/JD content is not sent to Gemini background storage by default.
- Task records store inputs under `docs/ai_tasks/`, which must be treated as private local generated data.

Implementation order:

- Backend contracts first.
- Durable queue second.
- Gemini wrapper third.
- Routes fourth.
- Frontend Q fifth.
- Page integrations last.

Open execution note:

- The current ApplAI worktree already has many modified files unrelated to this plan. Implementation agents must run `git status --short` before editing and avoid reverting user-owned changes.
