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

## ☁️ Google Drive Integration (Optional)

To enable automatic uploading and conversion of your CVs to Google Docs:

1. **Create a Google Cloud Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/).
   - Create a new project (e.g., `ApplAI-Integration`).

2. **Enable APIs**:
   - Navigate to **APIs & Services > Library**.
   - Search for and **Enable** both **Google Drive API** and **Google Docs API**.

3. **Create Service Account Credentials**:
   - Go to **APIs & Services > Credentials**.
   - Click **+ CREATE CREDENTIALS > Service account**.
   - Name it `appl-ai-agent` and click **Create and Continue**, then **Done**.
   - Click on the newly created service account email -> **Keys tab > Add Key > Create new key (JSON)**.
   - Rename the downloaded file to `google_credentials.json` and place it in the project root.

4. **Share a Folder**:
   - Create a folder in your personal Google Drive (e.g., `ApplAI Final Outputs`).
   - Share the folder with your **Service Account email** (found in Step 3) as an **Editor**.
   - Copy the folder ID from the URL (the alphanumeric string at the end) and add it to your `.env` file:
     `GOOGLE_DRIVE_FOLDER_ID=your_folder_id_here`

## 🔒 Privacy & Security

The project includes a `.gitignore` to ensure your API keys and Google OAuth tokens are never committed to public repositories.

---
*Created with ❤️ for smarter job hunting.*
