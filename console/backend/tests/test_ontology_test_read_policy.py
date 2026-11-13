from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityScope
from agent_console.test_resource_read_access import snapshot_matches
from agent_console.test_resource_read_policy import TestReadTarget
from pydantic import ValidationError


def target(**changes):
    return TestReadTarget.model_validate(
        dict(
            owner="BUSINESS_ONTOLOGY",
            action="READ",
            resource="business-ontology:document:r1",
            digest="a" * 64,
            purpose="TEST_RESOURCE_READ",
        )
        | changes
    )


def test_exact_ontology_collection_and_revision_only():
    target()
    target(action="LIST", resource="business-ontology:collection", digest=None)
    for changes in (
        {"digest": None},
        {"action": "LIST", "resource": "business-ontology:foreign", "digest": None},
        {"action": "LIST", "resource": "business-ontology:collection"},
    ):
        with pytest.raises(ValidationError):
            target(**changes)


@pytest.mark.parametrize("action", ["USE", "CREATE", "REVISE", "TEST", "PUBLISH"])
def test_ontology_read_policy_never_grants_execution_or_maintenance(action):
    with pytest.raises(ValidationError, match="WRITE_FORBIDDEN"):
        target(action=action)


@pytest.mark.parametrize(
    ("row", "matches"),
    [({"digest": "a" * 64}, True), ({"digest": "b" * 64}, False), (None, False)],
)
def test_ontology_snapshot_is_exact_and_scoped(row, matches):
    class Connection:
        def execute(self, sql, parameters):
            assert "business_ontology.revisions" in sql
            assert "namespace=%s AND security_domain=%s" in sql
            assert "ontology_id || ':' || revision_id" in sql
            assert parameters == (
                "test",
                "isolated",
                "business-ontology:",
                "business-ontology:document:r1",
            )
            return SimpleNamespace(fetchone=lambda: row)

    context = SimpleNamespace(scope=AuthorityScope("test", "isolated"))
    assert snapshot_matches(Connection(), context, target()) is matches
