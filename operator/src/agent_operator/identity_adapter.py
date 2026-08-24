"""Component-only adapter from the current Task target to the A2 spine.

This module is deliberately not imported by ``task_controller``. Activating it
requires later reconciliation/idempotency integration ownership.
"""

from typing import Any

from agent_core.interface_spine.v0_2 import DefinitionFacingRequest
from agent_core.representation.v0_2 import DesiredRuntimeBinding


def adapt_task_target(
    *,
    task_spec: dict[str, Any],
    task_name: str,
    namespace: str,
    desired_runtime_binding: DesiredRuntimeBinding,
) -> DefinitionFacingRequest:
    """Map unchanged ``Task.spec.agentRef.name`` into an internal request."""
    agent_ref = task_spec.get("agentRef")
    if not isinstance(agent_ref, dict):
        raise ValueError("Task agentRef must be an object")
    agent_name = agent_ref.get("name")
    if not isinstance(agent_name, str) or not agent_name.strip():
        raise ValueError("Task agentRef.name must be a non-empty string")
    return DefinitionFacingRequest(
        namespace=namespace,
        agent_name=agent_name,
        desired_runtime_binding=desired_runtime_binding,
        source_task_name=task_name,
    )
