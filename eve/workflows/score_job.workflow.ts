import { requiresApproval } from "../lib/approval-policy.js";
import { scoreJob } from "../lib/score-job-adapter.js";
import type { ScoreJobInput, ScoreJobOutput } from "../lib/contracts.js";

export interface ScoreJobWorkflowResult {
  score: ScoreJobOutput;
  recommendation: ScoreJobOutput["recommendation"];
  next_actions: string[];
  workflow_status: "complete_no_followup" | "paused_before_state_change";
  pause_reason: string;
  approval_required_before_state_change: boolean;
}

export async function runScoreJobWorkflow(input: ScoreJobInput): Promise<ScoreJobWorkflowResult> {
  const score = await scoreJob(input);
  const next_actions =
    score.recommendation === "apply"
      ? ["Offer full application packet workflow after approval."]
      : score.recommendation === "worth_20_minutes"
        ? ["Offer lightweight CV review after approval."]
        : ["Stop after explanation unless Ata overrides."];

  return {
    score,
    recommendation: score.recommendation,
    next_actions,
    workflow_status: "paused_before_state_change",
    pause_reason: "Score-only workflow stops here. Approval is required before saving, tailoring follow-up, or ready-to-submit changes.",
    approval_required_before_state_change: requiresApproval("save_application", { status: "ready_to_submit" }),
  };
}
