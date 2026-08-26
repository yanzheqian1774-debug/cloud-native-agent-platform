import tomllib
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


def test_pytest_discovery_uses_narrow_harness_source_path() -> None:
    repository = Path(__file__).parents[2]
    configuration = tomllib.loads(
        (repository / "pyproject.toml").read_text(encoding="utf-8")
    )["tool"]["pytest"]["ini_options"]
    assert configuration["pythonpath"][0] == "conformance_harness/src"
    assert "." not in configuration["pythonpath"]
    assert configuration["testpaths"] == [
        "core/tests",
        "tests",
        "gateway/tests",
        "operator/tests",
        "runtime/tests",
        "workflow/tests",
        "console/backend/tests",
        "experiments/s5-spike-005-runtime-target-manifest/tests",
        "experiments/s5-spike-007-capability-rest-fixtures/tests",
    ]


def test_harness_owns_no_kubernetes_controller_or_provider_implementation() -> None:
    repository = Path(__file__).parents[2]
    harness_root = repository / "conformance_harness" / "src" / "conformance_harness"
    prohibited_names = {"controller.py", "provider.py", "crd.py", "schema.py"}
    assert not prohibited_names.intersection(
        source.name for source in harness_root.rglob("*.py")
    )
