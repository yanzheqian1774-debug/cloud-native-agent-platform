"""Source handoff is exact configuration provenance, never execution authority."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from agent_console.business_problem_domain import canonical_bytes
from agent_console.fixed_work_sources_postgres import STRUCTURE, digest
from agent_console.workbench_fixed_work_source import (
    FixedWorkSourceOwner,
    SourceCommand,
    source_operations,
)
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from pydantic import ValidationError


def test_source_routes_default_off_and_exact_team_maintenance_only():
    owner = object()
    assert source_operations(owner) == ()
    operations = source_operations(owner, enabled=True)
    assert [(op.name, op.method) for op in operations] == [
        ("PREPARE_FIXED_WORK_CONVERSATION", "POST"),
        ("READ_FIXED_WORK_SOURCE", "GET"),
        ("BIND_FIXED_WORK_SOURCE", "POST"),
    ]
    for op in operations:
        grants = op.grant_builder(
            None, {"team_id": "t", "team_revision_id": "r"}, {}, {}
        )
        expected = [("TEAM", "READ", "team:t:r")]
        if op.method == "POST":
            expected.append(("TEAM", "REVISE", "team:t:aggregate"))
        assert [(g.owner, g.action, g.exact_resource) for g in grants] == expected


@pytest.mark.parametrize(
    "field", ["subjectId", "target", "enabled", "serviceCredential", "executionId"]
)
def test_client_cannot_supply_authority_or_target(field):
    with pytest.raises(ValidationError):
        SourceCommand.model_validate(
            {
                "conversationId": "c",
                "workDigest": "a" * 64,
                "commandId": "same-key",
                field: "forged",
            }
        )


def test_confirmed_numeric_criterion_digest_survives_json_storage():
    import json

    value = {
        "measurement": {"threshold": 0.75},
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    stored = json.loads(canonical_bytes(value))
    assert digest(value) == digest(stored)
    assert stored["measurement"]["threshold"] == 0.75
    assert len(STRUCTURE) == 3


def test_unknown_operation_rejected_before_owners_or_storage():
    owner = FixedWorkSourceOwner(None, None, None)
    with pytest.raises(WorkbenchOwnerError, match="OPERATION_UNSUPPORTED"):
        owner(SimpleNamespace(operation="START_FIXED_WORK"))


class ModeConnection:
    def __init__(self, present, records):
        self.present, self.records = present, records

    def execute(self, query, params=None):
        if "to_regclass('fixed_work_successions.schema_migrations')" in query:
            return SimpleNamespace(fetchone=lambda: {"relation": None})
        if "to_regclass" in query:
            return SimpleNamespace(
                fetchone=lambda: {"name": "handoffs" if self.present else None}
            )
        assert "conversation_id=%s" in query
        assert params == ("t", "d", "c")
        return SimpleNamespace(fetchall=lambda: self.records)


def test_retained_pause_survives_disabled_new_authoring_without_authority():
    from agent_console.fixed_work_sources_postgres import conversation_mode

    ctx = SimpleNamespace(scope=SimpleNamespace(tenant_id="t", security_domain="d"))
    record = {
        "subjectId": "original-human",
        "work": {"resource_id": "w", "revision_id": "r", "digest": "a" * 64},
        "team": {"teamId": "t", "revisionId": "r", "digest": "b" * 64},
        "conversationId": "c",
        "mode": "TARGET_REVIEW_ONLY",
        "executionEnabled": False,
    }
    assert conversation_mode(ModeConnection(False, []), ctx, "c") is None
    assert conversation_mode(ModeConnection(True, []), ctx, "c") is None
    proof = {"record": record, "digest": digest(record)}
    assert conversation_mode(ModeConnection(True, [proof]), ctx, "c") == {
        "mode": "TARGET_REVIEW_ONLY",
        "handoffDigest": proof["digest"],
        "work": record["work"],
        "team": record["team"],
    }
    # Existing conversation UI pause only; no credential or grant reader.
    for bad in (
        [proof, proof],
        [{**proof, "digest": "f" * 64}],
        [
            {
                "record": {**record, "executionEnabled": True},
                "digest": digest({**record, "executionEnabled": True}),
            }
        ],
    ):
        with pytest.raises(WorkbenchOwnerError):
            conversation_mode(ModeConnection(True, bad), ctx, "c")


def test_dedicated_database_mode_rejects_other_databases_before_connect(monkeypatch):
    from fixed_work_dedicated_database import NAME, selected

    monkeypatch.delenv("FIXED_WORK_DEDICATED_DATABASE", raising=False)
    assert selected("not interpreted unless explicitly selected") is None
    monkeypatch.setenv("FIXED_WORK_DEDICATED_DATABASE", NAME)
    safe = f"postgresql://postgres:test@127.0.0.1:53428/{NAME}"
    assert selected(safe) == NAME
    for unsafe in (
        safe.replace(NAME, "postgres"),
        safe.replace("53428", "64330"),
        safe.replace("127.0.0.1", "remote.invalid"),
        safe.replace("postgres:test", "other:test"),
    ):
        with pytest.raises(AssertionError):
            selected(unsafe)
