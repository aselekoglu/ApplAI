from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from api.app.schemas.tailored_examples import DiffClassification, DiffClassificationRequest, TailoredExamplesResponse
from api.app.services.tailored_examples_service import classify_master_example_diff, list_tailored_examples

router = APIRouter(prefix="/tailored-examples", tags=["tailored-examples"])


@router.get("", response_model=TailoredExamplesResponse)
def examples(role_label: Optional[str] = Query(default=None)) -> TailoredExamplesResponse:
    parsed = list_tailored_examples(role_label=role_label)
    return TailoredExamplesResponse(examples=parsed, count=len(parsed))


@router.post("/classify-diff", response_model=DiffClassification)
def classify_diff(payload: DiffClassificationRequest) -> DiffClassification:
    return classify_master_example_diff(
        payload.master_text,
        payload.example_text,
        master_source_path=payload.master_source_path,
        example_source_path=payload.example_source_path,
    )
