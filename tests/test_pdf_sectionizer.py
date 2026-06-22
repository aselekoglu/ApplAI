import pytest
from unittest.mock import patch, MagicMock
import pdf_parser
import agent_workflow

def make_mock_word(text, top, x0, x1=None):
    if x1 is None:
        x1 = x0 + len(text) * 6
    return {
        "text": text,
        "x0": float(x0),
        "x1": float(x1),
        "top": float(top),
        "bottom": float(top + 10),
        "doctop": float(top)
    }

def make_mock_page_words(lines_spec):
    words = []
    for item in lines_spec:
        if isinstance(item[0], list):
            for text, x0 in item[0]:
                for i, w in enumerate(text.split()):
                    words.append(make_mock_word(w, item[1], x0 + i * 40))
        else:
            text = item[0]
            x_curr = item[2]
            for w in text.split():
                words.append(make_mock_word(w, item[1], x_curr))
                x_curr += len(w) * 6 + 4
    return words

@pytest.fixture
def mock_pdfplumber_nrc():
    # Setup lines spec representing the NRC CV layout
    lines_spec = [
        ("Alp Aselekoglu", 10, 100),
        ("Email: alp@example.com | Phone: 123-456-7890", 22, 80),
        ("PROFILE", 40, 50),
        ("• Analytical and solutions-focused Software & Data Developer.", 55, 50),
        ("SUMMARY OF QUALIFICATIONS", 75, 50),
        ("• Python, SQL, Streamlit", 90, 50),
        ("EXPERIENCE", 110, 50),
        ([("Technical Business Analyst", 50), ("Mar 2021 - Feb 2024", 350)], 125, 0),
        ("Call Center Studio, Remote", 140, 50),
        ("• Led API integrations", 155, 50),
        ("• Optimized database", 170, 50),
        ("queries and scripts", 182, 65), # Wrapped bullet continuation
        ("EDUCATION", 210, 50),
        ("Bachelor of Science", 225, 50),
        ("Algonquin College", 240, 50),
        ("PROJECTS", 260, 50),
        ([("ApplAI Tailoring Assistant", 50), ("2026", 350)], 275, 0),
        ("• Implemented reliable master CV extraction", 290, 50),
        ("ADDITIONAL", 310, 50),
        ("Languages: English, French", 325, 50),
    ]
    mock_words = make_mock_page_words(lines_spec)
    
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "\n".join([item[0] if isinstance(item[0], str) else " ".join([p[0] for p in item[0]]) for item in lines_spec])
    mock_page.extract_words.return_value = mock_words
    
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    
    return mock_pdf

@pytest.fixture
def mock_pdfplumber_ambiguous():
    lines_spec = [
        ("Alp Aselekoglu", 10, 100),
        ("Email: alp@example.com", 22, 80),
        ("Some random paragraph here that is quite long and describes my life story and contains no headings at all.", 40, 50),
        ("Another paragraph explaining other details about work.", 60, 50),
    ]
    mock_words = make_mock_page_words(lines_spec)
    
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "\n".join([item[0] for item in lines_spec])
    mock_page.extract_words.return_value = mock_words
    
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    
    return mock_pdf

def test_pdf_sectionizer_nrc_split(mock_pdfplumber_nrc):
    with patch('pdfplumber.open') as mock_open:
        mock_open.return_value.__enter__.return_value = mock_pdfplumber_nrc
        
        res = pdf_parser.parse_pdf_to_json("dummy_nrc.pdf")
        
        assert res is not None
        assert res["parser_version"] == "sectionizer_v1"
        assert res["structure_status"] == "ok"
        assert len(res["structure_warnings"]) == 0
        
        sections = res["structured_sections"]
        canonical_types = [sec["canonical_type"] for sec in sections]
        
        # Sections include: contact, profile, summary_qualifications, experience, education, projects, additional
        assert "contact" in canonical_types
        assert "profile" in canonical_types
        assert "summary_qualifications" in canonical_types
        assert "experience" in canonical_types
        assert "education" in canonical_types
        assert "projects" in canonical_types
        assert "additional" in canonical_types
        
        # Verify it's not one profile block
        assert len(sections) > 1
        
        # Verify wrapped bullets merged in the raw parsed lines
        exp_sec = next(s for s in sections if s["canonical_type"] == "experience")
        # Body lines of experience should include the merged bullet
        # The original was: "• Optimized database", "queries and scripts"
        assert any("Optimized database queries and scripts" in line for line in exp_sec["body_lines"])

def test_load_canonical_cv_parsing(mock_pdfplumber_nrc):
    with patch('pdfplumber.open') as mock_open:
        mock_open.return_value.__enter__.return_value = mock_pdfplumber_nrc
        
        raw_json = pdf_parser.parse_pdf_to_json("dummy_nrc.pdf")
        cv = agent_workflow.load_canonical_cv(raw_json)
        
        assert cv is not None
        assert cv.full_name == "Alp Aselekoglu"
        assert cv.contact["email"] == "alp@example.com"
        assert cv.contact["phone"] == "123-456-7890"
        
        # Profile bullets
        assert len(cv.profile_bullets) == 1
        assert "Analytical and solutions-focused" in cv.profile_bullets[0].text
        
        # Skills section
        assert "Key Qualifications" in cv.skills_sections
        assert "Python, SQL, Streamlit" in cv.skills_sections["Key Qualifications"][0]
        
        # Experience entries
        assert len(cv.experience) == 1
        exp = cv.experience[0]
        assert exp.role == "Technical Business Analyst"
        assert exp.employer == "Call Center Studio"
        assert exp.start_date == "Mar 2021"
        assert exp.end_date == "Feb 2024"
        assert exp.location == "Remote"
        
        # Check experience bullets and merging
        assert len(exp.bullets) == 2
        assert exp.bullets[0].text == "Led API integrations"
        assert exp.bullets[1].text == "Optimized database queries and scripts" # Merged wrapped bullet!
        
        # Education entries
        assert len(cv.education) == 1
        edu = cv.education[0]
        assert edu.degree == "Bachelor of Science"
        assert edu.institution == "Algonquin College"
        
        # Project entries
        assert len(cv.projects) == 1
        proj = cv.projects[0]
        assert proj.title == "ApplAI Tailoring Assistant"
        assert proj.date == "2026"
        assert len(proj.bullets) == 1
        assert proj.bullets[0].text == "Implemented reliable master CV extraction"
        
        # Additional text
        assert "Languages: English, French" in cv.additional

def test_pdf_sectionizer_ambiguous_review(mock_pdfplumber_ambiguous):
    with patch('pdfplumber.open') as mock_open:
        mock_open.return_value.__enter__.return_value = mock_pdfplumber_ambiguous
        
        res = pdf_parser.parse_pdf_to_json("dummy_ambiguous.pdf")
        
        assert res is not None
        assert res["structure_status"] == "needs_review"
        assert len(res["structure_warnings"]) > 0
        assert "No section headings could be identified" in res["structure_warnings"][0]
