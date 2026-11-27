"""Actual composition registration; DB/model builder ports explicitly controlled."""

import json
from types import SimpleNamespace as NS

import pytest
from agent_console import native_loop_runtime, prepared_native_composition
from agent_console.native_data_adapters import ADAPTERS
from agent_console.native_data_skill import NativeDataSkillExecutor
from agent_console.skill_invocation_domain import SkillInvocationError


@pytest.mark.parametrize("enabled", [False, True])
def test_original_composer_registers_only_explicit_exact_adapter(
    tmp_path, monkeypatch, enabled
):
    config = tmp_path / "native.json"
    config.write_text(
        json.dumps(
            {"nativeDataAdapters": [ADAPTERS[1].descriptor()]} if enabled else {}
        )
    )
    captured = {}

    def skills(*args):
        captured["registry"] = args[4]
        return NS(invocation_repository=object(), closeables=())

    calls = []
    runtime = NS(
        subject="human:original",
        run=lambda *args: calls.append(args) or {"status": "SUCCEEDED"},
    )
    monkeypatch.setattr(
        prepared_native_composition, "compose_governed_skill_invocation", skills
    )
    monkeypatch.setattr(
        native_loop_runtime, "NativeLoopRuntime", lambda *args, **kwargs: runtime
    )
    caller, _ = prepared_native_composition.compose(
        None,
        None,
        None,
        None,
        NS(policy_version="p"),
        lambda *_: True,
        native_loop_path=config,
    )
    assert caller.runtime is runtime
    expected = NativeDataSkillExecutor(ADAPTERS[1])
    if not enabled:
        with pytest.raises(SkillInvocationError, match="EXECUTOR_REVISION_UNAVAILABLE"):
            captured["registry"].resolve(expected.revision)
    else:
        executor = captured["registry"].resolve(expected.revision)
        assert executor.adapter == ADAPTERS[1]
        executor.runner("invocation", {"source": "test"}, 123)
        assert calls == [("invocation", {"source": "test"}, 123)]
        with pytest.raises(SkillInvocationError, match="EXECUTOR_REVISION_UNAVAILABLE"):
            captured["registry"].resolve(NativeDataSkillExecutor(ADAPTERS[0]).revision)
