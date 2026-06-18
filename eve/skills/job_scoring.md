---
description: Use before scoring job descriptions or explaining job fit.
---

# Job Scoring

Use the `score_job` tool for pasted job descriptions. The tool calls ApplAI Core and returns:

- `match_score`
- `recommendation`: `apply`, `skip`, or `worth_20_minutes`
- reasons, concerns, missing keywords, and evidence block ids

If the recommendation is `skip`, stop after the explanation unless Ata overrides. If it is `worth_20_minutes`, offer a lightweight draft. If it is `apply`, offer the full application packet workflow. Any transition into saving non-draft state or preparing submission requires approval.
