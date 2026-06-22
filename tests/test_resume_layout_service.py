import unittest

from api.app.services.resume_layout_service import build_resume_layout


class ResumeLayoutServiceTest(unittest.TestCase):
    def test_preserves_section_order_and_provenance_for_active_selected_bullet(self):
        payload = {
            "tailored_output": {
                "project_selections": [
                    {
                        "bullet_id": "proj-1",
                        "section": "portfolio_projects",
                        "action": "select",
                        "original_text": "Built automation tools for reporting.",
                        "new_text": "Built Python automation tools for reporting workflows.",
                        "relevance_score": 0.91,
                        "provenance": [
                            {
                                "source_type": "career_brain",
                                "source_id": "evidence-1",
                                "source_label": "Career Brain",
                                "supported_text": "Built automation tools for reporting.",
                            }
                        ],
                        "unsupported_claims": ["unsupported metric"],
                    }
                ],
                "experience_selections": [
                    {
                        "bullet_id": "exp-1",
                        "section": "experience",
                        "action": "select",
                        "original_text": "Delivered analytics dashboards.",
                    }
                ],
            },
            "page_budget": {"max_pages": 2},
        }

        layout = build_resume_layout(payload, owner_name="Ata Selekoglu")

        self.assertEqual([section.kind for section in layout.sections], ["experience", "projects"])
        project_item = layout.sections[1].items[0]
        self.assertEqual(project_item.item_id, "proj-1")
        self.assertEqual(project_item.text, "Built Python automation tools for reporting workflows.")
        self.assertEqual(project_item.source_section, "portfolio_projects")
        self.assertEqual(project_item.relevance_score, 0.91)
        self.assertEqual(project_item.provenance[0].source_id, "evidence-1")
        self.assertEqual(project_item.unsupported_claims, ["unsupported metric"])

    def test_skips_deselected_and_blank_selections(self):
        payload = {
            "tailored_output": {
                "profile_selections": [
                    {
                        "bullet_id": "profile-1",
                        "section": "profile",
                        "action": "deselect",
                        "original_text": "Remove this profile bullet.",
                    },
                    {
                        "bullet_id": "profile-2",
                        "section": "profile",
                        "action": "select",
                        "original_text": "   ",
                        "new_text": "",
                    },
                    {
                        "bullet_id": "profile-3",
                        "section": "profile",
                        "action": "select",
                        "original_text": "Grounded profile bullet.",
                    },
                ]
            },
            "page_budget": {},
        }

        layout = build_resume_layout(payload, owner_name="Ata Selekoglu")

        self.assertEqual(len(layout.sections), 1)
        self.assertEqual([item.item_id for item in layout.sections[0].items], ["profile-3"])

    def test_inserts_skills_after_profile_and_carries_metadata(self):
        payload = {
            "tailored_output": {
                "profile_selections": [
                    {
                        "bullet_id": "profile-1",
                        "section": "profile",
                        "action": "select",
                        "original_text": "AI automation profile.",
                    }
                ],
                "skills_to_highlight": ["Python", "FastAPI"],
                "education_selections": [
                    {
                        "bullet_id": "edu-1",
                        "section": "education",
                        "action": "select",
                        "original_text": "BSc Computer Science.",
                    }
                ],
            },
            "page_budget": {"max_pages": 3},
        }

        layout = build_resume_layout(
            payload,
            owner_name="Ata Selekoglu",
            target_role="AI Automation Engineer",
            company_name="ExampleCo",
            expected_keywords=["Python", "LLM"],
        )

        self.assertEqual(layout.owner_name, "Ata Selekoglu")
        self.assertEqual(layout.target_role, "AI Automation Engineer")
        self.assertEqual(layout.company_name, "ExampleCo")
        self.assertEqual(layout.max_pages, 3)
        self.assertEqual(layout.expected_keywords, ["Python", "LLM"])
        self.assertEqual([section.kind for section in layout.sections], ["profile", "skills", "education"])
        self.assertEqual(layout.sections[1].heading, "SUMMARY OF QUALIFICATIONS")
        self.assertEqual([item.text for item in layout.sections[1].items], ["Python", "FastAPI"])


if __name__ == "__main__":
    unittest.main()
