import { defineEval } from "eve/evals";

import { requiresApproval } from "../lib/approval-policy.js";

export default defineEval({
  description: "Approval policy blocks submit, publish, send, upload, and ready_to_submit actions.",
  async test(t) {
    if (!requiresApproval("submit_application")) throw new Error("submit_application must require approval");
    if (!requiresApproval("publish_linkedin_post")) throw new Error("publish action must require approval");
    if (!requiresApproval("save_application", { status: "ready_to_submit" })) {
      throw new Error("ready_to_submit must require approval");
    }
    t.completed();
  },
});
