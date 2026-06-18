from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from api.app.adapters.workflow_adapter import run_tailoring
from api.app.config import settings
from api.app.schemas.tailoring import RunDetailResponse, RunSummary, TailorRunRequest, TailorRunResponse, TailoringResultPayload
from api.app.services.master_service import get_master


def ensure_runs_dir() -> None:
    Path(settings.runs_dir).mkdir(parents=True, exist_ok=True)


def _run_path(run_id: str) -> Path:
    return Path(settings.runs_dir) / f"{run_id}.json"


def _to_result_payload(result) -> TailoringResultPayload:
    return TailoringResultPayload.model_validate(
        {
            "canonical_cv": result.canonical_cv.model_dump(),
            "jd_analysis": result.jd_analysis.model_dump(),
            "tailored_output": result.tailored_output.model_dump(),
            "change_log": result.change_log.model_dump(),
            "qa_report": result.qa_report.model_dump(),
            "ats_report": result.ats_report.model_dump(),
            "cover_letter": result.cover_letter or "",
        }
    )


def _to_response(record: Dict[str, Any]) -> RunDetailResponse:
    return RunDetailResponse(
        run_id=record["run_id"],
        master_id=record["master_id"],
        created_at=record["created_at"],
        options=record["options"],
        result=record["result"],
        exports=record.get("exports"),
    )


def run_tailoring_job(payload: TailorRunRequest) -> TailorRunResponse:
    ensure_runs_dir()
    master = get_master(payload.master_id)
    base_cv_json_text = json.dumps(master.payload)
    result = run_tailoring(payload.job_description, base_cv_json_text, payload.options)
    run_id = uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()

    source_docx = master.summary.source_docx
    source_file = master.summary.source_file
    template_path = ""
    if source_docx:
        template_path = os.path.join(settings.docs_dir, source_docx)
    elif source_file.endswith(".pdf"):
        template_path = os.path.join(settings.docs_dir, source_file.replace(".pdf", ".docx"))

    result_payload = _to_result_payload(result)
    record = {
        "run_id": run_id,
        "master_id": master.summary.master_id,
        "created_at": created_at,
        "options": payload.options.model_dump(),
        "job_description": payload.job_description,
        "workflow_inputs": {
            "job_desc": payload.job_description,
            "base_cv_json_text": base_cv_json_text,
            "company_name": payload.options.company_name,
            "job_title": payload.options.job_title,
            "selected_cv_json": f"{master.summary.master_id}.json",
            "selected_model": payload.options.model_name,
            "quick_mode": payload.options.quick_mode,
            "include_cover_letter": payload.options.include_cover_letter,
            "include_ats": payload.options.include_ats,
            "include_qa": payload.options.include_qa,
            "allow_experience_rewrites": payload.options.allow_experience_rewrites,
            "allow_education_rewrites": payload.options.allow_education_rewrites,
            "max_pages": payload.options.max_pages,
            "template_path": template_path,
            "template_config_path": master.summary.template_config_path,
        },
        "result": result_payload.model_dump(),
    }
    _run_path(run_id).write_text(json.dumps(record, indent=2), encoding="utf-8")

    return TailorRunResponse(
        run_id=run_id,
        master_id=record["master_id"],
        created_at=created_at,
        options=payload.options,
        result=result_payload,
    )


def list_runs() -> List[RunSummary]:
    ensure_runs_dir()
    summaries: List[RunSummary] = []
    for path in sorted(Path(settings.runs_dir).glob("*.json"), reverse=True):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        options = record.get("options", {})
        summaries.append(
            RunSummary(
                run_id=record.get("run_id", path.stem),
                master_id=record.get("master_id", ""),
                created_at=record.get("created_at", ""),
                model_name=options.get("model_name", settings.default_model),
                company_name=options.get("company_name", ""),
                job_title=options.get("job_title", ""),
            )
        )
    return summaries


def get_run(run_id: str) -> RunDetailResponse:
    path = _run_path(run_id)
    if not path.exists():
        raise FileNotFoundError(f"Run '{run_id}' was not found")
    record = json.loads(path.read_text(encoding="utf-8"))
    return _to_response(record)


def update_run_exports(run_id: str, exports: Dict[str, Any]) -> None:
    path = _run_path(run_id)
    if not path.exists():
        raise FileNotFoundError(f"Run '{run_id}' was not found")
    record = json.loads(path.read_text(encoding="utf-8"))
    record["exports"] = exports
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")


def get_run_record(run_id: str) -> Dict[str, Any]:
    path = _run_path(run_id)
    if not path.exists():
        raise FileNotFoundError(f"Run '{run_id}' was not found")
    return json.loads(path.read_text(encoding="utf-8"))
