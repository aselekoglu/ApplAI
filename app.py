import streamlit as st
import time
import os
import json
import datetime
import re
import requests
import threading
import html
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Local imports
import agent_workflow
import pdf_parser
import master_cv
from artifact_export import compile_result_artifacts

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

    div[class*="st-key-imp_insert_row_"] {
        margin-top: -10px;
        margin-bottom: 14px;
        min-height: 28px;
    }

    div[class*="st-key-imp_insert_row_"] .imp-insert-row-seg {
        height: 1px;
        width: 100%;
        background: rgba(255,255,255,0.08);
        transition: background 150ms ease;
        margin-top: 0;
    }

    div[class*="st-key-imp_insert_row_"] .stButton > button {
        border-radius: 999px;
        width: 28px;
        height: 28px;
        min-height: 28px;
        aspect-ratio: 1 / 1;
        padding: 0;
        font-size: 1rem;
        border: 1px solid rgba(255,255,255,0.2);
        background: rgba(20,22,28,0.95);
        color: rgba(255,255,255,0.75);
        opacity: 0;
        transform: scale(0.92);
        transition: opacity 120ms ease, transform 120ms ease, border-color 120ms ease, color 120ms ease;
        margin: 0 auto;
    }

    div[class*="st-key-imp_insert_row_"] .stButton {
        width: 28px !important;
        min-width: 28px !important;
        max-width: 28px !important;
        margin-left: auto;
        margin-right: auto;
    }

    div[class*="st-key-imp_insert_row_"]:hover .imp-insert-row-seg {
        background: rgba(255,255,255,0.22);
    }

    div[class*="st-key-imp_insert_row_"]:hover .stButton > button {
        opacity: 1;
        transform: scale(1);
    }

    div[class*="st-key-imp_insert_row_"] .stButton > button:hover {
        opacity: 1;
        color: #ffffff;
        border-color: rgba(255,255,255,0.45);
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
        'change_log_entries': [],
        'extracted_co': "",
        'extracted_ti': "",
        'job_desc_input': "",
        'jd_url': "",
        'jd_method': "Paste Text",
        'import_sections': [],
        'import_source_filename': "",
        'import_error': "",
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


def list_master_json_files():
    export_dir = os.path.join("docs", "json_exports")
    if not os.path.exists(export_dir):
        return []
    return sorted([f for f in os.listdir(export_dir) if f.endswith(".json")])


def render_change_suggestions(change_log):
    st.markdown("### Suggestions")
    rows = []
    for entry in change_log.entries:
        rows.append({
            "Section": entry.section,
            "Action": entry.action,
            "Original": entry.original_text,
            "Suggested": entry.new_text or "",
            "Why": entry.rationale,
        })
    st.session_state.change_log_entries = rows
    st.dataframe(rows, use_container_width=True, hide_index=True)


def detect_template_drift(template_config_path: str, source_docx_filename: str) -> str:
    if not template_config_path or not source_docx_filename:
        return ""
    docx_path = os.path.join("docs", source_docx_filename)
    if not os.path.exists(template_config_path) or not os.path.exists(docx_path):
        return ""
    try:
        with open(template_config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        saved_ranges = config.get("section_ranges", [])
        if not saved_ranges:
            return ""

        outline = master_cv.extract_docx_outline(docx_path)
        current_para_count = len(outline)
        saved_max_end = max((r.get("end_para", 0) or 0) for r in saved_ranges)
        saved_para_count_estimate = saved_max_end + 1
        saved_section_count = len(saved_ranges)
        current_heading_like = len(master_cv.propose_sections(outline))

        para_delta = abs(current_para_count - saved_para_count_estimate)
        para_delta_ratio = para_delta / max(saved_para_count_estimate, 1)
        section_delta = abs(current_heading_like - saved_section_count)

        if para_delta_ratio > 0.2 or section_delta >= 2:
            return (
                f"Template drift detected for `{source_docx_filename}`: "
                f"saved≈{saved_para_count_estimate} paragraphs/{saved_section_count} sections, "
                f"current≈{current_para_count} paragraphs/{current_heading_like} sections. "
                "Re-run Import Master CV to refresh anchors before generating final DOCX."
            )
    except Exception:
        return ""
    return ""


def _add_empty_import_section():
    _insert_import_section(len(st.session_state.import_sections))


def _insert_import_section(position: int):
    insert_at = max(0, min(position, len(st.session_state.import_sections)))
    st.session_state.import_sections.insert(
        insert_at,
        {
            "title": "NEW SECTION",
            "kind": "other",
            "start_para": 0,
            "end_para": 0,
            "body_text": "",
            "custom_kind_name": "",
            "role_label": "",
            "employer_line": "",
            "title_line": "",
            "date_line": "",
        }
    )


def _split_import_section(idx: int):
    body = st.session_state.get(f"imp_body_{idx}", "")
    chunks = [c.strip() for c in re.split(r"\n\s*\n", body) if c.strip()]
    if len(chunks) <= 1:
        return
    base = st.session_state.import_sections[idx].copy()
    base["body_text"] = chunks[0]
    st.session_state.import_sections[idx] = base
    insert_pos = idx + 1
    for chunk in chunks[1:]:
        new_sec = base.copy()
        new_sec["body_text"] = chunk
        st.session_state.import_sections.insert(insert_pos, new_sec)
        insert_pos += 1


def _merge_import_section_up(idx: int):
    if idx <= 0:
        return
    curr_body = st.session_state.get(f"imp_body_{idx}", st.session_state.import_sections[idx].get("body_text", ""))
    prev_body = st.session_state.get(f"imp_body_{idx - 1}", st.session_state.import_sections[idx - 1].get("body_text", ""))
    st.session_state.import_sections[idx - 1]["body_text"] = (prev_body + "\n\n" + curr_body).strip()
    st.session_state.import_sections.pop(idx)

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
            st.session_state.change_log = res.change_log
            ats = res.ats_report
            st.session_state.kw_data = {"jd": set(ats.jd_keywords), "cv": set(ats.covered_keywords), "added": set(ats.added_by_tailoring), "gaps": set(ats.gap_keywords)}

            should_generate = inp.get("output_mode", "Generate DOCX and cover letter") == "Generate DOCX and cover letter"
            if should_generate:
                try:
                    artifact_data = compile_result_artifacts(res, inp)
                    st.session_state.docs_url = artifact_data["docs_url"]
                    st.session_state.cv_file_bytes = artifact_data["cv_bytes"]
                    st.session_state.cover_letter_bytes = artifact_data["cl_bytes"]
                    st.session_state.cv_filename = os.path.basename(artifact_data["cv_path"])
                    st.session_state.cl_filename = os.path.basename(artifact_data["cl_path"])
                    st.session_state.cover_letter_text = artifact_data["cover_letter_text"]
                except Exception as exc:
                    st.error(f"Could not generate files automatically: {exc}")
                    st.session_state.cv_file_bytes = None
                    st.session_state.cover_letter_bytes = None
            else:
                st.session_state.docs_url = None
                st.session_state.cv_file_bytes = None
                st.session_state.cover_letter_bytes = None
                st.session_state.cv_filename = ""
                st.session_state.cl_filename = ""
                st.session_state.cover_letter_text = res.cover_letter or ""
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
        master_json_files = list_master_json_files()
        sc1, sc2 = st.columns(2)
        sel_json = sc1.selectbox("Base Master CV", master_json_files if master_json_files else ["No indexed masters"])
        sel_model = sc2.selectbox("Execution Model", get_available_models())

        md1, md2 = st.columns(2)
        run_mode = md1.selectbox("Run Mode", ["Deep", "Quick"])
        output_mode = md2.selectbox("Output", ["Generate DOCX and cover letter", "Suggestions only"])

        op1, op2 = st.columns(2)
        include_cover_letter = op1.checkbox("Generate cover letter", value=True)
        include_qa = op2.checkbox("Run ATS + QA checks", value=True)
        rw1, rw2, pg = st.columns([2, 2, 1])
        allow_exp_rw = rw1.checkbox("Allow safe rewrites in Experience", value=False)
        allow_edu_rw = rw2.checkbox("Allow safe rewrites in Education", value=False)
        max_pages = pg.number_input("Max pages", min_value=1, max_value=3, value=2)

        if st.button("Start Tailoring Sequence", key="btn_start_v6", use_container_width=True):
            jpath = os.path.join("docs", "json_exports", sel_json)
            if not os.path.exists(jpath):
                st.error("Index a master CV first.")
            else:
                with open(jpath, 'r', encoding='utf-8') as f: b_json = f.read()
                parsed = json.loads(b_json)
                template_path = ""
                if parsed.get("source_docx"):
                    template_path = os.path.join("docs", parsed["source_docx"])
                elif parsed.get("source_file", "").endswith(".pdf"):
                    template_path = os.path.join("docs", parsed["source_file"].replace(".pdf", ".docx"))
                workflow_inputs = {
                    "job_desc": st.session_state.job_desc_input,
                    "base_cv_json_text": b_json,
                    "company_name": st.session_state.extracted_co,
                    "job_title": st.session_state.extracted_ti,
                    "selected_cv_json": sel_json,
                    "selected_model": sel_model,
                    "quick_mode": run_mode == "Quick",
                    "include_cover_letter": include_cover_letter,
                    "include_ats": include_qa,
                    "include_qa": include_qa,
                    "allow_experience_rewrites": allow_exp_rw,
                    "allow_education_rewrites": allow_edu_rw,
                    "max_pages": int(max_pages),
                    "output_mode": output_mode,
                    "template_path": template_path,
                    "template_config_path": parsed.get("template_config_path", ""),
                }
                st.session_state.update({'workflow_is_running': True, 'workflow_completed': False, 'workflow_step_history': [], 'workflow_inputs': workflow_inputs})
                st.session_state.workflow_generator = agent_workflow.run_application_workflow_streaming(
                    st.session_state.job_desc_input,
                    b_json,
                    sel_model,
                    company_name=st.session_state.extracted_co,
                    job_title=st.session_state.extracted_ti,
                    quick_mode=workflow_inputs["quick_mode"],
                    include_cover_letter=workflow_inputs["include_cover_letter"],
                    include_ats=workflow_inputs["include_ats"],
                    include_qa=workflow_inputs["include_qa"],
                    allow_experience_rewrites=workflow_inputs["allow_experience_rewrites"],
                    allow_education_rewrites=workflow_inputs["allow_education_rewrites"],
                    max_pages=workflow_inputs["max_pages"],
                )
                st.rerun()
        if master_json_files and sel_json != "No indexed masters":
            try:
                selected_path = os.path.join("docs", "json_exports", sel_json)
                with open(selected_path, "r", encoding="utf-8") as f:
                    selected_master = json.load(f)
                drift_msg = detect_template_drift(
                    selected_master.get("template_config_path", ""),
                    selected_master.get("source_docx", ""),
                )
                if drift_msg:
                    st.warning(drift_msg)
            except Exception:
                pass
        st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.workflow_completed:
            st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
            st.markdown(f"<h2>Analysis Result: {st.session_state.match_score} Match</h2>", unsafe_allow_html=True)
            if st.session_state.docs_url: st.markdown(f"#### [🔗 View in Google Docs]({st.session_state.docs_url})")
            c_s, c_p = st.columns(2)
            strong_text = st.session_state.strong_points.replace("<br>", "\n")
            gap_text = st.session_state.pain_points.replace("<br>", "\n")
            c_s.info(f"**Strong Points:**\n\n{strong_text}")
            c_p.warning(f"**Gaps identified:**\n\n{gap_text}")
            st.divider()
            if st.session_state.change_log:
                render_change_suggestions(st.session_state.change_log)
            if st.session_state.cv_file_bytes and st.session_state.cover_letter_bytes:
                d1, d2 = st.columns(2)
                d1.download_button("Download DOCX", st.session_state.cv_file_bytes, st.session_state.cv_filename, use_container_width=True)
                d2.download_button("Download PDF", st.session_state.cover_letter_bytes, st.session_state.cl_filename, use_container_width=True)
            else:
                st.info("Suggestions-only mode is active. Review changes, then generate documents when ready.")
                if st.button("Generate Documents From Current Suggestions", use_container_width=True):
                    try:
                        artifacts = compile_result_artifacts(st.session_state.final_workflow_result, st.session_state.workflow_inputs)
                        st.session_state.docs_url = artifacts["docs_url"]
                        st.session_state.cv_file_bytes = artifacts["cv_bytes"]
                        st.session_state.cover_letter_bytes = artifacts["cl_bytes"]
                        st.session_state.cv_filename = os.path.basename(artifacts["cv_path"])
                        st.session_state.cl_filename = os.path.basename(artifacts["cl_path"])
                        st.session_state.cover_letter_text = artifacts["cover_letter_text"]
                    except Exception as exc:
                        st.error(f"Could not generate documents: {exc}")
                    st.rerun()
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
        st.caption("Import once, review detected sections, then reuse as your master for future tailoring.")

        up = st.file_uploader("Upload Master CV (DOCX preferred, PDF supported)", type=["docx", "pdf"], key="cv_up_v6")
        master_alias = st.text_input("Master CV name", placeholder="e.g. aselem_master_v1")
        if up and st.button("Analyze Master CV Structure", use_container_width=True):
            os.makedirs("docs", exist_ok=True)
            source_path = os.path.join("docs", up.name)
            with open(source_path, "wb") as f:
                f.write(up.getbuffer())

            st.session_state.import_source_filename = up.name
            st.session_state.import_error = ""
            try:
                if up.name.lower().endswith(".docx"):
                    outline = master_cv.extract_docx_outline(source_path)
                    st.session_state.import_sections = master_cv.propose_sections(outline)
                else:
                    parsed = pdf_parser.parse_pdf_to_json(source_path) or {"raw_text": ""}
                    st.session_state.import_sections = [
                        {
                            "title": "Profile",
                            "kind": "profile",
                            "start_para": 0,
                            "end_para": 0,
                            "body_text": parsed.get("raw_text", ""),
                        }
                    ]
            except Exception as exc:
                st.session_state.import_sections = []
                st.session_state.import_error = str(exc)
            st.rerun()

        if st.session_state.import_error:
            st.error(f"Import failed: {st.session_state.import_error}")

        if st.session_state.import_sections:
            st.markdown("#### Review detected sections")
            st.caption("Adjust section type, heading and content before saving. This becomes your trusted master structure.")
            ac1, ac2 = st.columns([1, 3])
            if ac1.button("Add Section", use_container_width=True):
                _add_empty_import_section()
                st.rerun()
            ac2.caption("Use Split/Merge/Remove to clean up parsing, then save.")
            for idx, sec in enumerate(st.session_state.import_sections):
                st.markdown(f"**Section {idx + 1}**")
                c1, c2 = st.columns([2, 1])
                c1.text_input("Heading", value=sec.get("title", ""), key=f"imp_title_{idx}")
                c2.selectbox("Kind", master_cv.SECTION_KINDS, index=master_cv.SECTION_KINDS.index(sec.get("kind", "other")) if sec.get("kind", "other") in master_cv.SECTION_KINDS else 0, key=f"imp_kind_{idx}")
                selected_kind = st.session_state.get(f"imp_kind_{idx}", sec.get("kind", "other"))
                if selected_kind == "other":
                    st.text_input(
                        "Custom section name",
                        value=sec.get("custom_kind_name", ""),
                        key=f"imp_custom_kind_name_{idx}",
                        placeholder="add name here",
                    )
                st.text_area("Section text", value=sec.get("body_text", ""), key=f"imp_body_{idx}", height=100)
                if selected_kind == "experience_block":
                    rc1, rc2, rc3 = st.columns(3)
                    rc1.text_input("Role label", value=sec.get("role_label", ""), key=f"imp_role_label_{idx}")
                    rc2.text_input("Employer line", value=sec.get("employer_line", ""), key=f"imp_employer_{idx}")
                    rc3.text_input("Date line", value=sec.get("date_line", ""), key=f"imp_date_{idx}")
                    st.text_input("Title line", value=sec.get("title_line", ""), key=f"imp_title_line_{idx}")

                a1, a2, a3 = st.columns(3)
                if a1.button("Split by blank lines", key=f"imp_split_{idx}", use_container_width=True):
                    _split_import_section(idx)
                    st.rerun()
                if a2.button("Merge Up", key=f"imp_merge_{idx}", use_container_width=True, disabled=(idx == 0)):
                    _merge_import_section_up(idx)
                    st.rerun()
                if a3.button("Remove", key=f"imp_remove_{idx}", use_container_width=True):
                    st.session_state.import_sections.pop(idx)
                    st.rerun()
                with st.container(key=f"imp_insert_row_{idx}"):
                    lcol, bcol, rcol = st.columns([8, 1, 8], vertical_alignment="center")
                    lcol.markdown('<div class="imp-insert-row-seg"></div>', unsafe_allow_html=True)
                    with bcol:
                        if st.button("+", key=f"imp_insert_{idx}", help="Add section here", use_container_width=True):
                            _insert_import_section(idx + 1)
                            st.rerun()
                    rcol.markdown('<div class="imp-insert-row-seg"></div>', unsafe_allow_html=True)

            if st.button("Save Master CV", use_container_width=True):
                reviewed_sections = []
                for idx, sec in enumerate(st.session_state.import_sections):
                    reviewed_sections.append(
                        {
                            "title": st.session_state.get(f"imp_title_{idx}", sec.get("title", "")),
                            "kind": st.session_state.get(f"imp_kind_{idx}", sec.get("kind", "other")),
                            "body_text": st.session_state.get(f"imp_body_{idx}", sec.get("body_text", "")),
                            "start_para": sec.get("start_para", 0),
                            "end_para": sec.get("end_para", 0),
                            "role_label": st.session_state.get(f"imp_role_label_{idx}", sec.get("role_label", "")),
                            "employer_line": st.session_state.get(f"imp_employer_{idx}", sec.get("employer_line", "")),
                            "title_line": st.session_state.get(f"imp_title_line_{idx}", sec.get("title_line", "")),
                            "date_line": st.session_state.get(f"imp_date_{idx}", sec.get("date_line", "")),
                            "custom_kind_name": st.session_state.get(f"imp_custom_kind_name_{idx}", sec.get("custom_kind_name", "")),
                        }
                    )
                source_name = st.session_state.import_source_filename or "master_cv.docx"
                json_path, config_path = master_cv.save_master_artifacts(
                    "docs",
                    source_name,
                    reviewed_sections,
                    canonical_name=master_alias.strip() if master_alias else None,
                )
                st.success(f"Master saved. JSON: {os.path.basename(json_path)} | Config: {os.path.basename(config_path)}")

        st.divider()
        st.markdown("#### Quick PDF index (legacy)")
        up_pdf = st.file_uploader("Upload PDF CV for fast indexing", type="pdf", key="legacy_pdf_up_v6")
        if up_pdf and st.button("Index PDF Only"):
            p = os.path.join("docs", up_pdf.name)
            with open(p, "wb") as f:
                f.write(up_pdf.getbuffer())
            js = pdf_parser.parse_pdf_to_json(p)
            os.makedirs("docs/json_exports", exist_ok=True)
            with open(os.path.join("docs/json_exports", up_pdf.name.replace(".pdf", ".json")), "w", encoding="utf-8") as f:
                json.dump(js, f, indent=4)
            st.success("PDF indexed.")
        st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
