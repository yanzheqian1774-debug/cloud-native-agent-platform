import json
from pathlib import Path

from agent_runtime.providers.openclaw import EXACT_TARGET

ROOT = Path(__file__).parents[2]


def test_operator_image_packages_production_import_closure() -> None:
    dockerfile = (ROOT / "operator" / "Dockerfile").read_text()

    assert "FROM node:22.23.1-bookworm-slim AS openclaw" in dockerfile
    assert "FROM python:3.12-slim-bookworm" in dockerfile
    for source in ("core/src", "gateway/src", "operator/src", "runtime/src"):
        assert f"COPY {source} ./{source}" in dockerfile
    assert "COPY --from=openclaw /opt/openclaw /opt/openclaw" in dockerfile
    assert "COPY operator/tests" not in dockerfile
    assert "COPY runtime/tests" not in dockerfile


def test_operator_image_openclaw_dependency_is_exact_and_integrity_locked() -> None:
    package = json.loads((ROOT / "operator" / "openclaw" / "package.json").read_text())
    lock = json.loads(
        (ROOT / "operator" / "openclaw" / "package-lock.json").read_text()
    )
    locked = lock["packages"]["node_modules/openclaw"]

    assert package["dependencies"] == {"openclaw": EXACT_TARGET.version}
    assert lock["packages"][""]["dependencies"] == package["dependencies"]
    assert locked["version"] == EXACT_TARGET.version
    assert locked["integrity"] == EXACT_TARGET.package_integrity
    assert locked["engines"]["node"] == (">=22.22.3 <23 || >=24.15.0 <25 || >=25.9.0")
