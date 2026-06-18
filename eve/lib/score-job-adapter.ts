import { callCoreApi } from "./core-api.js";
import type { ScoreJobInput, ScoreJobOutput } from "./contracts.js";

export async function scoreJob(input: ScoreJobInput): Promise<ScoreJobOutput> {
  return callCoreApi<ScoreJobOutput>("/jobs/score", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}
