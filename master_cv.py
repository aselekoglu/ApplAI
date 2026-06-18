from __future__ import annotations

import json
import os
import re
from docx import Document


SECTION_KINDS = ["profile", "experience_block", "education", "skills", "projects", "other"]


def extract_docx_outline(docx_path: str) -> list[dict]:
    doc = Document(docx_path)
    outline = []
    for idx, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue
        style_name = (para.style.name or "").strip() if para.style else ""
        outline.append({"index": idx, "text": text, "style_name": style_name})
    return outline


def propose_sections(paragraphs: list[dict]) -> list[dict]:
    if not paragraphs:
        return []

    heading_ids = []
    for i, p in enumerate(paragraphs):
        text = p["text"]
        style = p.get("style_name", "").lower()
        is_heading_style = style.startswith("heading")
        is_short_caps = len(text) <= 60 and text.upper() == text and len(text.split()) <= 6
        if is_heading_style or is_short_caps:
            heading_ids.append(i)

    if not heading_ids or heading_ids[0] != 0:
        heading_ids = [0] + heading_ids
    heading_ids = sorted(set(heading_ids))

    sections: list[dict] = []
    for idx, start in enumerate(heading_ids):
        end = (heading_ids[idx + 1] - 1) if idx + 1 < len(heading_ids) else len(paragraphs) - 1
        title = paragraphs[start]["text"][:80]
        body_lines = [paragraphs[i]["text"] for i in range(start + 1, end + 1)]
        kind = infer_section_kind(title)
        sections.append(
            {
                "title": title,
                "kind": kind,
                "start_para": paragraphs[start]["index"],
                "end_para": paragraphs[end]["index"],
                "body_text": "\n".join(body_lines).strip(),
            }
        )
    return sections


def infer_section_kind(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ["profile", "summary", "objective", "about"]):
        return "profile"
    if any(k in t for k in ["experience", "employment", "work history"]):
        return "experience_block"
    if any(k in t for k in ["education", "degree", "university"]):
        return "education"
    if any(k in t for k in ["skill", "tech stack", "tool"]):
        return "skills"
    if any(k in t for k in ["project", "portfolio"]):
        return "projects"
    return "other"


def sections_to_raw_text(sections: list[dict]) -> str:
    blocks = []
    for sec in sections:
        heading = sec.get("title", "SECTION").strip()
        body = sec.get("body_text", "").strip()
        if not heading:
            continue
        blocks.append(heading.upper())
        if body:
            blocks.append(body)
        blocks.append("")
    return "\n".join(blocks).strip()


def build_template_config(sections: list[dict]) -> dict:
    config = {
        "profile_headers": [],
        "experience_headers": [],
        "experience_blocks": [],
        "education_headers": [],
        "skills_headers": [],
        "project_headers": [],
        "section_ranges": [],
    }
    for sec in sections:
        title = sec.get("title", "").strip()
        kind = sec.get("kind", "other")
        if kind == "profile":
            config["profile_headers"].append(title)
        elif kind == "experience_block":
            config["experience_headers"].append(title)
            config["experience_blocks"].append(
                {
                    "heading_anchor": title,
                    "role_label": sec.get("role_label", ""),
                    "employer_line": sec.get("employer_line", ""),
                    "title_line": sec.get("title_line", ""),
                    "date_line": sec.get("date_line", ""),
                }
            )
        elif kind == "education":
            config["education_headers"].append(title)
        elif kind == "skills":
            config["skills_headers"].append(title)
        elif kind == "projects":
            config["project_headers"].append(title)
        config["section_ranges"].append(
            {
                "title": title,
                "kind": kind,
                "start_para": sec.get("start_para"),
                "end_para": sec.get("end_para"),
            }
        )
    return config


def save_master_artifacts(
    docs_dir: str,
    source_filename: str,
    sections: list[dict],
    canonical_name: str | None = None,
) -> tuple[str, str]:
    base = canonical_name or re.sub(r"\W+", "_", os.path.splitext(source_filename)[0]).strip("_")
    if not base:
        base = "master_cv"

    json_dir = os.path.join(docs_dir, "json_exports")
    cfg_dir = os.path.join(docs_dir, "master_configs")
    os.makedirs(json_dir, exist_ok=True)
    os.makedirs(cfg_dir, exist_ok=True)

    config = build_template_config(sections)
    config_path = os.path.join(cfg_dir, f"{base}.template.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    source_ext = os.path.splitext(source_filename)[1].lower()
    source_docx = source_filename if source_ext == ".docx" else ""
    source_pdf = source_filename if source_ext == ".pdf" else ""
    payload = {
        "source_file": source_filename,
        "source_docx": source_docx,
        "source_pdf": source_pdf,
        "raw_text": sections_to_raw_text(sections),
        "template_config_path": config_path,
        # Persist structured sections so the web UI can reload after refresh.
        "sections": list(sections),
    }
    json_path = os.path.join(json_dir, f"{base}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return json_path, config_path
