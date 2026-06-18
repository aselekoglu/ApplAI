import { useEffect, useMemo, useState } from "react";
import { RichTextEditorPlaceholder } from "../features/editor/RichTextEditorPlaceholder";
import { SuggestionsList } from "../features/suggestions/SuggestionsList";
import { TailorOptionsForm } from "../features/tailoring/TailorOptionsForm";
import { apiClient } from "../lib/api-client";
import type { MasterSummary, TailorRunOptions, TailorRunResponse } from "../lib/types";

const defaultOptions: TailorRunOptions = {
  model_name: "gemini-2.5-flash",
  company_name: "",
  job_title: "",
  quick_mode: false,
  include_cover_letter: true,
  include_ats: true,
  include_qa: true,
  allow_experience_rewrites: false,
  allow_education_rewrites: false,
  max_pages: 2,
};

export function TailoringPage() {
  const [masters, setMasters] = useState<MasterSummary[]>([]);
  const [masterId, setMasterId] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [options, setOptions] = useState<TailorRunOptions>(defaultOptions);
  const [runResult, setRunResult] = useState<TailorRunResponse | null>(null);
  const [exportPaths, setExportPaths] = useState<{ cv?: string; cl?: string; docsUrl?: string | null }>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiClient
      .listMasters()
      .then((data) => {
        setMasters(data);
        if (data[0]) setMasterId(data[0].master_id);
      })
      .catch((err) => setError((err as Error).message));
  }, []);

  const qa = runResult?.result.qa_report;
  const ats = runResult?.result.ats_report;
  const changeEntries = useMemo(() => runResult?.result.change_log.entries ?? [], [runResult]);

  async function handleRun() {
    setBusy(true);
    setError(null);
    setExportPaths({});
    try {
      const result = await apiClient.runTailoring({
        master_id: masterId,
        job_description: jobDescription,
        options,
      });
      setRunResult(result);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleExport() {
    if (!runResult) return;
    setBusy(true);
    setError(null);
    try {
      const response = await apiClient.exportRun(runResult.run_id);
      setExportPaths({
        cv: response.cv_path,
        cl: response.cover_letter_path,
        docsUrl: response.docs_url,
      });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="stack">
      <h2>Tailoring workspace</h2>
      <div className="card">
        <div className="grid2">
          <label className="field">
            <span>Master CV</span>
            <select value={masterId} onChange={(event) => setMasterId(event.target.value)}>
              {masters.map((master) => (
                <option key={master.master_id} value={master.master_id}>
                  {master.master_id}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Company</span>
            <input
              value={options.company_name}
              onChange={(event) => setOptions({ ...options, company_name: event.target.value })}
              placeholder="Company name"
            />
          </label>
        </div>
        <label className="field">
          <span>Job title</span>
          <input
            value={options.job_title}
            onChange={(event) => setOptions({ ...options, job_title: event.target.value })}
            placeholder="Role title"
          />
        </label>
        <label className="field">
          <span>Job description</span>
          <textarea
            rows={10}
            value={jobDescription}
            onChange={(event) => setJobDescription(event.target.value)}
            placeholder="Paste the job description..."
          />
        </label>
      </div>

      <TailorOptionsForm value={options} onChange={setOptions} />

      <div className="row">
        <button disabled={!masterId || !jobDescription || busy} onClick={handleRun}>
          Run tailoring
        </button>
        <button disabled={!runResult || busy} onClick={handleExport}>
          Export artifacts
        </button>
      </div>
      {error ? <p className="error">{error}</p> : null}

      {runResult ? (
        <section className="stack">
          <div className="grid3">
            <article className="card">
              <h3>QA summary</h3>
              <p>Match score: {qa?.matching_rate_score ?? 0}%</p>
              <p>Keyword coverage: {qa?.keyword_coverage_pct ?? 0}%</p>
            </article>
            <article className="card">
              <h3>ATS summary</h3>
              <p>Coverage: {ats?.coverage_pct ?? 0}%</p>
              <p>Covered keywords: {ats?.covered_keywords.length ?? 0}</p>
            </article>
            <article className="card">
              <h3>Run</h3>
              <p>ID: {runResult.run_id}</p>
              <p>Created: {new Date(runResult.created_at).toLocaleString()}</p>
            </article>
          </div>

          <RichTextEditorPlaceholder />

          <section className="card">
            <h3>Suggestions & change log</h3>
            <SuggestionsList entries={changeEntries} />
          </section>

          <section className="card">
            <h3>Cover letter</h3>
            <pre>{runResult.result.cover_letter || "No cover letter generated."}</pre>
          </section>

          {exportPaths.cv ? (
            <section className="card">
              <h3>Export artifacts</h3>
              <p>CV: {exportPaths.cv}</p>
              <p>Cover letter: {exportPaths.cl}</p>
              {exportPaths.docsUrl ? <p>Google Docs: {exportPaths.docsUrl}</p> : null}
            </section>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}
