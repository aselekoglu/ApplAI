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
    def new(
        cls,
        *,
        kind: AiTaskKind,
        title: str,
        related_label: str = "",
        input: Dict[str, Any] | None = None,
    ) -> "AiTaskRecord":
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
