from copy import deepcopy

import pytest
from agent_core.interface_spine.v0_2 import InternalExecutionEnvelope
from agent_core.representation.v0_2 import (
    AgentDefinitionRef,
    AgentInstanceId,
    NativeCorrelationId,
    PlatformExecutionIdentity,
)
from agent_operator.compatibility_interpreter import (
    ConflictingIdentityEvidenceError,
    InvalidLegacyEvidenceError,
    MissingDefinitionError,
    interpret_legacy_task,
)
from agent_operator.resources import build_workflow_task

TASK_SPEC = {
    "agentRef": {"name": "researcher"},
    "input": {"prompt": "hello"},
}
TASK_META = {
    "name": "task-1",
    "namespace": "workloads",
    "uid": "task-uid-1",
}
AGENT = {
    "apiVersion": "agentos.io/v1alpha1",
    "kind": "Agent",
    "metadata": {
        "name": "researcher",
        "namespace": "workloads",
        "uid": "agent-uid-1",
        "creationTimestamp": "2026-08-24T00:00:00Z",
    },
    "spec": {
        "runtime": {
            "type": "native",
            "image": "enterprise-agent-runtime:v0.1-dev",
        },
        "model": {"provider": "mock", "name": "mock-model"},
    },
}


def interpret(
    *,
    task_spec=TASK_SPEC,
    task_meta=TASK_META,
    candidates=(AGENT,),
) -> InternalExecutionEnvelope:
    return interpret_legacy_task(
        task_spec=deepcopy(task_spec),
        task_metadata=deepcopy(task_meta),
        namespace="workloads",
        agent_candidates=deepcopy(candidates),
    )


def test_legacy_agent_and_task_project_without_public_mutation() -> None:
    task = deepcopy(TASK_SPEC)
    agent = deepcopy(AGENT)
    context = interpret(task_spec=task, candidates=(agent,))
    assert context.definition_ref == AgentDefinitionRef("workloads", "researcher")
    assert context.source_task_ref is not None
    assert context.source_task_ref.name == "task-1"
    assert task == TASK_SPEC
    assert agent == AGENT


def test_namespace_projection_is_preserved() -> None:
    context = interpret()
    assert context.definition_ref.namespace == "workloads"
    assert context.effective_runtime_binding.value.configuration["serviceName"] == (
        "researcher"
    )


def test_definition_name_is_not_reused_as_instance_identity() -> None:
    context = interpret()
    assert isinstance(context.selected_instance_id, AgentInstanceId)
    assert context.selected_instance_id.value != context.definition_ref.name


def test_same_task_replay_recovers_immutable_execution_context() -> None:
    first = interpret()
    second = interpret()
    assert first == second
    assert first.execution_identity is not second.execution_identity
    assert first.execution_identity == second.execution_identity


def test_recreated_task_is_a_new_logical_execution() -> None:
    first = interpret()
    second = interpret(task_meta={**TASK_META, "uid": "task-uid-2"})
    assert first.execution_identity != second.execution_identity
    assert first.selected_instance_id == second.selected_instance_id


def test_replaced_agent_selects_a_new_internal_instance() -> None:
    first = interpret()
    replacement = deepcopy(AGENT)
    replacement["metadata"]["uid"] = "agent-uid-2"
    second = interpret(candidates=(replacement,))
    assert first.selected_instance_id != second.selected_instance_id
    assert first.definition_ref == second.definition_ref


def test_desired_and_effective_runtime_evidence_remain_distinct_typed_values() -> None:
    context = interpret()
    assert context.desired_runtime_binding.value.mode == "native"
    assert context.effective_runtime_binding.value.mode == "native"
    assert context.desired_runtime_binding is not context.effective_runtime_binding


def test_missing_definition_fails_closed() -> None:
    with pytest.raises(MissingDefinitionError):
        interpret(candidates=())


def test_ambiguous_definition_evidence_fails_closed() -> None:
    duplicate = deepcopy(AGENT)
    duplicate["metadata"]["uid"] = "agent-uid-2"
    with pytest.raises(ConflictingIdentityEvidenceError):
        interpret(candidates=(AGENT, duplicate))


@pytest.mark.parametrize(
    "metadata_patch",
    [
        {"name": "other"},
        {"namespace": "other"},
    ],
)
def test_conflicting_namespaced_agent_evidence_is_not_remapped(
    metadata_patch: dict[str, str],
) -> None:
    agent = deepcopy(AGENT)
    agent["metadata"].update(metadata_patch)
    with pytest.raises(ConflictingIdentityEvidenceError):
        interpret(candidates=(agent,))


@pytest.mark.parametrize(
    "mutator",
    [
        lambda agent: agent["metadata"].pop("uid"),
        lambda agent: agent["metadata"].update(
            {"deletionTimestamp": "2026-08-24T01:00:00Z"}
        ),
        lambda agent: agent["spec"].pop("runtime"),
        lambda agent: agent["spec"]["runtime"].update({"type": ""}),
    ],
)
def test_missing_mixed_or_invalid_agent_evidence_fails_closed(mutator) -> None:
    agent = deepcopy(AGENT)
    mutator(agent)
    with pytest.raises(InvalidLegacyEvidenceError):
        interpret(candidates=(agent,))


def test_task_namespace_conflict_fails_closed() -> None:
    with pytest.raises(ConflictingIdentityEvidenceError):
        interpret(task_meta={**TASK_META, "namespace": "other"})


@pytest.mark.parametrize(
    "task_patch",
    [
        {"instanceRef": {"name": "instance-1"}},
        {"executionIdentity": "native-request-1"},
        {"runtimeId": "native-request-1"},
    ],
)
def test_mixed_identity_evidence_fails_without_silent_remap(task_patch) -> None:
    with pytest.raises(ConflictingIdentityEvidenceError):
        interpret(task_spec={**TASK_SPEC, **task_patch})


def test_richer_agent_reference_evidence_fails_without_silent_remap() -> None:
    with pytest.raises(ConflictingIdentityEvidenceError):
        interpret(
            task_spec={
                **TASK_SPEC,
                "agentRef": {"name": "researcher", "uid": "agent-uid-1"},
            }
        )


@pytest.mark.parametrize(
    "task_meta",
    [
        {**TASK_META, "uid": ""},
        {**TASK_META, "uid": NativeCorrelationId("runtime-request-1")},
    ],
)
def test_native_or_missing_id_cannot_substitute_for_platform_execution_identity(
    task_meta,
) -> None:
    with pytest.raises(InvalidLegacyEvidenceError):
        interpret(task_meta=task_meta)


def test_platform_execution_identity_is_typed_and_not_a_native_id() -> None:
    context = interpret()
    assert isinstance(context.execution_identity, PlatformExecutionIdentity)
    assert not isinstance(context.execution_identity, NativeCorrelationId)
    assert context.native_correlations == ()


def test_legacy_runtime_binding_rejects_secret_shaped_mixed_evidence() -> None:
    agent = deepcopy(AGENT)
    agent["spec"]["runtime"]["api_key"] = "must-not-be-imported"
    context = interpret(candidates=(agent,))
    assert "api_key" not in context.desired_runtime_binding.value.configuration


def test_workflow_created_task_enters_same_interpreter_without_wire_change() -> None:
    resource = build_workflow_task(
        workflow_name="workflow-1",
        namespace="workloads",
        task_spec={
            "name": "research",
            "agentRef": {"name": "researcher"},
            "input": {"prompt": "hello"},
        },
    )
    original = deepcopy(resource)
    context = interpret_legacy_task(
        task_spec=resource["spec"],
        task_metadata={
            **resource["metadata"],
            "uid": "workflow-task-uid-1",
        },
        namespace="workloads",
        agent_candidates=[deepcopy(AGENT)],
    )
    assert context.definition_ref == AgentDefinitionRef("workloads", "researcher")
    assert resource == original
    assert "instanceRef" not in resource["spec"]
    assert "executionIdentity" not in resource["spec"]
