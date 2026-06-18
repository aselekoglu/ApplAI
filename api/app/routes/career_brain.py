from __future__ import annotations

from typing import Dict

from fastapi import APIRouter

from api.app.schemas.career_brain import CareerBrainProfile, CareerBrainUpdateResponse
from api.app.services.career_brain_service import career_brain_profile_path, ensure_career_brain_profile, update_career_brain_profile

router = APIRouter(prefix="/career-brain", tags=["career-brain"])


@router.get("", response_model=CareerBrainProfile)
def read_profile() -> CareerBrainProfile:
    return ensure_career_brain_profile()


@router.put("", response_model=CareerBrainUpdateResponse)
def update_profile(payload: CareerBrainProfile) -> CareerBrainUpdateResponse:
    profile, path = update_career_brain_profile(payload)
    return CareerBrainUpdateResponse(profile=profile, path=path)


@router.get("/path", response_model=Dict[str, str])
def profile_path() -> Dict[str, str]:
    return {"path": str(career_brain_profile_path())}
