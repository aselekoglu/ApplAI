import unittest

from api.app.schemas.resume_render import ResumeContact, ResumeEntry, ResumeItem, ResumeLayout
from api.app.services.resume_layout_service import build_resume_layout, extract_contact_from_master_text


class ResumeRenderSchemaTest(unittest.TestCase):
    def test_resume_layout_carries_contact_and_structured_entries(self):
        layout = ResumeLayout(
            owner_name="ATABERK (ATA) SELEKOGLU",
            contact=ResumeContact(
                location="Ottawa, ON",
                phone="613-793-5109",
                email="sele0007@algonquinlive.com",
                links=["https://github.com/aselekoglu"],
            ),
            experience_entries=[
                ResumeEntry(
                    entry_id="exp-1",
                    title="Technical Business Analyst",
                    organization="Call Center Studio",
                    date_range="Mar 2021 - Feb 2024",
                    items=[
                        ResumeItem(
                            item_id="e1",
                            text="Built REST API integrations.",
                            source_section="experience",
                        )
                    ],
                )
            ],
            project_entries=[
                ResumeEntry(
                    entry_id="project-1",
                    title="ApplAI - AI Assisted Job Application Automation Platform",
                    date_range="Mar 2026",
                )
            ],
        )

        self.assertEqual(layout.contact.email, "sele0007@algonquinlive.com")
        self.assertEqual(layout.experience_entries[0].title, "Technical Business Analyst")
        self.assertEqual(
            layout.project_entries[0].title,
            "ApplAI - AI Assisted Job Application Automation Platform",
        )


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

    def test_falls_back_to_canonical_profile_and_skills_when_tailoring_selections_are_sparse(self):
        payload = {
            "canonical_cv": {
                "profile_bullets": [
                    {
                        "bullet_id": "prof-1",
                        "text": "Frontend developer building AI-assisted applications and REST API workflows.",
                    }
                ],
                "skills_sections": {
                    "Frontend": ["React", "TypeScript", "Vite", "React"],
                    "AI": ["AI Agents", "LLMs"],
                },
            },
            "tailored_output": {},
            "page_budget": {"max_pages": 2},
        }

        layout = build_resume_layout(payload, owner_name="Ata Selekoglu")

        self.assertEqual([section.kind for section in layout.sections], ["profile", "skills"])
        self.assertEqual(layout.sections[0].items[0].item_id, "prof-1")
        self.assertIn("AI-assisted applications", layout.sections[0].items[0].text)
        self.assertEqual(
            [item.text for item in layout.sections[1].items],
            ["React", "TypeScript", "Vite", "AI Agents", "LLMs"],
        )

    def test_falls_back_to_master_profile_and_skills_when_canonical_is_sparse(self):
        payload = {
            "canonical_cv": {
                "profile_bullets": [],
                "skills_sections": {},
            },
            "tailored_output": {},
            "page_budget": {"max_pages": 2},
        }
        master = {
            "sections": [
                {
                    "title": "PROFILE",
                    "kind": "profile",
                    "body_text": "AI Application Developer building agentic front-end applications.\nSoftware Developer with REST API experience.",
                },
                {
                    "title": "SUMMARY OF QUALIFICATIONS",
                    "kind": "skills",
                    "body_text": "React, TypeScript, Vite, JavaScript\nAI Agents, LLMs, REST APIs",
                },
            ]
        }

        layout = build_resume_layout(payload, owner_name="Ata Selekoglu", master_payload=master)

        self.assertEqual([section.kind for section in layout.sections], ["profile", "skills"])
        self.assertEqual(layout.sections[0].items[0].text, "AI Application Developer building agentic front-end applications.")
        self.assertEqual(
            [item.text for item in layout.sections[1].items],
            ["React", "TypeScript", "Vite", "JavaScript", "AI Agents", "LLMs", "REST APIs"],
        )


class MasterTextExtractionTest(unittest.TestCase):
    def test_extract_contact_from_master_text(self):
        contact = extract_contact_from_master_text(
            "ATABERK (ATA) SELEKOGLU\n"
            "Ottawa, ON, K1Z 0C9\n"
            "613-793-5109, sele0007@algonquinlive.com\n"
            "https://www.linkedin.com/in/aselekoglu/\n"
            "https://github.com/aselekoglu\n"
            "PROFILE\n"
        )

        self.assertEqual(contact.location, "Ottawa, ON, K1Z 0C9")
        self.assertEqual(contact.phone, "613-793-5109")
        self.assertEqual(contact.email, "sele0007@algonquinlive.com")
        self.assertEqual(
            contact.links,
            ["https://www.linkedin.com/in/aselekoglu/", "https://github.com/aselekoglu"],
        )


class StructuredResumeLayoutTest(unittest.TestCase):
    def test_layout_carries_contact_and_structured_entries(self):
        payload = {
            "canonical_cv": {
                "experience": [
                    {
                        "employer": "Call Center Studio",
                        "role": "Technical Business Analyst",
                        "start_date": "Mar 2021",
                        "end_date": "Feb 2024",
                        "location": "Remote",
                    }
                ],
                "projects": [
                    {
                        "title": "ApplAI - AI Assisted Job Application Automation Platform",
                        "date": "Mar 2026",
                        "institution": "",
                    }
                ],
                "education": [
                    {
                        "institution": "Algonquin College",
                        "degree": "Post-graduate",
                        "field_of_study": "Artificial Intelligence Software Development",
                        "start_date": "2025",
                        "end_date": "Present",
                    }
                ],
            },
            "tailored_output": {
                "profile_selections": [
                    {
                        "bullet_id": "profile-1",
                        "section": "profile",
                        "action": "select_as_is",
                        "original_text": "Frontend developer building AI-assisted applications.",
                    }
                ],
                "skills_to_highlight": ["React", "TypeScript", "Vite", "AI Agents"],
                "experience_selections": [
                    {
                        "bullet_id": "exp_0_0",
                        "section": "experience",
                        "action": "select_as_is",
                        "original_text": "Built REST API integrations for CRM workflows.",
                    }
                ],
                "project_selections": [
                    {
                        "bullet_id": "proj_0_0",
                        "section": "projects",
                        "action": "select_as_is",
                        "original_text": "Built an AI-driven job application workflow system.",
                    }
                ],
                "education_selections": [
                    {
                        "bullet_id": "edu_0_0",
                        "section": "education",
                        "action": "select_as_is",
                        "original_text": "Completed AI software development coursework.",
                    }
                ],
            },
            "page_budget": {"max_pages": 2},
        }
        master = {
            "raw_text": (
                "ATABERK (ATA) SELEKOGLU\n"
                "Ottawa, ON, K1Z 0C9\n"
                "613-793-5109, sele0007@algonquinlive.com\n"
                "https://www.linkedin.com/in/aselekoglu/\n"
                "https://github.com/aselekoglu\n"
                "PROFILE\n"
            )
        }

        layout = build_resume_layout(
            payload,
            owner_name="ATABERK (ATA) SELEKOGLU",
            target_role="Applied AI Junior Front-End Developer",
            company_name="Trend Micro",
            expected_keywords=["React", "TypeScript"],
            master_payload=master,
        )

        self.assertEqual(layout.contact.location, "Ottawa, ON, K1Z 0C9")
        self.assertEqual(layout.contact.email, "sele0007@algonquinlive.com")
        self.assertIn("https://github.com/aselekoglu", layout.contact.links)
        self.assertEqual(layout.experience_entries[0].title, "Technical Business Analyst")
        self.assertEqual(layout.experience_entries[0].organization, "Call Center Studio")
        self.assertEqual(layout.project_entries[0].title, "ApplAI - AI Assisted Job Application Automation Platform")
        self.assertEqual(layout.education_entries[0].organization, "Algonquin College")


if __name__ == "__main__":
    unittest.main()
