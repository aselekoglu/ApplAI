import { defineTool } from "eve/tools";
import { z } from "zod";

import { callCoreApi } from "../lib/core-api.js";

export default defineTool({
  description: "Create a draft tailored CV by calling ApplAI Core. This does not approve or submit the artifact.",
  inputSchema: z.object({
    job_id: z.string().min(1),
    master_id: z.string().min(1),
    max_pages: z.number().int().min(1).max(3).default(2),
    mode: z.enum(["quick", "full"]).default("quick"),
  }),
  async execute(input) {
    throw new Error(
      `Core tailoring by job_id is not exposed yet for ${input.job_id}. Use /tailor/run once the job record endpoint exists.`
    );
  },
});
