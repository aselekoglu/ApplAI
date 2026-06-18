# ApplAI - Agentic Job Application Workflow

ApplAI helps you run a repeatable JD-to-application flow: import a master CV once, review AI suggestions for each job description, and then export tailored files only when you approve the edits.

## Features

- **Suggestions-first tailoring**: review original vs suggested bullet edits before generating outputs.
- **Import Master CV**: upload DOCX/PDF, auto-detect sections, manually review/edit, and persist your canonical master.
- **Template-aware rendering**: stores section anchors in per-master config files so output is not tied to hardcoded headers.
- **Quick and deep modes**: quick mode minimizes LLM-heavy steps; deep mode runs full rewriting and QA flow.
- **Configurable rewriting**: optional safe rewrites for experience and education with factual checks.
- **Optional modules**: independently toggle cover letter generation and ATS/QA analysis.
- **Google Drive integration**: optional upload and conversion of tailored DOCX outputs.

## Built With

- **Python + Streamlit** for UI and orchestration.
- **FastAPI** for backend API routes and orchestration adapters.
- **React + TypeScript (Vite)** for the new web editing/tailoring workspace.
- **Google Gemini API** for structured extraction and rewrite suggestions.
- **Pydantic** for strict pipeline contracts.
- **python-docx, pdfplumber, ReportLab** for CV import and document output.

## Getting Started

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

4. **Run Streamlit fallback**:
   ```bash
   streamlit run app.py
   ```

## Run API (new stack)

From the repository root:

```bash
PYTHONPATH=. ./.venv/bin/python -m uvicorn api.app.main:app --reload
```

- Health check: `http://127.0.0.1:8000/health`
- OpenAPI docs: `http://127.0.0.1:8000/docs`

## Run Web (new stack)

From the repository root:

```bash
cd web
npm install
npm run dev
```

- Dev server URL: **`http://127.0.0.1:5173`**. Port **5173** is pinned in `web/vite.config.ts` (some Vite setups default to **3000**; this repo does not use 3000 for `npm run dev` unless you change the config).
- API base URL for the browser: copy `web/.env.example` to `web/.env` and set **`VITE_API_URL`** (for example `VITE_API_URL=http://127.0.0.1:8000`). Without a local `.env`, the app falls back to the same default as in `.env.example`.
- After you finalize a master, use **Edit** on the Masters page (or open `/masters/<master_id>`). The structured sections are stored in `docs/json_exports/<master_id>.json`, so a browser refresh reloads the same content from the API.

## Dual-stack migration status

ApplAI now supports a first production scaffold for the dual-stack migration:

- FastAPI routes for master import/finalize, tailoring runs, exports, and run history.
- React + TypeScript workspace for master editing, tailoring execution, and run inspection.
- Existing Streamlit app (`app.py`) remains fully available as a fallback path.
- For **parallel Cursor subagent runs** (split API / web / integration, with specific prompt templates), see [`docs/subagent-runbook.md`](docs/subagent-runbook.md).

## Workflow

1. Import your master CV in the **CV Library** tab (DOCX recommended).
2. Review and edit the detected section structure, then save.
3. In **Application Generator**, paste a JD and choose your saved master JSON.
4. Pick run mode/options, review suggestions, and export files when ready.

## Template and Docs Layout

- Place source CV files under `docs/`.
- Structured master exports are stored in `docs/json_exports/`.
- Master template configs are stored in `docs/master_configs/`.
- If you heavily rearrange your master DOCX layout, run **Import Master CV** again to refresh anchors.

## Google Drive Integration (Optional)

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

## Privacy & Security

The project includes a `.gitignore` to ensure your API keys and Google OAuth tokens are never committed to public repositories.

---
Created for smarter job hunting workflows.
