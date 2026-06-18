import type { SectionProposal } from "./types";

function coerceSection(raw: unknown): SectionProposal | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const title = typeof o.title === "string" ? o.title : "Section";
  const kind = typeof o.kind === "string" ? o.kind : "other";
  const body_text = typeof o.body_text === "string" ? o.body_text : "";
  const start_para = typeof o.start_para === "number" ? o.start_para : 0;
  const end_para = typeof o.end_para === "number" ? o.end_para : 0;
  return {
    title,
    kind,
    body_text,
    start_para,
    end_para,
    role_label: typeof o.role_label === "string" ? o.role_label : "",
    employer_line: typeof o.employer_line === "string" ? o.employer_line : "",
    title_line: typeof o.title_line === "string" ? o.title_line : "",
    date_line: typeof o.date_line === "string" ? o.date_line : "",
    custom_kind_name: typeof o.custom_kind_name === "string" ? o.custom_kind_name : "",
  };
}

/**
 * Build editable sections from a saved master JSON payload.
 * Older exports without `sections` fall back to a single block using `raw_text`.
 */
export function sectionsFromMasterPayload(payload: Record<string, unknown>): SectionProposal[] {
  const raw = payload.sections;
  if (Array.isArray(raw) && raw.length > 0) {
    const out: SectionProposal[] = [];
    for (const item of raw) {
      const sec = coerceSection(item);
      if (sec) out.push(sec);
    }
    if (out.length) return out;
  }
  const rt = typeof payload.raw_text === "string" ? payload.raw_text : "";
  return [
    {
      title: "Full CV (legacy)",
      kind: "other",
      body_text: rt,
      start_para: 0,
      end_para: 0,
    },
  ];
}
