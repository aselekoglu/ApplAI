from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from api.app.config import settings
from api.app.schemas.career_brain import CareerBrainProfile, EvidenceBlock, SkillInventory
from api.app.schemas.jobs import ScoreJobRequest
from api.app.services.career_brain_service import save_career_brain_profile
from api.app.services.job_records_service import list_job_records, load_job_record
from api.app.services.job_scoring_service import score_job


class JobScoringServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._original_docs_dir = settings.docs_dir
        self._tmp = tempfile.TemporaryDirectory()
        settings.docs_dir = self._tmp.name
        profile = CareerBrainProfile(
            role_preferences={"preferred_roles": ["Software Developer", "AI Automation Developer", "Technical Analyst"]},
            skills=SkillInventory(
                categories={
                    "programming": ["Python", "TypeScript", "SQL"],
                    "web": ["FastAPI", "React", "REST APIs"],
                    "automation": ["workflow automation", "Google Apps Script"],
                    "ai": ["LLMs", "AI-assisted workflows"],
                }
            ),
            evidence_blocks=[
                EvidenceBlock(
                    block_id="ev_api_automation",
                    kind="project",
                    text="Built Python FastAPI services, React dashboards, SQL reports, and workflow automation for business users.",
                    source_label="Test Career Brain",
                    technologies=["Python", "FastAPI", "React", "SQL"],
                    skill_categories=["programming", "web", "automation"],
                    ats_keywords=["REST APIs", "workflow automation"],
                    priority=5,
                ),
                EvidenceBlock(
                    block_id="ev_ai_tools",
                    kind="project",
                    text="Developed LLM-assisted document automation and AI workflow tooling.",
                    source_label="Test Career Brain",
                    technologies=["LLMs", "Python"],
                    skill_categories=["ai", "automation"],
                    ats_keywords=["AI", "document automation"],
                    priority=4,
                ),
            ],
        )
        save_career_brain_profile(profile)

    def tearDown(self) -> None:
        settings.docs_dir = self._original_docs_dir
        self._tmp.cleanup()

    def test_score_job_returns_contract_fields(self) -> None:
        result = score_job(
            ScoreJobRequest(
                job_description="Python developer role building REST APIs, React dashboards, SQL reports, and automation.",
                company_name="ExampleCo",
                job_title="Software Developer",
            )
        )

        self.assertTrue(result.job_id.startswith("job_"))
        self.assertGreaterEqual(result.match_score, 0)
        self.assertLessEqual(result.match_score, 100)
        self.assertIn(result.recommendation, {"apply", "skip", "worth_20_minutes"})
        self.assertIsInstance(result.reasons, list)
        self.assertIsInstance(result.concerns, list)
        self.assertIsInstance(result.missing_keywords, list)
        self.assertIsInstance(result.best_evidence_block_ids, list)
        self.assertEqual(result.best_evidence_block_ids, result.top_evidence_block_ids)
        self.assertTrue(result.parsed_jd_summary.keywords)
        self.assertEqual(result.score_report.match_score, result.match_score)

    def test_score_job_is_deterministic_for_same_input(self) -> None:
        payload = ScoreJobRequest(job_description="Python SQL React automation")

        first = score_job(payload)
        second = score_job(payload)

        self.assertEqual(first.job_id, second.job_id)
        self.assertEqual(first.match_score, second.match_score)
        self.assertEqual(first.recommendation, second.recommendation)

    def test_score_job_can_persist_draft_record(self) -> None:
        result = score_job(
            ScoreJobRequest(
                job_description="Software Developer building Python FastAPI REST APIs, React tools, SQL reporting, and workflow automation.",
                company_name="DraftCo",
                job_title="Software Developer",
                save_draft=True,
            )
        )

        self.assertTrue(result.saved)
        self.assertIsNotNone(result.job_record_path)
        expected_description = (
            "Software Developer building Python FastAPI REST APIs, React tools, SQL reporting, and workflow automation."
        )
        record = load_job_record(result.job_id)
        self.assertEqual(record.company_name, "DraftCo")
        self.assertEqual(record.raw_description, expected_description)
        self.assertEqual(record.recommendation, result.recommendation)
        self.assertEqual(record.parsed.keywords, result.parsed_jd_summary.keywords)
        self.assertEqual([item.job_id for item in list_job_records()], [result.job_id])

    def test_career_brain_evidence_drives_apply_recommendation(self) -> None:
        result = score_job(
            ScoreJobRequest(
                job_description=(
                    "Software Developer role. Responsibilities include building Python FastAPI REST APIs, "
                    "React dashboards, SQL reports, and workflow automation for internal teams."
                ),
                job_title="Software Developer",
            )
        )

        self.assertEqual(result.recommendation, "apply")
        self.assertIn("ev_api_automation", result.top_evidence_block_ids)
        self.assertIn("web", result.score_report.skill_category_hits)

    def test_recommendation_boundaries(self) -> None:
        weak = score_job(
            ScoreJobRequest(job_description="Senior embedded firmware role using Rust, C++, CAN bus, and device drivers.")
        )
        partial = score_job(
            ScoreJobRequest(
                job_description=(
                    "Technical Analyst role using SQL reporting, Python automation, stakeholder documentation, "
                    "and vendor coordination."
                )
            )
        )

        self.assertEqual(weak.recommendation, "skip")
        self.assertEqual(partial.recommendation, "worth_20_minutes")

    def test_docs_jobs_json_files_are_gitignored(self) -> None:
        completed = subprocess.run(
            ["git", "check-ignore", "docs/jobs/example-private-job.json"],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
