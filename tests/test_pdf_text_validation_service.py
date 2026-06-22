import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api.app.schemas.resume_render import ResumeItem, ResumeLayout, ResumeSection
from api.app.services.html_resume_renderer import render_resume_pdf
from api.app.services.pdf_text_validation_service import extract_pdf_text, validate_pdf_text


def _layout() -> ResumeLayout:
    return ResumeLayout(
        owner_name="Ata Selekoglu",
        expected_keywords=["Python", "FastAPI"],
        sections=[
            ResumeSection(
                kind="profile",
                heading="PROFILE",
                items=[
                    ResumeItem(
                        item_id="profile-1",
                        text="Built Python automation for application workflows.",
                        source_section="profile",
                    )
                ],
            ),
            ResumeSection(
                kind="skills",
                heading="SUMMARY OF QUALIFICATIONS",
                items=[
                    ResumeItem(item_id="skill-1", text="Python", source_section="skills"),
                    ResumeItem(item_id="skill-2", text="FastAPI", source_section="skills"),
                ],
            ),
            ResumeSection(
                kind="experience",
                heading="EXPERIENCE",
                items=[
                    ResumeItem(
                        item_id="experience-1",
                        text="Delivered FastAPI integrations for CRM reporting.",
                        source_section="experience",
                    )
                ],
            ),
        ],
    )


class PdfTextValidationServiceTest(unittest.TestCase):
    def test_validate_pdf_text_passes_when_headings_items_keywords_and_order_are_extractable(self):
        extracted = (
            "Ata Selekoglu\n"
            "PROFILE\n"
            "Built Python automation for application workflows.\n"
            "SUMMARY OF QUALIFICATIONS\n"
            "Python FastAPI\n"
            "EXPERIENCE\n"
            "Delivered FastAPI integrations for CRM reporting."
        )

        with patch("api.app.services.pdf_text_validation_service.extract_pdf_text", return_value=extracted):
            result = validate_pdf_text("fake.pdf", _layout())

        self.assertTrue(result.ats_parse_passed)
        self.assertEqual(result.missing_headings, [])
        self.assertEqual(result.missing_items, [])
        self.assertEqual(result.missing_keywords, [])
        self.assertTrue(result.order_passed)
        self.assertEqual(result.notes, ["PDF text extraction passed ATS readability checks."])

    def test_validate_pdf_text_fails_when_heading_item_and_keyword_are_missing(self):
        extracted = "Ata Selekoglu\nPROFILE\nBuilt Python automation for application workflows."

        with patch("api.app.services.pdf_text_validation_service.extract_pdf_text", return_value=extracted):
            result = validate_pdf_text("fake.pdf", _layout())

        self.assertFalse(result.ats_parse_passed)
        self.assertIn("SUMMARY OF QUALIFICATIONS", result.missing_headings)
        self.assertIn("EXPERIENCE", result.missing_headings)
        self.assertIn("Delivered FastAPI integrations for CRM reporting.", result.missing_items)
        self.assertIn("FastAPI", result.missing_keywords)
        self.assertTrue(any("Missing headings:" in note for note in result.notes))
        self.assertTrue(any("Missing selected items:" in note for note in result.notes))
        self.assertTrue(any("Missing keywords:" in note for note in result.notes))

    def test_validate_pdf_text_fails_when_section_order_does_not_match_layout(self):
        extracted = (
            "EXPERIENCE\n"
            "Delivered FastAPI integrations for CRM reporting.\n"
            "SUMMARY OF QUALIFICATIONS\n"
            "Python FastAPI\n"
            "PROFILE\n"
            "Built Python automation for application workflows."
        )

        with patch("api.app.services.pdf_text_validation_service.extract_pdf_text", return_value=extracted):
            result = validate_pdf_text("fake.pdf", _layout())

        self.assertFalse(result.ats_parse_passed)
        self.assertFalse(result.order_passed)
        self.assertIn("Section reading order did not match layout order.", result.notes)

    def test_validate_pdf_text_allows_heading_word_before_actual_heading(self):
        extracted = (
            "Ata Selekoglu\n"
            "PROFILE\n"
            "Built Python automation for application workflows.\n"
            "Relevant experience includes CRM systems.\n"
            "SUMMARY OF QUALIFICATIONS\n"
            "Python FastAPI\n"
            "EXPERIENCE\n"
            "Delivered FastAPI integrations for CRM reporting."
        )

        with patch("api.app.services.pdf_text_validation_service.extract_pdf_text", return_value=extracted):
            result = validate_pdf_text("fake.pdf", _layout())

        self.assertTrue(result.ats_parse_passed)
        self.assertTrue(result.order_passed)

    def test_validate_pdf_text_rejects_keyword_substring_false_positives(self):
        layout = ResumeLayout(
            owner_name="Ata Selekoglu",
            expected_keywords=["Go", "AI", "SQL", "C++", "C#", ".NET", "FastAPI integrations"],
            sections=[
                ResumeSection(
                    kind="profile",
                    heading="PROFILE",
                    items=[
                        ResumeItem(
                            item_id="profile-1",
                            text="Built C++, C#, .NET, and FastAPI integrations.",
                            source_section="profile",
                        )
                    ],
                )
            ],
        )
        extracted = (
            "Ata Selekoglu\n"
            "PROFILE\n"
            "Built C++, C#, .NET, and FastAPI integrations while ongoing NoSQL mailer work remained."
        )

        with patch("api.app.services.pdf_text_validation_service.extract_pdf_text", return_value=extracted):
            result = validate_pdf_text("fake.pdf", layout)

        self.assertFalse(result.ats_parse_passed)
        self.assertIn("Go", result.missing_keywords)
        self.assertIn("AI", result.missing_keywords)
        self.assertIn("SQL", result.missing_keywords)
        self.assertNotIn("C++", result.missing_keywords)
        self.assertNotIn("C#", result.missing_keywords)
        self.assertNotIn(".NET", result.missing_keywords)
        self.assertNotIn("FastAPI integrations", result.missing_keywords)

    def test_validate_pdf_text_fails_when_owner_name_is_missing(self):
        extracted = (
            "PROFILE\n"
            "Built Python automation for application workflows.\n"
            "SUMMARY OF QUALIFICATIONS\n"
            "Python FastAPI\n"
            "EXPERIENCE\n"
            "Delivered FastAPI integrations for CRM reporting."
        )

        with patch("api.app.services.pdf_text_validation_service.extract_pdf_text", return_value=extracted):
            result = validate_pdf_text("fake.pdf", _layout())

        self.assertFalse(result.ats_parse_passed)
        self.assertTrue(any("Owner name missing" in note for note in result.notes))

    def test_extract_pdf_text_returns_empty_string_for_missing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.pdf"

            self.assertEqual(extract_pdf_text(str(missing_path)), "")

    def test_render_resume_pdf_writes_html_and_prints_with_playwright(self):
        layout = _layout()
        with tempfile.TemporaryDirectory() as temp_dir:
            html_path = Path(temp_dir) / "resume.html"
            pdf_path = Path(temp_dir) / "resume.pdf"
            playwright_context = patch("api.app.services.html_resume_renderer.sync_playwright")
            with playwright_context as sync_playwright:
                playwright = sync_playwright.return_value.__enter__.return_value
                browser = playwright.chromium.launch.return_value
                page = browser.new_page.return_value

                result = render_resume_pdf(layout, str(html_path), str(pdf_path))

            self.assertEqual(result, str(pdf_path))
            self.assertTrue(html_path.exists())
            page.goto.assert_called_once_with(html_path.resolve().as_uri(), wait_until="networkidle")
            page.pdf.assert_called_once_with(path=str(pdf_path), format="Letter", print_background=True)
            browser.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
