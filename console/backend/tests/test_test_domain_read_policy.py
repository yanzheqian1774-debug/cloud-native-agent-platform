from datetime import UTC, datetime

import pytest
from agent_console.test_resource_read_policy import (
    IsolatedDomainTestReadPolicy,
    TestReadPolicy,
)
from pydantic import ValidationError
from test_test_resource_read_policy import policy


def document():
    return policy().model_dump(mode="json") | dict(
        schemaVersion="test-resource-read-policy.v5",
        testDomainMode="ISOLATED_TEST_DOMAIN",
        shareWithCurrentLocalHumans=True,
        enrolledResources=[dict(kind="employee", logicalId="employee:test")],
        registeredResources=[
            dict(kind="team", mode="CREATOR_ONLY", purpose="TEST_DOMAIN_READ"),
            dict(
                kind="employee",
                mode="ISOLATED_TEST_DOMAIN_SHARE",
                purpose="TEST_DOMAIN_READ",
            ),
        ],
    )


def test_explicit_v5_default_off_and_no_old_fields(tmp_path):
    before = policy()
    old = before.model_dump(mode="json")
    new = IsolatedDomainTestReadPolicy.model_validate(document())
    assert new.enabled is False and "registeredResources" not in old
    path = tmp_path / "policy.json"
    path.write_text(new.model_dump_json())
    assert type(TestReadPolicy.load(path)) is IsolatedDomainTestReadPolicy
    assert TestReadPolicy.model_validate(old).digest == before.digest


@pytest.mark.parametrize(
    "change",
    [
        dict(grantTTLSeconds=3601),
        dict(expiresAt=datetime(2027, 1, 1, tzinfo=UTC)),
        dict(testDomainMode="PRODUCTION"),
        dict(
            registeredResources=[
                dict(
                    kind="knowledge", mode="ISOLATED_TEST_DOMAIN_SHARE", purpose="READ"
                )
            ]
        ),
        dict(
            registeredResources=[
                dict(kind="employee", mode="CREATOR_ONLY", purpose="READ")
            ]
        ),
        dict(
            registeredResources=[dict(kind="team", mode="ANY_CREATOR", purpose="READ")]
        ),
    ],
)
def test_explicit_boundary_rejects(change):
    with pytest.raises(ValidationError):
        IsolatedDomainTestReadPolicy.model_validate(document() | change)


@pytest.mark.parametrize(
    "enrollment",
    [
        [],
        [{"kind": "employee", "logicalId": "*"}],
        [{"kind": "team", "logicalId": "team:wrong-mode"}],
    ],
)
def test_sharing_requires_explicit_kind_and_logical_id(enrollment):
    with pytest.raises(ValidationError):
        IsolatedDomainTestReadPolicy.model_validate(
            document() | {"enrolledResources": enrollment}
        )
