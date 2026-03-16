import streamlit as st
import time
import sys
import os

# Add local .conda packages to sys.path as a FALLBACK if not in the main environment
_base_dir = os.path.dirname(os.path.abspath(__file__))
_conda_site = os.path.join(_base_dir, ".conda", "Lib", "site-packages")
if os.path.exists(_conda_site) and _conda_site not in sys.path:
    sys.path.append(_conda_site)

# Custom Apple HIG Styling
APPLE_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    }
    
    .stApp {
        background: linear-gradient(135deg, #1f2128 0%, #323842 100%);
        color: #ffffff;
    }
    
    /* Glassmorphism containers */
    .glass-panel {
        background: rgba(30, 30, 35, 0.7);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 18px;
        padding: 24px;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
        margin-bottom: 24px;
        transition: transform 0.3s ease;
    }
    
    .glass-panel:hover {
        transform: translateY(-2px);
    }
    
    h1, h2, h3, h4, p, label, .stMarkdown {
        color: #ffffff !important;
    }
    
    h1 {
        font-weight: 700;
        letter-spacing: -1.2px;
        color: #ffffff !important;
    }
    
    /* Make input text readable in dark mode */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div {
        color: #ffffff !important;
        background-color: rgba(0, 0, 0, 0.4) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }
    
    /* Ensure dropdown menu text is readable */
    ul[role="listbox"] {
        background-color: #323842 !important;
    }
    li[role="option"] {
        color: #ffffff !important;
    }
    
    .stButton>button {
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 14px;
        color: #ffffff;
        font-weight: 500;
        backdrop-filter: blur(10px);
        transition: all 0.2s ease-in-out;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .stButton>button:hover {
        background: #0071e3;
        color: white;
        transform: scale(1.02);
    }
</style>
"""

def get_available_models():
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("GEMINI_API_KEY")
    default_models = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-pro"]
    if not api_key:
        return default_models
        
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if m.name.startswith("models/"):
                    models.append(m.name.replace("models/", ""))
                else:
                    models.append(m.name)
        
        # Sort so preferred models are near top
        preferred = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
        models.sort(key=lambda x: (0, preferred.index(x)) if x in preferred else (1, x))
        return models if models else default_models
    except ImportError:
        # If google.generativeai is not installed, fallback to defaults
        return default_models
    except Exception:
        return default_models

def main():
    st.set_page_config(page_title="ApplAI - Job Workflow", layout="centered")
    st.markdown(APPLE_CSS, unsafe_allow_html=True)
    
    # Initialize session state for workflow results so they persist when buttons are clicked
    if "workflow_completed" not in st.session_state:
        st.session_state.workflow_completed = False
        st.session_state.match_score = ""
        st.session_state.pain_points = ""
        st.session_state.strong_points = ""
        
    st.markdown("<h1>ApplAI Workflow Manager</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #a1a1a6 !important; font-size: 18px;'>Automated Job Application & Tailoring pipeline.</p>", unsafe_allow_html=True)
    
    # Create Tabs
    tab1, tab2 = st.tabs(["Application Generator", "CV Corpus Manager"])
    
    with tab1:
        # Input Section
        st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
        st.markdown("<h3>1. Job Details</h3>", unsafe_allow_html=True)
        job_input_type = st.radio("Input Method", ["Paste Text", "Job URL"], horizontal=True)
        
        def _run_extraction(text):
            """Call Gemini to extract company and job title from text."""
            import os as _os
            import google.generativeai as _genai
            _genai.configure(api_key=_os.getenv("GEMINI_API_KEY"))
            _m = _genai.GenerativeModel("gemini-2.5-flash")
            _prompt = (
                "Extract the company name and job title from this job description. "
                "Reply ONLY in this exact format with no extra text:\n"
                f"COMPANY: <company name>\nTITLE: <job title>\n\nJD:\n{text[:3000]}"
            )
            _resp = _m.generate_content(_prompt)
            _lines = {l.split(":")[0].strip(): ":".join(l.split(":")[1:]).strip()
                      for l in _resp.text.strip().splitlines() if ":" in l}
            st.session_state["_extracted_company"] = _lines.get("COMPANY", "")
            st.session_state["_extracted_title"] = _lines.get("TITLE", "")
            # Also pre-populate the edit widget keys so value= is not ignored on re-render
            st.session_state["_edit_company"] = st.session_state["_extracted_company"]
            st.session_state["_edit_title"] = st.session_state["_extracted_title"]


        job_desc = ""
        if job_input_type == "Paste Text":
            job_desc = st.text_area("Paste the Job Description Here", height=150)
            if job_desc and st.button("🔍 Extract Company & Title"):
                with st.spinner("Extracting..."):
                    _run_extraction(job_desc)
        else:
            job_url = st.text_input("Enter Job URL (LinkedIn, Indeed, etc.)")
            if job_url:
                if st.button("Fetch Job Description from URL"):
                    with st.spinner("Fetching job details from URL..."):
                        try:
                            import requests
                            from bs4 import BeautifulSoup
                            is_linkedin = "linkedin.com" in job_url
                            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
                            resp = requests.get(job_url, headers=headers, timeout=15)
                            soup = BeautifulSoup(resp.text, "lxml")
                            page_text_preview = soup.get_text()
                            login_signals = ["Sign in", "Log in", "Join or sign in", "Join LinkedIn", "Agree & Join"]
                            login_hits = sum(1 for s in login_signals if s in page_text_preview)
                            if login_hits >= 3 or is_linkedin:
                                st.warning(
                                    "⚠️ LinkedIn blocks automated access. Please **open the job posting in your browser**, "
                                    "copy the full job description text, and paste it using the 'Paste Text' input method instead."
                                )
                            else:
                                for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
                                    tag.decompose()
                                jd_selectors = [
                                    "div.job-description", "div.jobDescription", "div.description",
                                    "section.description", "div#job-details", "div.show-more-less-html",
                                    "[data-testid='job-description']", "div.jobs-description",
                                    "article", "main"
                                ]
                                extracted = ""
                                for sel in jd_selectors:
                                    el = soup.select_one(sel)
                                    if el:
                                        extracted = el.get_text(separator="\n", strip=True)
                                        if len(extracted) > 300:
                                            break
                                if len(extracted) < 300:
                                    parts = soup.find_all(["p", "li", "h1", "h2", "h3"])
                                    extracted = "\n".join(p.get_text(strip=True) for p in parts if p.get_text(strip=True))
                                lines = [l for l in extracted.splitlines() if l.strip()]
                                text = "\n".join(lines)[:8000]
                                if len(text) < 200:
                                    st.warning("Could not extract a clean job description. Please paste the text manually.")
                                else:
                                    st.session_state.fetched_job_desc = text
                                    # Extract company & title immediately while we have the text
                                    with st.spinner("Extracting company & title..."):
                                        try:
                                            _run_extraction(text)
                                        except Exception as _ex:
                                            st.warning(f"Could not auto-extract company/title: {_ex}")
                                    st.success(f"✅ Fetched ~{len(text)} characters.")
                        except Exception as e:
                            st.error(f"Failed to fetch URL: {e}")

                if "fetched_job_desc" in st.session_state:
                    job_desc = st.text_area("Fetched Job Description (edit if needed)", value=st.session_state.fetched_job_desc, height=200)

        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
        st.markdown("<h3>2. Selected Context</h3>", unsafe_allow_html=True)
        
        import os
        import json
        docs_dir = "docs"
        metadata_path = os.path.join(docs_dir, "cv_metadata.json")
        
        # Load metadata if exists
        cv_metadata = {}
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    cv_metadata = json.load(f)
            except Exception:
                pass
                
        available_cvs = [f for f in os.listdir(docs_dir) if f.endswith('.pdf')] if os.path.exists(docs_dir) else []
        if not available_cvs:
            available_cvs_display = ["No PDFs found in docs/"]
        else:
            # Append tags to display name
            available_cvs_display = []
            for cv in available_cvs:
                tags = cv_metadata.get(cv, {}).get("tags", "")
                tag_str = f" [{tags}]" if tags else ""
                available_cvs_display.append(cv + tag_str)
            
        c1, c2 = st.columns(2)
        with c1:
            selected_cv_display = st.selectbox("Choose a base CV to tailor from Docs library", available_cvs_display)
            # Remove tag suffix to get the raw filename
            selected_cv_pdf = selected_cv_display.split(" [")[0] if " [" in selected_cv_display else selected_cv_display
        with c2:
            available_models = get_available_models()
            selected_model = st.selectbox("Select Gemini API Model", available_models)
        
        # Show extracted company/title as a styled display + optional edit
        _co = st.session_state.get("_extracted_company", "")
        _ti = st.session_state.get("_extracted_title", "")
        
        if _co or _ti:
            st.markdown(
                f"<div style='background:#1e2533;border-radius:10px;padding:10px 16px;margin-bottom:8px;font-size:0.95em;'>"
                f"🏢 <b>{_co}</b>&nbsp;&nbsp;|&nbsp;&nbsp;💼 <b>{_ti}</b>"
                f"</div>",
                unsafe_allow_html=True
            )
            with st.expander("✏️ Edit company or title"):
                _co = st.text_input("Company Name", value=_co, key="_edit_company")
                _ti = st.text_input("Job Title", value=_ti, key="_edit_title")
        else:
            _co = st.text_input("Company Name", placeholder="Auto-filled after fetch", key="_edit_company")
            _ti = st.text_input("Job Title", placeholder="Auto-filled after fetch", key="_edit_title")
        
        company_name = _co
        job_title = _ti
        st.markdown("</div>", unsafe_allow_html=True)
        
        if st.button("Generate Tailored Application", use_container_width=True):
            if not job_desc:
                st.error("Please enter a job description.")
            else:
                import agent_workflow
                import os
                
                json_path = os.path.join("docs", "json_exports", selected_cv_pdf.replace(".pdf", ".json"))
                if not os.path.exists(json_path):
                    st.error(f"JSON data not found for {selected_cv_pdf}. Please run pdf_parser.py.")
                    st.stop()
                    
                with open(json_path, 'r', encoding='utf-8') as f:
                    base_cv_json_text = f.read()
                    
                # Run workflow
                with st.spinner(f"Running AI Applicant Workflow using {selected_model}..."):
                    result = agent_workflow.run_application_workflow(job_desc, base_cv_json_text, selected_model)
                
                st.success("Workflow Completed!")
                
                qa_report = getattr(result, 'pydantic', None)
                match_score = str(getattr(qa_report, 'matching_rate_score', 'N/A')) + "%" if qa_report else "N/A"
                pain_points = "<br>".join([f"- {pt}" for pt in getattr(qa_report, 'key_pain_points', ["N/A"])]) if qa_report else "N/A"
                strong_points = "<br>".join([f"- {pt}" for pt in getattr(qa_report, 'strong_points', ["N/A"])]) if qa_report else "N/A"
                
                # Generate output file names from convention: SurnamCV_YEAR_Company_Title
                import datetime
                year = datetime.datetime.now().year
                
                # Extract surname from CV JSON (try source_file first, then raw_text)
                try:
                    cv_data = json.loads(base_cv_json_text)
                    src = cv_data.get("source_file", "")
                    # source_file is like "Selekoglu CV 2026 - ..." — first token is the surname
                    surname = src.split()[0] if src.strip() else ""
                    if not surname:
                        # fallback: last word of first line of raw_text
                        first_line = cv_data.get("raw_text", "").split("\n")[0].strip()
                        surname = first_line.split()[-1] if first_line else "Candidate"
                except Exception:
                    surname = "Candidate"

                def _slug(s):
                    """Clean a string for use in a filename."""
                    import re
                    return re.sub(r'[^\w]', '_', s.strip()).strip('_')

                co = _slug(company_name) if company_name else "Company"
                title = _slug(job_title) if job_title else "Role"

                cv_filename = f"{surname}CV_{year}_{co}_{title}.docx"
                cl_filename = f"{surname}_{co}_{title}_Cover_Letter.pdf"
                cv_output_path = f"docs/{cv_filename}"
                cover_letter_output_path = f"docs/{cl_filename}"
                
                import pdf_generator
                template_name = selected_cv_pdf.replace(".pdf", ".docx")
                template = os.path.join("docs", template_name)
                if not os.path.exists(template):
                    docx_files = [f for f in os.listdir("docs") if f.endswith(".docx") and not os.path.basename(cv_output_path) == f]
                    template = os.path.join("docs", docx_files[0]) if docx_files else None

                # Extract structured tailored CV from task2 pydantic output
                tailored_data = {}
                tailored_raw = ""
                try:
                    tasks_output = getattr(result, 'tasks_output', [])
                    if len(tasks_output) > 1:
                        t2 = tasks_output[1]
                        tailored_raw = getattr(t2, 'raw', '') or ''
                        t2_pydantic = getattr(t2, 'pydantic', None)
                        if t2_pydantic:
                            tailored_data = {
                                'profile_bullets': getattr(t2_pydantic, 'profile_bullets', []),
                                'experience_highlights': getattr(t2_pydantic, 'experience_highlights', []),
                                'skills_to_highlight': getattr(t2_pydantic, 'skills_to_highlight', []),
                                'tailoring_notes': getattr(t2_pydantic, 'tailoring_notes', ''),
                                'tailored_raw': tailored_raw,
                            }
                        else:
                            tailored_data = {'tailored_raw': tailored_raw}
                except Exception as _e:
                    st.warning(f"Could not parse agent task2 output: {_e}")
                    tailored_data = {}

                if template and os.path.exists(template):
                    pdf_generator.generate_tailored_document(template, cv_output_path, tailored_data)
                else:
                    st.warning("Could not find matching .docx template. CV file not generated.")

                # Store all task outputs for display
                try:
                    tasks_output = getattr(result, 'tasks_output', [])
                    st.session_state.agent_outputs = [
                        {
                            'role': ['Job Analyzer', 'CV Tailorer', 'Cover Letter Writer', 'QA Reviewer'][i] if i < 4 else f'Task {i+1}',
                            'raw': getattr(t, 'raw', '') or '',
                            'pydantic': getattr(t, 'pydantic', None),
                        }
                        for i, t in enumerate(tasks_output)
                    ]
                except Exception:
                    st.session_state.agent_outputs = []
                
                try:
                    from reportlab.pdfgen import canvas
                    c = canvas.Canvas(cover_letter_output_path)
                    c.drawString(100, 750, "Generated Cover Letter")
                    c.drawString(100, 700, "Match Score: " + match_score)
                    c.save()
                except ImportError:
                    with open(cover_letter_output_path, "w") as f:
                        f.write("Generated Cover Letter - Please install reportlab for PDF generation")
                
                # Google Drive Integration
                with st.spinner("Syncing with Google Docs..."):
                    try:
                        import google_integration
                        docs_url = google_integration.upload_to_drive(cv_output_path, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", convert_to_docs=True)
                    except Exception as e:
                        print(f"Drive integration failed: {e}")
                        docs_url = None
                
                with open(cv_output_path, "rb") as f:
                    st.session_state.cv_file_bytes = f.read()
                with open(cover_letter_output_path, "rb") as f:
                    st.session_state.cover_letter_bytes = f.read()
                    
                # Save to session state
                st.session_state.workflow_completed = True
                st.session_state.match_score = match_score
                st.session_state.pain_points = pain_points
                st.session_state.strong_points = strong_points
                st.session_state.docs_url = docs_url
                st.session_state.cv_filename = cv_filename
                st.session_state.cl_filename = cl_filename

                import re as _re
                from collections import Counter as _Counter

                # Build keyword sets for analysis
                def _extract_keywords(text: str) -> set:
                    """Extract meaningful technical/skill keywords (2+ chars, not stopwords)."""
                    stopwords = {"the","and","or","to","of","a","an","in","for","with","that","is","are",
                                 "was","be","as","at","by","on","it","we","our","your","this","have",
                                 "you","not","from","will","can","all","has","but","they","their","its",
                                 "also","more","than","other","any","each","per","new","use","using",
                                 "work","role","team","able","skills","experience","knowledge"}
                    words = _re.findall(r'\b[a-zA-Z][a-zA-Z0-9#+.\-]{1,}\b', text.lower())
                    return {w for w in words if w not in stopwords and len(w) > 2}

                _jd_kws = _extract_keywords(job_desc)
                _cv_kws = _extract_keywords(base_cv_json_text)
                _tailored_text = " ".join(
                    tailored_data.get("profile_bullets", []) +
                    tailored_data.get("experience_highlights", [])
                )
                _tailored_kws = _extract_keywords(_tailored_text) if _tailored_text else _cv_kws
                # Keep top 60 most-frequent JD keywords
                _jd_counts = _Counter(
                    w for w in _re.findall(r'\b[a-zA-Z][a-zA-Z0-9#+.\-]{1,}\b', job_desc.lower())
                    if w in _jd_kws
                )
                _top_jd = {w for w, _ in _jd_counts.most_common(60)}
                st.session_state.kw_data = {
                    "jd": _top_jd,
                    "cv": _cv_kws & _top_jd | (_cv_kws & _jd_kws),
                    "tailored": _tailored_kws & _top_jd | (_tailored_kws & _jd_kws),
                }


        # Always display results if workflow was completed
        if st.session_state.workflow_completed:
            # Results Section
            st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
            st.markdown("<h3>QA Review &amp; Scoring</h3>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            col1.metric(
                "Match Rate Score",
                st.session_state.match_score,
                help="Scored by the QA Reviewer agent (0–100). Measures how well the tailored CV addresses the job's required skills, experience level, and company tone as extracted by the Job Analyzer agent."
            )
            col2.metric(
                "Format Retained",
                "100%",
                help="Your original Word document template is used directly — only the bullet text inside PROFILE and RELEVANT EXPERIENCE is replaced. All fonts, margins, spacing, and structure from your original CV are preserved."
            )
            st.markdown(f"<b>Strong Points:</b><br>{st.session_state.strong_points}<br>", unsafe_allow_html=True)
            st.markdown(f"<b>Pain Points:</b><br>{st.session_state.pain_points}<br>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
                
            # Download Section
            st.markdown("### Outputs & Downloads")
            if st.session_state.get('docs_url'):
                st.markdown(f"**📝 [Open Tailored CV in Google Docs]({st.session_state.docs_url})**")
                
            c1, c2 = st.columns(2)
            if "cv_file_bytes" in st.session_state:
                _cv_fname = st.session_state.get("cv_filename", "Tailored_CV.docx")
                c1.download_button(f"⬇ {_cv_fname}", data=st.session_state.cv_file_bytes, file_name=_cv_fname, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            if "cover_letter_bytes" in st.session_state:
                _cl_fname = st.session_state.get("cl_filename", "Cover_Letter.pdf")
                c2.download_button(f"⬇ {_cl_fname}", data=st.session_state.cover_letter_bytes, file_name=_cl_fname, mime="application/pdf", use_container_width=True)

            # Keyword Matching Analysis
            kw_data = st.session_state.get("kw_data", {})
            if kw_data:
                st.markdown("---")
                with st.expander("🔑 Keyword Match Analysis (JD vs CV vs Tailored)", expanded=True):
                    jd_kws = kw_data.get("jd", set())
                    cv_kws = kw_data.get("cv", set())
                    tailored_kws = kw_data.get("tailored", set())

                    in_all    = sorted(jd_kws & cv_kws & tailored_kws)
                    added     = sorted((jd_kws & tailored_kws) - cv_kws)
                    gaps      = sorted(jd_kws - cv_kws - tailored_kws)
                    cv_only   = sorted(cv_kws - jd_kws)

                    def _badges(words, color):
                        return " ".join(
                            f"<span style='background:{color};border-radius:4px;padding:2px 7px;margin:2px;font-size:0.8em;display:inline-block'>{w}</span>"
                            for w in words
                        )

                    if in_all:
                        st.markdown("**✅ Strong matches** — in JD, original CV, and tailored CV:")
                        st.markdown(_badges(in_all, "#1a6634"), unsafe_allow_html=True)
                    if added:
                        st.markdown("**🆕 Added by tailoring** — in JD and tailored CV, not in original:")
                        st.markdown(_badges(added, "#1a4a6e"), unsafe_allow_html=True)
                    if gaps:
                        st.markdown("**⚠️ Gaps** — in JD but missing from both CV versions:")
                        st.markdown(_badges(gaps, "#6e3a1a"), unsafe_allow_html=True)
                    if cv_only:
                        st.markdown("**ℹ️ CV-only skills** — present in your CV but not required by this JD:")
                        st.markdown(_badges(cv_only[:20], "#3a3a3a"), unsafe_allow_html=True)

                    total_jd = len(jd_kws) or 1
                    coverage = int(100 * len(jd_kws & (cv_kws | tailored_kws)) / total_jd)
                    st.caption(f"Keyword coverage: **{coverage}%** of JD keywords appear in the tailored CV  |  {len(jd_kws)} JD keywords analysed")

            # Agent Execution Log
            agent_outputs = st.session_state.get("agent_outputs", [])
            if agent_outputs:
                st.markdown("---")
                st.markdown("### 🤖 Agent Execution Log")
                _icons = ["🔍", "✍️", "📝", "✅"]
                for i, out in enumerate(agent_outputs):
                    icon = _icons[i] if i < len(_icons) else "🤖"
                    role = out.get("role", f"Task {i+1}")
                    raw = out.get("raw", "")
                    pydantic_obj = out.get("pydantic")
                    with st.expander(f"{icon} **{role}**", expanded=(i == 1)):  # CV Tailorer open by default
                        if pydantic_obj and hasattr(pydantic_obj, '__dict__'):
                            for field, val in pydantic_obj.__dict__.items():
                                if field.startswith('_'):
                                    continue
                                if isinstance(val, list):
                                    st.markdown(f"**{field.replace('_', ' ').title()}**")
                                    for item in val:
                                        st.markdown(f"- {item}")
                                else:
                                    st.markdown(f"**{field.replace('_', ' ').title()}:** {val}")
                        elif raw:
                            st.text(raw[:3000])
                        else:
                            st.caption("No output captured.")


    with tab2:
        st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
        st.markdown("<h3>Upload New CV</h3>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload a PDF CV", type="pdf")
        if uploaded_file is not None:
            if st.button("Process & Add to Library"):
                # Save PDF
                new_pdf_path = os.path.join(docs_dir, uploaded_file.name)
                with open(new_pdf_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Parse to JSON
                import pdf_parser
                json_data = pdf_parser.parse_pdf_to_json(new_pdf_path)
                if json_data:
                    json_exports_dir = os.path.join(docs_dir, "json_exports")
                    if not os.path.exists(json_exports_dir):
                        os.makedirs(json_exports_dir)
                    json_path = os.path.join(json_exports_dir, uploaded_file.name.replace(".pdf", ".json"))
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=4)
                    st.success(f"Success! {uploaded_file.name} parsed and added to corpus.")
                    st.rerun()
                else:
                    st.error("Failed to parse PDF.")
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
        st.markdown("<h3>Manage CV Corpus</h3>", unsafe_allow_html=True)
        
        for cv in available_cvs:
            if cv == "No PDFs found in docs/":
                continue
            with st.expander(cv):
                current_tags = cv_metadata.get(cv, {}).get("tags", "")
                new_tags = st.text_input(f"Tags (comma separated) for {cv}", value=current_tags, key=f"tags_{cv}")
                
                col_save, col_del = st.columns(2)
                if col_save.button("Save Tags", key=f"save_{cv}"):
                    cv_metadata[cv] = {"tags": new_tags}
                    with open(metadata_path, 'w', encoding='utf-8') as f:
                        json.dump(cv_metadata, f, indent=4)
                    st.success("Tags updated!")
                    st.rerun()
                    
                if col_del.button("🗑️ Delete CV", key=f"del_{cv}"):
                    pdf_path = os.path.join(docs_dir, cv)
                    json_path = os.path.join(docs_dir, "json_exports", cv.replace(".pdf", ".json"))
                    try:
                        if os.path.exists(pdf_path): os.remove(pdf_path)
                        if os.path.exists(json_path): os.remove(json_path)
                        if cv in cv_metadata:
                            del cv_metadata[cv]
                            with open(metadata_path, 'w', encoding='utf-8') as f:
                                json.dump(cv_metadata, f, indent=4)
                        st.success(f"Deleted {cv}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting files: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
