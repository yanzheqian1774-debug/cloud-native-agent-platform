import json

import pytest
from agent_console.workbench_static_bundle import pin_frontend


def test_runtime_assets_are_pinned_and_mode_mismatch_fails_closed(tmp_path):
    source = tmp_path / "dist"
    source.mkdir()
    profile = source / "workbench-build-profile.json"
    profile.write_text(
        json.dumps(
            {
                "schemaVersion": "workbench-build-profile.v1",
                "draftAssistance": True,
                "trustedWorkbenchRoutes": True,
            }
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
    profile.write_text(
        json.dumps(
            {
                "schemaVersion": "workbench-build-profile.v1",
                "draftAssistance": True,
                "trustedWorkbenchRoutes": False,
            }
        )
    )
    with pytest.raises(ValueError, match="MODE_MISMATCH"):
        pin_frontend(source, tmp_path / "runtime", assistance_required=True)


@pytest.mark.parametrize(
    "feature",
    [
        "currentWorkDirectory",
        "teamDefinitions",
        "businessCapabilities",
        "businessProcessDefinitions",
    ],
)
@pytest.mark.parametrize("value", [None, False, "true", 1])
def test_required_feature_mismatch_does_not_pin_assets(tmp_path, feature, value):
    source = tmp_path / "dist"
    source.mkdir()
    (source / "index.html").write_text("candidate")
    (source / "workbench-build-profile.json").write_text(
        json.dumps(
            {
                "schemaVersion": "workbench-build-profile.v1",
                feature: value,
            }
        )
    )
    with pytest.raises(ValueError, match="FEATURE_MISMATCH"):
        pin_frontend(
            source,
            tmp_path / "runtime",
            assistance_required=False,
            required_features=(feature,),
        )
    assert not (tmp_path / "runtime").exists()


def test_all_required_features_are_pinned_in_profile(tmp_path):
    source = tmp_path / "dist"
    source.mkdir()
    features = (
        "currentWorkDirectory",
        "teamDefinitions",
        "businessCapabilities",
        "businessProcessDefinitions",
    )
    profile = {
        "schemaVersion": "workbench-build-profile.v1",
        **dict.fromkeys(features, True),
    }
    (source / "index.html").write_text("candidate")
    (source / "workbench-build-profile.json").write_text(json.dumps(profile))
    pinned = pin_frontend(
        source,
        tmp_path / "runtime",
        assistance_required=False,
        required_features=features,
    )
    assert json.loads((pinned / "workbench-build-profile.json").read_text()) == profile
