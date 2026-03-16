import os
from docx import Document


def generate_tailored_document(template_path: str, output_path: str, tailored_data: dict):
    """
    Copies the Word template and injects the agent's tailored CV content.
    tailored_data may contain structured pydantic fields:
      - 'profile_bullets': list[str] from TailoredCV pydantic model
      - 'experience_highlights': list[str] from TailoredCV pydantic model
    Or fallback:
      - 'tailored_raw': raw text output from the CV tailoring agent
    """
    if not os.path.exists(template_path):
        print(f"Template not found: {template_path}")
        return False

    doc = Document(template_path)

    profile_bullets = tailored_data.get("profile_bullets", [])
    experience_highlights = tailored_data.get("experience_highlights", [])
    tailored_raw = tailored_data.get("tailored_raw", "")

    # If we have clean structured bullets, use them directly
    if profile_bullets:
        _replace_section_bullets(doc, "PROFILE", profile_bullets)
    elif tailored_raw:
        # fallback: extract profile from raw text
        extracted = _extract_section(tailored_raw, ["profile", "summary", "objective"])
        if extracted:
            lines = [l.strip().lstrip("-•*").strip() for l in extracted.splitlines() if l.strip()]
            _replace_section_bullets(doc, "PROFILE", [l for l in lines if len(l) > 5])

    if experience_highlights:
        _replace_section_bullets(doc, "RELEVANT EXPERIENCE", experience_highlights)
    elif tailored_raw:
        extracted = _extract_section(tailored_raw, ["experience", "relevant experience", "work experience"])
        if extracted:
            lines = [l.strip().lstrip("-•*").strip() for l in extracted.splitlines() if l.strip()]
            _replace_section_bullets(doc, "RELEVANT EXPERIENCE", [l for l in lines if len(l) > 5])

    try:
        doc.save(output_path)
        print(f"Successfully generated tailored CV: {output_path}")
        return True
    except Exception as e:
        print(f"Error saving document: {e}")
        return False


def _extract_section(text: str, keywords: list) -> str:
    """Extract a named section from agent raw text output."""
    lines = text.splitlines()
    in_section = False
    section_lines = []
    for line in lines:
        line_lower = line.strip().lower()
        if any(kw in line_lower for kw in keywords) and len(line.strip()) < 60:
            in_section = True
            continue
        if in_section:
            if (line.strip().isupper() and len(line.strip()) > 3) or line.strip().startswith("##"):
                break
            section_lines.append(line)
    return "\n".join(section_lines).strip()


def _replace_section_bullets(doc, section_header: str, new_bullets: list):
    """
    Find a section header in the doc and replace the following
    bullet paragraphs with new_bullets, preserving run formatting.
    """
    header_idx = None
    for i, para in enumerate(doc.paragraphs):
        if section_header.upper() in para.text.upper() and len(para.text.strip()) < 60:
            header_idx = i
            break

    if header_idx is None:
        print(f"Section '{section_header}' not found in document.")
        return

    # Collect ONLY actual bullet/list paragraphs after the header
    # Skip bold header paragraphs (job titles, company names, dates)
    bullet_indices = []
    for i in range(header_idx + 1, len(doc.paragraphs)):
        para = doc.paragraphs[i]
        text = para.text.strip()
        # Stop at the next all-caps section header (e.g. EDUCATION, SKILLS)
        if text and text.upper() == text and len(text) < 60 and len(text) > 3 and i > header_idx + 1:
            break
        if not text:
            continue
        # Detect if this paragraph is a bold job-title/company header — skip those
        is_all_bold = para.runs and all(run.bold for run in para.runs if run.text.strip())
        is_list_style = para.style.name.lower().startswith("list")
        # Only replace list-style bullets or non-bold body paragraphs
        if is_list_style or (not is_all_bold):
            bullet_indices.append(i)
        if len(bullet_indices) >= 12:
            break

    if not bullet_indices:
        print(f"No bullet paragraphs found under '{section_header}'.")
        return

    print(f"Replacing {min(len(bullet_indices), len(new_bullets))} bullets under '{section_header}'")

    # Replace paragraph text in-place, preserving run formatting
    for doc_idx, new_text in zip(bullet_indices, new_bullets):
        para = doc.paragraphs[doc_idx]
        if para.runs:
            # Capture formatting from first run
            first_run = para.runs[0]
            font_name = first_run.font.name
            font_size = first_run.font.size
            bold = first_run.bold
            italic = first_run.italic
            # Clear all runs
            for run in para.runs:
                run.text = ""
            # Set new text in first run with preserved formatting
            first_run.text = new_text
            if font_name:
                first_run.font.name = font_name
            if font_size:
                first_run.font.size = font_size
            first_run.bold = bold
            first_run.italic = italic
        else:
            para.text = new_text


if __name__ == "__main__":
    mock_data = {
        "profile_bullets": [
            "Results-driven Software Developer with 3+ years experience in full-stack development and AI integration.",
            "Proven expertise in Python, JavaScript, and REST APIs with a focus on automation and data pipelines.",
            "Collaborates effectively in Agile teams to deliver high-quality, production-grade web applications.",
        ],
        "experience_highlights": [
            "Implemented JavaScript middleware services and REST API integrations enabling seamless data exchange.",
            "Built event-driven automation pipelines using JSON payloads and HTTP endpoints.",
            "Developed and maintained automation scripts to validate and synchronize high-volume operational data.",
        ],
    }
    base_template = "docs/Selekoglu CV 2026 - Public Sector (Algonquin Email).docx"
    generate_tailored_document(base_template, "docs/Tailored_Output.docx", mock_data)
