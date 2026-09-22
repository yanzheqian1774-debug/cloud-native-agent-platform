import json

import pytest
from agent_console.workbench_static_bundle import pin_frontend


def test_runtime_assets_are_pinned_and_mode_mismatch_fails_closed(tmp_path):
    source = tmp_path / "dist"
    source.mkdir()
    profile = source / "workbench-build-profile.json"
    profile.write_text(
        json.dumps(
            {"schemaVersion": "workbench-build-profile.v1", "draftAssistance": True}
        )
    )
    (source / "index.html").write_text("assisted original")
    pinned = pin_frontend(source, tmp_path / "runtime", assistance_required=True)
    assert (
        pin_frontend(source, tmp_path / "runtime", assistance_required=True) == pinned
    )
    (source / "index.html").write_text("a later test build")
    assert (pinned / "index.html").read_text() == "assisted original"
    profile.write_text(
        json.dumps(
            {"schemaVersion": "workbench-build-profile.v1", "draftAssistance": False}
        )
    )
    with pytest.raises(ValueError, match="MODE_MISMATCH"):
        pin_frontend(source, tmp_path / "runtime", assistance_required=True)
