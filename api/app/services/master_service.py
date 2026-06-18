from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import List, Optional

import master_cv

from api.app.adapters.parser_adapter import import_docx_sections, import_pdf_sections
from api.app.config import settings
from api.app.schemas.cv import FinalizeMasterRequest, ImportMasterResponse, MasterDetail, MasterSummary


def _slugify(value: str) -> str:
    slug = re.sub(r"\W+", "_", value).strip("_").lower()
    return slug or "master_cv"


def _master_json_path(master_id: str) -> Path:
    normalized = master_id[:-5] if master_id.endswith(".json") else master_id
    return Path(settings.json_exports_dir) / f"{normalized}.json"


def ensure_master_dirs() -> None:
    Path(settings.docs_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.json_exports_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.master_configs_dir).mkdir(parents=True, exist_ok=True)


def save_uploaded_source(filename: str, content: bytes) -> str:
    ensure_master_dirs()
    safe_name = os.path.basename(filename)
    source_path = Path(settings.docs_dir) / safe_name
    source_path.write_bytes(content)
    return safe_name


def import_master_sections(source_filename: str, alias: Optional[str] = None) -> ImportMasterResponse:
    source_path = Path(settings.docs_dir) / source_filename
    ext = source_path.suffix.lower()
    if ext == ".docx":
        sections = import_docx_sections(str(source_path))
    elif ext == ".pdf":
        sections = import_pdf_sections(str(source_path))
    else:
        raise ValueError("Only DOCX and PDF files are supported")
    return ImportMasterResponse(
        source_filename=source_filename,
        alias=alias,
        sections=sections,
        section_kinds=master_cv.SECTION_KINDS,
    )


def finalize_master(master_id: str, payload: FinalizeMasterRequest) -> tuple[str, str]:
    ensure_master_dirs()
    canonical_name = _slugify(master_id)
    json_path = _master_json_path(canonical_name)
    cfg_path = Path(settings.master_configs_dir) / f"{canonical_name}.template.json"
    if not payload.overwrite and (json_path.exists() or cfg_path.exists()):
        raise FileExistsError(f"Master '{canonical_name}' already exists")
    return master_cv.save_master_artifacts(
        settings.docs_dir,
        payload.source_filename,
        [section.model_dump() for section in payload.sections],
        canonical_name=canonical_name,
    )


def list_masters() -> List[MasterSummary]:
    ensure_master_dirs()
    masters: List[MasterSummary] = []
    for path in sorted(Path(settings.json_exports_dir).glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        masters.append(
            MasterSummary(
                master_id=path.stem,
                source_file=payload.get("source_file", ""),
                source_docx=payload.get("source_docx", ""),
                source_pdf=payload.get("source_pdf", ""),
                json_path=str(path),
                template_config_path=payload.get("template_config_path", ""),
            )
        )
    return masters


def get_master(master_id: str) -> MasterDetail:
    path = _master_json_path(master_id)
    if not path.exists():
        raise FileNotFoundError(f"Master '{master_id}' was not found")
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = MasterSummary(
        master_id=path.stem,
        source_file=payload.get("source_file", ""),
        source_docx=payload.get("source_docx", ""),
        source_pdf=payload.get("source_pdf", ""),
        json_path=str(path),
        template_config_path=payload.get("template_config_path", ""),
    )
    return MasterDetail(summary=summary, payload=payload)
