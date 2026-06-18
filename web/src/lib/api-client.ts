/**
 * HTTP client for the FastAPI backend. Set `VITE_API_URL` in `.env` (see repo `web/.env.example`);
 * when unset, requests use http://127.0.0.1:8000 (must match CORS / running API).
 */
import type {
  ExportResponse,
  FinalizeMasterRequest,
  ImportMasterResponse,
  MasterDetail,
  MasterSummary,
  RunDetailResponse,
  RunSummary,
  TailorRunOptions,
  TailorRunResponse,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch (error) {
    const hint =
      `Could not reach API at ${API_BASE_URL}. ` +
      `Make sure FastAPI is running and VITE_API_URL/CORS are configured for your web origin.`;
    throw new Error(`${hint} (${(error as Error)?.message ?? "network error"})`);
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      if (payload?.detail) detail = payload.detail;
    } catch {
      // ignore parse fallback
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export const apiClient = {
  async importMaster(file: File, alias?: string): Promise<ImportMasterResponse> {
    const formData = new FormData();
    formData.append("file", file);
    if (alias) formData.append("alias", alias);
    return request<ImportMasterResponse>("/masters/import", {
      method: "POST",
      body: formData,
    });
  },
  async finalizeMaster(masterId: string, payload: FinalizeMasterRequest) {
    return request<{ master_id: string; json_path: string; template_config_path: string; source_filename: string }>(
      `/masters/${encodeURIComponent(masterId)}/finalize`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    );
  },
  async listMasters(): Promise<MasterSummary[]> {
    return request<MasterSummary[]>("/masters");
  },
  async getMaster(masterId: string): Promise<MasterDetail> {
    return request<MasterDetail>(`/masters/${encodeURIComponent(masterId)}`);
  },
  async runTailoring(payload: {
    master_id: string;
    job_description: string;
    options: TailorRunOptions;
  }): Promise<TailorRunResponse> {
    return request<TailorRunResponse>("/tailor/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  async listRuns(): Promise<RunSummary[]> {
    return request<RunSummary[]>("/tailor/runs");
  },
  async getRun(runId: string): Promise<RunDetailResponse> {
    return request<RunDetailResponse>(`/tailor/runs/${encodeURIComponent(runId)}`);
  },
  async exportRun(runId: string): Promise<ExportResponse> {
    return request<ExportResponse>("/tailor/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: runId }),
    });
  },
};
