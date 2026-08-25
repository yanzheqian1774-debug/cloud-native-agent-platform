import json
from pathlib import Path

from agent_runtime.main import app
from agent_runtime.providers.native.compatibility import (
    MANIFEST_PROVIDER_PACKAGE_ID,
    PROVIDER_PACKAGE,
    RUNTIME_TARGET,
)

ROOT = Path(__file__).parents[2]
MANIFEST = (
    ROOT
    / "experiments/s5-spike-005-runtime-target-manifest/fixtures/native-supported.json"
)


def test_candidate_constants_consume_integrated_experimental_manifest() -> None:
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["provider_package_id"] == MANIFEST_PROVIDER_PACKAGE_ID
    assert PROVIDER_PACKAGE.version == manifest["provider_package_version"]
    assert RUNTIME_TARGET.name == manifest["runtime_name"]
    assert RUNTIME_TARGET.exact_version == manifest["runtime_exact_version"]
    assert RUNTIME_TARGET.profile == manifest["runtime_profile"]
    assert manifest["conformance_state"] == "SUPPORTED_CANDIDATE"
    assert manifest["certification_state"] == "NOT_CERTIFIED"


def test_existing_runtime_http_wire_is_unchanged() -> None:
    routes = {
        (route.path, tuple(sorted(route.methods or ())))
        for route in app.routes
        if route.path in {"/healthz", "/readyz", "/v1/info", "/v1/invoke"}
    }
    assert routes == {
        ("/healthz", ("GET",)),
        ("/readyz", ("GET",)),
        ("/v1/info", ("GET",)),
        ("/v1/invoke", ("POST",)),
    }


def test_native_provider_has_no_active_openclaw_or_hermes_import() -> None:
    native_root = ROOT / "runtime/src/agent_runtime/providers/native"
    source = "\n".join(path.read_text() for path in native_root.glob("*.py"))
    assert "agent_runtime.providers.openclaw" not in source
    assert "agent_runtime.providers.hermes" not in source


def test_component_only_has_no_experiments_dependency() -> None:
    runtime_root = ROOT / "runtime/src/agent_runtime"
    native_root = runtime_root / "providers/native"
    native_source = "\n".join(path.read_text() for path in native_root.glob("*.py"))
    consumers = [
        path
        for path in runtime_root.rglob("*.py")
        if native_root not in path.parents
        and (
            "agent_runtime.providers.native" in path.read_text()
            or "NativeRuntimeProvider" in path.read_text()
        )
    ]
    assert "experiments" not in native_source
    assert "manifest_candidate" not in native_source
    assert consumers == []
