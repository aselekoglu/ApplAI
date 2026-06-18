from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import agent_workflow

from api.app.config import settings
from api.app.schemas.career_brain import CareerBrainProfile, EvidenceBlock, SkillInventory
from api.app.schemas.jobs import ScoreJobRequest
from api.app.services.career_brain_service import save_career_brain_profile
from api.app.services.job_scoring_service import score_job
from api.app.services.tailoring_service import get_run_record, run_tailoring_job
from api.app.schemas.tailoring import TailorRunOptions, TailorRunRequest


class TailoringServiceSprint3Test(unittest.TestCase):
    def setUp(self) -> None:
        self._original_docs_dir = settings.docs_dir
        self._tmp = tempfile.TemporaryDirectory()
        settings.docs_dir = self._tmp.name
        Path(settings.json_exports_dir).mkdir(parents=True, exist_ok=True)
        self.master_id = "test_master"
        self.master_payload = {
            "source_file": "test_master.docx",
            "source_docx": "test_master.docx",
            "raw_text": "Ata built Python FastAPI services and React dashboards for workflow automation.",
        }
        Path(settings.json_exports_dir, f"{self.master_id}.json").write_text(
            json.dumps(self.master_payload),
            encoding="utf-8",
        )
        Path(settings.docs_dir, "test_master.docx").write_bytes(b"placeholder")

        profile = CareerBrainProfile(
            skills=SkillInventory(
                categories={
                    "programming": ["Python", "TypeScript", "SQL"],
                    "web": ["FastAPI", "React", "REST APIs"],
                    "automation": ["workflow automation"],
                }
            ),
            evidence_blocks=[
                EvidenceBlock(
                    block_id="ev_api_automation",
                    kind="project",
                    text="Built Python FastAPI services, REST APIs, React dashboards, and workflow automation for business users.",
                    source_label="Career Brain Test Evidence",
                    source_path="docs/career_brain/profile.json",
                    technologies=["Python", "FastAPI", "React"],
                    ats_keywords=["REST APIs", "workflow automation"],
                    priority=5,
                ),
                EvidenceBlock(
                    block_id="ev_sql_reporting",
                    kind="experience",
                    text="Created SQL reporting workflows for internal stakeholders.",
                    source_label="Career Brain SQL Evidence",
                    technologies=["SQL"],
                    ats_keywords=["reporting"],
                    priority=3,
                ),
            ],
        )
        save_career_brain_profile(profile)
        scored = score_job(
            ScoreJobRequest(
                job_description="Software Developer role building Python FastAPI REST APIs, React dashboards, and automation.",
                company_name="CoreCo",
                job_title="Software Developer",
                save_draft=True,
            )
        )
        self.job_id = scored.job_id

    def tearDown(self) -> None:
        settings.docs_dir = self._original_docs_dir
        self._tmp.cleanup()

    def _fake_workflow_result(self, job_description: str, base_cv_json_text: str, options: TailorRunOptions):
        self.assertIn("Python FastAPI REST APIs", job_description)
        self.assertEqual(options.company_name, "CoreCo")
        cv = agent_workflow.CanonicalCV(
            full_name="Ata Selekoglu",
            profile_bullets=[
                agent_workflow.BulletEvidence(
                    bullet_id="prof_0",
                    text="Built Python FastAPI services for workflow automation.",
                    section="profile",
                )
            ],
            skills_sections={"Technical": ["Python", "FastAPI", "React"]},
        )
        jd = agent_workflow.JDAnalysis(
            domain="software",
            must_have_keywords=["python", "fastapi", "react", "automation"],
            raw_summary="Build internal software automation.",
        )
        tailored = agent_workflow.TailoredOutput(
            profile_selections=[
                agent_workflow.BulletSelection(
                    bullet_id="prof_0",
                    section="profile",
                    action="rewrite",
                    original_text="Built Python FastAPI services for workflow automation.",
                    new_text="Built Python FastAPI services for workflow automation and Kubernetes platforms.",
                    rewrite_rationale="Emphasized platform delivery.",
                    relevance_score=0.9,
                    jd_requirements_addressed=["Build internal software automation."],
                )
            ],
            skills_to_highlight=["Python", "FastAPI", "React"],
        )
        ats = agent_workflow.ATSReport(
            jd_keywords=["python", "fastapi", "react", "automation"],
            covered_keywords=["python", "fastapi", "automation"],
            gap_keywords=["react"],
            coverage_pct=75.0,
        )
        qa = agent_workflow.QAReport(matching_rate_score=80, factual_support_passed=True, keyword_coverage_pct=75.0)
        change_log = agent_workflow.generate_change_log(tailored)
        return agent_workflow.WorkflowResult(
            canonical_cv=cv,
            jd_analysis=jd,
            tailored_output=tailored,
            qa_report=qa,
            change_log=change_log,
            ats_report=ats,
            cover_letter="Draft cover letter.",
        )

    def test_saved_job_tailoring_adds_evidence_provenance_and_layout_metadata(self) -> None:
        with patch("api.app.services.tailoring_service.run_tailoring", side_effect=self._fake_workflow_result):
            response = run_tailoring_job(
                TailorRunRequest(
                    job_id=self.job_id,
                    master_id=self.master_id,
                    options=TailorRunOptions(include_cover_letter=False, max_pages=2),
                )
            )

        self.assertEqual(response.job_id, self.job_id)
        self.assertIn("ev_api_automation", response.selected_evidence_block_ids)
        self.assertEqual(response.result.selected_evidence[0].evidence_block_id, "ev_api_automation")

        selection = response.result.tailored_output.profile_selections[0]
        self.assertTrue(selection.provenance)
        self.assertEqual(selection.provenance[0].source_type, "master_cv")
        self.assertTrue(any(ref.source_type == "career_brain" for ref in selection.provenance))

        self.assertFalse(response.result.qa_report.unsupported_claim_guard_passed)
        self.assertFalse(response.result.qa_report.factual_support_passed)
        self.assertTrue(any("kubernetes" in claim.lower() for claim in response.result.qa_report.unsupported_claims))

        self.assertEqual(response.result.page_budget.max_pages, 2)
        self.assertEqual(
            response.result.page_budget.compression_order,
            [
                "remove_low_priority_bullets",
                "shorten_verbose_bullets",
                "reduce_project_detail",
                "compress_skills",
                "adjust_spacing_last",
            ],
        )
        self.assertIsNotNone(response.result.layout_validation.layout_passed)
        self.assertEqual(response.result.approval_status, "draft")
        self.assertNotIn("ready_to_submit", response.model_dump_json())

        persisted = get_run_record(response.run_id)
        self.assertEqual(persisted["job_id"], self.job_id)
        self.assertEqual(persisted["result"]["selected_evidence_block_ids"], response.selected_evidence_block_ids)


if __name__ == "__main__":
    unittest.main()
