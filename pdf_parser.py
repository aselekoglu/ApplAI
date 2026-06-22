import os
import json
import re
import pdfplumber

SECTION_ALIASES = {
    "profile": ["PROFILE", "PROFESSIONAL PROFILE", "SUMMARY", "PROFESSIONAL SUMMARY", "OBJECTIVE"],
    "summary_qualifications": [
        "SUMMARY OF QUALIFICATIONS", "QUALIFICATIONS", "SKILLS SUMMARY",
        "TECHNICAL SKILLS", "SKILLS & TOOLS", "SKILLS AND TOOLS",
        "AREAS OF EXPERTISE", "CORE COMPETENCIES"
    ],
    "experience": ["EXPERIENCE", "WORK EXPERIENCE", "RELEVANT EXPERIENCE", "PROFESSIONAL EXPERIENCE", "EMPLOYMENT HISTORY", "CAREER HISTORY"],
    "education": ["EDUCATION", "ACADEMIC BACKGROUND", "ACADEMIC HISTORY", "EDUCATION & CERTIFICATIONS", "EDUCATION AND CERTIFICATIONS"],
    "projects": ["PROJECTS", "TECHNICAL PROJECTS", "SELECTED PROJECTS", "ACADEMIC PROJECTS", "PERSONAL PROJECTS"],
    "certifications": ["CERTIFICATIONS", "LICENSES", "PROFESSIONAL DEVELOPMENT"],
    "additional": ["ADDITIONAL", "ACTIVITIES", "LANGUAGES", "REFERENCES", "ADDITIONAL INFORMATION", "COMMUNITY INVOLVEMENT", "VOLUNTEER EXPERIENCE"]
}

DATE_RANGE_PATTERN = re.compile(
    r'\b(?:\d{4}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*(?:\d{4})?\s*[-–—]\s*(?:\d{4}|Present|Current|Ongoing|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*(?:\d{4})?\b',
    re.IGNORECASE
)

def normalize_text(text):
    t = text.strip()
    t = re.sub(r'^[\-\*•●■▪⁃◦◦·\s]+', '', t)
    t = re.sub(r'[\s\-\*•●■▪⁃◦◦·]+$', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t.upper()

def match_section_alias(text):
    norm = normalize_text(text)
    for sect, aliases in SECTION_ALIASES.items():
        if norm in aliases:
            return sect
    return None

def is_likely_heading_or_entry(line):
    if match_section_alias(line['text']) is not None:
        return True
    if DATE_RANGE_PATTERN.search(line['text']):
        return True
    if line['is_all_caps'] and len(line['text'].split()) < 6:
        return True
    return False

def group_words_into_lines(words, tolerance=3.0):
    if not words:
        return []

    # Sort words by top, then x0
    words = sorted(words, key=lambda w: (w['top'], w['x0']))
    lines = []
    current_line_words = []
    current_top = None

    for word in words:
        if current_top is None:
            current_top = word['top']
            current_line_words.append(word)
        elif abs(word['top'] - current_top) <= tolerance:
            current_line_words.append(word)
        else:
            lines.append(current_line_words)
            current_line_words = [word]
            current_top = word['top']

    if current_line_words:
        lines.append(current_line_words)

    cv_lines = []
    for line_idx, line_words in enumerate(lines):
        line_words = sorted(line_words, key=lambda w: w['x0'])
        text = " ".join(w['text'] for w in line_words).strip()
        if not text:
            continue
        x0 = line_words[0]['x0']
        x1 = line_words[-1]['x1']
        top = sum(w['top'] for w in line_words) / len(line_words)

        bullet_chars = ('•', '●', '■', '▪', '⁃', '◦', '·')
        is_bullet = text.startswith(bullet_chars) or (text.startswith('-') and not text.startswith('--')) or (text.startswith('*') and not text.startswith('**'))
        is_all_caps = any(c.isalpha() for c in text) and text.isupper()

        cv_lines.append({
            "text": text,
            "page": 1,
            "line_no": line_idx + 1,
            "x0": x0,
            "x1": x1,
            "top": top,
            "is_bullet": is_bullet,
            "is_all_caps": is_all_caps,
            "indent_level": x0
        })
    return cv_lines

def join_wrapped_bullets(lines):
    joined = []
    for line in lines:
        if not joined:
            joined.append(line)
            continue

        prev = joined[-1]
        is_prev_bullet = prev.get('is_bullet', False) or prev.get('is_bullet_continuation', False)
        is_curr_bullet = line.get('is_bullet', False)

        is_indented = line['x0'] >= prev['x0'] - 5

        if is_prev_bullet and not is_curr_bullet and not is_likely_heading_or_entry(line) and is_indented:
            prev['text'] = prev['text'] + " " + line['text']
            prev['x1'] = max(prev['x1'], line['x1'])
            prev['is_bullet_continuation'] = True
            if 'line_end' not in prev:
                prev['line_start'] = prev.get('line_start', prev['line_no'])
            prev['line_end'] = line['line_no']
        else:
            line['is_bullet_continuation'] = False
            joined.append(line)
    return joined

def parse_pdf_to_json(pdf_path):
    """
    Extracts text from a given PDF, structures it into layout-aware lines,
    merges bullets, and segments it into sections based on explicit or inferred headings.
    """
    extracted_text = ""
    cv_lines = []
    total_line_counter = 1

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                page_num = page_idx + 1
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"

                words = page.extract_words()
                if words:
                    page_lines = group_words_into_lines(words)
                    for line in page_lines:
                        line["page"] = page_num
                        line["line_no"] = total_line_counter
                        total_line_counter += 1
                        cv_lines.append(line)
                else:
                    if text:
                        for raw_line in text.splitlines():
                            stripped = raw_line.strip()
                            if not stripped:
                                continue
                            bullet_chars = ('•', '●', '■', '▪', '⁃', '◦', '·')
                            is_bullet = stripped.startswith(bullet_chars) or (stripped.startswith('-') and not stripped.startswith('--')) or (stripped.startswith('*') and not stripped.startswith('**'))
                            is_all_caps = any(c.isalpha() for c in stripped) and stripped.isupper()
                            cv_lines.append({
                                "text": stripped,
                                "page": page_num,
                                "line_no": total_line_counter,
                                "x0": 0.0,
                                "x1": 0.0,
                                "top": total_line_counter * 12.0,
                                "is_bullet": is_bullet,
                                "is_all_caps": is_all_caps,
                                "indent_level": 0.0
                            })
                            total_line_counter += 1

        processed_lines = join_wrapped_bullets(cv_lines)

        heading_indices = []
        for i, line in enumerate(processed_lines):
            if not line['is_bullet'] and len(line['text'].split()) <= 6:
                sect = match_section_alias(line['text'])
                if sect:
                    heading_indices.append((i, sect, "explicit_heading", 0.98))

        is_inferred = False
        if not heading_indices:
            is_inferred = True
            for i, line in enumerate(processed_lines):
                if line['is_bullet'] or len(line['text'].split()) > 8:
                    continue
                text_lower = line['text'].lower()
                if "education" in text_lower or "academic" in text_lower:
                    heading_indices.append((i, "education", "inferred_content", 0.70))
                elif "experience" in text_lower or "work history" in text_lower or "employment" in text_lower:
                    heading_indices.append((i, "experience", "inferred_content", 0.70))
                elif "projects" in text_lower:
                    heading_indices.append((i, "projects", "inferred_content", 0.70))
                elif "skills" in text_lower or "qualifications" in text_lower:
                    heading_indices.append((i, "summary_qualifications", "inferred_content", 0.70))
            heading_indices = sorted(list(set(heading_indices)), key=lambda x: x[0])

        structured_sections = []
        structure_warnings = []
        structure_status = "ok"

        if processed_lines:
            if heading_indices:
                first_heading_idx = heading_indices[0][0]
                if first_heading_idx > 0:
                    first_lines = processed_lines[:first_heading_idx]
                    structured_sections.append({
                        "section_id": "contact",
                        "canonical_type": "contact",
                        "display_title": "Contact Information",
                        "title_source": "inferred_content",
                        "confidence": 0.98,
                        "page_start": first_lines[0]['page'],
                        "page_end": first_lines[-1]['page'],
                        "line_start": first_lines[0]['line_no'],
                        "line_end": first_lines[-1]['line_no'],
                        "body_lines": [l['text'] for l in first_lines],
                        "bullets": [
                            {
                                "text": l['text'],
                                "line_start": l.get('line_start', l['line_no']),
                                "line_end": l.get('line_end', l['line_no'])
                            } for l in first_lines if l.get('is_bullet') or l.get('is_bullet_continuation')
                        ],
                        "warnings": []
                    })

                for idx in range(len(heading_indices)):
                    start_line_idx, canonical_type, source_type, conf = heading_indices[idx]
                    end_line_idx = heading_indices[idx+1][0] if idx + 1 < len(heading_indices) else len(processed_lines)

                    heading_line = processed_lines[start_line_idx]
                    content_lines = processed_lines[start_line_idx+1:end_line_idx]

                    p_start = heading_line['page']
                    p_end = content_lines[-1]['page'] if content_lines else p_start
                    l_start = heading_line['line_no']
                    l_end = content_lines[-1]['line_no'] if content_lines else l_start

                    structured_sections.append({
                        "section_id": f"{canonical_type}_{idx}",
                        "canonical_type": canonical_type,
                        "display_title": heading_line['text'],
                        "title_source": source_type,
                        "confidence": conf,
                        "page_start": p_start,
                        "page_end": p_end,
                        "line_start": l_start,
                        "line_end": l_end,
                        "body_lines": [l['text'] for l in content_lines],
                        "bullets": [
                            {
                                "text": l['text'],
                                "line_start": l.get('line_start', l['line_no']),
                                "line_end": l.get('line_end', l['line_no'])
                            } for l in content_lines if l.get('is_bullet') or l.get('is_bullet_continuation')
                        ],
                        "warnings": []
                    })
            else:
                contact_end = 0
                for i, line in enumerate(processed_lines[:5]):
                    if "@" in line['text'] or "linkedin.com" in line['text'].lower() or "github.com" in line['text'].lower():
                        contact_end = i + 1
                if contact_end == 0 and len(processed_lines) > 2:
                    contact_end = 2

                if contact_end > 0:
                    contact_lines = processed_lines[:contact_end]
                    structured_sections.append({
                        "section_id": "contact",
                        "canonical_type": "contact",
                        "display_title": "Contact Information",
                        "title_source": "inferred_content",
                        "confidence": 0.98,
                        "page_start": contact_lines[0]['page'],
                        "page_end": contact_lines[-1]['page'],
                        "line_start": contact_lines[0]['line_no'],
                        "line_end": contact_lines[-1]['line_no'],
                        "body_lines": [l['text'] for l in contact_lines],
                        "bullets": [],
                        "warnings": []
                    })

                profile_lines = processed_lines[contact_end:]
                if profile_lines:
                    structured_sections.append({
                        "section_id": "profile_default",
                        "canonical_type": "profile",
                        "display_title": "PROFILE",
                        "title_source": "inferred_content",
                        "confidence": 0.50,
                        "page_start": profile_lines[0]['page'],
                        "page_end": profile_lines[-1]['page'],
                        "line_start": profile_lines[0]['line_no'],
                        "line_end": profile_lines[-1]['line_no'],
                        "body_lines": [l['text'] for l in profile_lines],
                        "bullets": [
                            {
                                "text": l['text'],
                                "line_start": l.get('line_start', l['line_no']),
                                "line_end": l.get('line_end', l['line_no'])
                            } for l in profile_lines if l.get('is_bullet') or l.get('is_bullet_continuation')
                        ],
                        "warnings": ["Entire content fell back to Profile due to missing explicit headings."]
                    })
                structure_warnings.append("No section headings could be identified. The entire CV was grouped into a default Profile section.")
                structure_status = "needs_review"

        present_types = {sec["canonical_type"] for sec in structured_sections}
        major_types = {"profile", "experience", "education"}
        missing_major = major_types - present_types
        if missing_major:
            structure_warnings.append(f"Missing major sections: {', '.join(missing_major)}")
            structure_status = "needs_review"

        total_lines = len(processed_lines)
        for sec in structured_sections:
            sec_lines = len(sec["body_lines"]) + 1
            if total_lines > 0 and (sec_lines / total_lines) > 0.60:
                structure_warnings.append(f"Section '{sec['display_title']}' consumes {sec_lines/total_lines:.1%} of the CV (exceeds 60%).")
                structure_status = "needs_review"
            if sec["confidence"] < 0.75:
                structure_warnings.append(f"Section '{sec['display_title']}' has low classification confidence ({sec['confidence']}).")
                structure_status = "needs_review"

        cv_data = {
            "source_file": os.path.basename(pdf_path),
            "raw_text": extracted_text.strip(),
            "parser_version": "sectionizer_v1",
            "structure_status": structure_status,
            "structured_sections": structured_sections,
            "structure_warnings": structure_warnings
        }
        return cv_data
    except Exception as e:
        print(f"Error parsing {pdf_path}: {e}")
        return {
            "source_file": os.path.basename(pdf_path),
            "raw_text": "",
            "parser_version": "sectionizer_v1",
            "structure_status": "failed",
            "structured_sections": [],
            "structure_warnings": [f"Error occurred during parsing: {str(e)}"]
        }

def process_all_pdfs(docs_dir="docs", output_dir="docs/json_exports"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(docs_dir):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(docs_dir, filename)
            print(f"Processing {filename}...")
            data = parse_pdf_to_json(pdf_path)
            if data:
                output_filename = filename.replace(".pdf", ".json")
                output_path = os.path.join(output_dir, output_filename)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
                print(f"Saved JSON to {output_path}")

if __name__ == "__main__":
    process_all_pdfs()
