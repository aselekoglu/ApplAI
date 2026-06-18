import { defineTool } from "eve/tools";
import { z } from "zod";

export default defineTool({
  description: "Record an explicit human approval decision for an artifact. This is a contract scaffold until Core approval storage exists.",
  inputSchema: z.object({
    artifact_id: z.string().min(1),
    decision: z.enum(["approved", "rejected", "needs_changes"]),
    notes: z.string().optional(),
  }),
  needsApproval: () => true,
  async execute(input) {
    throw new Error(`Approval event storage is not exposed yet for artifact ${input.artifact_id}.`);
  },
});
