import { defineTool } from "eve/tools";
import { z } from "zod";

import { readCareerBrain } from "../lib/career-brain-adapter.js";

export default defineTool({
  description: "Read Ata's local Career Brain profile from ApplAI Core.",
  inputSchema: z.object({}),
  async execute() {
    return readCareerBrain();
  },
});
