# ApplAI - Automated Job Application Workflow

ApplAI is a sleek, AI-powered tool designed to streamline your job application process. It handles everything from extracting job details to tailoring your CV and generating cover letters, all while preserving your original document formatting.

## 🚀 Features

- **Automated Job Extraction**: Paste a job description and let AI extract the company name and role.
- **Smart CV Tailoring**: Automatically updates your Profile and Relevant Experience sections to match the job description.
- **Format Preservation**: Uses your original Word doc template to ensure your professional design is never lost.
- **Cover Letter Generation**: Creates personalized cover letters based on the job requirements.
- **Keyword Match Analysis**: Visualizes how well your CV aligns with the job keywords (Match Rate vs Gaps).
- **Google Docs Integration**: Seamlessly syncs your generated applications to Google Drive.
- **Agent Execution Log**: Full visibility into what each AI agent (Job Analyzer, CV Tailorer, QA Reviewer) did.

## 🛠️ Built With

- **Python & Streamlit**: Sleek, interactive web interface.
- **CrewAI**: Multi-agent orchestration for complex workflows.
- **Google Gemini API**: State-of-the-art LLM for content extraction and generation.
- **ReportLab & python-docx**: Robust document handling.

## 🏁 Getting Started

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd ApplAI
   ```

2. **Set up your environment**:
   - Create a `.env` file with your `GEMINI_API_KEY`.
   - Place your `google_credentials.json` in the root (if using Google Drive sync).

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the app**:
   ```bash
   streamlit run app.py
   ```

## 🔒 Privacy & Security

The project includes a `.gitignore` to ensure your API keys and Google OAuth tokens are never committed to public repositories.

---
*Created with ❤️ for smarter job hunting.*
