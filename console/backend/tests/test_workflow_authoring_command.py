"""Trusted commands reject ambiguous intent before entering a write transaction."""

import pytest
from agent_console.workflow_authoring import WorkflowAuthoringCommand
from pydantic import ValidationError

CONTENT = {
    "tasks": [{"taskId": "one", "name": "检查"}],
    "runtimeProfile": {
        "kind": "RUNTIME_PROFILE",
        "resourceId": "runtime:one",
        "revisionId": "runtime:v1",
        "digest": "a" * 64,
    },
}


@pytest.mark.parametrize(
    "patch",
    [
        {"name": " "},
        {"workflowId": "unexpected"},
        {"expectedVersion": 1},
        {"content": None},
        {"reason": "unexpected"},
        {
            "content": {
                **CONTENT,
                "runtimeProfile": {**CONTENT["runtimeProfile"], "kind": "SKILL"},
            }
        },
    ],
)
def test_create_rejects_ambiguous_or_non_runtime_fields(patch):
    with pytest.raises(ValidationError):
        WorkflowAuthoringCommand.model_validate(
            {
                "action": "create",
                "commandKey": "one",
                "name": "检查流程",
                "content": CONTENT,
                **patch,
            }
        )


@pytest.mark.parametrize(
    "action", ["edit", "validate", "review", "publish", "successor"]
)
def test_mutation_requires_explicit_aggregate_version(action):
    with pytest.raises(ValidationError):
        WorkflowAuthoringCommand.model_validate(
            {"action": action, "commandKey": "one", "workflowId": "workflow:one"}
        )
