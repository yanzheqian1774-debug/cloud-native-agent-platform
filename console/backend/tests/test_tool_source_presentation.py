from datetime import UTC, datetime
from types import SimpleNamespace as NS

import pytest
from agent_console.execution_domain import ScopeIdentity, record_digest
from agent_console.tool_source_journal import SourceJournal
from agent_console.tool_source_presentation import read_source_presentation
from psycopg.types.json import Jsonb
from test_tool_source_execution import owner as owner
from test_tool_source_execution import package


@pytest.mark.parametrize(
    "status,reason", [("UNKNOWN", None), ("FAILED", "TOOL_SOURCE_OUTPUT_INVALID")]
)
def test_historical_basis_and_latest_source_failure_are_separate(status, reason):
    now = datetime(2026, 11, 28, tzinfo=UTC)
    basis = dict(
        command_key="basis",
        revision_id="rev",
        digest="a" * 64,
        source_digest="b" * 64,
        started_at=now,
        recorded_at=now,
        status="FAILED",
        reason_code="TOOL_SOURCE_EXPECTATION_MISMATCH",
        runtime="known",
        runtime_revision="1",
        actual_execution=True,
        source_invoked=True,
        verification_level="ISOLATED_EXACT_TOOL_SOURCE_EXECUTION",
    )
    latest = dict(
        basis,
        command_key="latest",
        status=status,
        reason_code=reason,
        recorded_at=None if status == "UNKNOWN" else now,
        runtime=None if status == "UNKNOWN" else "known",
        runtime_revision=None if status == "UNKNOWN" else "1",
    )
    queries = []
    rows = iter([{"requests": "requests", "facts": "facts"}, basis, latest])

    class Connection:
        def execute(self, sql, params=None):
            queries.append((sql, params))
            return NS(fetchone=lambda: next(rows))

    current = dict(
        toolId="tool", revisionId="rev", digest="a" * 64, sourceDigest="b" * 64
    )
    summary = read_source_presentation(
        Connection(),
        NS(namespace="tenant", security_domain="domain"),
        current,
        {"runtimeEvidence": {"commandKey": "basis"}},
        "actor",
    )
    assert summary["basis"]["expectationMismatch"] is True
    assert summary["basis"]["status"] == "FAILED"
    assert summary["latest"]["status"] == status
    assert summary["latest"]["expectationMismatch"] is False
    assert summary["latest"]["recordedAt"] == (
        None if status == "UNKNOWN" else now.isoformat()
    )
    assert (
        summary["currentAvailability"] == summary["allTestsPassed"] == "NOT_ESTABLISHED"
    )
    assert summary["executionAuthorized"] is False
    for sql, params in queries[1:]:
        assert params[:7] == (
            "tenant",
            "domain",
            "actor",
            "tool",
            "rev",
            "a" * 64,
            "b" * 64,
        )
        assert "DISPATCH_CLAIM" in sql and "source_test_requests" in sql
        assert "->'actual'" not in sql and "->'input'" not in sql
    assert queries[1][1][-2:] == ("basis", "basis")
    assert queries[2][1][-2:] == (None, None)


def test_optional_source_tables_absent_is_not_a_fake_result():
    class Connection:
        def execute(self, sql):
            assert "to_regclass" in sql
            return NS(fetchone=lambda: {"requests": None, "facts": None})

    assert read_source_presentation(Connection(), None, None, None, "actor") is None


# The following two cases execute only metadata SQL on a random isolated DB.
# Seeded result metadata represents owner records; no code/runtime is invoked.
def _metadata_tool(owner):
    scope = ScopeIdentity("presentation-synthetic", "isolated")
    with owner.pool.connection() as c, c.transaction():
        item = owner.import_drafts(
            c,
            scope,
            "PLUGIN_ZIP",
            package(),
            ["sum"],
            {},
            effects={"sum": "read-only"},
            command_id="import:presentation",
            actor_id="human:presenter",
            decision_id="synthetic:metadata",
        )["items"][0]
        current = owner.read(c, scope, item["toolId"], item["revisionId"])
    return scope, current


def _metadata_context(scope, actor="human:presenter"):
    return NS(
        scope=NS(tenant_id=scope.namespace, security_domain=scope.security_domain),
        principal_id=actor,
    )


def _seed_attempt(owner, scope, current, key, result=None, actor="human:presenter"):
    context = _metadata_context(scope, actor)
    request = {
        "toolId": current["toolId"],
        "revisionId": current["revisionId"],
        "digest": current["digest"],
        "sourceDigest": current["sourceDigest"],
        "command": {
            "input": {"private": "INPUT_SECRET_SENTINEL"},
            "expectedOutput": {"private": "EXPECTED_SECRET_SENTINEL"},
        },
    }
    journal = SourceJournal(owner.pool)
    fresh, _ = journal.claim(context, key, "f" * 64, request, 20)
    assert fresh
    if result is not None:
        journal.finish(context, key, result)
    return context


def _metadata_result(status="FAILED", reason="TOOL_SOURCE_EXPECTATION_MISMATCH"):
    return {
        "status": status,
        "reasonCode": reason,
        "actualExecution": True,
        "toolSourceInvoked": True,
        "verificationLevel": "ISOLATED_EXACT_TOOL_SOURCE_EXECUTION",
        "actual": {"private": "ACTUAL_SECRET_SENTINEL"},
        "sourceExecution": {
            "runtime": "reviewed-python-function.v1",
            "runtimeRevision": "synthetic-reviewed-1",
            "private": "EXECUTION_SECRET_SENTINEL",
        },
        "policyMaterial": "POLICY_SECRET_SENTINEL",
    }


def _summary(owner, scope, current, resolution=None, actor="human:presenter"):
    with owner.pool.connection() as c, c.transaction():
        c.execute("SET TRANSACTION READ ONLY")
        return read_source_presentation(c, scope, current, resolution, actor)


def test_actual_pg_summary_keeps_basis_latest_nulls_times_and_exact_actor_tuple(owner):
    import json

    scope, current = _metadata_tool(owner)
    _seed_attempt(owner, scope, current, "basis", _metadata_result())
    _seed_attempt(owner, scope, current, "pending")
    resolution = {"runtimeEvidence": {"commandKey": "basis"}}
    first = _summary(owner, scope, current, resolution)
    assert first["basis"]["status"] == "FAILED"
    assert first["basis"]["expectationMismatch"] is True
    assert first["latest"]["status"] == "UNKNOWN"
    assert first["latest"]["recordedAt"] is None
    assert first["latest"]["runtime"] is None
    assert first["latest"]["reasonCode"] is None
    with owner.pool.connection() as c:
        times = {
            r["command_key"]: r
            for r in c.execute(
                "SELECT r.command_key,r.created_at,f.recorded_at FROM "
                "tool_definition.source_test_requests r LEFT JOIN "
                "tool_definition.source_test_facts f ON "
                "(r.namespace,r.security_domain,r.subject_id,r.command_key)="
                "(f.namespace,f.security_domain,f.subject_id,f.command_key) "
                "AND f.kind='RESULT' WHERE r.command_key IN ('basis','pending')"
            ).fetchall()
        }
    assert first["basis"]["startedAt"] == times["basis"]["created_at"].isoformat()
    assert first["basis"]["recordedAt"] == times["basis"]["recorded_at"].isoformat()
    assert first["latest"]["startedAt"] == times["pending"]["created_at"].isoformat()
    SourceJournal(owner.pool).finish(
        _metadata_context(scope),
        "pending",
        {
            "status": "UNKNOWN",
            "reasonCode": "TOOL_SOURCE_OUTCOME_UNKNOWN",
            "actual": None,
        },
    )
    terminal = _summary(owner, scope, current, resolution)
    assert terminal["latest"]["recordedAt"] is not None
    assert terminal["latest"]["status"] == "UNKNOWN"
    assert terminal["basis"] == first["basis"]
    _seed_attempt(
        owner,
        scope,
        current,
        "latest-invalid",
        _metadata_result(reason="TOOL_SOURCE_OUTPUT_INVALID"),
    )
    invalid = _summary(owner, scope, current, resolution)
    assert invalid["latest"]["reasonCode"] == "TOOL_SOURCE_OUTPUT_INVALID"
    assert invalid["latest"]["recordedAt"] is not None
    assert invalid["latest"]["expectationMismatch"] is False
    assert invalid["basis"] == first["basis"]
    # All these rows are newer, but none belongs to the exact display key.
    _seed_attempt(
        owner,
        scope,
        current,
        "foreign-actor",
        _metadata_result(status="PASSED"),
        actor="human:other",
    )
    for field, value in (
        ("toolId", "tool:other"),
        ("revisionId", "revision:other"),
        ("digest", "0" * 64),
        ("sourceDigest", "0" * 64),
    ):
        _seed_attempt(
            owner,
            scope,
            {**current, field: value},
            "wrong-" + field,
            _metadata_result(status="PASSED"),
        )
    for foreign in (
        ScopeIdentity("other-namespace", scope.security_domain),
        ScopeIdentity(scope.namespace, "other-domain"),
    ):
        _seed_attempt(
            owner, foreign, current, "foreign-scope", _metadata_result(status="PASSED")
        )
    assert _summary(owner, scope, current, resolution) == invalid
    wrong_actor_basis = _summary(
        owner, scope, current, {"runtimeEvidence": {"commandKey": "foreign-actor"}}
    )
    assert wrong_actor_basis["basis"] is None
    assert wrong_actor_basis["latest"] == invalid["latest"]
    assert (
        invalid["currentAvailability"] == invalid["allTestsPassed"] == "NOT_ESTABLISHED"
    )
    assert invalid["executionAuthorized"] is False
    for value in (first, terminal, invalid, wrong_actor_basis):
        rendered = json.dumps(value)
        for secret in (
            "INPUT_SECRET_SENTINEL",
            "EXPECTED_SECRET_SENTINEL",
            "ACTUAL_SECRET_SENTINEL",
            "EXECUTION_SECRET_SENTINEL",
            "POLICY_SECRET_SENTINEL",
        ):
            assert secret not in rendered
    assert set(invalid["latest"]) == {
        "commandKey",
        "revisionId",
        "digest",
        "sourceDigest",
        "startedAt",
        "recordedAt",
        "status",
        "reasonCode",
        "runtime",
        "runtimeRevision",
        "expectationMismatch",
    }


def test_actual_pg_old_mapping_is_not_source_and_missing_tables_read_safely(owner):
    scope, current = _metadata_tool(owner)
    mapping = {
        "commandKind": "TEST",
        "items": [
            {
                "toolId": current["toolId"],
                "revisionId": current["revisionId"],
                "digest": current["digest"],
            }
        ],
        "testResult": {
            "status": "PASSED",
            "actualExecution": True,
            "toolSourceInvoked": False,
            "verificationLevel": "ISOLATED_REGISTERED_SKILL_COMPUTATION",
            "actual": {"private": "OLD_MAPPING_SECRET"},
        },
    }
    with owner.pool.connection() as c, c.transaction():
        c.execute(
            "INSERT INTO tool_definition.receipts(namespace,security_domain,"
            "command_id,actor_id,decision_id,payload_digest,result) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                scope.namespace,
                scope.security_domain,
                "legacy-mapping",
                "human:presenter",
                "synthetic:metadata",
                record_digest(mapping),
                Jsonb(mapping),
            ),
        )
    resolution = {"runtimeEvidence": {"commandKey": "legacy-mapping"}}
    empty = _summary(owner, scope, current, resolution)
    assert empty["basis"] is None and empty["latest"] is None
    with owner.pool.connection() as c, c.transaction():
        c.execute("DROP TABLE tool_definition.source_test_facts")
    assert _summary(owner, scope, current, resolution) is None
    with owner.pool.connection() as c, c.transaction():
        c.execute("DROP TABLE tool_definition.source_test_requests")
    assert _summary(owner, scope, current, resolution) is None
    with owner.pool.connection() as c:
        assert c.execute(
            "SELECT to_regclass('tool_definition.source_test_requests') requests,"
            "to_regclass('tool_definition.source_test_facts') facts"
        ).fetchone() == {"requests": None, "facts": None}
        assert (
            c.execute(
                "SELECT result FROM tool_definition.receipts "
                "WHERE command_id='legacy-mapping'"
            ).fetchone()["result"]
            == mapping
        )
