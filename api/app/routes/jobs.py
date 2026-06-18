from __future__ import annotations

from fastapi import APIRouter

from api.app.schemas.jobs import JobImportRequest, JobListResponse, JobRecord, ScoreJobRequest, ScoreJobResponse
from api.app.services.job_records_service import list_job_records, load_job_record
from api.app.services.job_scoring_service import score_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/score", response_model=ScoreJobResponse)
def score(payload: ScoreJobRequest) -> ScoreJobResponse:
    return score_job(payload)


@router.post("/import", response_model=ScoreJobResponse)
def import_job(payload: JobImportRequest) -> ScoreJobResponse:
    return score_job(payload.model_copy(update={"save_draft": True}))


@router.get("", response_model=JobListResponse)
def list_jobs() -> JobListResponse:
    jobs = list_job_records()
    return JobListResponse(jobs=jobs, count=len(jobs))


@router.get("/{job_id}", response_model=JobRecord)
def get_job(job_id: str) -> JobRecord:
    return load_job_record(job_id)
