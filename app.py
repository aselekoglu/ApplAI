import streamlit as st
import time
import os
import json
import datetime
import re
import textwrap
import requests
import threading
import html
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Local imports
import agent_workflow
import pdf_generator
import pdf_parser
try:
    import google_integration
except ImportError:
    google_integration = None

load_dotenv()

# =============================================================================
# Premium UI Styles & Animations
# =============================================================================
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
    
    .glass-panel {
        background: rgba(30,30,35,0.7);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 18px;
        padding: 24px;
        box-shadow: 0 8px 32px 0 rgba(31,38,135,0.07);
        margin-bottom: 24px;
    }
    
    .loading-overlay {
        position: fixed;
        top: 0; left: 0; width: 100vw; height: 100vh;
        background: #121216 !important; 
        z-index: 99999;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
    }

    .step-card {
        background: #1e2227;
        border: 1px solid rgba(255,255,255,0.25);
        border-radius: 40px;
        padding: 4.5rem;
        width: 940px;
        max-width: 92vw;
        box-shadow: 0 80px 160px rgba(0,0,0,1.0);
        color: white;
        display: flex;
        flex-direction: column;
    }

    .log-window {
        background: #0d0f12;
        border-radius: 24px;
        padding: 2rem;
        height: 380px;
        overflow-y: auto;
        font-family: 'Fira Code', 'Monaco', monospace;
        font-size: 0.95rem;
        margin-top: 2rem;
        border: 1px solid rgba(255,255,255,0.1);
        line-height: 1.8;
        color: #d1d4d9;
    }

    .log-line { 
        margin-bottom: 14px; 
        color: #e0e4eb; 
        border-left: 4px solid #0071e3; 
        padding-left: 20px; 
        white-space: pre-wrap; 
        word-wrap: break-word; 
    }
    
    .step-header { 
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        margin-bottom: 2rem; 
    }
    
    .step-indicator { 
        background: #0071e3; 
        padding: 14px 28px; 
        border-radius: 20px; 
        font-weight: 700; 
        font-size: 1.1rem; 
        text-transform: uppercase; 
        letter-spacing: 1.2px; 
    }

    .nav-container-fixed {
        margin-top: 45px;
        display: flex;
        gap: 30px;
        justify-content: center;
        width: 100%;
    }
    
    /* Post-Run Log Styles */
    .history-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 1rem;
    }
</style>
"""

def init_state():
    defaults = {
        'workflow_step_history': [],
        'workflow_view_index': -1,
        'workflow_is_running': False,
        'workflow_generator': None,
        'final_workflow_result': None,
        'workflow_completed': False,
        'workflow_inputs': {},
        'cv_metadata': {},
        'match_score': "",
        'pain_points': "",
        'strong_points': "",
        'docs_url': None,
        'cv_filename': "",
        'cl_filename': "",
        'cover_letter_text': "",
        'cv_file_bytes': None,
        'cover_letter_bytes': None,
        'kw_data': {},
        'change_log': None,
        'agent_outputs': [],
        'extracted_co': "",
        'extracted_ti': "",
        'job_desc_input': "",
        'jd_url': "",
        'jd_method': "Paste Text"
    }
    if 'workflow_lock' not in st.session_state:
        st.session_state.workflow_lock = threading.Lock()
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

def get_available_models():
    api_key = os.getenv("GEMINI_API_KEY")
    default_models = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    if not api_key: return default_models
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        models = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferred = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        models.sort(key=lambda x: (0, preferred.index(x)) if x in preferred else (1, x))
        return models if models else default_models
    except Exception: return default_models

def main():
    init_state()
    st.set_page_config(page_title="ApplAI - AI CV Tailoring", layout="wide")
    st.markdown(APPLE_CSS, unsafe_allow_html=True)

    # ── 1. LOADING OVERLAY ──────────────────────────────────────────────────
    if st.session_state.workflow_is_running and st.session_state.workflow_generator:
        is_at_latest = (st.session_state.workflow_view_index == len(st.session_state.workflow_step_history) - 1)
        
        should_rerun = False
        if is_at_latest or st.session_state.workflow_view_index == -1:
            if st.session_state.workflow_lock.acquire(blocking=False):
                try:
                    update = next(st.session_state.workflow_generator)
                    if update.status == "done" or not st.session_state.workflow_step_history:
                        if st.session_state.workflow_step_history and st.session_state.workflow_step_history[-1].step_num == update.step_num:
                            st.session_state.workflow_step_history[-1] = update
                        else:
                            st.session_state.workflow_step_history.append(update)
                    st.session_state.workflow_view_index = len(st.session_state.workflow_step_history) - 1
                    
                    if update.partial_result:
                        st.session_state.final_workflow_result = update.partial_result
                        st.session_state.workflow_is_running = False
                        st.session_state.workflow_generator = None
                        should_rerun = True
                except StopIteration:
                    st.session_state.workflow_is_running = False
                    st.session_state.workflow_generator = None
                    should_rerun = True
                except ValueError as e:
                    if "generator already executing" in str(e): should_rerun = True
                    else: raise e
                finally:
                    st.session_state.workflow_lock.release()
            else:
                time.sleep(0.1); should_rerun = True

        if should_rerun: st.rerun()

        if st.session_state.workflow_view_index >= 0:
            curr = st.session_state.workflow_step_history[st.session_state.workflow_view_index]
            safe_lines = [html.escape(line) for line in curr.detail_lines]
            log_lines_html = "".join([f'<div class="log-line">{line}</div>' for line in safe_lines])
            
            # Using st.empty() for a clean full-screen takeover if possible, otherwise fixed flex
            st.markdown(f"""
                <div class="loading-overlay">
                    <div style="display:flex; flex-direction:column; align-items:center;">
                        <div class="step-card">
                            <div class="step-header">
                                <h2 style="margin:0; color:white; font-weight:800; font-size:2.8rem;">{curr.module_name}</h2>
                                <div class="step-indicator">Step {curr.step_num} of 8</div>
                            </div>
                            <p style="font-size:1.6rem; color:#0A84FF; font-weight:600; margin-bottom:1.8rem;">{curr.summary}</p>
                            <div class="log-window">
                                {log_lines_html}
                            </div>
                        </div>
                        <div class="nav-container-fixed">
                            <!-- Streamlit controls inside this spatial zone -->
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Button layout using container but floating within the flex center
            btn_col1, btn_col2, btn_col3, btn_col4, btn_col5 = st.columns([1,2,2,2,1])
            with btn_col2:
                if st.session_state.workflow_view_index > 0:
                    if st.button("← Previous Agent Step", key="btn_p_v6", use_container_width=True):
                        st.session_state.workflow_view_index -= 1; st.rerun()
            with btn_col4:
                if st.session_state.workflow_view_index < len(st.session_state.workflow_step_history) - 1:
                    if st.button("Next Agent Step →", key="btn_n_v6", use_container_width=True):
                        st.session_state.workflow_view_index += 1; st.rerun()
            
            if is_at_latest and st.session_state.workflow_is_running:
                time.sleep(0.1); st.rerun()
            st.stop()

    # ── 2. RESULT PROCESSING ───────────────────────────────────────────────
    if st.session_state.final_workflow_result and not st.session_state.workflow_completed:
        res = st.session_state.final_workflow_result
        inp = st.session_state.workflow_inputs
        with st.spinner("Compiling Final Results..."):
            qa = res.pydantic
            st.session_state.match_score = f"{getattr(qa, 'matching_rate_score', 0)}%"
            st.session_state.pain_points = "<br>".join([f"- {p}" for p in getattr(qa, 'key_pain_points', [])])
            st.session_state.strong_points = "<br>".join([f"- {s}" for s in getattr(qa, 'strong_points', [])])
            
            surname = res.canonical_cv.full_name.split()[-1] if res.canonical_cv.full_name else "Candidate"
            safe_co = re.sub(r'\W+', '_', inp.get("company_name", "Co"))
            cv_path = f"docs/{surname}_CV_Tailored_{safe_co}.docx"
            cl_path = f"docs/{surname}_CL_Tailored_{safe_co}.pdf"

            template = os.path.join("docs", inp.get("selected_cv_pdf", "").replace(".pdf", ".docx"))
            if not os.path.exists(template):
                docx_files = [f for f in os.listdir("docs") if f.endswith(".docx") and "Tailored" not in f]
                template = os.path.join("docs", docx_files[0]) if docx_files else None
            
            if template: pdf_generator.generate_tailored_document(template, cv_path, {"tailored_output": res.tailored_output})
            cl_txt = res.cover_letter or "No cover letter."
            try:
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import letter
                c = canvas.Canvas(cl_path, pagesize=letter); c.setFont("Helvetica", 11); y = 750
                for line in cl_txt.splitlines():
                    for wrap in textwrap.wrap(line or " ", width=90):
                        c.drawString(60, y, wrap); y -= 15
                        if y < 50: c.showPage(); c.setFont("Helvetica", 11); y = 750
                c.save()
            except:
                with open(cl_path, "w") as f: f.write(cl_txt)
            
            if google_integration:
                try: st.session_state.docs_url = google_integration.upload_to_drive(cv_path, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", convert_to_docs=True)
                except: pass

            with open(cv_path, "rb") as f: st.session_state.cv_file_bytes = f.read()
            with open(cl_path, "rb") as f: st.session_state.cover_letter_bytes = f.read()
            st.session_state.cv_filename = os.path.basename(cv_path)
            st.session_state.cl_filename = os.path.basename(cl_path)
            st.session_state.cover_letter_text = cl_txt
            
            ats = res.ats_report
            st.session_state.kw_data = {"jd": set(ats.jd_keywords), "cv": set(ats.covered_keywords), "added": set(ats.added_by_tailoring), "gaps": set(ats.gap_keywords)}
            st.session_state.workflow_completed = True; st.rerun()

    # ── 3. MAIN UI ───────────────────────────────────────────────────────────
    st.title("ApplAI - Smart CV Tailoring")
    
    t_gen, t_lib = st.tabs(["Application Generator", "CV Library"])
    
    with t_gen:
        st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
        st.markdown("<h3>1. Job Details</h3>", unsafe_allow_html=True)
        jd_method = st.radio("Input Method", ["Paste Text", "Job URL"], horizontal=True, key="jd_meth_v6")
        if jd_method == "Job URL":
            st.text_input("Job URL", key="jd_url_v6")
            if st.button("Fetch Job Details", key="btn_scrape_v6"):
                try:
                    resp = requests.get(st.session_state.jd_url_v6, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
                    soup = BeautifulSoup(resp.text, "lxml")
                    for s in soup(["script", "style"]): s.decompose()
                    st.session_state.job_desc_input = soup.get_text(separator="\n", strip=True)
                    st.rerun()
                except: st.error("Scrape failed.")
        
        st.text_area("Job Description", height=200, key="job_desc_input")
        c_co, c_ti = st.columns(2)
        st.session_state.extracted_co = c_co.text_input("Company Name", value=st.session_state.extracted_co, key="co_v6")
        st.session_state.extracted_ti = c_ti.text_input("Job Title", value=st.session_state.extracted_ti, key="ti_v6")
        if st.button("Analyze Company & Title", key="btn_analyze_v6"):
            with st.spinner("AI Extracting..."):
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                    m = genai.GenerativeModel("gemini-1.5-flash")
                    r = m.generate_content(f"Extract Company Name|Job Title. JD:\n{st.session_state.job_desc_input[:2000]}")
                    if "|" in r.text:
                        co, ti = r.text.split("|")
                        st.session_state.extracted_co, st.session_state.extracted_ti = co.strip(), ti.strip()
                        st.rerun()
                except: st.error("Failed to analyze.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
        st.markdown("<h3>2. Selected Context</h3>", unsafe_allow_html=True)
        pdfs = [f for f in os.listdir("docs") if f.endswith(".pdf")] if os.path.exists("docs") else []
        sc1, sc2 = st.columns(2)
        sel_cv = sc1.selectbox("Base Master CV", pdfs if pdfs else ["No CVs available"])
        sel_model = sc2.selectbox("Execution Model", get_available_models())
        if st.button("Start Tailoring Sequence", key="btn_start_v6", use_container_width=True):
            jpath = os.path.join("docs", "json_exports", sel_cv.replace(".pdf", ".json"))
            if not os.path.exists(jpath): st.error("Index CV first.")
            else:
                with open(jpath, 'r', encoding='utf-8') as f: b_json = f.read()
                st.session_state.update({'workflow_is_running':True, 'workflow_completed':False, 'workflow_step_history':[], 'workflow_inputs':{"job_desc":st.session_state.job_desc_input, "base_cv_json_text":b_json, "company_name":st.session_state.extracted_co, "job_title":st.session_state.extracted_ti, "selected_cv_pdf":sel_cv, "selected_model":sel_model}})
                st.session_state.workflow_generator = agent_workflow.run_application_workflow_streaming(st.session_state.job_desc_input, b_json, sel_model, company_name=st.session_state.extracted_co, job_title=st.session_state.extracted_ti)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.workflow_completed:
            st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
            st.markdown(f"<h2>Analysis Result: {st.session_state.match_score} Match</h2>", unsafe_allow_html=True)
            if st.session_state.docs_url: st.markdown(f"#### [🔗 View in Google Docs]({st.session_state.docs_url})")
            c_s, c_p = st.columns(2)
            c_s.info(f"**Strong Points:**\n\n{st.session_state.strong_points.replace('<br>','\n')}")
            c_p.warning(f"**Gaps identified:**\n\n{st.session_state.pain_points.replace('<br>','\n')}")
            st.divider()
            d1, d2 = st.columns(2)
            d1.download_button("Download DOCX", st.session_state.cv_file_bytes, st.session_state.cv_filename, use_container_width=True)
            d2.download_button("Download PDF", st.session_state.cover_letter_bytes, st.session_state.cl_filename, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
            # --- AGENT EXECUTION HISTORY SECTION ---
            st.markdown("### 🛠 Agent Pipeline Execution History")
            st.markdown("Review the logic and comments from each individual module in the tailoring pipeline.")
            for step in st.session_state.workflow_step_history:
                with st.expander(f"Module {step.step_num}: {step.module_name}", expanded=False):
                    st.write(f"**Outcome:** {step.summary}")
                    # Render the same log window style but inline
                    step_logs_safe = [html.escape(l) for l in step.detail_lines]
                    step_logs_html = "".join([f'<div style="margin-bottom:8px; border-left:3px solid #0071e3; padding-left:12px; font-family:monospace; font-size:0.9rem;">{l}</div>' for l in step_logs_safe])
                    st.markdown(f"""
                        <div style="background:#121216; padding:1.5rem; border-radius:12px; border:1px solid rgba(255,255,255,0.05);">
                            {step_logs_html}
                        </div>
                    """, unsafe_allow_html=True)

    with t_lib:
        st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
        st.markdown("<h3>Master Library</h3>", unsafe_allow_html=True)
        up = st.file_uploader("Upload PDF CV", type="pdf", key="cv_up_v6")
        if up and st.button("Index Master CV"):
            p = os.path.join("docs", up.name)
            with open(p, "wb") as f: f.write(up.getbuffer())
            js = pdf_parser.parse_pdf_to_json(p)
            os.makedirs("docs/json_exports", exist_ok=True)
            with open(os.path.join("docs/json_exports", up.name.replace(".pdf", ".json")), "w") as f: json.dump(js, f, indent=4)
            st.success("CV Indexed."); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
