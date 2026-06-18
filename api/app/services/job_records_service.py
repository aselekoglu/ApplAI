from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from api.app.config import settings
from api.app.schemas.jobs import JobRecord


def jobs_dir() -> Path:
    return Path(settings.jobs_dir)


def _safe_job_id(job_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", job_id).strip("._-")
    if not safe:
        raise ValueError("job_id must contain at least one safe filename character")
    return safe


def job_record_path(job_id: str) -> Path:
    return jobs_dir() / f"{_safe_job_id(job_id)}.json"


def save_job_record(record: JobRecord) -> str:
    path = job_record_path(record.job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(record.model_dump(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return str(path)


def load_job_record(job_id: str) -> JobRecord:
    path = job_record_path(job_id)
    if not path.exists():
        raise ValueError(f"Job record not found: {job_id}")
    return JobRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))


def list_job_records() -> List[JobRecord]:
    directory = jobs_dir()
    if not directory.exists():
        return []

    records: List[JobRecord] = []
    for path in sorted(directory.glob("*.json")):
        try:
            records.append(JobRecord.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    records.sort(key=lambda record: record.updated_at, reverse=True)
    return records
