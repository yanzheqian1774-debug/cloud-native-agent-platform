"""Explicit successor gate; no runtime/model registration or execution."""

import json

import pytest
from agent_console.native_document_resource_bundle import resource_content
from agent_console.native_document_skill import NativeDurableDocumentSkillExecutor
from agent_console.native_typed_document_skill import (
    NativeTypedQuestionDocumentSkillExecutor,
)
from agent_console.native_wait_configuration import (
    DurableWaitConfiguration,
    TypedQuestionWaitConfiguration,
)
from pydantic import ValidationError
from test_native_document_tools import SOURCE


def configuration(typed=False):
    ref = (
        NativeTypedQuestionDocumentSkillExecutor
        if typed
        else NativeDurableDocumentSkillExecutor
    ).revision
    return {
        "schemaVersion": "native-durable-wait.v2"
        if typed
        else "native-durable-wait.v1",
        "enabled": True,
        "executorId": ref.executor_id,
        "executorRevision": ref.executor_revision,
        "executorConfigurationDigest": ref.configuration_digest,
        "nativeRuntimePolicyDigest": "a" * 64,
        "maximumHumanWaitSeconds": 600,
        **({"typedQuestions": True} if typed else {}),
    }


def test_explicit_v2_loader_preserves_v1_and_rejects_mixed_tuple(tmp_path):
    path = tmp_path / "wait.json"
    for typed in (False, True):
        value = configuration(typed)
        path.write_text(json.dumps(value))
        loaded = DurableWaitConfiguration.load(path, "a" * 64)
        assert isinstance(loaded, TypedQuestionWaitConfiguration) is typed
        assert loaded.model_dump() == value
        with pytest.raises(ValueError, match="RUNTIME_BINDING_CHANGED"):
            DurableWaitConfiguration.load(path, "b" * 64)
    for wrong in (
        {**configuration(False), "typedQuestions": True},
        {**configuration(True), "typedQuestions": False},
        {**configuration(True), "executorRevision": "6"},
        {**configuration(False), "executorRevision": "7"},
        {**configuration(True), "executorConfigurationDigest": "b" * 64},
    ):
        path.write_text(json.dumps(wrong))
        with pytest.raises(ValidationError):
            DurableWaitConfiguration.load(path, "a" * 64)


def test_typed_resource_requires_explicit_durable_and_keeps_old_default():
    with pytest.raises(ValueError, match="DURABLE_WAIT_REQUIRED"):
        resource_content(SOURCE, rule_bound=True, typed_questions=True)
    old = resource_content(SOURCE, rule_bound=True, durable_wait=True)
    new = resource_content(
        SOURCE, rule_bound=True, durable_wait=True, typed_questions=True
    )
    assert old != new
    assert resource_content(SOURCE, rule_bound=True, durable_wait=True) == old


@pytest.mark.parametrize("typed", [False, True])
def test_formal_composition_selects_only_configured_successor(
    tmp_path, monkeypatch, typed
):
    from agent_console import prepared_native_composition as composition
    from agent_console.skill_invocation_domain import SkillInvocationError
    from agent_runtime.native_loop import digest

    runtime = tmp_path / "native.json"
    runtime.write_text(json.dumps({"controlled": "runtime-content"}))
    config = configuration(typed)
    config["nativeRuntimePolicyDigest"] = digest(json.loads(runtime.read_text()))
    wait = tmp_path / "wait.json"
    wait.write_text(json.dumps(config))
    selected = (
        NativeTypedQuestionDocumentSkillExecutor
        if typed
        else NativeDurableDocumentSkillExecutor
    )
    other = (
        NativeDurableDocumentSkillExecutor
        if typed
        else NativeTypedQuestionDocumentSkillExecutor
    )

    class RegistryReached(Exception):
        pass

    def capture(_url, _migrations, _none, _policy, registry):
        assert isinstance(registry.resolve(selected.revision), selected)
        with pytest.raises(SkillInvocationError, match="EXECUTOR_REVISION_UNAVAILABLE"):
            registry.resolve(other.revision)
        raise RegistryReached

    monkeypatch.setattr(composition, "compose_governed_skill_invocation", capture)
    with pytest.raises(RegistryReached):
        composition.compose(
            None,
            "unused",
            None,
            None,
            None,
            None,
            native_loop_path=runtime,
            durable_wait_path=wait,
        )
