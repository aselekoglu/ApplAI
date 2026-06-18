from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Iterable, List, Sequence

from api.app.schemas.career_brain import CareerBrainProfile, EvidenceBlock, utc_now_iso
from api.app.schemas.jobs import (
    EvidenceMatch,
    JobRecord,
    ParsedJobDescription,
    ScoreJobRequest,
    ScoreJobResponse,
    ScoreReport,
)
from api.app.services.career_brain_service import ensure_career_brain_profile
from api.app.services.job_records_service import save_job_record


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
    "llms",
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
    "business systems": "business-systems",
    "data analyst": "data-analyst",
    "data engineer": "data-engineer",
    "full stack": "full-stack",
    "full-stack": "full-stack",
    "google apps script": "google-apps-script",
    "machine learning": "machine-learning",
    "rest api": "rest-api",
    "software developer": "software-developer",
    "technical analyst": "technical-analyst",
    "workflow automation": "workflow-automation",
}

RESPONSIBILITY_MARKERS = ("responsib", "what you", "duties", "you will", "day to day", "role")
QUALIFICATION_MARKERS = ("qualification", "requirement", "must have", "preferred", "skills", "experience")
LOCATION_TERMS = ("remote", "hybrid", "on-site", "onsite", "ottawa", "toronto", "canada", "ontario")
EFFORT_TERMS = ("cover letter", "portfolio", "assessment", "security clearance", "clearance", "travel", "references")


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


def _canonical_terms(values: Iterable[str]) -> set[str]:
    terms: set[str] = set()
    for value in values:
        terms.update(_terms(value))
    return terms


def _line_items(text: str) -> List[str]:
    items: List[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"^\s*[-*•\d.)]+\s*", "", raw_line).strip()
        if 8 <= len(line) <= 260:
            items.append(line)
    if items:
        return items
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [sentence.strip() for sentence in sentences if 20 <= len(sentence.strip()) <= 260][:12]


def _section_items(text: str, markers: Sequence[str]) -> List[str]:
    lowered_markers = tuple(marker.lower() for marker in markers)
    items = _line_items(text)
    selected: List[str] = []
    active = False
    for item in items:
        lowered = item.lower()
        if any(marker in lowered for marker in lowered_markers):
            active = True
            if len(item.split()) > 4:
                selected.append(item)
            continue
        if active:
            if any(marker in lowered for marker in RESPONSIBILITY_MARKERS + QUALIFICATION_MARKERS) and selected:
                break
            selected.append(item)
    return selected[:10]


def _keywords(text: str) -> List[str]:
    terms = _terms(text)
    technical = {term for term in terms if term in TECH_TERMS or term in PHRASES.values()}
    counts = Counter(term for term in terms if len(term) > 2)
    ranked = [term for term, _ in counts.most_common() if term in technical]
    if len(ranked) < 8:
        ranked.extend(term for term, _ in counts.most_common() if term not in ranked)
    return sorted(dict.fromkeys(ranked))[:24]


def parse_job_description(text: str) -> ParsedJobDescription:
    responsibilities = _section_items(text, RESPONSIBILITY_MARKERS)
    qualifications = _section_items(text, QUALIFICATION_MARKERS)
    if not responsibilities:
        responsibilities = _line_items(text)[:5]
    if not qualifications:
        qualifications = [item for item in _line_items(text) if any(term in item.lower() for term in TECH_TERMS)][:5]

    lowered = text.lower()
    if re.search(r"\b(senior|lead|principal|staff)\b", lowered):
        seniority = "senior"
    elif re.search(r"\b(junior|entry|intern|co-op|coop|student)\b", lowered):
        seniority = "early_career"
    elif re.search(r"\b(\d\+?\s+years|years of experience)\b", lowered):
        seniority = "mid_level"
    else:
        seniority = "unspecified"

    domain = "general"
    for candidate, triggers in {
        "ai_automation": ("ai", "llm", "automation", "machine learning"),
        "software": ("software", "backend", "frontend", "full stack", "api"),
        "data": ("data analyst", "data engineer", "sql", "etl", "reporting"),
        "business_systems": ("business analyst", "crm", "systems analyst"),
    }.items():
        if any(trigger in lowered for trigger in triggers):
            domain = candidate
            break

    return ParsedJobDescription(
        responsibilities=responsibilities[:10],
        qualifications=qualifications[:10],
        keywords=_keywords(text),
        seniority=seniority,
        domain=domain,
        location_remote_hints=[term for term in LOCATION_TERMS if term in lowered],
        effort_signals=[term for term in EFFORT_TERMS if term in lowered],
    )


def _profile_terms(profile: CareerBrainProfile) -> set[str]:
    values: List[str] = []
    values.extend(block.text for block in profile.evidence_blocks)
    for block in profile.evidence_blocks:
        values.extend(block.technologies)
        values.extend(block.skill_categories)
        values.extend(block.ats_keywords)
        values.extend(block.relevance_tags)
    for skills in profile.skills.categories.values():
        values.extend(skills)
    values.extend(profile.skills.categories.keys())
    values.extend(profile.role_preferences.preferred_roles)
    values.extend(profile.writing_preferences.preferred_terms)
    return _canonical_terms(values)


def _evidence_terms(block: EvidenceBlock) -> set[str]:
    return _canonical_terms(
        [block.text, block.source_label]
        + block.relevance_tags
        + block.technologies
        + block.skill_categories
        + block.ats_keywords
    )


def _rank_evidence(blocks: Sequence[EvidenceBlock], wanted_terms: set[str]) -> List[EvidenceMatch]:
    matches: List[EvidenceMatch] = []
    for block in blocks:
        overlap = sorted(wanted_terms & _evidence_terms(block))
        if not overlap:
            continue
        score = len(overlap) * 10 + block.priority
        matches.append(EvidenceMatch(evidence_block_id=block.block_id, score=score, matched_terms=overlap[:10]))
    matches.sort(key=lambda item: (-item.score, item.evidence_block_id))
    return matches[:5]


def _role_preference_hits(profile: CareerBrainProfile, parsed: ParsedJobDescription, payload: ScoreJobRequest) -> List[str]:
    context = " ".join([payload.job_title or "", parsed.domain, payload.job_description]).lower()
    hits: List[str] = []
    for role in profile.role_preferences.preferred_roles:
        role_terms = _terms(role)
        if role_terms and any(term.replace("-", " ") in context or term in context for term in role_terms):
            hits.append(role)
    return hits[:5]


def _skill_category_hits(profile: CareerBrainProfile, wanted_terms: set[str]) -> List[str]:
    hits: List[str] = []
    for category, skills in profile.skills.categories.items():
        category_terms = _canonical_terms([category] + skills)
        if wanted_terms & category_terms:
            hits.append(category)
    return hits


def _recommendation(score: int, concerns: Sequence[str]) -> str:
    if score >= 70 and not any("senior" in concern.lower() for concern in concerns):
        return "apply"
    if score >= 45:
        return "worth_20_minutes"
    return "skip"


def _job_id(payload: ScoreJobRequest) -> str:
    digest_source = "\n".join(
        [
            payload.company_name or "",
            payload.job_title or "",
            payload.source_url or "",
            payload.job_description,
        ]
    )
    return "job_" + hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]


def _score_report(payload: ScoreJobRequest, parsed: ParsedJobDescription, profile: CareerBrainProfile) -> ScoreReport:
    wanted_terms = set(parsed.keywords)
    career_terms = _profile_terms(profile)
    matched_terms = sorted(wanted_terms & career_terms)
    missing_terms = sorted(wanted_terms - career_terms)
    evidence_matches = _rank_evidence(profile.evidence_blocks, wanted_terms)
    role_hits = _role_preference_hits(profile, parsed, payload)
    skill_hits = _skill_category_hits(profile, wanted_terms)

    keyword_coverage = len(matched_terms) / max(len(wanted_terms), 1)
    evidence_component = min(25, sum(match.score for match in evidence_matches[:3]) // 5)
    role_component = min(15, len(role_hits) * 8)
    skill_component = min(10, len(skill_hits) * 3)
    score = round(keyword_coverage * 50 + evidence_component + role_component + skill_component)

    concerns: List[str] = []
    if missing_terms:
        concerns.append(f"Missing or weakly represented keywords: {', '.join(missing_terms[:8])}.")
    if not evidence_matches:
        concerns.append("No strong Career Brain evidence block matched the job keywords.")
    if parsed.seniority == "senior":
        concerns.append("Job appears senior-level; confirm scope and years of experience before investing heavily.")
    if parsed.effort_signals:
        concerns.append(f"Extra application effort detected: {', '.join(parsed.effort_signals[:5])}.")

    bounded_score = max(0, min(100, score))
    recommendation = _recommendation(bounded_score, concerns)

    reasons: List[str] = []
    if matched_terms:
        reasons.append(f"Career Brain covers {len(matched_terms)} JD keywords: {', '.join(matched_terms[:8])}.")
    if evidence_matches:
        reasons.append(f"Found {len(evidence_matches)} relevant Career Brain evidence blocks.")
    if role_hits:
        reasons.append(f"Role aligns with preferences: {', '.join(role_hits[:3])}.")
    if skill_hits:
        reasons.append(f"Relevant skill categories: {', '.join(skill_hits[:5])}.")
    if recommendation == "apply":
        reasons.append("Strong enough match to consider a full application packet.")
    elif recommendation == "worth_20_minutes":
        reasons.append("Partial match; worth a short review before a full tailoring run.")
    if not reasons:
        reasons.append("Insufficient overlap found between the job description and Career Brain evidence.")

    top_ids = [match.evidence_block_id for match in evidence_matches]
    return ScoreReport(
        match_score=bounded_score,
        recommendation=recommendation,
        reasons=reasons,
        concerns=concerns,
        missing_keywords=missing_terms[:12],
        top_evidence_block_ids=top_ids,
        evidence_matches=evidence_matches,
        keyword_coverage=round(keyword_coverage, 3),
        role_preference_hits=role_hits,
        skill_category_hits=skill_hits,
    )


def score_job(payload: ScoreJobRequest) -> ScoreJobResponse:
    profile = ensure_career_brain_profile()
    parsed = parse_job_description(payload.job_description)
    report = _score_report(payload, parsed, profile)
    job_id = _job_id(payload)

    saved = False
    record_path = None
    if payload.save_draft:
        now = utc_now_iso()
        record = JobRecord(
            job_id=job_id,
            company_name=payload.company_name,
            job_title=payload.job_title,
            source_url=payload.source_url,
            raw_description=payload.job_description,
            parsed=parsed,
            score_report=report,
            recommendation=report.recommendation,
            status="draft",
            created_at=now,
            updated_at=now,
        )
        record_path = save_job_record(record)
        saved = True

    return ScoreJobResponse(
        job_id=job_id,
        company_name=payload.company_name,
        job_title=payload.job_title,
        source_url=payload.source_url,
        match_score=report.match_score,
        recommendation=report.recommendation,
        reasons=report.reasons,
        concerns=report.concerns,
        missing_keywords=report.missing_keywords,
        best_evidence_block_ids=report.top_evidence_block_ids,
        top_evidence_block_ids=report.top_evidence_block_ids,
        parsed_jd_summary=parsed,
        score_report=report,
        saved=saved,
        job_record_path=record_path,
    )
