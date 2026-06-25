import unittest

from api.app.services.tailoring_service import evaluate_output_quality


class CvOutputQualityGateTest(unittest.TestCase):
    def test_rejects_one_page_sparse_two_page_target(self):
        validation = evaluate_output_quality(
            max_pages=2,
            page_count=1,
            extracted_word_count=212,
            section_headings=["EXPERIENCE", "PROJECTS", "EDUCATION"],
            keyword_coverage_pct=7.5,
            missing_required_sections=["PROFILE", "SUMMARY OF QUALIFICATIONS"],
            broken_bullets=[],
        )

        self.assertFalse(validation.layout_passed)
        self.assertEqual(validation.validation_method, "html_pdf_quality_gate")
        self.assertIn("underfilled", " ".join(validation.notes).lower())
        self.assertIn("PROFILE", " ".join(validation.notes))
        self.assertIn("SUMMARY OF QUALIFICATIONS", " ".join(validation.notes))

    def test_accepts_dense_two_page_target_with_required_sections(self):
        validation = evaluate_output_quality(
            max_pages=2,
            page_count=2,
            extracted_word_count=850,
            section_headings=[
                "PROFILE",
                "SUMMARY OF QUALIFICATIONS",
                "RELEVANT EXPERIENCE",
                "PROJECTS",
                "EDUCATION",
            ],
            keyword_coverage_pct=42.0,
            missing_required_sections=[],
            broken_bullets=[],
        )

        self.assertTrue(validation.layout_passed)
        self.assertIn("quality gate passed", " ".join(validation.notes).lower())

    def test_rejects_broken_bullet_fragments(self):
        validation = evaluate_output_quality(
            max_pages=2,
            page_count=1,
            extracted_word_count=700,
            section_headings=["PROFILE", "SUMMARY OF QUALIFICATIONS", "EXPERIENCE", "PROJECTS", "EDUCATION"],
            keyword_coverage_pct=45.0,
            missing_required_sections=[],
            broken_bullets=["Designed marketing processes such as."],
        )

        self.assertFalse(validation.layout_passed)
        self.assertIn("Broken bullets: 1", validation.notes)

    def test_normalizes_headings_for_required_section_dedupe(self):
        validation = evaluate_output_quality(
            max_pages=2,
            page_count=2,
            extracted_word_count=850,
            section_headings=[
                " profile: ",
                "SUMMARY   OF   QUALIFICATIONS:",
                " relevant   experience: ",
                "projects:",
                "education:",
            ],
            keyword_coverage_pct=42.0,
            missing_required_sections=[" profile: ", "summary   of qualifications:"],
            broken_bullets=[],
        )

        self.assertTrue(validation.layout_passed)
        self.assertEqual(["HTML PDF quality gate passed."], validation.notes)


if __name__ == "__main__":
    unittest.main()
