from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, status

from api.app.schemas.tailoring import ExportRequest, ExportResponse, RunDetailResponse, RunSummary, TailorRunRequest, TailorRunResponse
from api.app.services.export_service import export_run
from api.app.services.tailoring_service import get_run, list_runs, rerun_tailoring_job, run_tailoring_job

router = APIRouter(prefix="/tailor", tags=["tailoring"])


@router.post("/run", response_model=TailorRunResponse)
def run(payload: TailorRunRequest) -> TailorRunResponse:
    try:
        return run_tailoring_job(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Tailoring failed: {exc}") from exc


@router.post("/export", response_model=ExportResponse)
def export(payload: ExportRequest) -> ExportResponse:
    try:
        return export_run(payload.run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Export failed: {exc}") from exc


@router.get("/runs", response_model=List[RunSummary])
def runs() -> List[RunSummary]:
    return list_runs()


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
def run_detail(run_id: str) -> RunDetailResponse:
    try:
        return get_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/runs/{run_id}/rerun", response_model=TailorRunResponse)
def rerun(run_id: str) -> TailorRunResponse:
    try:
        return rerun_tailoring_job(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Rerun failed: {exc}") from exc
