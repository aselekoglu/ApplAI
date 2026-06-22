import { useEffect, useState } from "react";
import { apiClient, API_BASE_URL } from "../lib/api-client";
import type { ExportMetadata, RunDetailResponse, RunSummary } from "../lib/types";

function statusLabel(value?: boolean | null) {
  if (value === true) return "passed";
  if (value === false) return "failed";
  return "not available";
}

function buildFileUrl(path?: string | null): string {
  if (!path) return "";
  const cleaned = path.replace(/^docs[\\/]/, "");
  return `${API_BASE_URL}/static-docs/${encodeURIComponent(cleaned)}`;
}

function ExportDetails({ exports, maxPages }: { exports: ExportMetadata; maxPages: number }) {
  const finalPdfPath = exports.pdf_path ?? exports.cv_path;
  const atsNotes = exports.ats_parse_notes ?? [];

  return (
    <div className="stack compact" style={{ fontSize: "0.85rem", lineHeight: "1.5" }}>
      {finalPdfPath ? (
        <p style={{ margin: "0.2rem 0" }}>
          Final PDF:{" "}
          <a href={buildFileUrl(finalPdfPath)} target="_blank" rel="noreferrer" style={{ color: "#8ab4ff", textDecoration: "underline", fontWeight: "600" }}>
            Open Tailored PDF
          </a>
        </p>
      ) : null}
      {exports.cover_letter_path ? (
        <p style={{ margin: "0.2rem 0" }}>
          Cover letter:{" "}
          <a href={buildFileUrl(exports.cover_letter_path)} target="_blank" rel="noreferrer" style={{ color: "#8ab4ff", textDecoration: "underline", fontWeight: "600" }}>
            Open Cover Letter PDF
          </a>
        </p>
      ) : null}
      {exports.page_count != null ? (
        <p style={{ margin: "0.2rem 0" }}>
          PDF pages: <strong>{exports.page_count}</strong> / {maxPages}
        </p>
      ) : null}
      {exports.layout_passed != null ? (
        <p style={{ margin: "0.2rem 0" }}>
          Visual layout: <strong style={{ color: exports.layout_passed ? "#a5d6a7" : "#ff9f9f" }}>{statusLabel(exports.layout_passed)}</strong>
        </p>
      ) : null}
      {exports.ats_parse_passed != null ? (
        <p style={{ margin: "0.2rem 0" }}>
          ATS text extraction: <strong style={{ color: exports.ats_parse_passed ? "#a5d6a7" : "#ff9f9f" }}>{statusLabel(exports.ats_parse_passed)}</strong>
        </p>
      ) : null}
      {exports.html_path ? (
        <p style={{ margin: "0.2rem 0" }}>
          HTML preview:{" "}
          <a href={buildFileUrl(exports.html_path)} target="_blank" rel="noreferrer" style={{ color: "#8ab4ff", textDecoration: "underline" }}>
            View HTML
          </a>
        </p>
      ) : null}
      {exports.docx_path ? (
        <p style={{ margin: "0.2rem 0" }}>
          DOCX compatibility:{" "}
          <a href={buildFileUrl(exports.docx_path)} download style={{ color: "#8ab4ff", textDecoration: "underline" }}>
            Download Word Document (DOCX)
          </a>
        </p>
      ) : null}
      {exports.ats_parse_passed === false || atsNotes.length ? (
        <div style={{ marginTop: "0.5rem" }}>
          <p style={{ margin: "0.2rem 0", fontWeight: "bold" }}>ATS notes:</p>
          {atsNotes.length ? (
            <ul className="simpleList" style={{ paddingLeft: "1.2rem", margin: "0.2rem 0" }}>
              {atsNotes.map((note, index) => (
                <li key={`${index}-${note}`} style={{ color: "#ff9f9f" }}>{note}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">No notes returned.</p>
          )}
        </div>
      ) : null}
      {exports.docs_url ? (
        <p style={{ margin: "0.2rem 0" }}>
          Google Docs:{" "}
          <a href={exports.docs_url} target="_blank" rel="noreferrer" style={{ color: "#8ab4ff", textDecoration: "underline" }}>
            Open Google Docs
          </a>
        </p>
      ) : null}
    </div>
  );
}

export function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selected, setSelected] = useState<RunDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "cv" | "cl" | "changelog">("overview");

  async function refresh() {
    const data = await apiClient.listRuns();
    setRuns(data);
    if (data[0] && !selected) {
      const detail = await apiClient.getRun(data[0].run_id);
      setSelected(detail);
    }
  }

  useEffect(() => {
    refresh().catch((err) => setError((err as Error).message));
  }, []);

  async function selectRun(runId: string) {
    setBusy(true);
    setError(null);
    try {
      setSelected(await apiClient.getRun(runId));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function exportRun() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await apiClient.exportRun(selected.run_id);
      setSelected(await apiClient.getRun(selected.run_id));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const copyToClipboard = () => {
    if (selected?.result.cover_letter) {
      navigator.clipboard.writeText(selected.result.cover_letter);
      alert("Cover letter copied to clipboard!");
    }
  };

  const renderSelection = (sel: any) => {
    const isDeselected = sel.action === "deselect";
    const isRewritten = sel.action === "rewrite" || sel.action === "compression_shorten_verbose_bullets" || sel.new_text;

    return (
      <div key={sel.bullet_id} style={{
        padding: "0.65rem 0",
        borderBottom: "1px solid #232a35",
        opacity: isDeselected ? 0.45 : 1,
        textDecoration: isDeselected ? "line-through" : "none"
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.25rem" }}>
          <span style={{ fontSize: "0.72rem", color: "#8ea0b8", fontFamily: "monospace" }}>{sel.bullet_id}</span>
          {isDeselected && <span style={{ background: "#c62828", color: "#ffffff", padding: "0.1rem 0.4rem", borderRadius: "4px", fontSize: "0.65rem", fontWeight: "bold" }}>DESELECTED</span>}
          {isRewritten && !isDeselected && <span style={{ background: "#1565c0", color: "#ffffff", padding: "0.1rem 0.4rem", borderRadius: "4px", fontSize: "0.65rem", fontWeight: "bold" }}>TAILORED</span>}
        </div>
        <p style={{ margin: 0, fontSize: "0.88rem", lineHeight: "1.45" }}>
          {sel.new_text || sel.original_text}
        </p>
        {isRewritten && !isDeselected && sel.original_text !== (sel.new_text || sel.original_text) && (
          <details style={{ marginTop: "0.4rem", fontSize: "0.8rem", color: "#8ea0b8" }}>
            <summary style={{ cursor: "pointer" }}>Show Original Bullet</summary>
            <p style={{ margin: "0.2rem 0 0 0", fontStyle: "italic", textDecoration: "line-through" }}>
              {sel.original_text}
            </p>
          </details>
        )}
        {sel.rewrite_rationale && (
          <div style={{ marginTop: "0.25rem", fontSize: "0.78rem", color: "#9fb3cc" }}>
            <em>Rationale:</em> {sel.rewrite_rationale}
          </div>
        )}
      </div>
    );
  };

  const overviewTab = selected && (
    <div className="stack" style={{ gap: "1rem" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
        <div className="card" style={{ padding: "0.8rem", background: "#181e28" }}>
          <strong>Match Score</strong>
          <div style={{ fontSize: "2rem", fontWeight: "bold", color: "#3d8bff", margin: "0.5rem 0" }}>
            {selected.result.qa_report.matching_rate_score}%
          </div>
          <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
            Keyword Coverage: {Math.round(selected.result.ats_report.coverage_pct || 0)}%
          </p>
        </div>
        <div className="card" style={{ padding: "0.8rem", background: "#181e28" }}>
          <strong>Render Status</strong>
          <div style={{ margin: "0.5rem 0", display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.85rem" }}>
            <div>Visual Layout: <span style={{ color: selected.exports?.layout_passed ? "#a5d6a7" : "#ff9f9f" }}>
              {selected.exports?.layout_passed ? "Passed" : "Failed / Unchecked"}
            </span></div>
            <div>ATS Readability: <span style={{ color: selected.exports?.ats_parse_passed ? "#a5d6a7" : "#ff9f9f" }}>
              {selected.exports?.ats_parse_passed ? "Passed" : "Failed / Unchecked"}
            </span></div>
          </div>
        </div>
      </div>

      {selected.result.qa_report.feedback && (
        <div className="card" style={{ padding: "0.8rem", background: "#151a22" }}>
          <strong>Tailoring Feedback</strong>
          <p style={{ fontSize: "0.9rem", margin: "0.5rem 0 0 0", whiteSpace: "pre-wrap" }}>
            {selected.result.qa_report.feedback}
          </p>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
        <div className="card" style={{ padding: "0.8rem", background: "#151a22" }}>
          <strong>Key Strengths</strong>
          <ul className="simpleList" style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}>
            {selected.result.qa_report.strong_points?.map((pt, i) => <li key={i}>{pt}</li>)}
            {!selected.result.qa_report.strong_points?.length && <li className="muted">None listed.</li>}
          </ul>
        </div>
        <div className="card" style={{ padding: "0.8rem", background: "#151a22" }}>
          <strong>Gaps / Pain Points</strong>
          <ul className="simpleList" style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}>
            {selected.result.qa_report.key_pain_points?.map((pt, i) => <li key={i}>{pt}</li>)}
            {!selected.result.qa_report.key_pain_points?.length && <li className="muted">None listed.</li>}
          </ul>
        </div>
      </div>

      <div className="card" style={{ padding: "0.8rem", background: "#151a22" }}>
        <strong>ATS Keyword Gap Analysis</strong>
        <div style={{ marginTop: "0.8rem" }}>
          <span className="muted" style={{ display: "block", fontSize: "0.8rem", marginBottom: "0.4rem" }}>
            Covered Keywords ({selected.result.ats_report.covered_keywords?.length || 0}):
          </span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginBottom: "1rem" }}>
            {selected.result.ats_report.covered_keywords?.map((kw) => (
              <span key={kw} className="pill" style={{ borderColor: "#2e7d32", color: "#a5d6a7", background: "rgba(46, 125, 50, 0.1)", fontSize: "0.75rem", padding: "0.15rem 0.4rem" }}>
                {kw}
              </span>
            ))}
            {!selected.result.ats_report.covered_keywords?.length && <span className="muted">None.</span>}
          </div>

          <span className="muted" style={{ display: "block", fontSize: "0.8rem", marginBottom: "0.4rem" }}>
            Missing / Gap Keywords ({selected.result.ats_report.gap_keywords?.length || 0}):
          </span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
            {selected.result.ats_report.gap_keywords?.map((kw) => (
              <span key={kw} className="pill" style={{ borderColor: "#c62828", color: "#ef9a9a", background: "rgba(198, 40, 40, 0.1)", fontSize: "0.75rem", padding: "0.15rem 0.4rem" }}>
                {kw}
              </span>
            ))}
            {!selected.result.ats_report.gap_keywords?.length && <span className="muted">None.</span>}
          </div>
        </div>
      </div>
    </div>
  );

  const cvTab = selected && (
    <div className="stack" style={{ gap: "1rem" }}>
      <div className="card" style={{ padding: "0.8rem", background: "#151a22" }}>
        <h4 style={{ margin: "0 0 0.5rem 0", color: "#8ab4ff" }}>Profile Summary</h4>
        {selected.result.tailored_output.profile_selections?.map(renderSelection)}
        {!selected.result.tailored_output.profile_selections?.length && <p className="muted" style={{ margin: 0 }}>No profile bullets tailored.</p>}
      </div>

      <div className="card" style={{ padding: "0.8rem", background: "#151a22" }}>
        <h4 style={{ margin: "0 0 0.5rem 0", color: "#8ab4ff" }}>Work Experience</h4>
        {selected.result.tailored_output.experience_selections?.map(renderSelection)}
        {!selected.result.tailored_output.experience_selections?.length && <p className="muted" style={{ margin: 0 }}>No experience bullets tailored.</p>}
      </div>

      <div className="card" style={{ padding: "0.8rem", background: "#151a22" }}>
        <h4 style={{ margin: "0 0 0.5rem 0", color: "#8ab4ff" }}>Projects</h4>
        {selected.result.tailored_output.project_selections?.map(renderSelection)}
        {!selected.result.tailored_output.project_selections?.length && <p className="muted" style={{ margin: 0 }}>No project bullets tailored.</p>}
      </div>

      <div className="card" style={{ padding: "0.8rem", background: "#151a22" }}>
        <h4 style={{ margin: "0 0 0.5rem 0", color: "#8ab4ff" }}>Education</h4>
        {selected.result.tailored_output.education_selections?.map(renderSelection)}
        {!selected.result.tailored_output.education_selections?.length && <p className="muted" style={{ margin: 0 }}>No education bullets tailored.</p>}
      </div>
    </div>
  );

  const clTab = selected && (
    <div className="stack" style={{ gap: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button onClick={copyToClipboard} style={{ fontSize: "0.8rem", padding: "0.3rem 0.6rem" }}>
          Copy Cover Letter Text
        </button>
      </div>
      <div style={{
        background: "#11161d",
        border: "1px solid #2e3642",
        borderRadius: "8px",
        padding: "1.2rem",
        fontFamily: "Georgia, serif",
        color: "#e6e9ef",
        lineHeight: "1.6",
        fontSize: "0.95rem",
        whiteSpace: "pre-wrap",
        minHeight: "400px"
      }}>
        {selected.result.cover_letter || "No cover letter was generated for this run."}
      </div>
    </div>
  );

  const changelogTab = selected && (
    <div className="stack" style={{ gap: "1rem" }}>
      <div className="card" style={{ padding: "0.8rem", background: "#151a22" }}>
        <strong>QA / Consistency Report</strong>
        <div style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}>
          <div>Fact Check Status: <span style={{ color: selected.result.qa_report.factual_support_passed ? "#a5d6a7" : "#ff9f9f", fontWeight: "bold" }}>
            {selected.result.qa_report.factual_support_passed ? "PASSED" : "FAILED / WARNING"}
          </span></div>

          {selected.result.qa_report.unsupported_claims?.length ? (
            <div style={{ marginTop: "0.5rem" }}>
              <span style={{ color: "#ff9f9f", fontWeight: "bold" }}>Unsupported Claims Flagged:</span>
              <ul className="simpleList" style={{ marginTop: "0.25rem", color: "#ff9f9f" }}>
                {selected.result.qa_report.unsupported_claims.map((claim, i) => <li key={i}>{claim}</li>)}
              </ul>
            </div>
          ) : (
            <div style={{ color: "#a5d6a7", marginTop: "0.25rem" }}>✓ No unsupported claims or hallucinated facts introduced.</div>
          )}

          {selected.result.qa_report.style_issues?.length ? (
            <div style={{ marginTop: "0.5rem" }}>
              <strong>Style / Formatting Warnings:</strong>
              <ul className="simpleList" style={{ marginTop: "0.25rem" }}>
                {selected.result.qa_report.style_issues.map((issue, i) => <li key={i}>{issue}</li>)}
              </ul>
            </div>
          ) : null}
        </div>
      </div>

      <div className="card" style={{ padding: "0.8rem", background: "#151a22" }}>
        <strong>Durable Tailoring Change Log ({selected.result.change_log.entries?.length || 0} modifications)</strong>
        <div style={{ marginTop: "0.8rem", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
          {selected.result.change_log.entries?.map((entry, index) => (
            <div key={index} style={{ padding: "0.5rem", background: "#1a212d", border: "1px solid #2c3545", borderRadius: "6px", fontSize: "0.82rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", color: "#8ea0b8", marginBottom: "0.25rem", fontSize: "0.75rem" }}>
                <span>Section: <strong>{entry.section}</strong></span>
                <span>Action: <strong>{entry.action}</strong></span>
              </div>
              {entry.new_text ? (
                <div>
                  <span className="muted" style={{ fontSize: "0.75rem" }}>Changed to:</span>
                  <p style={{ margin: "0.15rem 0", color: "#a5d6a7" }}>{entry.new_text}</p>
                </div>
              ) : (
                <div>
                  <span className="muted" style={{ fontSize: "0.75rem" }}>Deselected bullet:</span>
                  <p style={{ margin: "0.15rem 0", color: "#ef9a9a", textDecoration: "line-through" }}>{entry.original_text}</p>
                </div>
              )}
              <div style={{ color: "#adc2db", marginTop: "0.25rem", fontSize: "0.78rem" }}>
                <em>Rationale:</em> {entry.rationale}
              </div>
            </div>
          ))}
          {!selected.result.change_log.entries?.length && <p className="muted" style={{ margin: 0 }}>No modifications recorded.</p>}
        </div>
      </div>
    </div>
  );

  return (
    <section className="stack">
      <h2>Run history</h2>
      {error ? <p className="error">{error}</p> : null}
      <div className="grid2">
        <div className="card">
          <h3>Runs</h3>
          <ul className="simpleList">
            {runs.map((run) => (
              <li key={run.run_id}>
                <button className="linkButton" disabled={busy} onClick={() => selectRun(run.run_id)}>
                  {run.run_id.slice(0, 8)} — {run.job_title || "Untitled role"}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="card">
          <h3>Run details</h3>
          {!selected ? <p className="muted">Select a run to inspect details.</p> : null}
          {selected ? (
            <div className="stack" style={{ gap: "1rem" }}>
              <div style={{ borderBottom: "1px solid #232a35", paddingBottom: "0.8rem" }}>
                <p style={{ margin: "0.2rem 0" }}>Run ID: <code style={{ fontSize: "0.8rem" }}>{selected.run_id}</code></p>
                <p style={{ margin: "0.2rem 0" }}>Master: <strong>{selected.master_id}</strong></p>
                <p style={{ margin: "0.2rem 0" }}>Model: <code>{selected.options.model_name}</code></p>
              </div>

              {selected.exports ? (
                <div style={{ background: "#11161e", padding: "0.6rem", borderRadius: "8px", border: "1px solid #232a35" }}>
                  <ExportDetails exports={selected.exports} maxPages={selected.options.max_pages} />
                </div>
              ) : (
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <button className="btnPrimary" disabled={busy} onClick={exportRun}>
                    Export files (PDF / DOCX)
                  </button>
                  <span className="muted" style={{ fontSize: "0.8rem" }}>Exports PDF, Word document and cover letter.</span>
                </div>
              )}

              <div style={{ display: "flex", gap: "0.4rem", borderBottom: "1px solid #2e3642", paddingBottom: "0.4rem", marginTop: "0.8rem" }}>
                {(["overview", "cv", "cl", "changelog"] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    style={{
                      background: activeTab === tab ? "#2b6fd6" : "transparent",
                      borderColor: activeTab === tab ? "#3d7fe0" : "transparent",
                      color: "#e6e9ef",
                      fontWeight: activeTab === tab ? "bold" : "normal",
                      padding: "0.4rem 0.8rem",
                      fontSize: "0.82rem",
                      borderRadius: "6px",
                    }}
                  >
                    {tab === "overview"
                      ? "Overview"
                      : tab === "cv"
                      ? "Tailored Resume"
                      : tab === "cl"
                      ? "Cover Letter"
                      : "Change Log & QA"}
                  </button>
                ))}
              </div>

              <div style={{ minHeight: "200px" }}>
                {activeTab === "overview" && overviewTab}
                {activeTab === "cv" && cvTab}
                {activeTab === "cl" && clTab}
                {activeTab === "changelog" && changelogTab}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
