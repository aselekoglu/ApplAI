from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from api.app.adapters.workflow_adapter import run_tailoring
from api.app.config import settings
from api.app.schemas.career_brain import CareerBrainProfile, EvidenceBlock
from api.app.schemas.jobs import JobRecord
from api.app.schemas.tailoring import (
    LayoutValidation,
    PageBudgetMetadata,
    ProvenanceRef,
    RunDetailResponse,
    RunSummary,
    SelectedEvidenceBlock,
    Selection,
    TailorRunRequest,
    TailorRunResponse,
    TailoringResultPayload,
)
from api.app.services.career_brain_service import ensure_career_brain_profile
from api.app.services.job_records_service import load_job_record
from api.app.services.master_service import get_master


_CLAIM_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "using",
}


def ensure_runs_dir() -> None:
    Path(settings.runs_dir).mkdir(parents=True, exist_ok=True)


def _run_path(run_id: str) -> Path:
    return Path(settings.runs_dir) / f"{run_id}.json"


def _to_result_payload(
    result,
    *,
    job_id: Optional[str],
    master_id: str,
    selected_evidence: List[SelectedEvidenceBlock],
    page_budget: PageBudgetMetadata,
    layout_validation: LayoutValidation,
) -> TailoringResultPayload:
    return TailoringResultPayload.model_validate(
        {
            "canonical_cv": result.canonical_cv.model_dump(),
            "jd_analysis": result.jd_analysis.model_dump(),
            "tailored_output": _tailored_output_with_provenance(
                result.tailored_output.model_dump(),
                selected_evidence,
            ),
            "change_log": _change_log_with_provenance(
                result.change_log.model_dump(),
                result.tailored_output.model_dump(),
                selected_evidence,
            ),
            "qa_report": _qa_report_with_guard(
                result.qa_report.model_dump(),
                result.tailored_output.model_dump(),
                selected_evidence,
            ),
            "ats_report": result.ats_report.model_dump(),
            "cover_letter": result.cover_letter or "",
            "job_id": job_id,
            "master_id": master_id,
            "selected_evidence_block_ids": [item.evidence_block_id for item in selected_evidence],
            "selected_evidence": [item.model_dump() for item in selected_evidence],
            "page_budget": page_budget.model_dump(),
            "layout_validation": layout_validation.model_dump(),
            "approval_status": "draft",
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
        job_id=record.get("job_id"),
    )


def _claim_tokens(text: str) -> set[str]:
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9#+.\-]{2,}\b", text.lower())
    return {token.strip(".-") for token in tokens if token not in _CLAIM_STOPWORDS}


def _evidence_map(profile: CareerBrainProfile) -> Dict[str, EvidenceBlock]:
    return {block.block_id: block for block in profile.evidence_blocks}


def _selected_evidence_from_job(job_record: Optional[JobRecord], profile: CareerBrainProfile) -> List[SelectedEvidenceBlock]:
    blocks_by_id = _evidence_map(profile)
    selected: List[SelectedEvidenceBlock] = []
    seen: set[str] = set()

    if job_record:
        for match in job_record.score_report.evidence_matches:
            block = blocks_by_id.get(match.evidence_block_id)
            if not block or block.block_id in seen:
                continue
            seen.add(block.block_id)
            selected.append(_selected_evidence_payload(block, match.score, match.matched_terms))

    if selected:
        return selected[:8]

    wanted_terms = set(job_record.parsed.keywords if job_record else [])
    fallback: List[tuple[int, EvidenceBlock, List[str]]] = []
    for block in profile.evidence_blocks:
        terms = _claim_tokens(" ".join([block.text, *block.technologies, *block.ats_keywords, *block.relevance_tags]))
        matched = sorted(wanted_terms & terms)
        if matched:
            fallback.append((len(matched) * 10 + block.priority, block, matched))
    fallback.sort(key=lambda item: (-item[0], item[1].block_id))
    return [_selected_evidence_payload(block, score, matched_terms) for score, block, matched_terms in fallback[:8]]


def _selected_evidence_payload(block: EvidenceBlock, score: int, matched_terms: Iterable[str]) -> SelectedEvidenceBlock:
    return SelectedEvidenceBlock(
        evidence_block_id=block.block_id,
        source_label=block.source_label,
        text=block.text,
        score=score,
        matched_terms=list(matched_terms)[:12],
        priority=block.priority,
        provenance=[
            ProvenanceRef(
                source_type="career_brain",
                source_id=block.block_id,
                source_label=block.source_label,
                source_path=block.source_path,
                supported_text=block.text,
            )
        ],
    )


def _selection_provenance(selection: Dict[str, Any], selected_evidence: List[SelectedEvidenceBlock]) -> List[Dict[str, Any]]:
    refs = [
        ProvenanceRef(
            source_type="master_cv",
            source_id=str(selection.get("bullet_id", "")),
            source_label="Canonical master CV bullet",
            supported_text=str(selection.get("original_text") or ""),
        ).model_dump()
    ]
    refs.extend(ref.model_dump() for evidence in selected_evidence[:3] for ref in evidence.provenance)
    return refs


def _unsupported_claims(selection: Dict[str, Any], selected_evidence: List[SelectedEvidenceBlock]) -> List[str]:
    candidate_text = str(selection.get("new_text") or selection.get("original_text") or "")
    support_text = " ".join(
        [
            str(selection.get("original_text") or ""),
            *(evidence.text for evidence in selected_evidence),
        ]
    )
    unsupported_terms = sorted(_claim_tokens(candidate_text) - _claim_tokens(support_text))
    if not unsupported_terms:
        return []
    return [f"{selection.get('bullet_id', 'unknown')}: unsupported terms introduced: {', '.join(unsupported_terms[:8])}"]


def _iter_selection_groups(tailored_output: Dict[str, Any]) -> Iterable[List[Dict[str, Any]]]:
    for key in ("profile_selections", "experience_selections", "project_selections", "education_selections"):
        group = tailored_output.get(key, [])
        if isinstance(group, list):
            yield group


def _tailored_output_with_provenance(
    tailored_output: Dict[str, Any],
    selected_evidence: List[SelectedEvidenceBlock],
) -> Dict[str, Any]:
    enriched = json.loads(json.dumps(tailored_output))
    for group in _iter_selection_groups(enriched):
        for selection in group:
            selection["provenance"] = _selection_provenance(selection, selected_evidence)
            selection["unsupported_claims"] = _unsupported_claims(selection, selected_evidence)
    return enriched


def _change_log_with_provenance(
    change_log: Dict[str, Any],
    tailored_output: Dict[str, Any],
    selected_evidence: List[SelectedEvidenceBlock],
) -> Dict[str, Any]:
    enriched = json.loads(json.dumps(change_log))
    selections_by_id = {
        str(selection.get("bullet_id")): selection
        for group in _iter_selection_groups(tailored_output)
        for selection in group
    }
    for entry in enriched.get("entries", []):
        selection = selections_by_id.get(str(entry.get("bullet_id")), entry)
        entry["provenance"] = _selection_provenance(selection, selected_evidence)
        entry["unsupported_claims"] = _unsupported_claims(selection, selected_evidence)
    return enriched


def _qa_report_with_guard(
    qa_report: Dict[str, Any],
    tailored_output: Dict[str, Any],
    selected_evidence: List[SelectedEvidenceBlock],
) -> Dict[str, Any]:
    unsupported: List[str] = list(qa_report.get("unsupported_claims") or [])
    for group in _iter_selection_groups(tailored_output):
        for selection in group:
            unsupported.extend(_unsupported_claims(selection, selected_evidence))
    deduped = list(dict.fromkeys(unsupported))
    qa_report["unsupported_claims"] = deduped
    qa_report["unsupported_claim_guard_passed"] = not deduped
    qa_report["factual_support_passed"] = bool(qa_report.get("factual_support_passed", True)) and not deduped
    if deduped and "Unsupported claim guard flagged unsupported terms for review." not in qa_report.get("style_issues", []):
        qa_report.setdefault("style_issues", []).append("Unsupported claim guard flagged unsupported terms for review.")
    return qa_report


def _page_budget(max_pages: int, result) -> PageBudgetMetadata:
    selections = (
        result.tailored_output.profile_selections
        + result.tailored_output.experience_selections
        + result.tailored_output.project_selections
        + result.tailored_output.education_selections
    )
    selected_text = [selection.new_text or selection.original_text for selection in selections if selection.action != "deselect"]
    return PageBudgetMetadata(
        max_pages=max_pages,
        target_page_count=max_pages,
        profile_bullet_budget=3 if max_pages <= 2 else 4,
        experience_bullet_budget=8 if max_pages <= 2 else 10,
        project_bullet_budget=3 if max_pages <= 2 else 4,
        education_bullet_budget=2 if max_pages <= 2 else 3,
        estimated_selected_bullets=len(selected_text),
        estimated_words=sum(len(text.split()) for text in selected_text),
    )


def _pre_render_layout_validation(page_budget: PageBudgetMetadata) -> LayoutValidation:
    bullet_limit = (
        page_budget.profile_bullet_budget
        + page_budget.experience_bullet_budget
        + page_budget.project_bullet_budget
        + page_budget.education_bullet_budget
    )
    notes: List[str] = []
    layout_passed = page_budget.estimated_selected_bullets <= bullet_limit and page_budget.estimated_words <= 650
    if page_budget.estimated_selected_bullets > bullet_limit:
        notes.append(f"Selected bullet estimate {page_budget.estimated_selected_bullets} exceeds budget {bullet_limit}.")
    if page_budget.estimated_words > 650:
        notes.append(f"Selected text estimate {page_budget.estimated_words} words exceeds initial two-page budget.")
    if not notes:
        notes.append("Pre-render budget is within deterministic two-page targets.")
    return LayoutValidation(
        max_pages=page_budget.max_pages,
        page_count=None,
        layout_passed=layout_passed,
        validation_method="pre_render_budget",
        notes=notes,
    )


def run_tailoring_job(payload: TailorRunRequest) -> TailorRunResponse:
    ensure_runs_dir()
    master = get_master(payload.master_id)
    job_record: Optional[JobRecord] = load_job_record(payload.job_id) if payload.job_id else None
    profile = ensure_career_brain_profile()
    selected_evidence = _selected_evidence_from_job(job_record, profile)
    job_description = job_record.raw_description if job_record else str(payload.job_description or "")

    options = payload.options
    if job_record:
        options = payload.options.model_copy(
            update={
                "company_name": payload.options.company_name or job_record.company_name or "",
                "job_title": payload.options.job_title or job_record.job_title or "",
            }
        )

    base_cv_json_text = json.dumps(master.payload)
    result = run_tailoring(job_description, base_cv_json_text, options)
    run_id = uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()

    source_docx = master.summary.source_docx
    source_file = master.summary.source_file
    template_path = ""
    if source_docx:
        template_path = os.path.join(settings.docs_dir, source_docx)
    elif source_file.endswith(".pdf"):
        template_path = os.path.join(settings.docs_dir, source_file.replace(".pdf", ".docx"))

    page_budget = _page_budget(options.max_pages, result)
    layout_validation = _pre_render_layout_validation(page_budget)
    result_payload = _to_result_payload(
        result,
        job_id=job_record.job_id if job_record else payload.job_id,
        master_id=master.summary.master_id,
        selected_evidence=selected_evidence,
        page_budget=page_budget,
        layout_validation=layout_validation,
    )
    record = {
        "run_id": run_id,
        "master_id": master.summary.master_id,
        "job_id": job_record.job_id if job_record else payload.job_id,
        "created_at": created_at,
        "options": options.model_dump(),
        "job_description": job_description,
        "workflow_inputs": {
            "job_id": job_record.job_id if job_record else payload.job_id,
            "job_desc": job_description,
            "base_cv_json_text": base_cv_json_text,
            "company_name": options.company_name,
            "job_title": options.job_title,
            "selected_cv_json": f"{master.summary.master_id}.json",
            "selected_model": options.model_name,
            "quick_mode": options.quick_mode,
            "include_cover_letter": options.include_cover_letter,
            "include_ats": options.include_ats,
            "include_qa": options.include_qa,
            "allow_experience_rewrites": options.allow_experience_rewrites,
            "allow_education_rewrites": options.allow_education_rewrites,
            "max_pages": options.max_pages,
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
        options=options,
        result=result_payload,
        job_id=record["job_id"],
        selected_evidence_block_ids=result_payload.selected_evidence_block_ids,
        page_count=result_payload.layout_validation.page_count,
        layout_passed=result_payload.layout_validation.layout_passed,
        artifact_ids=[artifact.artifact_id for artifact in result_payload.artifacts],
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


def update_run_record(run_id: str, updates: Dict[str, Any]) -> None:
    path = _run_path(run_id)
    if not path.exists():
        raise FileNotFoundError(f"Run '{run_id}' was not found")
    record = json.loads(path.read_text(encoding="utf-8"))
    record.update(updates)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")


def get_run_record(run_id: str) -> Dict[str, Any]:
    path = _run_path(run_id)
    if not path.exists():
        raise FileNotFoundError(f"Run '{run_id}' was not found")
    return json.loads(path.read_text(encoding="utf-8"))
