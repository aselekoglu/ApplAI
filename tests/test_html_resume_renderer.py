import tempfile
import unittest
from pathlib import Path

from api.app.schemas.resume_render import ResumeContact, ResumeEntry, ResumeItem, ResumeLayout, ResumeSection
from api.app.services.html_resume_renderer import render_resume_html, write_resume_html


def _sample_layout() -> ResumeLayout:
    return ResumeLayout(
        owner_name="Ata <script>alert('x')</script> Selekoglu",
        target_role="AI Automation Engineer",
        company_name="ExampleCo",
        sections=[
            ResumeSection(
                kind="profile",
                heading="PROFILE",
                items=[
                    ResumeItem(
                        item_id="profile-1",
                        text="Builds <script>bad()</script> workflow automations.",
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
        ],
        expected_keywords=["Python"],
    )


class HtmlResumeRendererTest(unittest.TestCase):
    def test_renders_real_text_for_owner_metadata_bullets_and_skills(self):
        html = render_resume_html(_sample_layout())

        self.assertIn("Ata &lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt; Selekoglu", html)
        self.assertIn("AI Automation Engineer", html)
        self.assertIn("ExampleCo", html)
        self.assertIn("PROFILE", html)
        self.assertIn("Builds &lt;script&gt;bad()&lt;/script&gt; workflow automations.", html)
        self.assertIn("Python", html)
        self.assertIn("FastAPI", html)

    def test_embeds_print_css_with_page_rule(self):
        html = render_resume_html(_sample_layout())

        self.assertIn("@page", html)

    def test_does_not_emit_canvas_or_images(self):
        html = render_resume_html(_sample_layout()).lower()

        self.assertNotIn("<canvas", html)
        self.assertNotIn("<img", html)

    def test_escapes_dynamic_text_without_real_script_tags(self):
        html = render_resume_html(_sample_layout()).lower()

        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_placeholder_text_in_header_is_not_replaced_by_later_substitution(self):
        layout = ResumeLayout(
            owner_name="Ata __RESUME_SECTIONS__ Selekoglu",
            target_role="Role __RESUME_SECTIONS__",
            company_name="Company __RESUME_SECTIONS__",
            sections=[
                ResumeSection(
                    kind="profile",
                    heading="PROFILE",
                    items=[
                        ResumeItem(
                            item_id="profile-1",
                            text="Rendered section bullet.",
                            source_section="profile",
                        )
                    ],
                )
            ],
        )

        html = render_resume_html(layout)
        header_html = html.split("</header>", maxsplit=1)[0]

        self.assertIn("Ata __RESUME_SECTIONS__ Selekoglu", header_html)
        self.assertIn("Role __RESUME_SECTIONS__", header_html)
        self.assertIn("Company __RESUME_SECTIONS__", header_html)
        self.assertNotIn("Rendered section bullet.", header_html)
        self.assertIn("Rendered section bullet.", html)

    def test_escapes_script_and_quotes_in_metadata_and_headings(self):
        layout = ResumeLayout(
            owner_name="Ata Selekoglu",
            target_role='AI "<script>role()</script>" Engineer',
            company_name='Example "Co" <script>company()</script>',
            sections=[
                ResumeSection(
                    kind="profile",
                    heading='PROFILE "<script>heading()</script>"',
                    items=[
                        ResumeItem(
                            item_id="profile-1",
                            text="Grounded profile bullet.",
                            source_section="profile",
                        )
                    ],
                )
            ],
        )

        html = render_resume_html(layout).lower()

        self.assertIn("ai &quot;&lt;script&gt;role()&lt;/script&gt;&quot; engineer", html)
        self.assertIn("example &quot;co&quot; &lt;script&gt;company()&lt;/script&gt;", html)
        self.assertIn("profile &quot;&lt;script&gt;heading()&lt;/script&gt;&quot;", html)
        self.assertNotIn("<script>", html)

    def test_write_resume_html_creates_file_and_returns_path(self):
        layout = _sample_layout()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "resume.html"

            returned_path = write_resume_html(layout, str(output_path))

            self.assertEqual(returned_path, str(output_path))
            self.assertTrue(output_path.exists())
            self.assertIn("PROFILE", output_path.read_text(encoding="utf-8"))


class StructuredHtmlResumeRendererTest(unittest.TestCase):
    def test_renders_contact_and_entry_metadata(self):
        layout = ResumeLayout(
            owner_name="Ata Selekoglu",
            contact=ResumeContact(
                location="Ottawa, ON",
                phone="613-793-5109",
                email="sele0007@algonquinlive.com",
                links=["https://github.com/aselekoglu"],
            ),
            target_role="Applied AI Junior Front-End Developer",
            company_name="Trend Micro",
            sections=[
                ResumeSection(
                    kind="profile",
                    heading="PROFILE",
                    items=[
                        ResumeItem(
                            item_id="p1",
                            text="Frontend AI developer.",
                            source_section="profile",
                        )
                    ],
                ),
                ResumeSection(
                    kind="skills",
                    heading="SUMMARY OF QUALIFICATIONS",
                    items=[
                        ResumeItem(
                            item_id="s1",
                            text="React, TypeScript, Vite",
                            source_section="skills",
                        )
                    ],
                ),
            ],
            experience_entries=[
                ResumeEntry(
                    entry_id="exp1",
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
                    entry_id="proj1",
                    title="ApplAI - AI Assisted Job Application Automation Platform",
                    date_range="Mar 2026",
                    items=[
                        ResumeItem(
                            item_id="pr1",
                            text="Built LLM-powered CV tailoring workflows.",
                            source_section="projects",
                        )
                    ],
                )
            ],
        )

        html = render_resume_html(layout)

        self.assertIn("613-793-5109", html)
        self.assertIn("sele0007@algonquinlive.com", html)
        self.assertIn("https://github.com/aselekoglu", html)
        self.assertIn("Technical Business Analyst", html)
        self.assertIn("Call Center Studio", html)
        self.assertIn("Mar 2021 - Feb 2024", html)
        self.assertIn("ApplAI - AI Assisted Job Application Automation Platform", html)
        self.assertIn("Built LLM-powered CV tailoring workflows.", html)


if __name__ == "__main__":
    unittest.main()
