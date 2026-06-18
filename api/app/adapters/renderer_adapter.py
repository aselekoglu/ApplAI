from __future__ import annotations

from typing import Any, Dict

import agent_workflow

from artifact_export import compile_result_artifacts


def render_run_artifacts(result: agent_workflow.WorkflowResult, workflow_inputs: Dict[str, Any]) -> Dict[str, Any]:
    return compile_result_artifacts(result, workflow_inputs)
