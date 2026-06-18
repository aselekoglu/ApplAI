from __future__ import annotations

import os
from typing import Any, Dict, List

import master_cv
import pdf_parser


def import_docx_sections(docx_path: str) -> List[Dict[str, Any]]:
    outline = master_cv.extract_docx_outline(docx_path)
    return master_cv.propose_sections(outline)


def import_pdf_sections(pdf_path: str) -> List[Dict[str, Any]]:
    parsed = pdf_parser.parse_pdf_to_json(pdf_path) or {"raw_text": ""}
    return [
        {
            "title": "Profile",
            "kind": "profile",
            "start_para": 0,
            "end_para": 0,
            "body_text": parsed.get("raw_text", ""),
            "source_file": os.path.basename(pdf_path),
        }
    ]
