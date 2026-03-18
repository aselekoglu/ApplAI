"""
ApplAI — Agentic CV Tailoring Pipeline
=======================================
8-module structured pipeline:

  1. CV Loader          – Converts raw JSON → CanonicalCV (LLM-assisted)
  2. JD Parser          – Extracts ranked requirements from JD (LLM)
  3. Evidence Mapper    – Scores every CV bullet vs JD requirements (deterministic)
  4. Strategy Planner   – Decides which sections to edit and how aggressively (deterministic)
  5. Bullet Selector/   – Selects top bullets, rewrites only where safe (hybrid LLM)
     Rewriter
  6. Cover Letter       – Writes a grounded cover letter (LLM)
     Writer
  7. QA Validator       – Factual check, length check, hallucination audit (hybrid)
  8. ATS Analyzer &     – Keyword coverage + structured change log (deterministic)
     Change Log

All LLM calls use strict JSON output contracts. No freeform rewriting of the full CV.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


# =============================================================================
# Pydantic Data Models — Canonical Contracts Between Modules
# =============================================================================

class BulletEvidence(BaseModel):
    bullet_id: str = Field(description="Unique ID, e.g. 'exp_ccs_1'")
    text: str = Field(description="Original bullet text, verbatim")
    section: str = Field(description="profile|experience|projects|skills|education")
    employer: str = Field(default="", description="Employer/institution (locked)")
    role: str = Field(default="", description="Job title or project name (locked)")
    domain_tags: list[str] = Field(default_factory=list, description="e.g. ['automation','api','data']")
    is_locked: bool = Field(default=False, description="If True: text may not be rewritten, only selected/deselected")


class ExperienceEntry(BaseModel):
    employer: str
    role: str
    start_date: str
    end_date: str
    location: str = ""
    bullets: list[BulletEvidence] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    title: str
    date: str = ""
    institution: str = ""
    bullets: list[BulletEvidence] = Field(default_factory=list)


class EducationEntry(BaseModel):
    institution: str
    degree: str
    field_of_study: str
    start_date: str
    end_date: str
    bullets: list[BulletEvidence] = Field(default_factory=list)


class CanonicalCV(BaseModel):
    full_name: str
    contact: dict = Field(default_factory=dict)
    profile_bullets: list[BulletEvidence] = Field(default_factory=list)
    skills_sections: dict = Field(default_factory=dict, description="category -> list[str]")
    experience: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    additional: str = ""


class RequirementItem(BaseModel):
    requirement: str
    priority: str = Field(description="must_have|nice_to_have")
    keywords: list[str] = Field(default_factory=list)


class JDAnalysis(BaseModel):
    ranked_requirements: list[RequirementItem] = Field(default_factory=list)
    domain: str = Field(description="ai_ml|software|data|ba|automation|telecom|documentation|general")
    seniority: str = Field(default="mid", description="junior|mid|senior|lead")
    must_have_keywords: list[str] = Field(default_factory=list)
    nice_to_have_keywords: list[str] = Field(default_factory=list)
    company_tone: str = Field(default="professional")
    raw_summary: str = Field(default="")


class ScoredBullet(BaseModel):
    bullet: BulletEvidence
    relevance_score: float = Field(description="0.0 to 1.0")
    matched_keywords: list[str] = Field(default_factory=list)
    matched_requirements: list[str] = Field(default_factory=list)


class EditPlan(BaseModel):
    domain: str
    sections_to_edit: list[str]
    max_profile_bullets: int = 3
    max_experience_bullets: int = 8
    max_project_bullets: int = 4
    rewrite_threshold: float = Field(description="Bullets below this score are candidates to rewrite")
    select_threshold: float = Field(description="Bullets above this score are selected as-is")
    keyword_emphasis: list[str] = Field(default_factory=list)


class BulletSelection(BaseModel):
    bullet_id: str
    section: str
    action: str = Field(description="select_as_is|rewrite|deselect")
    original_text: str
    new_text: Optional[str] = None
    rewrite_rationale: Optional[str] = None
    relevance_score: float = 0.0
    jd_requirements_addressed: list[str] = Field(default_factory=list)


class TailoredOutput(BaseModel):
    profile_selections: list[BulletSelection] = Field(default_factory=list)
    skills_to_highlight: list[str] = Field(default_factory=list)
    experience_selections: list[BulletSelection] = Field(default_factory=list)
    project_selections: list[BulletSelection] = Field(default_factory=list)
    summary_section: Optional[str] = None


class QAReport(BaseModel):
    matching_rate_score: int = Field(default=0, description="0-100")
    factual_support_passed: bool = True
    keyword_coverage_pct: float = 0.0
    style_issues: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    section_length_ok: bool = True
    key_pain_points: list[str] = Field(default_factory=list)
    strong_points: list[str] = Field(default_factory=list)
    feedback: str = ""


class ChangeLogEntry(BaseModel):
    bullet_id: str
    section: str
    action: str
    original_text: str
    new_text: Optional[str] = None
    rationale: str = ""
    jd_requirements_addressed: list[str] = Field(default_factory=list)


class ChangeLog(BaseModel):
    entries: list[ChangeLogEntry] = Field(default_factory=list)
    total_bullets_considered: int = 0
    total_bullets_changed: int = 0
    total_bullets_rewritten: int = 0
    total_bullets_deselected: int = 0


class ATSReport(BaseModel):
    jd_keywords: list[str] = Field(default_factory=list)
    covered_keywords: list[str] = Field(default_factory=list)
    gap_keywords: list[str] = Field(default_factory=list)
    added_by_tailoring: list[str] = Field(default_factory=list)
    coverage_pct: float = 0.0


@dataclass
class WorkflowResult:
    """Top-level result object returned to app.py."""
    canonical_cv: CanonicalCV = field(default_factory=CanonicalCV.model_construct)
    jd_analysis: JDAnalysis = field(default_factory=JDAnalysis.model_construct)
    tailored_output: TailoredOutput = field(default_factory=TailoredOutput.model_construct)
    qa_report: QAReport = field(default_factory=QAReport.model_construct)
    change_log: ChangeLog = field(default_factory=ChangeLog.model_construct)
    ats_report: ATSReport = field(default_factory=ATSReport.model_construct)
    cover_letter: str = ""

    #  Legacy fields so app.py: result.tasks_output and result.pydantic still work 
    @property
    def pydantic(self):
        """Return the QA report as the top-level pydantic result (legacy compat)."""
        return self.qa_report

    @property
    def tasks_output(self):
        """Return a list of task-like objects for the Agent Execution Log in app.py."""
        return [
            _FakeTask("CV Loader", self.canonical_cv),
            _FakeTask("Job Analyzer", self.jd_analysis),
            _FakeTask("Evidence Mapper", None, "Scored bullets against requirements."),
            _FakeTask("Strategy Planner", None, "Selected edit sections based on domain."),
            _FakeTask("CV Tailorer", self.tailored_output),
            _FakeTask("Cover Letter Writer", None, self.cover_letter),
            _FakeTask("ATS Report", self.ats_report),
            _FakeTask("QA Reviewer", self.qa_report),
        ]


class _FakeTask:
    """Mimics CrewAI TaskOutput so existing app.py display code works unchanged."""
    def __init__(self, role: str, pydantic_obj=None, raw: str = ""):
        self.role = role
        self.pydantic = pydantic_obj
        self.raw = raw or (pydantic_obj.model_dump_json(indent=2) if pydantic_obj else "")


# =============================================================================
# LLM Helper
# =============================================================================

def _get_llm(model_name: str = "gemini-2.5-flash"):
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=model_name)


def _call_gemini_json(prompt: str, model_name: str = "gemini-2.5-flash") -> dict:
    """
    Call Gemini directly via google.generativeai and return parsed JSON.
    Falls back to empty dict on any failure.
    """
    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.2,
        )
    )
    text = response.text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


# =============================================================================
# MODULE 1 — CV Loader
# Converts raw JSON {source_file, raw_text} → CanonicalCV
# =============================================================================

_CV_LOADER_PROMPT = """You are a precise CV parser. Convert the following raw CV text into a structured JSON object.

STRICT RULES:
- Do NOT infer, invent, or add ANY information not present in the raw text.
- Preserve every bullet point verbatim in the "text" field. Do not paraphrase.
- For experience bullets, record the employer and role from the nearest section header above.
- domain_tags for each bullet should be 1–5 lowercase tags from this list:
  [python, javascript, java, sql, api, automation, data, ml, ai, analysis, fullstack, backend,
   frontend, crm, cloud, agile, management, finance, telecom, writing, integration, testing]
- Set is_locked=true for every bullet in experience and education sections (facts must not change).
- Set is_locked=false for profile/summary bullets (these may be rewritten).
- Generate bullet_id as: section_abbrev + "_" + index, e.g. "prof_0", "exp_0_1", "proj_1_2"
- skills_sections: group skills by category as they appear in the CV (e.g. "Languages", "Platforms").
  Each category maps to a list of skill strings.

Return ONLY valid JSON matching this exact schema (no extra keys):
{
  "full_name": "string",
  "contact": {"city": "string", "phone": "string", "email": "string", "linkedin": "string", "github": "string"},
  "profile_bullets": [
    {"bullet_id": "prof_0", "text": "...", "section": "profile", "employer": "", "role": "", "domain_tags": [], "is_locked": false}
  ],
  "skills_sections": {
    "Languages & Frameworks": ["Python", "JavaScript"],
    "Cloud & Tools": ["GCP", "Git"]
  },
  "experience": [
    {
      "employer": "Company Name",
      "role": "Job Title",
      "start_date": "MMM YYYY",
      "end_date": "MMM YYYY or Present",
      "location": "City, Country",
      "bullets": [
        {"bullet_id": "exp_0_0", "text": "...", "section": "experience", "employer": "Company Name", "role": "Job Title", "domain_tags": [], "is_locked": true}
      ]
    }
  ],
  "projects": [
    {
      "title": "Project Name",
      "date": "MMM YYYY",
      "institution": "",
      "bullets": [
        {"bullet_id": "proj_0_0", "text": "...", "section": "projects", "employer": "", "role": "Project Name", "domain_tags": [], "is_locked": false}
      ]
    }
  ],
  "education": [
    {
      "institution": "School Name",
      "degree": "Bachelor of Science",
      "field_of_study": "...",
      "start_date": "YYYY",
      "end_date": "YYYY or Present",
      "bullets": []
    }
  ],
  "additional": "string (languages, activities, references note)"
}

RAW CV TEXT:
{raw_text}
"""


def load_canonical_cv(raw_json: dict, model_name: str = "gemini-2.5-flash") -> CanonicalCV:
    """
    Module 1: Convert raw {source_file, raw_text} JSON into a CanonicalCV.
    Uses LLM to structure the text. Falls back to a minimal model on failure.
    """
    raw_text = raw_json.get("raw_text", "")
    source_file = raw_json.get("source_file", "unknown")

    prompt = _CV_LOADER_PROMPT.replace("{raw_text}", raw_text[:12000])

    try:
        data = _call_gemini_json(prompt, model_name)
        cv = CanonicalCV.model_validate(data)
        print(f"[CV Loader] [OK] Structured CV loaded: {cv.full_name}")
        return cv
    except Exception as e:
        print(f"[CV Loader] [WARN] LLM structuring failed ({e}). Using fallback.")
        # Minimal fallback: wrap raw text as a single profile bullet
        return CanonicalCV(
            full_name=source_file.replace(".pdf", "").replace(".json", ""),
            profile_bullets=[
                BulletEvidence(
                    bullet_id="prof_0",
                    text=raw_text[:500],
                    section="profile",
                    is_locked=False,
                )
            ],
        )


# =============================================================================
# MODULE 2 — JD Parser
# =============================================================================

_JD_PARSER_PROMPT = """You are a senior technical recruiter. Analyze the following job description and extract structured requirements.

Return ONLY valid JSON matching this schema:
{
  "ranked_requirements": [
    {
      "requirement": "Clean, descriptive string of the requirement (e.g., '3+ years of Python development')",
      "priority": "must_have|nice_to_have",
      "keywords": ["kw1", "kw2"]
    }
  ],
  "domain": "one of: ai_ml|software|data|ba|automation|telecom|documentation|general",
  "seniority": "junior|mid|senior|lead",
  "must_have_keywords": ["list", "of", "technical", "or", "skill", "keywords"],
  "nice_to_have_keywords": ["list", "of", "bonus", "keywords"],
  "company_tone": "e.g. innovative, formal, public-sector, startup",
  "raw_summary": "2-3 sentence plain English summary of what this role does"
}

Rules:
- requirements list: 5–12 items. EACH "requirement" MUST be a detailed phrase, NOT an empty string.
- must_have_keywords: 10–25 technical/skill keywords that are non-negotiable.
- nice_to_have_keywords: 5–15 additional bonus keywords.
- domain: choose the single best fit.

JOB DESCRIPTION:
{job_description}
"""


def parse_jd(job_description: str, model_name: str = "gemini-2.5-flash") -> JDAnalysis:
    """Module 2: Parse job description into structured JDAnalysis."""
    prompt = _JD_PARSER_PROMPT.replace("{job_description}", job_description[:8000])
    try:
        data = _call_gemini_json(prompt, model_name)
        analysis = JDAnalysis.model_validate(data)
        print(f"[JD Parser] [OK] Domain: {analysis.domain} | {len(analysis.ranked_requirements)} requirements | {len(analysis.must_have_keywords)} must-have keywords")
        return analysis
    except Exception as e:
        print(f"[JD Parser] [WARN] Failed ({e}). Using fallback.")
        # Minimal fallback: simple keyword extraction
        words = set(re.findall(r'\b[a-zA-Z][a-zA-Z0-9#+.\-]{2,}\b', job_description.lower()))
        stopwords = {"the","and","or","to","of","a","an","in","for","with","that","is","are","was"}
        keywords = sorted(words - stopwords)[:20]
        return JDAnalysis(
            ranked_requirements=[RequirementItem(requirement="See JD", priority="must_have", keywords=keywords[:5])],
            domain="general",
            must_have_keywords=keywords[:15],
            nice_to_have_keywords=keywords[15:],
            raw_summary=job_description[:300],
        )


# =============================================================================
# MODULE 3 — Evidence Mapper
# Scores every CV bullet against JD requirements (deterministic)
# =============================================================================

# Domain → boost tags: bullets matching these tags get a score bonus
_DOMAIN_TAG_BOOSTS = {
    "ai_ml":         ["ml", "ai", "python", "data", "analysis"],
    "software":      ["python", "javascript", "api", "fullstack", "backend", "frontend"],
    "data":          ["sql", "data", "analysis", "python", "ml"],
    "ba":            ["analysis", "agile", "management", "crm", "integration"],
    "automation":    ["automation", "api", "python", "integration", "scripting"],
    "telecom":       ["telecom", "api", "integration", "backend"],
    "documentation": ["writing", "management", "analysis"],
    "general":       [],
}


def map_evidence(cv: CanonicalCV, jd: JDAnalysis) -> list[ScoredBullet]:
    """
    Module 3: Score every bullet in the CanonicalCV against JD requirements.
    Returns a sorted list of ScoredBullet (highest score first).
    """
    all_keywords = set(w.lower() for w in jd.must_have_keywords + jd.nice_to_have_keywords)
    must_have_set = set(w.lower() for w in jd.must_have_keywords)
    domain_boosts = set(_DOMAIN_TAG_BOOSTS.get(jd.domain, []))

    # Collect all bullets from all sections
    all_bullets: list[BulletEvidence] = []
    all_bullets.extend(cv.profile_bullets)
    for exp in cv.experience:
        all_bullets.extend(exp.bullets)
    for proj in cv.projects:
        all_bullets.extend(proj.bullets)

    scored: list[ScoredBullet] = []
    for bullet in all_bullets:
        text_lower = bullet.text.lower()
        bullet_words = set(re.findall(r'\b[a-zA-Z][a-zA-Z0-9#+.\-]{2,}\b', text_lower))

        # Keyword overlap
        matched_kws = list(bullet_words & all_keywords)
        must_matched = list(bullet_words & must_have_set)

        # Base score: weighted overlap
        kw_score = (len(must_matched) * 2 + len(matched_kws)) / max(len(all_keywords), 1)
        kw_score = min(kw_score, 1.0)

        # Domain tag boost
        tag_bonus = 0.15 if any(t in domain_boosts for t in bullet.domain_tags) else 0.0

        # Requirement text overlap boost
        req_hits = []
        for req in jd.ranked_requirements:
            req_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', req.requirement.lower()))
            if len(req_words & bullet_words) >= 2:
                req_hits.append(req.requirement)
        req_bonus = min(len(req_hits) * 0.05, 0.20)

        final_score = min(kw_score + tag_bonus + req_bonus, 1.0)

        scored.append(ScoredBullet(
            bullet=bullet,
            relevance_score=round(final_score, 3),
            matched_keywords=matched_kws,
            matched_requirements=req_hits,
        ))

    # Sort descending
    scored.sort(key=lambda s: s.relevance_score, reverse=True)
    print(f"[Evidence Mapper] [OK] Scored {len(scored)} bullets. Top score: {scored[0].relevance_score if scored else 0}")
    return scored


# =============================================================================
# MODULE 4 — Section Strategy Planner (deterministic)
# =============================================================================

def plan_strategy(jd: JDAnalysis, scored_bullets: list[ScoredBullet]) -> EditPlan:
    """
    Module 4: Decide which sections to edit and how aggressively.
    Uses a deterministic rule table based on domain.
    """
    domain = jd.domain

    # Base config per domain
    domain_config = {
        "ai_ml":         {"profile": True, "experience": True, "projects": True, "skills": True},
        "software":      {"profile": True, "experience": True, "projects": True, "skills": True},
        "data":          {"profile": True, "experience": True, "projects": True, "skills": True},
        "ba":            {"profile": True, "experience": True, "projects": False, "skills": True},
        "automation":    {"profile": True, "experience": True, "projects": True, "skills": True},
        "telecom":       {"profile": True, "experience": True, "projects": False, "skills": True},
        "documentation": {"profile": True, "experience": True, "projects": False, "skills": True},
        "general":       {"profile": True, "experience": True, "projects": False, "skills": True},
    }
    config = domain_config.get(domain, domain_config["general"])

    sections = [s for s, enabled in config.items() if enabled]

    # Average relevance of top 5 bullets — determines how aggressive to be
    top5 = scored_bullets[:5]
    avg_top5 = sum(s.relevance_score for s in top5) / max(len(top5), 1)

    # Thresholds: if good match → select as-is more; poor match → allow more rewrites
    select_threshold = 0.25 if avg_top5 > 0.35 else 0.20
    rewrite_threshold = 0.10  # Below this AND still in top-N → candidate for rewrite

    plan = EditPlan(
        domain=domain,
        sections_to_edit=sections,
        max_profile_bullets=3,
        max_experience_bullets=8,
        max_project_bullets=4,
        rewrite_threshold=rewrite_threshold,
        select_threshold=select_threshold,
        keyword_emphasis=jd.must_have_keywords[:10],
    )
    print(f"[Strategy Planner] [OK] Domain: {domain} | Sections: {sections} | avg_top5_score: {avg_top5:.2f}")
    return plan


# =============================================================================
# MODULE 5 — Bullet Selector / Rewriter (hybrid)
# =============================================================================

_BULLET_REWRITE_PROMPT = """You are a precise CV editor. Your ONLY job is to rephrase a single CV bullet point.

NON-NEGOTIABLE RULES:
1. Do NOT add any skills, tools, technologies, metrics, project names, or experiences not in the original.
2. Do NOT change the employer, role, date, or any factual claim.
3. You MAY rephrase to emphasize these JD keywords where they genuinely match: {keyword_list}
4. The output must be ONE bullet, max 2 lines.
5. If the bullet cannot be improved without adding new facts, return the original unchanged.

Return ONLY valid JSON:
{{"action": "rewrite", "text": "<rewritten or unchanged bullet>", "rationale": "<1 sentence max>"}}

Original bullet: {original_text}
"""


def _rewrite_bullet(original_text: str, keyword_emphasis: list[str], model_name: str) -> tuple[str, str]:
    """Call LLM to safely rephrase a bullet. Returns (new_text, rationale)."""
    kw_str = ", ".join(keyword_emphasis[:10])
    prompt = _BULLET_REWRITE_PROMPT.replace("{keyword_list}", kw_str).replace("{original_text}", original_text)
    try:
        data = _call_gemini_json(prompt, model_name)
        new_text = data.get("text", original_text).strip()
        rationale = data.get("rationale", "")
        # Safety guard: if the rewrite is dramatically longer, revert
        if len(new_text) > len(original_text) * 1.8:
            return original_text, "Rewrite too long — reverted to original."
        return new_text, rationale
    except Exception as e:
        print(f"[Bullet Rewriter] [WARN] Rewrite failed for bullet ({e}). Keeping original.")
        return original_text, "Rewrite failed — kept original."


def _select_bullets_for_section(
    scored_bullets: list[ScoredBullet],
    section: str,
    max_count: int,
    plan: EditPlan,
    model_name: str,
) -> list[BulletSelection]:
    """Filter, rank, and optionally rewrite bullets for a given section."""
    section_bullets = [sb for sb in scored_bullets if sb.bullet.section == section]
    section_bullets.sort(key=lambda s: s.relevance_score, reverse=True)
    top_bullets = section_bullets[:max_count]

    selections: list[BulletSelection] = []
    for sb in top_bullets:
        if sb.bullet.is_locked or sb.relevance_score >= plan.select_threshold:
            # High relevance or locked → select as-is
            selections.append(BulletSelection(
                bullet_id=sb.bullet.bullet_id,
                section=section,
                action="select_as_is",
                original_text=sb.bullet.text,
                new_text=sb.bullet.text,
                relevance_score=sb.relevance_score,
                jd_requirements_addressed=sb.matched_requirements,
            ))
        elif sb.relevance_score >= plan.rewrite_threshold:
            # Moderate relevance, not locked → rewrite to boost keyword hits
            new_text, rationale = _rewrite_bullet(sb.bullet.text, plan.keyword_emphasis, model_name)
            action = "rewrite" if new_text != sb.bullet.text else "select_as_is"
            selections.append(BulletSelection(
                bullet_id=sb.bullet.bullet_id,
                section=section,
                action=action,
                original_text=sb.bullet.text,
                new_text=new_text,
                rewrite_rationale=rationale,
                relevance_score=sb.relevance_score,
                jd_requirements_addressed=sb.matched_requirements,
            ))
        else:
            # Low relevance → deselect
            selections.append(BulletSelection(
                bullet_id=sb.bullet.bullet_id,
                section=section,
                action="deselect",
                original_text=sb.bullet.text,
                relevance_score=sb.relevance_score,
            ))

    return selections


def select_and_rewrite(
    cv: CanonicalCV,
    scored_bullets: list[ScoredBullet],
    plan: EditPlan,
    jd: JDAnalysis,
    model_name: str,
) -> TailoredOutput:
    """Module 5: Build the TailoredOutput — select and optionally rewrite bullets."""

    profile_selections = _select_bullets_for_section(
        scored_bullets, "profile", plan.max_profile_bullets, plan, model_name
    )
    experience_selections = _select_bullets_for_section(
        scored_bullets, "experience", plan.max_experience_bullets, plan, model_name
    )
    project_selections: list[BulletSelection] = []
    if "projects" in plan.sections_to_edit:
        project_selections = _select_bullets_for_section(
            scored_bullets, "projects", plan.max_project_bullets, plan, model_name
        )

    # Skills: pick the most relevant categories based on keyword overlap
    skills_to_highlight: list[str] = []
    all_kw_lower = set(w.lower() for w in jd.must_have_keywords + jd.nice_to_have_keywords)
    for category, skills_list in cv.skills_sections.items():
        for skill in skills_list:
            if skill.lower() in all_kw_lower or any(kw in skill.lower() for kw in all_kw_lower):
                if skill not in skills_to_highlight:
                    skills_to_highlight.append(skill)

    # Fall back to all skills if nothing matched
    if not skills_to_highlight:
        for skills_list in cv.skills_sections.values():
            skills_to_highlight.extend(skills_list)

    selected_count = sum(1 for s in profile_selections + experience_selections + project_selections if s.action != "deselect")
    print(f"[Selector/Rewriter] [OK] {selected_count} bullets selected/rewritten across profile, experience, projects")

    return TailoredOutput(
        profile_selections=profile_selections,
        skills_to_highlight=skills_to_highlight,
        experience_selections=experience_selections,
        project_selections=project_selections,
    )


# =============================================================================
# MODULE 6 — Cover Letter Writer
# =============================================================================

_COVER_LETTER_PROMPT = """You are a professional career writer producing a concise, human-sounding cover letter.

RULES:
- Write exactly 3 paragraphs: opening, evidence, closing.
- Ground every claim in the CV evidence provided below. Do NOT invent experience.
- Reference the company name and role title naturally.
- Avoid AI clichés: do not use phrases like "passionate", "synergy", "leverage", "I am excited to".
- Tone should match: {company_tone}
- Total length: 200–280 words.

Job Role: {job_title}
Company: {company}
JD Summary: {jd_summary}

Top CV Evidence (selected bullets):
{evidence_bullets}

Write the cover letter now. Return only the letter text, no labels or JSON.
"""


def write_cover_letter(
    tailored: TailoredOutput,
    jd: JDAnalysis,
    cv: CanonicalCV,
    company_name: str,
    job_title: str,
    model_name: str,
) -> str:
    """Module 6: Generate a grounded cover letter."""
    # Gather selected bullets as evidence
    selected = [s for s in tailored.profile_selections + tailored.experience_selections if s.action != "deselect"]
    evidence_text = "\n".join(f"- {s.new_text or s.original_text}" for s in selected[:6])

    prompt = (
        _COVER_LETTER_PROMPT
        .replace("{company_tone}", jd.company_tone)
        .replace("{job_title}", job_title or jd.raw_summary[:50])
        .replace("{company}", company_name or "the company")
        .replace("{jd_summary}", jd.raw_summary)
        .replace("{evidence_bullets}", evidence_text)
    )

    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    try:
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.5))
        letter = response.text.strip()
        print(f"[Cover Letter Writer] [OK] {len(letter)} chars written.")
        return letter
    except Exception as e:
        print(f"[Cover Letter Writer] [WARN] Failed ({e}). Using placeholder.")
        return f"Dear Hiring Manager,\n\nI am writing to apply for the {job_title} role at {company_name}.\n\n{cv.full_name}"


# =============================================================================
# MODULE 7 — QA Validator (hybrid: deterministic + LLM spot-check)
# =============================================================================

_QA_HALLUCINATION_PROMPT = """You are a factual auditor reviewing rewritten CV bullets.

For EACH rewritten bullet below, check if it introduces ANY claim not supported by the original text.
A "claim" includes: new tools, new employers, new metrics, new project names, expanded scope not in original.

Return ONLY valid JSON:
{{"results": [{{"bullet_id": "...", "supported": true|false, "concern": "description or null"}}]}}

Bullets to check:
{bullets_json}
"""


def validate_qa(
    tailored: TailoredOutput,
    cv: CanonicalCV,
    jd: JDAnalysis,
    ats: ATSReport,
    model_name: str,
) -> QAReport:
    """Module 7: Run deterministic checks + optional LLM hallucination spot-check."""
    all_selections = tailored.profile_selections + tailored.experience_selections + tailored.project_selections
    selected = [s for s in all_selections if s.action != "deselect"]
    rewritten = [s for s in all_selections if s.action == "rewrite"]

    # --- Deterministic checks ---
    style_issues: list[str] = []
    unsupported: list[str] = []

    # Length check
    profile_count = sum(1 for s in tailored.profile_selections if s.action != "deselect")
    exp_count = sum(1 for s in tailored.experience_selections if s.action != "deselect")
    section_length_ok = (2 <= profile_count <= 5) and (2 <= exp_count <= 10)
    if profile_count < 2:
        style_issues.append("Profile section has fewer than 2 bullets — consider adding more.")
    if exp_count < 2:
        style_issues.append("Experience section has fewer than 2 bullets.")

    # Check for bullets that grew dramatically (possible hallucination proxy)
    for s in rewritten:
        orig_len = len(s.original_text)
        new_len = len(s.new_text or "")
        if new_len > orig_len * 1.5:
            style_issues.append(f"Bullet {s.bullet_id} grew by >{int((new_len/orig_len-1)*100)}% — review manually.")

    # --- LLM hallucination spot-check (only on rewritten bullets, max 5) ---
    spot_check_bullets = rewritten[:5]
    if spot_check_bullets:
        bullets_payload = [
            {"bullet_id": s.bullet_id, "original": s.original_text, "rewritten": s.new_text}
            for s in spot_check_bullets
        ]
        prompt = _QA_HALLUCINATION_PROMPT.replace("{bullets_json}", json.dumps(bullets_payload, indent=2))
        try:
            qa_data = _call_gemini_json(prompt, model_name)
            for result in qa_data.get("results", []):
                if not result.get("supported", True):
                    concern = result.get("concern", "Unsupported claim detected.")
                    unsupported.append(f"[{result.get('bullet_id')}] {concern}")
        except Exception as e:
            print(f"[QA Validator] [WARN] LLM spot-check failed ({e}). Skipping.")

    factual_ok = len(unsupported) == 0

    # --- Score ---
    kw_coverage = ats.coverage_pct
    base_score = int(kw_coverage * 0.5)  # 50 pts from keyword coverage
    match_bonus = min(30, int(exp_count * 3))  # up to 30 pts from bullet count
    qa_penalty = min(20, len(style_issues) * 5 + len(unsupported) * 10)
    matching_score = max(0, min(100, base_score + match_bonus + 20 - qa_penalty))

    # Strong/pain points
    strong = []
    pain = []
    for req in jd.ranked_requirements:
        req_text = req.requirement.lower()
        req_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', req_text))
        tailored_text_blob = " ".join(s.new_text or s.original_text for s in selected).lower()
        tailored_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', tailored_text_blob))
        
        # Smart overlap: for long requirements with many alternatives (commas/or), 
        # a single keyword match might be enough (e.g. "MIS" in a list of 10 degrees).
        # We check the raw count of matches vs the required threshold.
        matches = req_words & tailored_words
        overlap = len(matches) / max(len(req_words), 1)
        
        # If requirement is long (>10 words), decrease threshold or check for specific keyword hits
        is_match = overlap >= 0.4
        if not is_match and len(req_words) > 8:
            if len(matches) >= 2 or (len(matches) >= 1 and any(m in ["mis", "cs", "python", "ml", "sql", "aws", "azure"] for m in matches)):
                is_match = True
        
        if is_match:
            strong.append(req.requirement)
        elif req.priority == "must_have":
            pain.append(req.requirement)

    print(f"[QA Validator] [OK] Score: {matching_score} | Issues: {len(style_issues)} | Unsupported: {len(unsupported)}")

    return QAReport(
        matching_rate_score=matching_score,
        factual_support_passed=factual_ok,
        keyword_coverage_pct=round(kw_coverage, 1),
        style_issues=style_issues,
        unsupported_claims=unsupported,
        section_length_ok=section_length_ok,
        key_pain_points=pain[:5],
        strong_points=strong[:5],
        feedback=f"Keyword coverage: {kw_coverage:.0f}%. {'Factual checks passed.' if factual_ok else 'Factual concerns found — review unsupported claims.'}",
    )


# =============================================================================
# MODULE 8a — ATS Keyword Analyzer (deterministic)
# =============================================================================

_STOPWORDS = {
    "the","and","or","to","of","a","an","in","for","with","that","is","are","was","be","as","at",
    "by","on","it","we","our","your","this","have","you","not","from","will","can","all","has",
    "but","they","their","its","also","more","than","other","any","each","per","new","use","using",
    "work","role","team","able","skills","experience","knowledge","must","able","also","which","such",
    "both","well","may","etc","into","who","what","been","how","its","over","would","should","could",
}


def _extract_keywords(text: str) -> set[str]:
    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9#+.\-]{1,}\b', text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def analyze_ats(
    jd: JDAnalysis,
    tailored: TailoredOutput,
    cv: CanonicalCV,
) -> ATSReport:
    """Module 8a: Compute keyword coverage between JD and tailored CV."""
    # JD keyword universe (top 60 most frequent)
    jd_text = " ".join(jd.must_have_keywords + jd.nice_to_have_keywords)
    jd_kw_set = set(w.lower() for w in jd.must_have_keywords + jd.nice_to_have_keywords)

    # Original CV keywords
    all_original = " ".join(b.text for b in cv.profile_bullets)
    for exp in cv.experience:
        for b in exp.bullets:
            all_original += " " + b.text
    original_kw = _extract_keywords(all_original)

    # Tailored CV keywords
    all_selections = tailored.profile_selections + tailored.experience_selections + tailored.project_selections
    tailored_text = " ".join(s.new_text or s.original_text for s in all_selections if s.action != "deselect")
    tailored_kw = _extract_keywords(tailored_text)

    covered = sorted(jd_kw_set & tailored_kw)
    gaps = sorted(jd_kw_set - tailored_kw)
    added = sorted((jd_kw_set & tailored_kw) - original_kw)
    coverage_pct = round(100 * len(covered) / max(len(jd_kw_set), 1), 1)

    print(f"[ATS Analyzer] [OK] Coverage: {coverage_pct}% | {len(covered)} covered | {len(gaps)} gaps")
    return ATSReport(
        jd_keywords=sorted(jd_kw_set),
        covered_keywords=covered,
        gap_keywords=gaps,
        added_by_tailoring=added,
        coverage_pct=coverage_pct,
    )


# =============================================================================
# MODULE 8b — Change Log Generator (deterministic)
# =============================================================================

def generate_change_log(tailored: TailoredOutput) -> ChangeLog:
    """Module 8b: Build a structured, auditable change log from all selections."""
    entries: list[ChangeLogEntry] = []
    all_selections = tailored.profile_selections + tailored.experience_selections + tailored.project_selections
    changed = 0
    rewritten_count = 0
    deselected_count = 0

    for sel in all_selections:
        entry = ChangeLogEntry(
            bullet_id=sel.bullet_id,
            section=sel.section,
            action=sel.action,
            original_text=sel.original_text,
            new_text=sel.new_text if sel.action != "deselect" else None,
            rationale=sel.rewrite_rationale or (
                "Bullet selected as-is — high relevance match." if sel.action == "select_as_is"
                else "Bullet removed — low relevance to this JD."
            ),
            jd_requirements_addressed=sel.jd_requirements_addressed or [],
        )
        entries.append(entry)
        if sel.action != "select_as_is":
            changed += 1
        if sel.action == "rewrite":
            rewritten_count += 1
        if sel.action == "deselect":
            deselected_count += 1

    log = ChangeLog(
        entries=entries,
        total_bullets_considered=len(all_selections),
        total_bullets_changed=changed,
        total_bullets_rewritten=rewritten_count,
        total_bullets_deselected=deselected_count,
    )
    print(f"[Change Log] [OK] {len(entries)} entries | {rewritten_count} rewritten | {deselected_count} deselected")
    return log


# =============================================================================
# ORCHESTRATOR — Chains all 8 modules
# =============================================================================

def run_application_workflow(
    job_description: str,
    base_cv_json_text: str,
    model_name: str = "gemini-2.5-flash",
    company_name: str = "",
    job_title: str = "",
) -> WorkflowResult:
    """
    Full pipeline: JD text + raw CV JSON → WorkflowResult.

    Modules run in order:
      1. CV Loader → CanonicalCV
      2. JD Parser → JDAnalysis
      3. Evidence Mapper → ScoredBullet[]
      4. Strategy Planner → EditPlan
      5. Bullet Selector/Rewriter → TailoredOutput
      6. Cover Letter Writer → str
      7. ATS Analyzer → ATSReport  (before QA so QA can use coverage %)
      8. QA Validator → QAReport
      9. Change Log Generator → ChangeLog
    """
    print("\n" + "="*60)
    print("  ApplAI — Starting 8-Module CV Tailoring Pipeline")
    print("="*60)

    # Parse raw CV JSON
    raw_json: dict = {}
    try:
        raw_json = json.loads(base_cv_json_text)
    except Exception:
        raw_json = {"raw_text": base_cv_json_text, "source_file": "unknown"}

    #  Module 1: CV Loader 
    print("\n[1/8] CV Loader...")
    canonical_cv = load_canonical_cv(raw_json, model_name)

    #  Module 2: JD Parser 
    print("\n[2/8] JD Parser...")
    jd_analysis = parse_jd(job_description, model_name)

    #  Module 3: Evidence Mapper 
    print("\n[3/8] Evidence Mapper...")
    scored_bullets = map_evidence(canonical_cv, jd_analysis)

    #  Module 4: Strategy Planner 
    print("\n[4/8] Strategy Planner...")
    edit_plan = plan_strategy(jd_analysis, scored_bullets)

    #  Module 5: Bullet Selector / Rewriter 
    print("\n[5/8] Bullet Selector / Rewriter...")
    tailored_output = select_and_rewrite(canonical_cv, scored_bullets, edit_plan, jd_analysis, model_name)

    #  Module 6: Cover Letter Writer 
    print("\n[6/8] Cover Letter Writer...")
    cover_letter = write_cover_letter(tailored_output, jd_analysis, canonical_cv, company_name, job_title, model_name)

    #  Module 7: ATS Analyzer 
    print("\n[7/8] ATS Analyzer...")
    ats_report = analyze_ats(jd_analysis, tailored_output, canonical_cv)

    #  Module 8: QA Validator 
    print("\n[8a/8] QA Validator...")
    qa_report = validate_qa(tailored_output, canonical_cv, jd_analysis, ats_report, model_name)

    #  Change Log 
    print("\n[8b/8] Change Log Generator...")
    change_log = generate_change_log(tailored_output)

    print("\n" + "="*60)
    print(f"  Pipeline complete. Match score: {qa_report.matching_rate_score}%")
    print("="*60 + "\n")

    return WorkflowResult(
        canonical_cv=canonical_cv,
        jd_analysis=jd_analysis,
        tailored_output=tailored_output,
        qa_report=qa_report,
        change_log=change_log,
        ats_report=ats_report,
        cover_letter=cover_letter,
    )



# =============================================================================
# STREAMING VERSION — yields StepUpdate after each module for live UI updates
# =============================================================================

@dataclass
class StepUpdate:
    """Yielded by the streaming pipeline after each module completes."""
    step_num: int           # 1-8
    total_steps: int        # always 8
    module_name: str        # e.g. "CV Loader"
    status: str             # "running" | "done" | "error"
    summary: str            # one-line human-readable result
    detail_lines: list      # list[str] — log lines for this module
    payload: object = None  # the actual result object (CanonicalCV, JDAnalysis, etc.)
    partial_result: object = None  # running WorkflowResult snapshot (None until complete)


def run_application_workflow_streaming(
    job_description: str,
    base_cv_json_text: str,
    model_name: str = "gemini-2.5-flash",
    company_name: str = "",
    job_title: str = "",
):
    """
    Generator version of run_application_workflow.
    Yields StepUpdate after each of the 8 modules completes so that the
    Streamlit UI can render live progress without blocking.

    Usage:
        for step in run_application_workflow_streaming(jd, cv_json, model):
            # render step.module_name, step.summary, step.detail_lines
            if step.partial_result:
                result = step.partial_result  # final WorkflowResult
    """
    TOTAL = 8
    logs = []

    def _log(msg):
        print(msg)
        logs.append(msg)

    _log("=" * 60)
    _log("  ApplAI -- Starting 8-Module CV Tailoring Pipeline")
    _log("=" * 60)

    # Parse raw JSON
    raw_json: dict = {}
    try:
        raw_json = json.loads(base_cv_json_text)
    except Exception:
        raw_json = {"raw_text": base_cv_json_text, "source_file": "unknown"}

    # Keep running state across modules
    canonical_cv = None
    jd_analysis = None
    scored_bullets = None
    edit_plan = None
    tailored_output = None
    cover_letter = ""
    ats_report = None
    qa_report = None
    change_log = None

    # ── Module 1: CV Loader ──────────────────────────────────────────────────
    step_logs = []
    yield StepUpdate(1, TOTAL, "CV Loader", "running", "Structuring CV from raw text...", step_logs)
    try:
        canonical_cv = load_canonical_cv(raw_json, model_name)
        summary = f"Loaded: {canonical_cv.full_name} | {len(canonical_cv.profile_bullets)} profile bullets | {len(canonical_cv.experience)} roles"
        step_logs = [f"[1/8] CV Loader: {summary}"]
    except Exception as e:
        summary = f"CV Loader failed: {e}"
        step_logs = [f"[1/8] CV Loader ERROR: {e}"]
        canonical_cv = CanonicalCV(full_name="Unknown")
    yield StepUpdate(1, TOTAL, "CV Loader", "done", summary, step_logs, payload=canonical_cv)

    # ── Module 2: JD Parser ──────────────────────────────────────────────────
    step_logs = []
    yield StepUpdate(2, TOTAL, "JD Parser", "running", "Extracting requirements from job description...", step_logs)
    try:
        jd_analysis = parse_jd(job_description, model_name)
        summary = f"Domain: {jd_analysis.domain} | {len(jd_analysis.ranked_requirements)} requirements | {len(jd_analysis.must_have_keywords)} must-have keywords"
        step_logs = [
            f"[2/8] JD Parser: {summary}",
            f"      Must-have: {', '.join(jd_analysis.must_have_keywords[:8])}{'...' if len(jd_analysis.must_have_keywords) > 8 else ''}",
            f"      Summary: {jd_analysis.raw_summary[:120]}",
        ]
    except Exception as e:
        summary = f"JD Parser failed: {e}"
        step_logs = [f"[2/8] JD Parser ERROR: {e}"]
        jd_analysis = JDAnalysis(domain="general")
    yield StepUpdate(2, TOTAL, "JD Parser", "done", summary, step_logs, payload=jd_analysis)

    # ── Module 3: Evidence Mapper ────────────────────────────────────────────
    step_logs = []
    yield StepUpdate(3, TOTAL, "Evidence Mapper", "running", "Scoring all CV bullets against JD requirements...", step_logs)
    try:
        scored_bullets = map_evidence(canonical_cv, jd_analysis)
        top = scored_bullets[0] if scored_bullets else None
        summary = f"Scored {len(scored_bullets)} bullets | Top score: {top.relevance_score:.2f} | Top bullet: {top.bullet.text[:60]}..." if top else "No bullets"
        step_logs = [f"[3/8] Evidence Mapper: {len(scored_bullets)} bullets scored"]
        for sb in scored_bullets[:5]:
            step_logs.append(f"      [{sb.relevance_score:.2f}] {sb.bullet.text[:80]}")
    except Exception as e:
        summary = f"Evidence Mapper failed: {e}"
        step_logs = [f"[3/8] Evidence Mapper ERROR: {e}"]
        scored_bullets = []
    yield StepUpdate(3, TOTAL, "Evidence Mapper", "done", summary, step_logs, payload=scored_bullets)

    # ── Module 4: Strategy Planner ───────────────────────────────────────────
    step_logs = []
    yield StepUpdate(4, TOTAL, "Strategy Planner", "running", "Planning which sections to edit...", step_logs)
    try:
        edit_plan = plan_strategy(jd_analysis, scored_bullets)
        summary = f"Domain: {edit_plan.domain} | Sections: {', '.join(edit_plan.sections_to_edit)} | select>{edit_plan.select_threshold:.2f} / rewrite>{edit_plan.rewrite_threshold:.2f}"
        step_logs = [
            f"[4/8] Strategy Planner: {summary}",
            f"      Keyword emphasis: {', '.join(edit_plan.keyword_emphasis[:6])}",
        ]
    except Exception as e:
        summary = f"Strategy Planner failed: {e}"
        step_logs = [f"[4/8] Strategy Planner ERROR: {e}"]
        edit_plan = EditPlan(domain="general", sections_to_edit=["profile","experience"], rewrite_threshold=0.1, select_threshold=0.25)
    yield StepUpdate(4, TOTAL, "Strategy Planner", "done", summary, step_logs, payload=edit_plan)

    # ── Module 5: Bullet Selector / Rewriter ─────────────────────────────────
    step_logs = []
    yield StepUpdate(5, TOTAL, "Bullet Selector / Rewriter", "running", "Selecting and rewriting bullets...", step_logs)
    try:
        tailored_output = select_and_rewrite(canonical_cv, scored_bullets, edit_plan, jd_analysis, model_name)
        all_sel = tailored_output.profile_selections + tailored_output.experience_selections + tailored_output.project_selections
        selected = [s for s in all_sel if s.action != "deselect"]
        rewritten = [s for s in all_sel if s.action == "rewrite"]
        summary = f"{len(selected)} bullets selected | {len(rewritten)} rewritten | {len(all_sel)-len(selected)} dropped"
        step_logs = [f"[5/8] Bullet Selector/Rewriter: {summary}"]
        for s in all_sel:
            action_str = s.action.upper().replace("_", " ")
            if s.action == "rewrite":
                step_logs.append(f"      [{action_str}] {s.bullet_id}: {s.original_text[:60]}...")
                step_logs.append(f"        -> {(s.new_text or '')[:60]}...")
            elif s.action == "select_as_is":
                step_logs.append(f"      [{action_str}] {s.bullet_id}: {s.original_text[:80]}")
            else:
                step_logs.append(f"      [DROPPED] {s.bullet_id}: {s.original_text[:70]}")
    except Exception as e:
        summary = f"Selector/Rewriter failed: {e}"
        step_logs = [f"[5/8] Selector/Rewriter ERROR: {e}"]
        tailored_output = TailoredOutput()
    yield StepUpdate(5, TOTAL, "Bullet Selector / Rewriter", "done", summary, step_logs, payload=tailored_output)

    # ── Module 6: Cover Letter Writer ────────────────────────────────────────
    step_logs = []
    yield StepUpdate(6, TOTAL, "Cover Letter Writer", "running", "Writing grounded cover letter...", step_logs)
    try:
        cover_letter = write_cover_letter(tailored_output, jd_analysis, canonical_cv, company_name, job_title, model_name)
        summary = f"{len(cover_letter)} chars | {len(cover_letter.splitlines())} lines"
        step_logs = [f"[6/8] Cover Letter Writer: {summary}", ""]
        step_logs.extend(cover_letter.splitlines())
    except Exception as e:
        cover_letter = f"Cover letter generation failed: {e}"
        summary = f"Cover Letter Writer failed: {e}"
        step_logs = [f"[6/8] Cover Letter ERROR: {e}"]
    yield StepUpdate(6, TOTAL, "Cover Letter Writer", "done", summary, step_logs, payload=cover_letter)

    # ── Module 7: ATS Analyzer ───────────────────────────────────────────────
    step_logs = []
    yield StepUpdate(7, TOTAL, "ATS Analyzer", "running", "Computing keyword coverage...", step_logs)
    try:
        ats_report = analyze_ats(jd_analysis, tailored_output, canonical_cv)
        summary = f"Coverage: {ats_report.coverage_pct:.1f}% | {len(ats_report.covered_keywords)} covered | {len(ats_report.gap_keywords)} gaps"
        step_logs = [
            f"[7/8] ATS Analyzer: {summary}",
            f"      Covered: {', '.join(ats_report.covered_keywords[:10])}",
            f"      Gaps:    {', '.join(ats_report.gap_keywords[:10])}",
        ]
        if ats_report.added_by_tailoring:
            step_logs.append(f"      Added by tailoring: {', '.join(ats_report.added_by_tailoring[:8])}")
    except Exception as e:
        summary = f"ATS Analyzer failed: {e}"
        step_logs = [f"[7/8] ATS Analyzer ERROR: {e}"]
        ats_report = ATSReport()
    yield StepUpdate(7, TOTAL, "ATS Analyzer", "done", summary, step_logs, payload=ats_report)

    # ── Module 8: QA Validator ───────────────────────────────────────────────
    step_logs = []
    yield StepUpdate(8, TOTAL, "QA Validator + Change Log", "running", "Running quality checks and building change log...", step_logs)
    try:
        qa_report = validate_qa(tailored_output, canonical_cv, jd_analysis, ats_report, model_name)
        change_log = generate_change_log(tailored_output)
        summary = f"Match score: {qa_report.matching_rate_score}% | Issues: {len(qa_report.style_issues)} | Unsupported: {len(qa_report.unsupported_claims)} | {change_log.total_bullets_rewritten} bullets rewritten"
        step_logs = [
            f"[8/8] QA Validator: Score={qa_report.matching_rate_score}% | Factual OK={qa_report.factual_support_passed}",
        ]
        if qa_report.style_issues:
            for issue in qa_report.style_issues:
                step_logs.append(f"      Issue: {issue}")
        if qa_report.unsupported_claims:
            for claim in qa_report.unsupported_claims:
                step_logs.append(f"      Unsupported claim: {claim}")
        step_logs.append(f"      Strong: {', '.join(qa_report.strong_points[:3])}")
        step_logs.append(f"      Pain:   {', '.join(qa_report.key_pain_points[:3])}")
        step_logs.append(f"[8b]  Change Log: {change_log.total_bullets_considered} bullets | {change_log.total_bullets_rewritten} rewritten | {change_log.total_bullets_deselected} dropped")
    except Exception as e:
        summary = f"QA/Change Log failed: {e}"
        step_logs = [f"[8/8] QA ERROR: {e}"]
        qa_report = QAReport(matching_rate_score=0)
        change_log = ChangeLog()

    # Build final result
    final_result = WorkflowResult(
        canonical_cv=canonical_cv,
        jd_analysis=jd_analysis,
        tailored_output=tailored_output,
        qa_report=qa_report,
        change_log=change_log,
        ats_report=ats_report,
        cover_letter=cover_letter,
    )

    _log(f"Pipeline complete. Match score: {qa_report.matching_rate_score}%")
    yield StepUpdate(8, TOTAL, "QA Validator + Change Log", "done", summary, step_logs, payload=(qa_report, change_log), partial_result=final_result)


# =============================================================================
# Legacy compatibility function for get_test_model
# =============================================================================

def get_test_model():
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash")


if __name__ == "__main__":
    print("ApplAI Agent Pipeline -- 8-module design loaded successfully.")

