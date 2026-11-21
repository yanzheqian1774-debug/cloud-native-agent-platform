import pytest
from agent_console.test_resource_read_policy import (
    CuratedPublishedTestReadPolicy,
    PublishedMcpTestReadPolicy,
    PublishedTestReadPolicy,
    TestReadPolicy,
)
from pydantic import ValidationError
from test_test_resource_read_policy import policy


def selector(i, kind="employee"):
    return dict(
        kind=kind,
        logicalId=f"{kind}-definition:curated-{i}",
        anchorRevision="published-anchor",
        anchorDigest="a" * 64,
        purpose="RESOURCE_PREPARATION",
    )


def test_v4_explicit_load_and_old_versions_keep_bytes(tmp_path):
    for cls, version in [
        (TestReadPolicy, "v1"),
        (PublishedTestReadPolicy, "v2"),
        (PublishedMcpTestReadPolicy, "v3"),
    ]:
        old = cls.model_validate(
            policy().model_dump(mode="json")
            | {"schemaVersion": f"test-resource-read-policy.{version}"}
        )
        path = tmp_path / "old.json"
        path.write_text(old.model_dump_json())
        loaded = TestReadPolicy.load(path)
        assert type(loaded) is cls
        assert (
            loaded.model_dump(mode="json") == old.model_dump(mode="json")
            and loaded.digest == old.digest
        )
    new = CuratedPublishedTestReadPolicy.model_validate(
        policy().model_dump(mode="json")
        | {
            "schemaVersion": "test-resource-read-policy.v4",
            "publishedResources": [selector(i) for i in range(4)],
        }
    )
    assert new.enabled is False
    path = tmp_path / "new.json"
    path.write_text(new.model_dump_json())
    assert type(TestReadPolicy.load(path)) is CuratedPublishedTestReadPolicy
    assert TestReadPolicy.load(path).digest == new.digest


@pytest.mark.parametrize(
    "cls,version", [(PublishedTestReadPolicy, "v2"), (PublishedMcpTestReadPolicy, "v3")]
)
def test_old_limits_not_relaxed(cls, version):
    with pytest.raises(ValidationError):
        cls.model_validate(
            policy().model_dump(mode="json")
            | {
                "schemaVersion": f"test-resource-read-policy.{version}",
                "publishedResources": [selector(i) for i in range(4)],
            }
        )


@pytest.mark.parametrize(
    "items",
    [
        [selector(i) for i in range(65)],
        [selector(1), selector(1)],
        [selector(1) | {"logicalId": "employee-definition:*"}],
        [selector(1) | {"kind": "knowledge"}],
    ],
)
def test_v4_rejects_unbounded_or_unsupported(items):
    with pytest.raises(ValidationError):
        CuratedPublishedTestReadPolicy.model_validate(
            policy().model_dump(mode="json")
            | {
                "schemaVersion": "test-resource-read-policy.v4",
                "publishedResources": items,
            }
        )
