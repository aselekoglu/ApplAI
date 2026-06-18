import { defineTool } from "eve/tools";
import { z } from "zod";

import { requiresApproval } from "../lib/approval-policy.js";

export default defineTool({
  description: "Save an application record through ApplAI Core. Draft saves are allowed; ready-to-submit requires approval.",
  inputSchema: z.object({
    job_id: z.string().min(1),
    run_id: z.string().optional(),
    artifact_ids: z.array(z.string()).default([]),
    status: z.enum(["draft", "ready_to_submit", "submitted", "rejected", "interview", "offer"]).default("draft"),
  }),
  needsApproval: ({ toolInput }) => requiresApproval("save_application", toolInput),
  async execute(input) {
    if (input.status !== "draft") {
      throw new Error("Application persistence endpoint is not exposed yet; non-draft status changes must remain approval-gated.");
    }
    throw new Error("Application draft persistence endpoint is not exposed yet in ApplAI Core.");
  },
});
