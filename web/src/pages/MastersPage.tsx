import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { MasterDocumentStudio } from "../features/masters/MasterDocumentStudio";
import { apiClient } from "../lib/api-client";
import type { ImportMasterResponse, MasterSummary, SectionProposal } from "../lib/types";

function slugify(value: string): string {
  return value.trim().toLowerCase().replace(/[^\w]+/g, "_").replace(/^_+|_+$/g, "") || "master_cv";
}

export function MastersPage() {
  const [file, setFile] = useState<File | null>(null);
  const [alias, setAlias] = useState("");
  const [importData, setImportData] = useState<ImportMasterResponse | null>(null);
  const [sections, setSections] = useState<SectionProposal[]>([]);
  const [masters, setMasters] = useState<MasterSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refreshMasters() {
    try {
      const rows = await apiClient.listMasters();
      setMasters(rows);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  useEffect(() => {
    void refreshMasters();
  }, []);

  const masterId = useMemo(() => slugify(alias || file?.name?.replace(/\.(docx|pdf)$/i, "") || ""), [alias, file]);

  async function handleImport() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const data = await apiClient.importMaster(file, alias || undefined);
      setImportData(data);
      setSections(data.sections);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleFinalize() {
    if (!importData) return;
    setBusy(true);
    setError(null);
    try {
      await apiClient.finalizeMaster(masterId, {
        source_filename: importData.source_filename,
        sections,
        overwrite: false,
      });
      await refreshMasters();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="stack">
      <h2>Master CV management</h2>
      <div className="card">
        <div className="grid2">
          <label className="field">
            <span>Upload DOCX/PDF</span>
            <input type="file" accept=".docx,.pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </label>
          <label className="field">
            <span>Alias (optional)</span>
            <input value={alias} onChange={(event) => setAlias(event.target.value)} placeholder="aselem_master_v1" />
          </label>
        </div>
        <div className="row">
          <button disabled={!file || busy} onClick={handleImport}>
            Analyze Master CV
          </button>
          <span className="muted">Master ID: {masterId}</span>
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}

      {importData ? (
        <section className="stack masterStudioPage">
          <div className="row spread masterStudioTop">
            <div>
              <h3>Review in studio</h3>
              <p className="muted">Select each block on the left (like a resume checker), then edit the page on the right.</p>
            </div>
            <button className="btnPrimary" disabled={busy || sections.length === 0} onClick={handleFinalize}>
              Finalize master
            </button>
          </div>
          <MasterDocumentStudio
            sections={sections}
            sectionKinds={importData.section_kinds}
            onChange={setSections}
            documentLabel={importData.source_filename}
          />
        </section>
      ) : null}

      <div className="card">
        <h3>Saved masters</h3>
        {masters.length === 0 ? <p className="muted">No masters saved yet.</p> : null}
        <ul className="masterList">
          {masters.map((master) => (
            <li key={master.master_id} className="masterListItem">
              <div>
                <strong>{master.master_id}</strong>
                <span className="muted"> — {master.source_file}</span>
              </div>
              <Link className="pill" to={`/masters/${encodeURIComponent(master.master_id)}`}>
                Edit
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
