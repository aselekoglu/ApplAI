import { defineTool } from "eve/tools";
import { z } from "zod";

import { callCoreApi } from "../lib/core-api.js";
import type { TailorCvOutput } from "../lib/contracts.js";

export default defineTool({
  description: "Create a draft tailored CV by calling ApplAI Core. This does not approve or submit the artifact.",
  inputSchema: z.object({
    job_id: z.string().min(1),
    master_id: z.string().min(1),
    max_pages: z.number().int().min(1).max(3).default(2),
    mode: z.enum(["quick", "full"]).default("quick"),
  }),
  async execute(input) {
    return callCoreApi<TailorCvOutput>("/tailor/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: input.job_id,
        master_id: input.master_id,
        options: {
          max_pages: input.max_pages,
          quick_mode: input.mode === "quick",
        },
      }),
    });
  },
});
