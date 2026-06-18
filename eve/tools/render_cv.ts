import { defineTool } from "eve/tools";
import { z } from "zod";

import { callCoreApi } from "../lib/core-api.js";

export default defineTool({
  description: "Render draft CV artifacts through ApplAI Core. Rendering drafts is allowed without approval.",
  inputSchema: z.object({
    run_id: z.string().min(1),
    format: z.enum(["docx", "pdf", "both"]).default("both"),
    max_pages: z.number().int().min(1).max(3).default(2),
  }),
  async execute(input) {
    const result = await callCoreApi<{ cv_path: string; cover_letter_path: string }>(
      "/tailor/export",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: input.run_id }),
      }
    );
    return {
      docx_path: input.format === "pdf" ? "" : result.cv_path,
      pdf_path: input.format === "docx" ? "" : result.cv_path.endsWith(".pdf") ? result.cv_path : "",
      page_count: null,
      layout_passed: null,
      core_response: result,
    };
  },
});
