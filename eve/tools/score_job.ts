import { defineTool } from "eve/tools";
import { z } from "zod";

import { scoreJob } from "../lib/score-job-adapter.js";

export default defineTool({
  description: "Score a pasted job description by calling the ApplAI Core API.",
  inputSchema: z.object({
    job_description: z.string().min(1),
    company_name: z.string().optional(),
    job_title: z.string().optional(),
    source_url: z.string().url().optional(),
    save_draft: z.boolean().optional(),
  }),
  async execute(input) {
    return scoreJob(input);
  },
});
