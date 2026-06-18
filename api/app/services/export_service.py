from __future__ import annotations

from typing import Any, Dict

import agent_workflow

from api.app.adapters.renderer_adapter import render_run_artifacts
from api.app.schemas.tailoring import ExportResponse
from api.app.services.tailoring_service import get_run_record, update_run_exports


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


def export_run(run_id: str) -> ExportResponse:
    record = get_run_record(run_id)
    workflow_result = _rehydrate_result(record["result"])
    artifact_data = render_run_artifacts(workflow_result, record["workflow_inputs"])
    exports = {
        "cv_path": artifact_data["cv_path"],
        "cover_letter_path": artifact_data["cl_path"],
        "docs_url": artifact_data.get("docs_url"),
    }
    update_run_exports(run_id, exports)
    return ExportResponse(
        run_id=run_id,
        cv_path=exports["cv_path"],
        cover_letter_path=exports["cover_letter_path"],
        docs_url=exports["docs_url"],
    )
