import { useEffect, useState } from "react";
import { apiClient } from "../lib/api-client";
import type { RunDetailResponse, RunSummary } from "../lib/types";

export function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selected, setSelected] = useState<RunDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
            <>
              <p>Run ID: {selected.run_id}</p>
              <p>Master: {selected.master_id}</p>
              <p>Model: {selected.options.model_name}</p>
              <p>Score: {selected.result.qa_report.matching_rate_score}%</p>
              <button disabled={busy} onClick={exportRun}>
                Export this run
              </button>
              {selected.exports ? (
                <div className="stack compact">
                  <p>CV: {selected.exports.cv_path}</p>
                  <p>Cover letter: {selected.exports.cover_letter_path}</p>
                  {selected.exports.docs_url ? <p>Google Docs: {selected.exports.docs_url}</p> : null}
                </div>
              ) : null}
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}
