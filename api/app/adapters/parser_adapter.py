from __future__ import annotations

import os
from typing import Any, Dict, List

import master_cv
import pdf_parser


def import_docx_sections(docx_path: str) -> List[Dict[str, Any]]:
    outline = master_cv.extract_docx_outline(docx_path)
    return master_cv.propose_sections(outline)


def import_pdf_sections(pdf_path: str) -> List[Dict[str, Any]]:
    import re
    parsed = pdf_parser.parse_pdf_to_json(pdf_path) or {}
    structured_sections = parsed.get("structured_sections", [])
    if not structured_sections:
        raw_text = parsed.get("raw_text", "")
        return [
            {
                "title": "Profile",
                "kind": "profile",
                "start_para": 0,
                "end_para": 0,
                "body_text": raw_text,
            }
        ]

    DATE_RANGE_PATTERN = pdf_parser.DATE_RANGE_PATTERN

    sections = []
    for sec in structured_sections:
        c_type = sec.get("canonical_type", "other")
        body_lines = sec.get("body_lines", [])

        if c_type == "experience":
            entry_indices = []
            for idx, line in enumerate(body_lines):
                bullet_chars = ('•', '●', '■', '▪', '⁃', '◦', '·')
                is_bullet = line.strip().startswith(bullet_chars) or (line.strip().startswith('-') and not line.strip().startswith('--')) or (line.strip().startswith('*') and not line.strip().startswith('**'))
                if not is_bullet and DATE_RANGE_PATTERN.search(line):
                    entry_indices.append(idx)
            if not entry_indices and body_lines:
                for idx, line in enumerate(body_lines):
                    bullet_chars = ('•', '●', '■', '▪', '⁃', '◦', '·')
                    is_bullet = line.strip().startswith(bullet_chars) or (line.strip().startswith('-') and not line.strip().startswith('--')) or (line.strip().startswith('*') and not line.strip().startswith('**'))
                    if not is_bullet:
                        entry_indices.append(idx)
                        break

            for k, start_idx in enumerate(entry_indices):
                end_idx = entry_indices[k+1] if k + 1 < len(entry_indices) else len(body_lines)
                entry_lines = body_lines[start_idx:end_idx]
                if not entry_lines:
                    continue
                header_line = entry_lines[0]
                date_match = DATE_RANGE_PATTERN.search(header_line)
                date_line = ""
                title_line = header_line
                if date_match:
                    date_line = date_match.group(0)
                    title_line = header_line.replace(date_line, "").strip()
                    title_line = re.sub(r'[\s,–\-—]+$', '', title_line).strip()

                employer_line = ""
                bullets_start_idx = 1
                if len(entry_lines) > 1:
                    second_line = entry_lines[1]
                    bullet_chars = ('•', '●', '■', '▪', '⁃', '◦', '·')
                    is_bullet = second_line.strip().startswith(bullet_chars) or (second_line.strip().startswith('-') and not second_line.strip().startswith('--')) or (second_line.strip().startswith('*') and not second_line.strip().startswith('**'))
                    if not is_bullet:
                        employer_line = second_line.strip()
                        bullets_start_idx = 2

                bullets = []
                for line in entry_lines[bullets_start_idx:]:
                    if line.strip():
                        bullets.append(line.strip())

                body_text = "\n".join(bullets)
                sections.append({
                    "title": title_line or "Experience Entry",
                    "kind": "experience_block",
                    "start_para": 0,
                    "end_para": 0,
                    "body_text": body_text,
                    "role_label": "",
                    "employer_line": employer_line,
                    "title_line": title_line,
                    "date_line": date_line,
                })

        elif c_type == "education":
            entry_indices = []
            degree_kws = ["bachelor", "master", "doctor", "post-graduate", "postgraduate", "diploma", "degree", "phd", "ph.d", "b.s", "m.s", "b.a", "m.a", "associate"]
            current_entry_had_date = False
            for idx, line in enumerate(body_lines):
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                bullet_chars = ('•', '●', '■', '▪', '⁃', '◦', '·')
                is_bullet = line_stripped.startswith(bullet_chars) or (line_stripped.startswith('-') and not line_stripped.startswith('--')) or (line_stripped.startswith('*') and not line_stripped.startswith('**'))
                if is_bullet:
                    current_entry_had_date = False
                    continue

                has_date = DATE_RANGE_PATTERN.search(line_stripped) or re.search(r'\b\d{4}\b', line_stripped)
                starts_with_degree = any(line_stripped.lower().startswith(kw) for kw in degree_kws) or any(kw in line_stripped.lower()[:20] for kw in degree_kws)

                is_start = False
                if idx == 0:
                    is_start = True
                else:
                    prev_line = body_lines[idx-1].strip()
                    prev_is_bullet = prev_line.startswith(bullet_chars) or (prev_line.startswith('-') and not prev_line.startswith('--')) or (prev_line.startswith('*') and not prev_line.startswith('**'))
                    if prev_is_bullet:
                        is_start = True
                    elif has_date and not current_entry_had_date and not (DATE_RANGE_PATTERN.search(prev_line) or re.search(r'\b\d{4}\b', prev_line)):
                        is_start = True
                    elif starts_with_degree:
                        is_start = True

                if is_start:
                    entry_indices.append(idx)
                    current_entry_had_date = bool(has_date)
                elif has_date:
                    current_entry_had_date = True

            for k, start_idx in enumerate(entry_indices):
                end_idx = entry_indices[k+1] if k + 1 < len(entry_indices) else len(body_lines)
                entry_lines = body_lines[start_idx:end_idx]
                if not entry_lines:
                    continue

                non_bullets = []
                bullets = []
                for line in entry_lines:
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    bullet_chars = ('•', '●', '■', '▪', '⁃', '◦', '·')
                    is_bullet = line_stripped.startswith(bullet_chars) or (line_stripped.startswith('-') and not line_stripped.startswith('--')) or (line_stripped.startswith('*') and not line_stripped.startswith('**'))
                    if is_bullet:
                        bullets.append(line_stripped)
                    else:
                        non_bullets.append(line_stripped)

                if not non_bullets:
                    continue

                first_line = non_bullets[0]
                date_match = DATE_RANGE_PATTERN.search(first_line) or re.search(r'\b\d{4}\b', first_line)
                date_line = ""
                title_line = first_line
                if date_match:
                    date_line = date_match.group(0)
                    title_line = first_line.replace(date_line, "").strip()
                    title_line = re.sub(r'[\s,–\-—]+$', '', title_line).strip()

                employer_line = ""
                if len(non_bullets) >= 2:
                    employer_line = non_bullets[1]

                role_label = ""
                if len(non_bullets) >= 3:
                    role_label = non_bullets[2]

                body_text = "\n".join(bullets)
                sections.append({
                    "title": title_line or "Education Entry",
                    "kind": "education",
                    "start_para": 0,
                    "end_para": 0,
                    "body_text": body_text,
                    "role_label": role_label,
                    "employer_line": employer_line,
                    "title_line": title_line,
                    "date_line": date_line,
                })

        elif c_type == "projects":
            entry_indices = []
            for idx, line in enumerate(body_lines):
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                bullet_chars = ('•', '●', '■', '▪', '⁃', '◦', '·')
                is_bullet = line_stripped.startswith(bullet_chars) or (line_stripped.startswith('-') and not line_stripped.startswith('--')) or (line_stripped.startswith('*') and not line_stripped.startswith('**'))
                if is_bullet:
                    continue
                is_start = False
                if idx == 0:
                    is_start = True
                else:
                    prev_line = body_lines[idx-1].strip()
                    prev_is_bullet = prev_line.startswith(bullet_chars) or (prev_line.startswith('-') and not prev_line.startswith('--')) or (prev_line.startswith('*') and not prev_line.startswith('**'))
                    if prev_is_bullet:
                        is_start = True

                if is_start:
                    entry_indices.append(idx)

            for k, start_idx in enumerate(entry_indices):
                end_idx = entry_indices[k+1] if k + 1 < len(entry_indices) else len(body_lines)
                entry_lines = body_lines[start_idx:end_idx]
                if not entry_lines:
                    continue

                non_bullets = []
                bullets = []
                for line in entry_lines:
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    bullet_chars = ('•', '●', '■', '▪', '⁃', '◦', '·')
                    is_bullet = line_stripped.startswith(bullet_chars) or (line_stripped.startswith('-') and not line_stripped.startswith('--')) or (line_stripped.startswith('*') and not line_stripped.startswith('**'))
                    if is_bullet:
                        bullets.append(line_stripped)
                    else:
                        non_bullets.append(line_stripped)

                if not non_bullets:
                    continue

                first_line = non_bullets[0]
                date_match = re.search(r'\b(?:\d{4}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*(?:\d{4})?\b', first_line, re.IGNORECASE)
                date_line = ""
                title_part = first_line
                if date_match:
                    date_line = date_match.group(0)
                    title_part = first_line.replace(date_line, "").strip()
                    title_part = re.sub(r'[\s,–\-—]+$', '', title_part).strip()

                title_line = title_part
                employer_line = ""
                for sep in (" – ", " - ", " | "):
                    if sep in title_part:
                        parts = title_part.split(sep, 1)
                        title_line = parts[0].strip()
                        employer_line = parts[1].strip()
                        break

                if len(non_bullets) >= 2:
                    extra_context = " ".join(non_bullets[1:])
                    if employer_line:
                        employer_line = f"{employer_line} | {extra_context}"
                    else:
                        employer_line = extra_context

                body_text = "\n".join(bullets)
                sections.append({
                    "title": title_line or "Project Entry",
                    "kind": "projects",
                    "start_para": 0,
                    "end_para": 0,
                    "body_text": body_text,
                    "role_label": "",
                    "employer_line": employer_line,
                    "title_line": title_line,
                    "date_line": date_line,
                })

        else:
            kind = "other"
            if c_type == "profile":
                kind = "profile"
            elif c_type == "summary_qualifications":
                kind = "skills"

            title = sec.get("display_title", "Untitled section")
            body_text = "\n".join(body_lines)

            sections.append({
                "title": title,
                "kind": kind,
                "start_para": 0,
                "end_para": 0,
                "body_text": body_text,
            })
    return sections
