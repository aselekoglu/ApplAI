import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { MasterDocumentStudio } from "../features/masters/MasterDocumentStudio";
import { apiClient } from "../lib/api-client";
import { sectionsFromMasterPayload } from "../lib/master-payload";
import { DEFAULT_SECTION_KINDS } from "../lib/section-kinds";
import type { MasterDetail, SectionProposal } from "../lib/types";

export function MasterEditorPage() {
  const { masterId: masterIdParam } = useParams<{ masterId: string }>();
  const masterId = masterIdParam ? decodeURIComponent(masterIdParam) : "";
  const navigate = useNavigate();

  const [detail, setDetail] = useState<MasterDetail | null>(null);
  const [sections, setSections] = useState<SectionProposal[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  useEffect(() => {
    if (!masterId) return;
    let cancelled = false;
    setError(null);
    void apiClient
      .getMaster(masterId)
      .then((data) => {
        if (cancelled) return;
        setDetail(data);
        setSections(sectionsFromMasterPayload(data.payload));
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [masterId]);

  async function handleSave() {
    if (!detail?.summary.source_file) return;
    setBusy(true);
    setError(null);
    try {
      await apiClient.finalizeMaster(masterId, {
        source_filename: detail.summary.source_file,
        sections,
        overwrite: true,
      });
      const refreshed = await apiClient.getMaster(masterId);
      setDetail(refreshed);
      setSections(sectionsFromMasterPayload(refreshed.payload));
      setSavedAt(new Date().toLocaleString());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!masterId) {
    return (
      <section className="stack">
        <p className="error">Missing master id.</p>
        <Link to="/masters">Back to masters</Link>
      </section>
    );
  }

  return (
    <section className="stack masterStudioPage">
      <div className="row spread masterStudioTop">
        <div>
          <h2>Master studio</h2>
          <p className="muted">
            <span className="pill">{masterId}</span> — edits sync to <code>docs/json_exports/</code> when you save
          </p>
        </div>
        <div className="row">
          <Link className="pill" to="/masters">
            ← All masters
          </Link>
          <button type="button" className="btnPrimary" disabled={busy || sections.length === 0} onClick={() => void handleSave()}>
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}
      {savedAt ? <p className="muted">Last saved: {savedAt}</p> : null}

      {detail ? (
        <p className="muted masterStudioNote">
          Source: <strong>{detail.summary.source_file}</strong>
          {Array.isArray(detail.payload["sections"]) && (detail.payload["sections"] as unknown[]).length > 0 ? null : (
            <span>
              {" "}
              — first-time legacy file: inferred from <code>raw_text</code>; save once to store full structure.
            </span>
          )}
        </p>
      ) : !error ? (
        <p className="muted">Loading master…</p>
      ) : null}

      {sections.length > 0 ? (
        <MasterDocumentStudio
          sections={sections}
          sectionKinds={DEFAULT_SECTION_KINDS}
          onChange={setSections}
          documentLabel={masterId}
        />
      ) : null}

      {detail && sections.length > 0 ? (
        <div className="row spread card masterStudioFooter">
          <p className="muted" style={{ margin: 0 }}>
            Doc-style canvas: pick a block on the left, edit on the right. Refresh keeps your saved master.
          </p>
          <div className="row">
            <button type="button" className="linkButton" onClick={() => navigate("/tailoring")}>
              Open tailoring →
            </button>
            <button type="button" className="btnPrimary" disabled={busy} onClick={() => void handleSave()}>
              {busy ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
