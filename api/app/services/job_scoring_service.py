from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from api.app.config import settings
from api.app.schemas.jobs import ScoreJobRequest, ScoreJobResponse


STOPWORDS = {
    "about",
    "across",
    "after",
    "also",
    "and",
    "are",
    "can",
    "for",
    "from",
    "has",
    "have",
    "into",
    "our",
    "the",
    "their",
    "this",
    "that",
    "with",
    "will",
    "work",
    "you",
    "your",
}

TECH_TERMS = {
    "ai",
    "api",
    "apis",
    "automation",
    "backend",
    "cloud",
    "crm",
    "css",
    "data",
    "database",
    "django",
    "docx",
    "etl",
    "fastapi",
    "firebase",
    "frontend",
    "gemini",
    "git",
    "github",
    "google",
    "html",
    "java",
    "javascript",
    "json",
    "kotlin",
    "langchain",
    "llm",
    "machine",
    "node",
    "nodejs",
    "pdf",
    "postgres",
    "postgresql",
    "python",
    "react",
    "rest",
    "sql",
    "typescript",
    "vite",
}

PHRASES = {
    "artificial intelligence": "ai",
    "business analyst": "business-analyst",
    "data analyst": "data-analyst",
    "data engineer": "data-engineer",
    "full stack": "full-stack",
    "full-stack": "full-stack",
    "google apps script": "google-apps-script",
    "machine learning": "machine-learning",
    "rest api": "rest-api",
    "software developer": "software-developer",
    "technical analyst": "technical-analyst",
}

FALLBACK_PROFILE_TEXT = """
Software developer and technical business analyst with Python, JavaScript, React,
Node, SQL, REST API, automation, CRM integration, Google Apps Script, data
processing, machine learning coursework, and document automation experience.
"""


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9#+.\-]{1,}\b", text.lower())
    return [token.strip(".-") for token in tokens if token not in STOPWORDS and len(token) > 1]


def _terms(text: str) -> List[str]:
    found = set(_tokenize(text))
    lowered = text.lower()
    for phrase, canonical in PHRASES.items():
        if phrase in lowered:
            found.add(canonical)
    return sorted(found)


def _job_terms(text: str) -> List[str]:
    terms = set(_terms(text))
    technical = {term for term in terms if term in TECH_TERMS or term in PHRASES.values()}
    if len(technical) >= 5:
        return sorted(technical)
    return sorted(terms)


def _load_profile_text() -> str:
    exports_dir = Path(settings.json_exports_dir)
    if not exports_dir.exists():
        return FALLBACK_PROFILE_TEXT.strip()

    payloads: List[str] = []
    for path in sorted(exports_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        raw_text = data.get("raw_text")
        if isinstance(raw_text, str) and raw_text.strip():
            payloads.append(raw_text)

    return "\n\n".join(payloads).strip() or FALLBACK_PROFILE_TEXT.strip()


def _evidence_blocks(profile_text: str) -> List[Tuple[str, str]]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", profile_text) if p.strip()]
    if not paragraphs:
        return [("profile_1", profile_text)]
    return [(f"profile_{index}", paragraph) for index, paragraph in enumerate(paragraphs, start=1)]


def _rank_evidence(blocks: Sequence[Tuple[str, str]], job_terms: Iterable[str]) -> List[str]:
    wanted = set(job_terms)
    scored: List[Tuple[int, str]] = []
    for block_id, text in blocks:
        overlap = wanted & set(_terms(text))
        if overlap:
            scored.append((len(overlap), block_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [block_id for _, block_id in scored[:5]]


def _recommendation(score: int) -> str:
    if score >= 70:
        return "apply"
    if score >= 45:
        return "worth_20_minutes"
    return "skip"


def _reasons(score: int, matched_terms: Sequence[str], company_name: str | None, job_title: str | None) -> List[str]:
    reasons: List[str] = []
    if matched_terms:
        reasons.append(f"Profile evidence covers {len(matched_terms)} important job terms: {', '.join(matched_terms[:8])}.")
    if job_title:
        reasons.append(f"Scored against pasted description for {job_title}.")
    if company_name:
        reasons.append(f"Company context captured for {company_name}.")
    if score >= 70:
        reasons.append("Strong enough match to consider a full application packet.")
    elif score >= 45:
        reasons.append("Partial match; worth a short review before investing in a full tailoring run.")
    return reasons or ["Insufficient overlap found between the pasted job description and available profile evidence."]


def _concerns(score: int, missing_terms: Sequence[str], evidence_ids: Sequence[str]) -> List[str]:
    concerns: List[str] = []
    if missing_terms:
        concerns.append(f"Missing or weakly represented keywords: {', '.join(missing_terms[:8])}.")
    if not evidence_ids:
        concerns.append("No strong evidence block was found in the current local master CV exports.")
    if score < 45:
        concerns.append("Low deterministic match score; skip unless there is outside context not captured locally.")
    return concerns


def score_job(payload: ScoreJobRequest) -> ScoreJobResponse:
    profile_text = _load_profile_text()
    job_terms = _job_terms(payload.job_description)
    profile_terms = set(_terms(profile_text))
    matched_terms = sorted(set(job_terms) & profile_terms)
    missing_terms = sorted(set(job_terms) - profile_terms)

    coverage = len(matched_terms) / max(len(job_terms), 1)
    score = round(min(100, coverage * 85 + min(len(matched_terms), 10) * 1.5))

    digest_source = "\n".join(
        [
            payload.company_name or "",
            payload.job_title or "",
            payload.source_url or "",
            payload.job_description,
        ]
    )
    job_id = "job_" + hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]
    evidence_ids = _rank_evidence(_evidence_blocks(profile_text), job_terms)

    return ScoreJobResponse(
        job_id=job_id,
        match_score=max(0, min(100, score)),
        recommendation=_recommendation(score),
        reasons=_reasons(score, matched_terms, payload.company_name, payload.job_title),
        concerns=_concerns(score, missing_terms, evidence_ids),
        missing_keywords=missing_terms[:12],
        best_evidence_block_ids=evidence_ids,
    )
