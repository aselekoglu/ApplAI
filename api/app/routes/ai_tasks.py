from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from api.app.schemas.ai_tasks import AiTaskCreateRequest, AiTaskListResponse, AiTaskRecord
from api.app.services import ai_task_service

router = APIRouter(prefix="/ai-tasks", tags=["ai-tasks"])


def _is_missing_task_error(exc: ValueError) -> bool:
    return str(exc).startswith("AI task not found:")


@router.post("", response_model=AiTaskRecord, status_code=status.HTTP_201_CREATED)
def create_ai_task(payload: AiTaskCreateRequest) -> AiTaskRecord:
    return ai_task_service.create_task(
        kind=payload.kind,
        title=payload.title,
        related_label=payload.related_label,
        input=payload.input,
    )


@router.get("", response_model=AiTaskListResponse)
def list_ai_tasks(limit: int = 50) -> AiTaskListResponse:
    clamped_limit = max(1, min(limit, 200))
    tasks = ai_task_service.list_tasks(limit=clamped_limit)
    return AiTaskListResponse(tasks=tasks, count=len(tasks))


@router.get("/{task_id}", response_model=AiTaskRecord)
def read_ai_task(task_id: str) -> AiTaskRecord:
    try:
        return ai_task_service.get_task(task_id)
    except ValueError as exc:
        if _is_missing_task_error(exc):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise


@router.post("/{task_id}/cancel", response_model=AiTaskRecord)
def cancel_ai_task(task_id: str) -> AiTaskRecord:
    try:
        return ai_task_service.cancel_task(task_id)
    except ValueError as exc:
        if _is_missing_task_error(exc):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise
