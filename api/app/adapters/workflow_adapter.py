from __future__ import annotations

import agent_workflow

from api.app.schemas.tailoring import TailorRunOptions


def run_tailoring(job_description: str, base_cv_json_text: str, options: TailorRunOptions) -> agent_workflow.WorkflowResult:
    return agent_workflow.run_application_workflow(
        job_description=job_description,
        base_cv_json_text=base_cv_json_text,
        model_name=options.model_name,
        company_name=options.company_name,
        job_title=options.job_title,
        quick_mode=options.quick_mode,
        include_cover_letter=options.include_cover_letter,
        include_ats=options.include_ats,
        include_qa=options.include_qa,
        allow_experience_rewrites=options.allow_experience_rewrites,
        allow_education_rewrites=options.allow_education_rewrites,
        max_pages=options.max_pages,
    )
