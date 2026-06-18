from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from api.app.schemas.cv import FinalizeMasterRequest, FinalizeMasterResponse, ImportMasterResponse, MasterDetail, MasterSummary
from api.app.services.master_service import finalize_master, get_master, import_master_sections, list_masters, save_uploaded_source

router = APIRouter(prefix="/masters", tags=["masters"])


@router.post("/import", response_model=ImportMasterResponse, status_code=status.HTTP_201_CREATED)
async def import_master(file: UploadFile = File(...), alias: Optional[str] = Form(default=None)) -> ImportMasterResponse:
    filename = file.filename or ""
    if not filename.lower().endswith((".docx", ".pdf")):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only DOCX and PDF files are supported")
    content = await file.read()
    source_filename = save_uploaded_source(filename, content)
    try:
        return import_master_sections(source_filename, alias=alias)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/{master_id}/finalize", response_model=FinalizeMasterResponse, status_code=status.HTTP_201_CREATED)
def finalize(master_id: str, payload: FinalizeMasterRequest) -> FinalizeMasterResponse:
    try:
        json_path, config_path = finalize_master(master_id, payload)
    except FileExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Finalize failed: {exc}") from exc
    return FinalizeMasterResponse(
        master_id=master_id,
        json_path=json_path,
        template_config_path=config_path,
        source_filename=payload.source_filename,
    )


@router.get("", response_model=List[MasterSummary])
def masters() -> List[MasterSummary]:
    return list_masters()


@router.get("/{master_id}", response_model=MasterDetail)
def master_detail(master_id: str) -> MasterDetail:
    try:
        return get_master(master_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
