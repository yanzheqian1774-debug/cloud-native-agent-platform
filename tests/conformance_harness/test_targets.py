from pathlib import Path


def test_production_code_does_not_import_conformance_harness() -> None:
    repository = Path(__file__).parents[2]
    production_roots = [
        "core/src",
        "gateway/src",
        "operator/src",
        "runtime/src",
        "console/backend/src",
    ]
    offenders = []
    for relative_root in production_roots:
        for source in (repository / relative_root).rglob("*.py"):
            if "conformance_harness" in source.read_text(encoding="utf-8"):
                offenders.append(source.relative_to(repository).as_posix())
    assert offenders == []


def test_component_specific_identity_types_remain_distinct() -> None:
    from agent_core.representation.v0_2 import (
        AgentInstanceId,
        NativeCorrelationId,
        PlatformExecutionIdentity,
    )

    execution = PlatformExecutionIdentity("same-text")
    instance = AgentInstanceId("same-text")
    native = NativeCorrelationId("same-text")
    assert type(execution) is not type(instance)
    assert type(execution) is not type(native)
    assert type(instance) is not type(native)
