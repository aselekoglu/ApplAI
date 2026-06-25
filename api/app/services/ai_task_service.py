from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, List
from uuid import uuid4

from api.app.config import settings
from api.app.schemas.ai_tasks import (
    AiTaskEvent,
    AiTaskKind,
    AiTaskRecord,
    AiTaskRestoreTarget,
    AiTaskStatus,
    utc_now,
)
from api.app.schemas.jobs import ScoreJobRequest
from api.app.schemas.tailoring import ExportRequest, TailorRunOptions, TailorRunRequest
from api.app.services.export_service import export_run
from api.app.services.gemini_interactions_service import GeminiInteractionRequest, create_text_interaction
from api.app.services.job_scoring_service import score_job
from api.app.services.tailoring_service import rerun_tailoring_job, run_tailoring_job


TaskHandler = Callable[[AiTaskRecord], tuple[Dict[str, Any], AiTaskRestoreTarget | None]]

_executor = ThreadPoolExecutor(max_workers=max(1, settings.ai_task_max_workers))
_lock = Lock()
_handlers: Dict[str, TaskHandler] = {}


def tasks_dir() -> Path:
    return Path(settings.ai_tasks_dir)


def ensure_tasks_dir() -> Path:
    directory = tasks_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _safe_task_id(task_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", task_id).strip("._-")
    if not safe:
        raise ValueError("task_id must contain at least one safe filename character")
    return safe


def task_path(task_id: str) -> Path:
    return tasks_dir() / f"{_safe_task_id(task_id)}.json"


def save_task(record: AiTaskRecord) -> str:
    path = task_path(record.task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.stem}.{os.getpid()}.{uuid4().hex}.tmp")
    tmp_path.write_text(json.dumps(record.model_dump(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return str(path)


def get_task(task_id: str) -> AiTaskRecord:
    path = task_path(task_id)
    if not path.exists():
        raise ValueError(f"AI task not found: {task_id}")
    return AiTaskRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))


def list_tasks(limit: int = 50) -> List[AiTaskRecord]:
    directory = tasks_dir()
    if not directory.exists():
        return []

    records: List[AiTaskRecord] = []
    for path in sorted(directory.glob("*.json")):
        try:
            records.append(AiTaskRecord.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    records.sort(key=lambda record: record.updated_at, reverse=True)
    return records[:limit]


def register_task_handler(kind: str, handler: TaskHandler) -> None:
    with _lock:
        _handlers[kind] = handler


def handle_score_job(record: AiTaskRecord) -> tuple[Dict[str, Any], AiTaskRestoreTarget]:
    payload = ScoreJobRequest.model_validate(record.input).model_copy(update={"save_draft": True})
    response = score_job(payload)
    return response.model_dump(), AiTaskRestoreTarget(
        path="/tailoring",
        state={"jobId": response.job_id},
    )


def handle_tailor_cv(record: AiTaskRecord) -> tuple[Dict[str, Any], AiTaskRestoreTarget]:
    payload = dict(record.input)
    options = TailorRunOptions.model_validate(payload.get("options") or {})
    request = TailorRunRequest(
        master_id=payload.get("master_id", ""),
        job_description=payload.get("job_description"),
        job_id=payload.get("job_id"),
        options=options,
    )
    response = run_tailoring_job(request)
    return response.model_dump(), AiTaskRestoreTarget(
        path="/runs",
        state={"selectedRunId": response.run_id},
    )


def handle_render_cv(record: AiTaskRecord) -> tuple[Dict[str, Any], AiTaskRestoreTarget]:
    payload = ExportRequest.model_validate(record.input)
    response = export_run(payload.run_id)
    result = response.model_dump()
    return result, AiTaskRestoreTarget(
        path="/runs",
        state={"selectedRunId": result.get("run_id", payload.run_id), "showExports": True},
    )


def handle_rerun_tailoring(record: AiTaskRecord) -> tuple[Dict[str, Any], AiTaskRestoreTarget]:
    run_id = record.input.get("run_id")
    if not run_id:
        raise ValueError("run_id is required")
    response = rerun_tailoring_job(str(run_id))
    return response.model_dump(), AiTaskRestoreTarget(
        path="/runs",
        state={"selectedRunId": response.run_id},
    )


def handle_gemini_interaction(record: AiTaskRecord) -> tuple[Dict[str, Any], None]:
    request = GeminiInteractionRequest.model_validate(record.input)
    result = create_text_interaction(request)
    return result, None


register_task_handler("score_job", handle_score_job)
register_task_handler("tailor_cv", handle_tailor_cv)
register_task_handler("render_cv", handle_render_cv)
register_task_handler("rerun_tailoring", handle_rerun_tailoring)
register_task_handler("gemini_interaction", handle_gemini_interaction)


def _append_event(record: AiTaskRecord, message: str, level: str = "info") -> AiTaskRecord:
    events = list(record.events)
    events.append(AiTaskEvent(message=message, level=level))
    return record.model_copy(update={"events": events, "updated_at": utc_now()})


def update_task_status(task_id: str, status: AiTaskStatus, message: str | None = None) -> AiTaskRecord:
    with _lock:
        record = get_task(task_id)
        now = utc_now()
        updates: Dict[str, Any] = {"status": status, "updated_at": now}
        if status == "running" and record.started_at is None:
            updates["started_at"] = now
        if status in {"succeeded", "failed", "cancelled"}:
            updates["finished_at"] = now
        updated = record.model_copy(update=updates)
        if message:
            updated = _append_event(updated, message, "error" if status == "failed" else "info")
        save_task(updated)
        return updated


def _claim_queued_task(task_id: str) -> AiTaskRecord:
    with _lock:
        record = get_task(task_id)
        if record.status == "cancelled":
            return record
        if record.status != "queued":
            return record

        now = utc_now()
        updated = record.model_copy(
            update={
                "status": "running",
                "updated_at": now,
                "started_at": record.started_at or now,
            }
        )
        updated = _append_event(updated, "Task started.")
        save_task(updated)
        return updated


def mark_task_succeeded(
    task_id: str,
    *,
    result: Dict[str, Any],
    restore_path: str | None = None,
    restore_state: Dict[str, Any] | None = None,
) -> AiTaskRecord:
    with _lock:
        record = get_task(task_id)
        now = utc_now()
        restore = None
        if restore_path:
            restore = AiTaskRestoreTarget(path=restore_path, state=restore_state or {})
        updated = record.model_copy(
            update={
                "status": "succeeded",
                "updated_at": now,
                "finished_at": now,
                "result": result,
                "error": None,
                "restore": restore,
            }
        )
        updated = _append_event(updated, "Task succeeded.")
        save_task(updated)
        return updated


def mark_task_failed(task_id: str, error: str) -> AiTaskRecord:
    with _lock:
        record = get_task(task_id)
        now = utc_now()
        updated = record.model_copy(
            update={
                "status": "failed",
                "updated_at": now,
                "finished_at": now,
                "error": error,
            }
        )
        updated = _append_event(updated, f"Task failed: {error}", "error")
        save_task(updated)
        return updated


def cancel_task(task_id: str) -> AiTaskRecord:
    with _lock:
        record = get_task(task_id)
        if record.status != "queued":
            raise ValueError("Only queued tasks can be cancelled")
        now = utc_now()
        updated = record.model_copy(
            update={
                "status": "cancelled",
                "updated_at": now,
                "finished_at": now,
            }
        )
        updated = _append_event(updated, "Cancelled before start.")
        save_task(updated)
        return updated


def create_task(
    *,
    kind: AiTaskKind,
    title: str,
    related_label: str = "",
    input: Dict[str, Any] | None = None,
    enqueue: bool = True,
) -> AiTaskRecord:
    if enqueue and kind not in _handlers:
        raise ValueError(f"No AI task handler registered for kind: {kind}")

    record = AiTaskRecord.new(kind=kind, title=title, related_label=related_label, input=input or {})
    with _lock:
        save_task(record)
    if enqueue:
        _executor.submit(run_task, record.task_id)
    return record


def run_task(task_id: str) -> AiTaskRecord:
    try:
        current = get_task(task_id)
    except Exception as exc:
        raise ValueError(f"Unable to load AI task {task_id}: {exc}") from exc

    if current.status == "cancelled":
        return current
    if current.status != "queued":
        return current

    claimed = _claim_queued_task(task_id)
    if claimed.status == "cancelled":
        return claimed
    if claimed.status != "running":
        return claimed

    handler = _handlers.get(claimed.kind)
    if handler is None:
        return mark_task_failed(task_id, f"No AI task handler registered for kind: {claimed.kind}")

    try:
        result, restore = handler(claimed)
        if restore is None:
            return mark_task_succeeded(task_id, result=result)
        return mark_task_succeeded(
            task_id,
            result=result,
            restore_path=restore.path,
            restore_state=restore.state,
        )
    except Exception as exc:
        return mark_task_failed(task_id, str(exc))
