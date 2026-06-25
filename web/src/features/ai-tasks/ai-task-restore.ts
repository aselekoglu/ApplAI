import type { AiTaskRecord } from "../../lib/types";

export function canOpenAiTask(task: AiTaskRecord): boolean {
  return task.status === "succeeded" && Boolean(task.restore?.path);
}
