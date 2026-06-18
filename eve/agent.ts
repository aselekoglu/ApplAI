import { defineAgent } from "eve";

export default defineAgent({
  description: "Private ApplAI career manager orchestration agent.",
  model: process.env.EVE_MODEL ?? "openai/gpt-5.4-mini",
});
