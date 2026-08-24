from datetime import UTC, datetime

import pytest
from agent_core.representation.v0_2 import (
    AgentDefinitionRef,
    AgentInstance,
    AgentInstanceId,
    AgentInstanceLifecycle,
    DesiredRuntimeBinding,
    RuntimeBinding,
)


@pytest.fixture
def timestamp() -> datetime:
    return datetime(2026, 8, 24, tzinfo=UTC)


@pytest.fixture
def definition_ref() -> AgentDefinitionRef:
    return AgentDefinitionRef(namespace="default", name="researcher")


@pytest.fixture
def desired_binding() -> DesiredRuntimeBinding:
    return DesiredRuntimeBinding(
        RuntimeBinding(
            binding_id="binding/researcher",
            provider_ref="runtime-provider/default",
            mode="MANAGED",
            configuration={"profile": "standard"},
        )
    )


@pytest.fixture
def make_instance(definition_ref, desired_binding, timestamp):
    def factory(value: str = "instance-001") -> AgentInstance:
        return AgentInstance(
            instance_id=AgentInstanceId(value),
            definition_ref=definition_ref,
            lifecycle=AgentInstanceLifecycle.ACTIVE,
            desired_runtime_binding=desired_binding,
            created_at=timestamp,
            updated_at=timestamp,
        )

    return factory
