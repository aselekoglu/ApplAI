from __future__ import annotations

from fastapi import APIRouter

from api.app.schemas.jobs import ScoreJobRequest, ScoreJobResponse
from api.app.services.job_scoring_service import score_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/score", response_model=ScoreJobResponse)
def score(payload: ScoreJobRequest) -> ScoreJobResponse:
    return score_job(payload)
