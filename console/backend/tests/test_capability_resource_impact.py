"""Capability projection permission and failure boundaries; no execution."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.business_capability_postgres import (
    PostgresBusinessCapabilityRepository,
)
from agent_console.resource_dependency_impact import capability_nodes
from agent_console.workbench_business_problem import OwnerPrincipal
from test_business_capability import capability


class Connection:
    def __init__(self, rows, available=True):
        self.rows, self.available = rows, available

    def execute(self, sql, params=None):
        if "to_regclass" in sql:
            return SimpleNamespace(fetchone=lambda: {"value": self.available})
        assert "r.namespace=%s AND r.security_domain=%s" in sql
        assert params == ("tenant:test", "isolated")
        return SimpleNamespace(fetchall=lambda: self.rows)


def test_exact_versions_authorization_and_state(monkeypatch):
    base = capability()
    revisions = [
        "revision:old",
        "revision:published",
        "revision:draft",
        "revision:hidden",
    ]
    rows = [
        dict(
            capability_id=base.capability_id,
            revision_id=r,
            head_revision_id=revisions[2],
            published_revision_id=revisions[1],
        )
        for r in revisions
    ]
    reads, checks = [], []

    class Authority:
        def require(self, principal, owner, action, target):
            checks.append((owner, action, target))
            if target.endswith("revision:hidden"):
                raise AuthorityError("READ_DENIED")

    def read(conn, scope, identity, revision):
        reads.append(revision)
        return replace(base, revision_id=revision)

    monkeypatch.setattr(PostgresBusinessCapabilityRepository, "read", read)
    p, limits = OwnerPrincipal("human:test", "tenant:test", "isolated"), []
    result = capability_nodes(
        SimpleNamespace(connection=Connection(rows), authority=Authority()), p, limits
    )
    assert [r["state"] for r in result] == ["HISTORICAL_REVISION", "PUBLISHED", "DRAFT"]
    assert reads == revisions[:3]
    assert len(checks) == 4 and all(
        c[:2] == ("BUSINESS_CAPABILITY", "READ") for c in checks
    )
    assert all(r["references"][1]["identity"] == "skill:test" for r in result)
    assert "revision:hidden" not in str(result)
    assert not limits


def test_missing_owner_is_explicit():
    p, limits = OwnerPrincipal("human:test", "tenant:test", "isolated"), []
    assert (
        capability_nodes(SimpleNamespace(connection=Connection([], False)), p, limits)
        == []
    )
    assert limits == ["BUSINESS_CAPABILITY_OWNER_UNAVAILABLE"]


def test_corrupt_revision_does_not_become_no_impact(monkeypatch):
    row = dict(
        capability_id="cap:test",
        revision_id="rev:test",
        head_revision_id="rev:test",
        published_revision_id=None,
    )

    def fail(*args):
        raise ValueError("CAPABILITY_RECORD_CORRUPT")

    monkeypatch.setattr(PostgresBusinessCapabilityRepository, "read", fail)
    call = SimpleNamespace(
        connection=Connection([row]), authority=SimpleNamespace(require=lambda *a: None)
    )
    with pytest.raises(ValueError, match="CAPABILITY_RECORD_CORRUPT"):
        capability_nodes(
            call, OwnerPrincipal("human:test", "tenant:test", "isolated"), []
        )


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("employee_digest", ["b" * 64, "c" * 64, None])
def test_indirect_binding_checks_every_hop_and_is_order_independent(
    reverse, employee_digest
):
    from agent_console.resource_dependency_impact import incoming_references

    root = {"revisionId": "skill:1", "digest": "a" * 64}
    employee = dict(
        kind="EMPLOYEE",
        identity="employee:1",
        revision="employee-rev:1",
        digest="b" * 64,
        name="Employee",
        state="SAVED_REVISION",
        references=[dict(identity="skill:test", revision="skill:1", digest="a" * 64)],
    )
    capability = dict(
        kind="BUSINESS_CAPABILITY",
        identity="cap:1",
        revision="cap-rev:1",
        digest="d" * 64,
        name="Capability",
        state="PUBLISHED",
        references=[
            dict(
                identity="employee:1", revision="employee-rev:1", digest=employee_digest
            )
        ],
    )
    nodes = [capability, employee] if reverse else [employee, capability]
    result = incoming_references(nodes, "skill:test", [root], root)
    row = next(x for x in result if x["kind"] == "BUSINESS_CAPABILITY")
    assert row["distance"] == 2 and row["via"]["identity"] == "employee:1"
    expected = (
        "CURRENT_VERSION"
        if employee_digest == "b" * 64
        else "DIGEST_MISMATCH"
        if employee_digest
        else "DIGEST_UNVERIFIED"
    )
    assert row["versionRelation"] == expected
    assert row["automaticUpgrade"] is False
    # Explicit direct binding wins over the indirect route, regardless of node order.
    capability["references"].append(
        dict(identity="skill:test", revision="skill:1", digest="a" * 64)
    )
    row = next(
        x
        for x in incoming_references(nodes, "skill:test", [root], root)
        if x["kind"] == "BUSINESS_CAPABILITY"
    )
    assert row["distance"] == 1 and row["versionRelation"] == "CURRENT_VERSION"
    # A fixed old-version root never substitutes a newer revision.
    old = {"revisionId": "skill:old", "digest": "e" * 64}
    assert incoming_references(nodes, "skill:test", [old], old) == []
