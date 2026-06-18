from __future__ import annotations

import os
import re
import textwrap

import pdf_generator

try:
    import google_integration
except ImportError:  # pragma: no cover - optional integration
    google_integration = None


def compile_result_artifacts(result, workflow_inputs: dict) -> dict:
    surname = result.canonical_cv.full_name.split()[-1] if result.canonical_cv.full_name else "Candidate"
    safe_co = re.sub(r"\W+", "_", workflow_inputs.get("company_name", "Co"))
    cv_path = f"docs/{surname}_CV_Tailored_{safe_co}.docx"
    cl_path = f"docs/{surname}_CL_Tailored_{safe_co}.pdf"

    template = workflow_inputs.get("template_path")
    if not template or not os.path.exists(template):
        docx_files = [f for f in os.listdir("docs")] if os.path.exists("docs") else []
        docx_files = [f for f in docx_files if f.endswith(".docx") and "Tailored" not in f]
        template = os.path.join("docs", docx_files[0]) if docx_files else None

    if template:
        pdf_generator.generate_tailored_document(
            template,
            cv_path,
            {"tailored_output": result.tailored_output, "template_config": workflow_inputs.get("template_config_path")},
            template_config=workflow_inputs.get("template_config_path"),
            max_pages=workflow_inputs.get("max_pages", 2),
        )
    else:
        raise FileNotFoundError("No DOCX template found to generate tailored CV.")

    cl_txt = result.cover_letter or "No cover letter."
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(cl_path, pagesize=letter)
        c.setFont("Helvetica", 11)
        y = 750
        for line in cl_txt.splitlines():
            for wrap in textwrap.wrap(line or " ", width=90):
                c.drawString(60, y, wrap)
                y -= 15
                if y < 50:
                    c.showPage()
                    c.setFont("Helvetica", 11)
                    y = 750
        c.save()
    except Exception:
        with open(cl_path, "w", encoding="utf-8") as f:
            f.write(cl_txt)

    docs_url = None
    if google_integration:
        try:
            docs_url = google_integration.upload_to_drive(
                cv_path,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                convert_to_docs=True,
            )
        except Exception:
            docs_url = None

    with open(cv_path, "rb") as f:
        cv_bytes = f.read()
    with open(cl_path, "rb") as f:
        cl_bytes = f.read()

    return {
        "docs_url": docs_url,
        "cv_path": cv_path,
        "cv_bytes": cv_bytes,
        "cl_path": cl_path,
        "cl_bytes": cl_bytes,
        "cover_letter_text": cl_txt,
    }
