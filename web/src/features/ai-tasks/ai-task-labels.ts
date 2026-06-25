import type { AiTaskKind, AiTaskRecord, AiTaskStatus } from "../../lib/types";

export const AI_TASK_KIND_LABELS: Record<AiTaskKind, string> = {
  score_job: "Score job",
  tailor_cv: "Tailor CV",
  render_cv: "Render CV",
  rerun_tailoring: "Rerun tailoring",
  gemini_interaction: "Gemini interaction",
};

export const AI_TASK_STATUS_LABELS: Record<AiTaskStatus, string> = {
  queued: "Queued",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
  cancelled: "Cancelled",
};

export const AI_TASK_ACTIVE_STATUSES: AiTaskStatus[] = ["queued", "running"];

export function isAiTaskActive(task: AiTaskRecord): boolean {
  return AI_TASK_ACTIVE_STATUSES.includes(task.status);
}
