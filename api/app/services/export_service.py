from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import agent_workflow

from api.app.adapters.renderer_adapter import render_run_artifacts
from api.app.schemas.tailoring import ArtifactMetadata, ExportResponse
from api.app.services.tailoring_service import get_run_record, update_run_record


def _rehydrate_result(result_payload: Dict[str, Any]) -> agent_workflow.WorkflowResult:
    return agent_workflow.WorkflowResult(
        canonical_cv=agent_workflow.CanonicalCV.model_validate(result_payload["canonical_cv"]),
        jd_analysis=agent_workflow.JDAnalysis.model_validate(result_payload["jd_analysis"]),
        tailored_output=agent_workflow.TailoredOutput.model_validate(result_payload["tailored_output"]),
        qa_report=agent_workflow.QAReport.model_validate(result_payload["qa_report"]),
        change_log=agent_workflow.ChangeLog.model_validate(result_payload["change_log"]),
        ats_report=agent_workflow.ATSReport.model_validate(result_payload["ats_report"]),
        cover_letter=result_payload.get("cover_letter", ""),
    )


def _pdf_page_count(path: Optional[str]) -> Optional[int]:
    if not path or not path.lower().endswith(".pdf") or not Path(path).exists():
        return None
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return len(pdf.pages)
    except Exception:
        return None


def export_run(run_id: str) -> ExportResponse:
    record = get_run_record(run_id)
    workflow_result = _rehydrate_result(record["result"])
    artifact_data = render_run_artifacts(workflow_result, record["workflow_inputs"])
    max_pages = int(record.get("workflow_inputs", {}).get("max_pages") or 2)
    cv_path = artifact_data["cv_path"]
    cv_page_count = _pdf_page_count(cv_path)
    previous_layout = record.get("result", {}).get("layout_validation", {})
    layout_passed = cv_page_count <= max_pages if cv_page_count is not None else previous_layout.get("layout_passed")
    validation_method = "pdf_page_count" if cv_page_count is not None else previous_layout.get("validation_method", "pre_render_budget")

    artifacts = [
        ArtifactMetadata(
            artifact_id=f"{run_id}:cv",
            kind="cv_docx" if cv_path.endswith(".docx") else "cv_pdf",
            path=cv_path,
            page_count=cv_page_count,
            layout_passed=layout_passed,
        ).model_dump(),
        ArtifactMetadata(
            artifact_id=f"{run_id}:cover_letter",
            kind="cover_letter_pdf",
            path=artifact_data["cl_path"],
            page_count=_pdf_page_count(artifact_data["cl_path"]),
            layout_passed=None,
        ).model_dump(),
    ]
    exports = {
        "cv_path": cv_path,
        "cover_letter_path": artifact_data["cl_path"],
        "docs_url": artifact_data.get("docs_url"),
        "page_count": cv_page_count,
        "layout_passed": layout_passed,
        "artifact_ids": [artifact["artifact_id"] for artifact in artifacts],
    }
    result_payload = record.get("result", {})
    result_payload["artifacts"] = artifacts
    result_payload["layout_validation"] = {
        **previous_layout,
        "max_pages": max_pages,
        "page_count": cv_page_count,
        "layout_passed": layout_passed,
        "validation_method": validation_method,
    }
    record["result"] = result_payload
    update_run_record(run_id, {"result": result_payload, "exports": exports})
    return ExportResponse(
        run_id=run_id,
        cv_path=exports["cv_path"],
        cover_letter_path=exports["cover_letter_path"],
        docs_url=exports["docs_url"],
        docx_path=exports["cv_path"] if exports["cv_path"].endswith(".docx") else None,
        pdf_path=exports["cv_path"] if exports["cv_path"].endswith(".pdf") else None,
        page_count=cv_page_count,
        layout_passed=layout_passed,
        artifact_ids=exports["artifact_ids"],
    )
