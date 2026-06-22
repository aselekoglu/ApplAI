import { defineTool } from "eve/tools";
import { z } from "zod";

import { callCoreApi } from "../lib/core-api.js";
import type { RenderCvOutput } from "../lib/contracts.js";

export default defineTool({
  description: "Render draft CV artifacts through ApplAI Core. Rendering drafts is allowed without approval.",
  inputSchema: z.object({
    run_id: z.string().min(1),
    format: z.enum(["docx", "pdf", "both"]).default("both"),
    max_pages: z.number().int().min(1).max(3).default(2),
  }),
  async execute(input) {
    const result = await callCoreApi<RenderCvOutput>(
      "/tailor/export",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: input.run_id }),
      }
    );
    return {
      run_id: result.run_id,
      cv_path: result.cv_path,
      cover_letter_path: result.cover_letter_path,
      docs_url: result.docs_url ?? null,
      docx_path: input.format === "pdf" ? "" : result.docx_path ?? null,
      pdf_path: input.format === "docx" ? "" : result.pdf_path ?? result.cv_path ?? "",
      html_path: result.html_path ?? "",
      page_count: result.page_count ?? null,
      layout_passed: result.layout_passed ?? null,
      ats_parse_passed: result.ats_parse_passed ?? null,
      ats_parse_notes: result.ats_parse_notes ?? [],
      artifact_ids: result.artifact_ids,
      core_response: result,
    };
  },
});
