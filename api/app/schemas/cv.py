from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SectionProposal(BaseModel):
    title: str
    kind: str
    body_text: str = ""
    start_para: int = 0
    end_para: int = 0
    role_label: str = ""
    employer_line: str = ""
    title_line: str = ""
    date_line: str = ""
    custom_kind_name: str = ""


class ImportMasterResponse(BaseModel):
    source_filename: str
    alias: Optional[str] = None
    sections: List[SectionProposal] = Field(default_factory=list)
    section_kinds: List[str] = Field(default_factory=list)


class FinalizeMasterRequest(BaseModel):
    source_filename: str
    sections: List[SectionProposal]
    overwrite: bool = False


class MasterSummary(BaseModel):
    master_id: str
    source_file: str
    source_docx: str = ""
    source_pdf: str = ""
    json_path: str
    template_config_path: str = ""


class MasterDetail(BaseModel):
    summary: MasterSummary
    payload: Dict[str, Any]


class FinalizeMasterResponse(BaseModel):
    master_id: str
    json_path: str
    template_config_path: str
    source_filename: str
