import { callCoreApi } from "./core-api.js";
import type { TailoredExamplesOutput } from "./contracts.js";

export interface ListTailoredExamplesInput {
  role_label?: string;
}

export async function listTailoredExamples(input: ListTailoredExamplesInput = {}): Promise<TailoredExamplesOutput> {
  const params = new URLSearchParams();
  if (input.role_label) params.set("role_label", input.role_label);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return callCoreApi<TailoredExamplesOutput>(`/tailored-examples${suffix}`);
}
