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
from api.app.schemas.resume_render import PdfTextValidation
from api.app.services.export_service import export_run
from api.app.services.career_brain_service import save_career_brain_profile
from api.app.services.job_scoring_service import score_job
from api.app.services import tailoring_service
from api.app.services.tailoring_service import get_run_record, rerun_tailoring_job, run_tailoring_job
from api.app.schemas.tailoring import TailorRunOptions, TailorRunRequest


class CompressionPolicyTest(unittest.TestCase):
    def test_shorten_text_avoids_open_clause_fragments(self) -> None:
        examples = [
            (
                "Built release automation for business systems such as internal dashboards and API services while coordinating rollout notes.",
                "Built release automation for business systems such.",
            ),
            (
                "Led intake cleanup for analytics, reporting, and stakeholder workflows across several internal teams.",
                "Led intake cleanup for analytics, reporting, and.",
            ),
            (
                "Supported automation delivery with strong documentation, validation, and operational follow-through for users.",
                "Supported automation delivery with strong.",
            ),
            (
                "Expanded validation coverage for every regression test scenario before release to production stakeholders.",
                "Expanded validation coverage for every regression test.",
            ),
        ]

        for source, broken_fragment in examples:
            with self.subTest(broken_fragment=broken_fragment):
                shortened = tailoring_service._shorten_text(source, max_words=7)
                self.assertNotEqual(shortened, broken_fragment)
                self.assertFalse(
                    tailoring_service._has_open_clause_ending(shortened),
                    shortened,
                )

    def test_pre_render_compression_skips_underfilled_two_page_content(self) -> None:
        self.assertFalse(
            tailoring_service.should_apply_pre_render_compression(
                max_pages=2,
                selected_bullet_count=12,
                selected_word_count=197,
            )
        )

    def test_pre_render_compression_runs_for_over_budget_two_page_content(self) -> None:
        self.assertTrue(
            tailoring_service.should_apply_pre_render_compression(
                max_pages=2,
                selected_bullet_count=28,
                selected_word_count=1100,
            )
        )


class RoleAwareSelectionTest(unittest.TestCase):
    def test_frontend_ai_role_recovers_profile_skills_and_projects(self) -> None:
        cv = agent_workflow.CanonicalCV(
            full_name="Ata Selekoglu",
            profile_bullets=[
                agent_workflow.BulletEvidence(
                    bullet_id="prof_ai_frontend",
                    section="profile",
                    text="AI Application Developer building AI-assisted applications, REST APIs, and frontend interfaces.",
                )
            ],
            skills_sections={
                "Technical": ["React", "TypeScript", "Vite", "JavaScript", "REST APIs", "AI Agents", "Puppeteer"]
            },
            projects=[
                agent_workflow.ProjectEntry(
                    title="ApplAI",
                    bullets=[
                        agent_workflow.BulletEvidence(
                            bullet_id="proj_0_0",
                            section="projects",
                            text="Developed ApplAI, an AI-driven system for CV tailoring, job description analysis, and document generation.",
                        )
                    ],
                ),
                agent_workflow.ProjectEntry(
                    title="Sehlikzade Family Archive",
                    bullets=[
                        agent_workflow.BulletEvidence(
                            bullet_id="proj_1_0",
                            section="projects",
                            text="Created a high-performance SPA using Vite and Vanilla JS/CSS with a custom hash router.",
                        )
                    ],
                ),
            ],
        )
        jd = agent_workflow.JDAnalysis(
            domain="software",
            must_have_keywords=["react", "typescript", "vite", "frontend development", "agentic ui", "ai tools"],
            nice_to_have_keywords=["playwright", "cypress", "github copilot"],
            raw_summary="Applied AI Junior Front-End Developer building React micro-frontend web applications.",
        )
        scored = agent_workflow.map_evidence(cv, jd)
        plan = agent_workflow.plan_strategy(jd, scored, max_pages=2)

        tailored = agent_workflow.select_and_rewrite(cv, scored, plan, jd, "test-model")

        profile_text = " ".join(selection.original_text for selection in tailored.profile_selections)
        project_text = " ".join(selection.original_text for selection in tailored.project_selections)
        skills_text = " ".join(tailored.skills_to_highlight)

        self.assertIn("AI Application Developer", profile_text)
        self.assertIn("ApplAI", project_text)
        self.assertIn("Vite", project_text)
        self.assertIn("React", skills_text)
        self.assertIn("TypeScript", skills_text)
        self.assertIn("AI Agents", skills_text)


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
            experience=[
                agent_workflow.ExperienceEntry(
                    employer="Core Systems",
                    role="Software Developer",
                    start_date="2022",
                    end_date="Present",
                    location="Toronto, ON",
                    bullets=[
                        agent_workflow.BulletEvidence(
                            bullet_id="exp_0_0",
                            text="Delivered FastAPI services and React dashboards for internal automation workflows.",
                            section="experience",
                            employer="Core Systems",
                            role="Software Developer",
                        )
                    ],
                )
            ],
            projects=[
                agent_workflow.ProjectEntry(
                    title="AI Application Workflow",
                    date="2024",
                    institution="Independent",
                    bullets=[
                        agent_workflow.BulletEvidence(
                            bullet_id="proj_0_0",
                            text="Built AI-assisted application tracking with REST APIs and job scoring.",
                            section="projects",
                            role="AI Application Workflow",
                        )
                    ],
                )
            ],
            education=[
                agent_workflow.EducationEntry(
                    institution="George Brown College",
                    degree="Diploma",
                    field_of_study="Computer Systems Technology",
                    start_date="2021",
                    end_date="2023",
                    bullets=[
                        agent_workflow.BulletEvidence(
                            bullet_id="edu_0_0",
                            text="Completed software development coursework covering Python, databases, and web systems.",
                            section="education",
                            role="Computer Systems Technology",
                        )
                    ],
                )
            ],
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
            experience_selections=[
                agent_workflow.BulletSelection(
                    bullet_id="exp_0_0",
                    section="experience",
                    action="rewrite",
                    original_text="Delivered FastAPI services and React dashboards for internal automation workflows.",
                    new_text="Delivered FastAPI services and React dashboards for internal automation workflows.",
                    relevance_score=0.88,
                    jd_requirements_addressed=["Build internal software automation."],
                )
            ],
            project_selections=[
                agent_workflow.BulletSelection(
                    bullet_id="proj_0_0",
                    section="projects",
                    action="rewrite",
                    original_text="Built AI-assisted application tracking with REST APIs and job scoring.",
                    new_text="Built AI-assisted application tracking with REST APIs and job scoring.",
                    relevance_score=0.84,
                    jd_requirements_addressed=["Build internal software automation."],
                )
            ],
            education_selections=[
                agent_workflow.BulletSelection(
                    bullet_id="edu_0_0",
                    section="education",
                    action="select_as_is",
                    original_text="Completed software development coursework covering Python, databases, and web systems.",
                    relevance_score=0.72,
                    jd_requirements_addressed=["Build internal software automation."],
                )
            ],
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

    def _bloated_workflow_result(self, job_description: str, base_cv_json_text: str, options: TailorRunOptions):
        cv = agent_workflow.CanonicalCV(
            full_name="Ata Selekoglu",
            profile_bullets=[
                agent_workflow.BulletEvidence(bullet_id="prof_keep", text="Built Python FastAPI services for workflow automation.", section="profile"),
                agent_workflow.BulletEvidence(bullet_id="prof_low", text="Provided general office support unrelated to software roles.", section="profile"),
                agent_workflow.BulletEvidence(bullet_id="prof_verbose", text="Built Python FastAPI services for workflow automation with REST APIs, React dashboards, stakeholder reporting, operational monitoring, documentation, training materials, release notes, support workflows, and extensive cross-functional enablement for business users.", section="profile"),
            ],
            skills_sections={"Technical": ["Python", "FastAPI", "React", "REST APIs", "SQL", "workflow automation", "Kubernetes", "Power BI"]},
        )
        jd = agent_workflow.JDAnalysis(
            domain="software",
            must_have_keywords=["python", "fastapi", "react", "automation", "sql"],
            raw_summary="Build internal software automation.",
        )
        tailored = agent_workflow.TailoredOutput(
            profile_selections=[
                agent_workflow.BulletSelection(
                    bullet_id="prof_keep",
                    section="profile",
                    action="select_as_is",
                    original_text="Built Python FastAPI services for workflow automation.",
                    relevance_score=0.95,
                ),
                agent_workflow.BulletSelection(
                    bullet_id="prof_low",
                    section="profile",
                    action="select_as_is",
                    original_text="Provided general office support unrelated to software roles.",
                    relevance_score=0.05,
                ),
                agent_workflow.BulletSelection(
                    bullet_id="prof_verbose",
                    section="profile",
                    action="rewrite",
                    original_text="Built Python FastAPI services for workflow automation.",
                    new_text="Built Python FastAPI services for workflow automation with REST APIs, React dashboards, stakeholder reporting, operational monitoring, documentation, Kubernetes deployment leadership, training materials, release notes, support workflows, and extensive cross-functional enablement for business users.",
                    rewrite_rationale="Emphasized delivery breadth.",
                    relevance_score=0.8,
                ),
            ],
            experience_selections=[
                agent_workflow.BulletSelection(
                    bullet_id=f"exp_{idx}",
                    section="experience",
                    action="select_as_is",
                    original_text=f"Created SQL reporting workflow {idx} for internal stakeholders.",
                    relevance_score=0.45 + idx / 100,
                )
                for idx in range(24)
            ],
            project_selections=[
                agent_workflow.BulletSelection(
                    bullet_id=f"proj_{idx}",
                    section="projects",
                    action="select_as_is",
                    original_text=f"Project detail {idx}: delivered Python automation, API integration, dashboard reporting, documentation, stakeholder rollout, and maintenance planning.",
                    relevance_score=0.35 + idx / 100,
                )
                for idx in range(5)
            ],
            skills_to_highlight=["Python", "FastAPI", "React", "REST APIs", "SQL", "workflow automation", "Kubernetes", "Power BI"],
        )
        ats = agent_workflow.ATSReport(
            jd_keywords=["python", "fastapi", "react", "automation", "sql"],
            covered_keywords=["python", "fastapi", "automation", "sql"],
            gap_keywords=["react"],
            coverage_pct=80.0,
        )
        qa = agent_workflow.QAReport(matching_rate_score=78, factual_support_passed=True, keyword_coverage_pct=80.0)
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

    def test_rerun_creates_new_draft_from_saved_run_inputs(self) -> None:
        with patch("api.app.services.tailoring_service.run_tailoring", side_effect=self._fake_workflow_result):
            original = run_tailoring_job(
                TailorRunRequest(
                    job_id=self.job_id,
                    master_id=self.master_id,
                    options=TailorRunOptions(include_cover_letter=False, max_pages=2),
                )
            )
            rerun = rerun_tailoring_job(original.run_id)

        self.assertNotEqual(rerun.run_id, original.run_id)
        self.assertEqual(rerun.master_id, original.master_id)
        self.assertEqual(rerun.job_id, original.job_id)
        self.assertEqual(rerun.options.company_name, "CoreCo")
        self.assertEqual(rerun.options.job_title, "Software Developer")
        self.assertEqual(rerun.result.approval_status, "draft")

        original_record = get_run_record(original.run_id)
        rerun_record = get_run_record(rerun.run_id)
        self.assertNotIn("rerun_of", original_record)
        self.assertEqual(rerun_record["rerun_of"], original.run_id)
        self.assertEqual(rerun_record["workflow_inputs"]["rerun_of"], original.run_id)
        self.assertEqual(rerun_record["workflow_inputs"]["job_id"], self.job_id)

    def test_rerun_falls_back_to_saved_job_description_when_job_record_is_missing(self) -> None:
        with patch("api.app.services.tailoring_service.run_tailoring", side_effect=self._fake_workflow_result):
            original = run_tailoring_job(
                TailorRunRequest(
                    job_id=self.job_id,
                    master_id=self.master_id,
                    options=TailorRunOptions(include_cover_letter=False, max_pages=2),
                )
            )
            Path(settings.jobs_dir, f"{self.job_id}.json").unlink()
            rerun = rerun_tailoring_job(original.run_id)

        self.assertIsNone(rerun.job_id)
        self.assertEqual(rerun.options.company_name, "CoreCo")
        rerun_record = get_run_record(rerun.run_id)
        self.assertIsNone(rerun_record["job_id"])
        self.assertIn("Python FastAPI REST APIs", rerun_record["job_description"])

    def test_compression_runs_in_deterministic_order_and_logs_decisions(self) -> None:
        with patch("api.app.services.tailoring_service.run_tailoring", side_effect=self._bloated_workflow_result):
            response = run_tailoring_job(
                TailorRunRequest(
                    job_id=self.job_id,
                    master_id=self.master_id,
                    options=TailorRunOptions(include_cover_letter=False, max_pages=2),
                )
            )

        decisions = response.result.page_budget.compression_decisions
        self.assertGreaterEqual(len(decisions), 4)
        self.assertEqual(
            [decision.action for decision in decisions[:4]],
            [
                "remove_low_priority_bullets",
                "shorten_verbose_bullets",
                "reduce_project_detail",
                "compress_skills",
            ],
        )
        self.assertEqual(response.result.tailored_output.profile_selections[1].action, "deselect")
        shortened_profile = response.result.tailored_output.profile_selections[2].new_text
        self.assertLess(len(shortened_profile.split()), 32)
        self.assertLessEqual(len(shortened_profile.split()), 24)
        self.assertFalse(tailoring_service._has_open_clause_ending(shortened_profile))
        self.assertLessEqual(len(response.result.tailored_output.project_selections), 3)
        self.assertLessEqual(len(response.result.tailored_output.skills_to_highlight), 6)

        compression_entries = [
            entry for entry in response.result.change_log.entries if entry.action.startswith("compression_")
        ]
        self.assertGreaterEqual(len(compression_entries), 4)
        self.assertTrue(any("remove_low_priority_bullets" in entry.rationale for entry in compression_entries))
        self.assertTrue(any("shorten_verbose_bullets" in entry.rationale for entry in compression_entries))
        self.assertTrue(any("reduce_project_detail" in entry.rationale for entry in compression_entries))
        self.assertTrue(any("compress_skills" in entry.rationale for entry in compression_entries))
        self.assertTrue(any("kubernetes" in claim.lower() for claim in response.result.qa_report.unsupported_claims))
        self.assertEqual(response.result.approval_status, "draft")
        self.assertNotIn("ready_to_submit", response.model_dump_json())

    def test_export_writes_html_pdf_as_final_cv_and_preserves_docx_compatibility(self) -> None:
        with patch("api.app.services.tailoring_service.run_tailoring", side_effect=self._fake_workflow_result):
            response = run_tailoring_job(
                TailorRunRequest(
                    job_id=self.job_id,
                    master_id=self.master_id,
                    options=TailorRunOptions(include_cover_letter=False, max_pages=2),
                )
            )

        docx_path = str(Path(settings.docs_dir, "Ata_CV_Tailored_CoreCo.docx"))
        cover_path = str(Path(settings.docs_dir, "Ata_CL_Tailored_CoreCo.pdf"))
        Path(docx_path).write_bytes(b"docx placeholder")
        Path(cover_path).write_bytes(b"%PDF-1.4 placeholder")
        artifact_data = {
            "cv_path": docx_path,
            "cl_path": cover_path,
            "docs_url": None,
            "cv_bytes": b"",
            "cl_bytes": b"",
            "cover_letter_text": "Draft cover letter.",
        }
        validation = PdfTextValidation(
            ats_parse_passed=True,
            extracted_text=" ".join(["Ata Selekoglu PROFILE Python FastAPI automation React REST APIs"] * 90),
            notes=["PDF text extraction passed ATS readability checks."],
        )

        returned_pdf = str(Path(settings.docs_dir, "renderer-returned", "Selekoglu_CV_Tailored_CoreCo.pdf"))

        with patch("api.app.services.export_service.render_run_artifacts", return_value=artifact_data), patch(
            "api.app.services.export_service.render_resume_pdf",
            return_value=returned_pdf,
        ) as render_pdf, patch(
            "api.app.services.export_service._pdf_page_count",
            side_effect=lambda path: 2 if path == returned_pdf else None,
        ) as page_count, patch(
            "api.app.services.export_service.validate_pdf_text",
            return_value=validation,
        ) as validate_text:
            export = export_run(response.run_id)

        expected_html = str(Path(settings.docs_dir, "Selekoglu_CV_Tailored_CoreCo.html"))
        requested_pdf = str(Path(settings.docs_dir, "Selekoglu_CV_Tailored_CoreCo.pdf"))
        self.assertEqual(export.cv_path, returned_pdf)
        self.assertEqual(export.pdf_path, returned_pdf)
        self.assertEqual(export.docx_path, docx_path)
        self.assertEqual(export.html_path, expected_html)
        self.assertEqual(export.page_count, 2)
        self.assertTrue(export.layout_passed)
        self.assertTrue(export.ats_parse_passed)
        self.assertEqual(export.ats_parse_notes, validation.notes)
        render_pdf.assert_called_once()
        validate_text.assert_called_once()

        layout = render_pdf.call_args.args[0]
        self.assertEqual(layout.owner_name, "Ata Selekoglu")
        self.assertEqual(layout.target_role, "Software Developer")
        self.assertEqual(layout.company_name, "CoreCo")
        self.assertIn("python", layout.expected_keywords)
        self.assertEqual(render_pdf.call_args.args[1], expected_html)
        self.assertEqual(render_pdf.call_args.args[2], requested_pdf)
        page_count.assert_any_call(returned_pdf)
        validate_text.assert_called_once_with(returned_pdf, layout)

        persisted = get_run_record(response.run_id)
        layout_validation = persisted["result"]["layout_validation"]
        self.assertEqual(layout_validation["validation_method"], "html_pdf_quality_gate")
        self.assertEqual(layout_validation["page_count"], 2)
        self.assertTrue(layout_validation["layout_passed"])
        self.assertTrue(any("within max_pages 2" in note for note in layout_validation["notes"]))
        self.assertTrue(any("PDF text extraction passed ATS readability checks." in note for note in layout_validation["notes"]))

        artifacts = {artifact["artifact_id"]: artifact for artifact in persisted["result"]["artifacts"]}
        cv_pdf = artifacts[f"{response.run_id}:cv"]
        self.assertEqual(cv_pdf["kind"], "cv_pdf")
        self.assertEqual(cv_pdf["path"], returned_pdf)
        self.assertEqual(cv_pdf["html_path"], expected_html)
        self.assertEqual(cv_pdf["page_count"], 2)
        self.assertTrue(cv_pdf["layout_passed"])
        self.assertTrue(cv_pdf["ats_parse_passed"])
        self.assertEqual(cv_pdf["ats_parse_notes"], validation.notes)
        cv_docx = artifacts[f"{response.run_id}:cv_docx"]
        self.assertEqual(cv_docx["kind"], "cv_docx")
        self.assertEqual(cv_docx["path"], docx_path)
        self.assertIsNone(cv_docx["layout_passed"])
        self.assertIn(f"{response.run_id}:cv", export.artifact_ids)
        self.assertIn(f"{response.run_id}:cv_docx", export.artifact_ids)

    def test_export_records_html_pdf_page_count_failure(self) -> None:
        with patch("api.app.services.tailoring_service.run_tailoring", side_effect=self._fake_workflow_result):
            response = run_tailoring_job(
                TailorRunRequest(
                    job_id=self.job_id,
                    master_id=self.master_id,
                    options=TailorRunOptions(include_cover_letter=False, max_pages=2),
                )
            )

        pdf_path = str(Path(settings.docs_dir, "Selekoglu_CV_Tailored_CoreCo.pdf"))
        cover_path = str(Path(settings.docs_dir, "Ata_CL_Tailored_CoreCo.pdf"))
        Path(cover_path).write_bytes(b"%PDF-1.4 placeholder")
        artifact_data = {
            "cv_path": str(Path(settings.docs_dir, "Ata_CV_Tailored_CoreCo.docx")),
            "cl_path": cover_path,
            "docs_url": None,
            "cv_bytes": b"",
            "cl_bytes": b"",
            "cover_letter_text": "Draft cover letter.",
        }
        with patch("api.app.services.export_service.render_run_artifacts", return_value=artifact_data), patch(
            "api.app.services.export_service.render_resume_pdf",
            return_value=pdf_path,
        ), patch(
            "api.app.services.export_service._pdf_page_count",
            side_effect=lambda path: 3 if path == pdf_path else 1,
        ), patch(
            "api.app.services.export_service.validate_pdf_text",
            return_value=PdfTextValidation(ats_parse_passed=True, extracted_text="", notes=["ATS passed."]),
        ):
            export = export_run(response.run_id)

        self.assertEqual(export.pdf_path, pdf_path)
        self.assertEqual(export.page_count, 3)
        self.assertFalse(export.layout_passed)
        self.assertTrue(export.ats_parse_passed)

        persisted = get_run_record(response.run_id)
        layout = persisted["result"]["layout_validation"]
        self.assertEqual(layout["validation_method"], "html_pdf_quality_gate")
        self.assertEqual(layout["page_count"], 3)
        self.assertFalse(layout["layout_passed"])
        self.assertTrue(any("exceeds max_pages 2" in note for note in layout["notes"]))

    def test_export_quality_gate_rejects_underfilled_one_page_cv(self) -> None:
        with patch("api.app.services.tailoring_service.run_tailoring", side_effect=self._fake_workflow_result):
            response = run_tailoring_job(
                TailorRunRequest(
                    job_id=self.job_id,
                    master_id=self.master_id,
                    options=TailorRunOptions(include_cover_letter=False, max_pages=2),
                )
            )

        pdf_path = str(Path(settings.docs_dir, "Selekoglu_CV_Tailored_CoreCo.pdf"))
        cover_path = str(Path(settings.docs_dir, "Ata_CL_Tailored_CoreCo.pdf"))
        Path(cover_path).write_bytes(b"%PDF-1.4 placeholder")
        artifact_data = {
            "cv_path": str(Path(settings.docs_dir, "Ata_CV_Tailored_CoreCo.docx")),
            "cl_path": cover_path,
            "docs_url": None,
            "cv_bytes": b"",
            "cl_bytes": b"",
            "cover_letter_text": "Draft cover letter.",
        }

        with patch("api.app.services.export_service.render_run_artifacts", return_value=artifact_data), patch(
            "api.app.services.export_service.render_resume_pdf",
            return_value=pdf_path,
        ), patch(
            "api.app.services.export_service._pdf_page_count",
            side_effect=lambda path: 1 if path == pdf_path else None,
        ), patch(
            "api.app.services.export_service.validate_pdf_text",
            return_value=PdfTextValidation(
                ats_parse_passed=True,
                extracted_text="Ata Selekoglu PROFILE Python FastAPI automation",
                notes=["PDF text extraction passed ATS readability checks."],
            ),
        ):
            export = export_run(response.run_id)

        self.assertFalse(export.layout_passed)
        persisted = get_run_record(response.run_id)
        layout = persisted["result"]["layout_validation"]
        self.assertEqual(layout["validation_method"], "html_pdf_quality_gate")
        self.assertEqual(layout["page_count"], 1)
        self.assertFalse(layout["layout_passed"])
        self.assertTrue(any("underfilled" in note for note in layout["notes"]))

    def test_export_records_ats_text_failure(self) -> None:
        with patch("api.app.services.tailoring_service.run_tailoring", side_effect=self._fake_workflow_result):
            response = run_tailoring_job(
                TailorRunRequest(
                    job_id=self.job_id,
                    master_id=self.master_id,
                    options=TailorRunOptions(include_cover_letter=False, max_pages=2),
                )
            )

        docx_path = str(Path(settings.docs_dir, "Ata_CV_Tailored_CoreCo.docx"))
        cover_path = str(Path(settings.docs_dir, "Ata_CL_Tailored_CoreCo.pdf"))
        Path(docx_path).write_bytes(b"docx placeholder")
        Path(cover_path).write_bytes(b"%PDF-1.4 placeholder")
        artifact_data = {
            "cv_path": docx_path,
            "cl_path": cover_path,
            "docs_url": None,
            "cv_bytes": b"",
            "cl_bytes": b"",
            "cover_letter_text": "Draft cover letter.",
        }
        with patch("api.app.services.export_service.render_run_artifacts", return_value=artifact_data), patch(
            "api.app.services.export_service.render_resume_pdf",
            return_value=str(Path(settings.docs_dir, "Selekoglu_CV_Tailored_CoreCo.pdf")),
        ), patch(
            "api.app.services.export_service._pdf_page_count",
            return_value=2,
        ), patch(
            "api.app.services.export_service.validate_pdf_text",
            return_value=PdfTextValidation(
                ats_parse_passed=False,
                extracted_text="",
                notes=["Missing keywords: python", "Section reading order did not match layout order."],
            ),
        ):
            export = export_run(response.run_id)

        self.assertEqual(export.docx_path, docx_path)
        self.assertEqual(export.pdf_path, str(Path(settings.docs_dir, "Selekoglu_CV_Tailored_CoreCo.pdf")))
        self.assertEqual(export.page_count, 2)
        self.assertFalse(export.layout_passed)
        self.assertFalse(export.ats_parse_passed)
        self.assertIn("Missing keywords: python", export.ats_parse_notes)
        persisted = get_run_record(response.run_id)
        layout = persisted["result"]["layout_validation"]
        self.assertEqual(layout["validation_method"], "html_pdf_quality_gate")
        self.assertFalse(layout["layout_passed"])
        self.assertTrue(any("Missing keywords: python" in note for note in layout["notes"]))


if __name__ == "__main__":
    unittest.main()
