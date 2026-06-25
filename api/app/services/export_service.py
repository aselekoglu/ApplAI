from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

import agent_workflow

from api.app.adapters.renderer_adapter import render_run_artifacts
from api.app.config import settings
from api.app.schemas.tailoring import ArtifactMetadata, ExportResponse
from api.app.services.html_resume_renderer import render_resume_pdf
from api.app.services.pdf_text_validation_service import validate_pdf_text
from api.app.services.resume_layout_service import build_resume_layout
from api.app.services.tailoring_service import evaluate_output_quality, get_run_record, update_run_record


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


def _safe_company_name(company_name: str) -> str:
    safe_company = re.sub(r"\W+", "_", company_name or "Co").strip("_")
    return safe_company or "Co"


def _candidate_surname(owner_name: str) -> str:
    cleaned = str(owner_name or "").strip()
    if not cleaned:
        return "Candidate"
    surname = cleaned.split()[-1]
    safe_surname = re.sub(r"\W+", "_", surname).strip("_")
    return safe_surname or "Candidate"


def _final_cv_paths(owner_name: str, company_name: str) -> tuple[str, str]:
    base_name = f"{_candidate_surname(owner_name)}_CV_Tailored_{_safe_company_name(company_name)}"
    return (
        str(Path(settings.docs_dir) / f"{base_name}.html"),
        str(Path(settings.docs_dir) / f"{base_name}.pdf"),
    )


def export_run(run_id: str) -> ExportResponse:
    record = get_run_record(run_id)
    workflow_result = _rehydrate_result(record["result"])
    workflow_inputs = record.get("workflow_inputs", {})
    artifact_data = render_run_artifacts(workflow_result, workflow_inputs)
    max_pages = int(workflow_inputs.get("max_pages") or 2)
    result_payload = record.get("result", {})
    owner_name = workflow_result.canonical_cv.full_name or "Candidate"
    expected_keywords = result_payload.get("ats_report", {}).get("jd_keywords") or []
    master_payload = {}
    base_cv_json_text = workflow_inputs.get("base_cv_json_text")
    if isinstance(base_cv_json_text, str) and base_cv_json_text.strip():
        try:
            master_payload = json.loads(base_cv_json_text)
        except json.JSONDecodeError:
            master_payload = {}
    layout = build_resume_layout(
        result_payload,
        owner_name=owner_name,
        target_role=workflow_inputs.get("job_title", ""),
        company_name=workflow_inputs.get("company_name", ""),
        expected_keywords=expected_keywords,
        master_payload=master_payload,
    )
    html_path, final_pdf_path = _final_cv_paths(owner_name, workflow_inputs.get("company_name", ""))
    final_pdf_path = render_resume_pdf(layout, html_path, final_pdf_path)
    cv_page_count = _pdf_page_count(final_pdf_path)
    ats_validation = validate_pdf_text(final_pdf_path, layout)
    extracted_word_count = len((ats_validation.extracted_text or "").split())
    section_headings = [section.heading for section in layout.sections]
    if layout.experience_entries:
        section_headings.append("RELEVANT EXPERIENCE")
    if layout.project_entries:
        section_headings.append("PROJECTS")
    if layout.education_entries:
        section_headings.append("EDUCATION")
    quality_validation = evaluate_output_quality(
        max_pages=max_pages,
        page_count=cv_page_count,
        extracted_word_count=extracted_word_count,
        section_headings=section_headings,
        keyword_coverage_pct=float(result_payload.get("ats_report", {}).get("coverage_pct") or 0.0),
        missing_required_sections=ats_validation.missing_headings,
        broken_bullets=[],
    )
    layout_passed = bool(quality_validation.layout_passed) and ats_validation.ats_parse_passed
    previous_layout = record.get("result", {}).get("layout_validation", {})
    notes = list(previous_layout.get("notes") or [])
    validation_method = "html_pdf_quality_gate"
    if cv_page_count is None:
        notes.append("HTML-rendered PDF page count was unavailable.")
    elif cv_page_count <= max_pages:
        notes.append(f"HTML-rendered PDF page count {cv_page_count} is within max_pages {max_pages}.")
    else:
        notes.append(f"HTML-rendered PDF page count {cv_page_count} exceeds max_pages {max_pages}.")
    notes.extend(quality_validation.notes)
    notes.extend(ats_validation.notes)

    artifacts = [
        ArtifactMetadata(
            artifact_id=f"{run_id}:cv",
            kind="cv_pdf",
            path=final_pdf_path,
            html_path=html_path,
            page_count=cv_page_count,
            layout_passed=layout_passed,
            ats_parse_passed=ats_validation.ats_parse_passed,
            ats_parse_notes=ats_validation.notes,
        ).model_dump(),
    ]
    docx_path = artifact_data["cv_path"] if artifact_data["cv_path"].lower().endswith(".docx") else None
    if docx_path:
        artifacts.append(
            ArtifactMetadata(
                artifact_id=f"{run_id}:cv_docx",
                kind="cv_docx",
                path=docx_path,
                page_count=None,
                layout_passed=None,
            ).model_dump()
        )
    artifacts.append(
        ArtifactMetadata(
            artifact_id=f"{run_id}:cover_letter",
            kind="cover_letter_pdf",
            path=artifact_data["cl_path"],
            page_count=_pdf_page_count(artifact_data["cl_path"]),
            layout_passed=None,
        ).model_dump(),
    )
    exports = {
        "cv_path": final_pdf_path,
        "cover_letter_path": artifact_data["cl_path"],
        "docs_url": artifact_data.get("docs_url"),
        "docx_path": docx_path,
        "pdf_path": final_pdf_path,
        "html_path": html_path,
        "page_count": cv_page_count,
        "layout_passed": layout_passed,
        "ats_parse_passed": ats_validation.ats_parse_passed,
        "ats_parse_notes": ats_validation.notes,
        "artifact_ids": [artifact["artifact_id"] for artifact in artifacts],
    }
    result_payload["artifacts"] = artifacts
    result_payload["layout_validation"] = {
        **previous_layout,
        "max_pages": max_pages,
        "page_count": cv_page_count,
        "layout_passed": layout_passed,
        "validation_method": validation_method,
        "notes": notes,
    }
    record["result"] = result_payload
    update_run_record(run_id, {"result": result_payload, "exports": exports})
    return ExportResponse(
        run_id=run_id,
        cv_path=exports["cv_path"],
        cover_letter_path=exports["cover_letter_path"],
        docs_url=exports["docs_url"],
        docx_path=exports["docx_path"],
        pdf_path=exports["pdf_path"],
        html_path=exports["html_path"],
        page_count=cv_page_count,
        layout_passed=layout_passed,
        ats_parse_passed=exports["ats_parse_passed"],
        ats_parse_notes=exports["ats_parse_notes"],
        artifact_ids=exports["artifact_ids"],
    )
