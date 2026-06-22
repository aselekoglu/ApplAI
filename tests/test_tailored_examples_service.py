from __future__ import annotations

import unittest

from api.app.services.tailored_examples_service import (
    classify_master_example_diff,
    discover_tailored_example_pdfs,
    extract_section_headings_from_text,
    list_tailored_examples,
)


class TailoredExamplesServiceTest(unittest.TestCase):
    def test_discovers_all_local_tailored_pdfs(self) -> None:
        pdfs = discover_tailored_example_pdfs()
        if not pdfs:
            self.skipTest("Private tailored example PDFs are not present in docs/tailored_examples/.")

        self.assertEqual(len(pdfs), 20)
        self.assertTrue(all(path.suffix.lower() == ".pdf" for path in pdfs))

    def test_each_tailored_pdf_is_two_pages_with_parse_metadata(self) -> None:
        pdfs = discover_tailored_example_pdfs()
        if not pdfs:
            self.skipTest("Private tailored example PDFs are not present in docs/tailored_examples/.")

        examples = list_tailored_examples()

        self.assertEqual(len(examples), 20)
        self.assertTrue(all(example.page_count == 2 for example in examples))
        self.assertTrue(all(example.source_pdf_path.startswith("docs/tailored_examples/") for example in examples))
        self.assertTrue(all(example.role_label for example in examples))
        self.assertTrue(all(example.extracted_text for example in examples))
        self.assertTrue(all(example.section_headings for example in examples))
        self.assertTrue(all(example.parse_confidence > 0.5 for example in examples))

    def test_heading_extraction_uses_known_resume_sections(self) -> None:
        headings = extract_section_headings_from_text(
            "ATABERK SELEKOGLU\nPROFILE\nText\nSUMMARY OF QUALIFICATIONS\nText\nPROJECTS\nText"
        )

        self.assertEqual(headings, ["PROFILE", "SUMMARY OF QUALIFICATIONS", "PROJECTS"])

    def test_diff_classifier_scaffold_labels_basic_decisions(self) -> None:
        master = "\n".join(
            [
                "PROFILE",
                "Built Python automation for reports and document workflows.",
                "Created React dashboards for operational users.",
                "Maintained unrelated legacy inventory process.",
            ]
        )
        example = "\n".join(
            [
                "PROFILE",
                "Built Python automation for reports and document workflows.",
                "Created React dashboards for users.",
                "Added business systems analyst positioning.",
            ]
        )

        diff = classify_master_example_diff(master, example)

        self.assertEqual(diff.retained_count, 1)
        self.assertEqual(diff.shortened_or_reworded_count, 1)
        self.assertEqual(diff.added_count, 1)
        self.assertEqual(diff.removed_count, 1)


if __name__ == "__main__":
    unittest.main()
