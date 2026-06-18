import { defineTool } from "eve/tools";
import { z } from "zod";

import { listTailoredExamples } from "../lib/tailored-examples-adapter.js";

export default defineTool({
  description: "List locally parsed tailored CV examples from ApplAI Core, optionally filtered by role label.",
  inputSchema: z.object({
    role_label: z.string().min(1).optional(),
  }),
  async execute(input) {
    return listTailoredExamples(input);
  },
});
