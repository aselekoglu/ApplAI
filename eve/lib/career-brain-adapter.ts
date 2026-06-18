import { callCoreApi } from "./core-api.js";
import type { CareerBrainProfile } from "./contracts.js";

export async function readCareerBrain(): Promise<CareerBrainProfile> {
  return callCoreApi<CareerBrainProfile>("/career-brain");
}
