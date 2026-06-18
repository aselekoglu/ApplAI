const DEFAULT_CORE_API_URL = "http://127.0.0.1:8000";

export function coreApiUrl(): string {
  return (process.env.APPLAI_CORE_API_URL ?? DEFAULT_CORE_API_URL).replace(/\/+$/, "");
}

export async function callCoreApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${coreApiUrl()}${path}`, init);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      if (payload?.detail) detail = String(payload.detail);
    } catch {
      // Keep HTTP fallback detail.
    }
    throw new Error(`ApplAI Core API request failed for ${path}: ${detail}`);
  }
  return (await response.json()) as T;
}
