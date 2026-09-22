"""D324-7 isolated owner and database tests; no deployment signature or traffic."""

import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError, ExactGrant
from agent_console.bounded_task_authorization import BoundedTaskAuthorization
from agent_console.bounded_task_policy import (
    ConfigurationRevision,
    TaskAuthorizationRequest,
    TaskPermission,
    TaskSignature,
    require_configuration,
    require_scope,
)
from agent_console.business_problem_domain import BusinessProblemRevision
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.execution_domain import ScopeIdentity
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.planning_call_admission import PlanningCallAdmission
from pydantic import ValidationError
from test_context_call_admission import ROOT, env, setup  # noqa: F401


def test_task_window_and_cross_scope_rejected():
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        TaskSignature(
            request_digest="a" * 64,
            idempotency_key="a",
            not_before=now,
            expires_at=now + timedelta(hours=9),
        )
    with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
        require_scope(
            "ISOLATED_NATIVE_VALIDATION", ("s5-323-demo", "isolated-real-demo")
        )


def test_signed_configuration_cannot_downgrade_to_old_digest_or_timeout():
    signed = ConfigurationRevision(
        revision_id="new",
        predecessor_digest="a" * 64,
        configuration_digest="b" * 64,
        ledger_id="original",
        model_target="model",
    )
    actual = dict(
        configuration_digest="b" * 64,
        ledger_id="original",
        model_target="model",
        connect_seconds=5,
        read_seconds=55,
        total_seconds=60,
        cost_microusd=10000000,
    )
    require_configuration(signed, actual, cleanup_seconds=2)
    for change in (
        {"read_seconds": 30},
        {"configuration_digest": "a" * 64},
        {"ledger_id": "new-ledger"},
        {"cost_microusd": 11000000},
    ):
        with pytest.raises(AuthorityError, match="CONFIGURATION_MISMATCH"):
            require_configuration(signed, {**actual, **change}, cleanup_seconds=2)
    with pytest.raises(AuthorityError):
        require_configuration(signed, actual, cleanup_seconds=3)


@pytest.fixture
def task_env(env):  # noqa: F811
    e = env
    PlanningCallAdmission(e.admission.delegation, e.limits).migrate()
    with e.repo.connection_scope() as c:
        for version in range(1, 13):
            c.execute(next(ROOT.glob(f"{version:04d}_*.sql")).read_text())
    problems = PostgresBusinessProblemRepository(
        e.repo.pool.conninfo,
        migration_path=ROOT / "0013_business_problem_authority.sql",
    )
    problems.migrate()
    revision = BusinessProblemRevision(
        ScopeIdentity("s5-323-demo", "isolated-real-demo"),
        "test-root",
        "test-root-1",
        1,
        None,
        "合成交付",
        "仅测试数据",
        "owner",
        e.business.principal_id,
        datetime.now(UTC),
    )
    problems.create_problem(
        revision,
        idempotency_key="root",
        payload_digest=revision.digest,
        authorized=True,
    )
    root = ExactReference(
        resource_id=revision.business_problem_id,
        revision_id=revision.revision_id,
        digest=revision.digest,
    )
    service = BoundedTaskAuthorization(
        e.admission.delegation,
        root_bindings={
            (
                "SAME_CASE_DELIVERY",
                "s5-323-demo",
                "isolated-real-demo",
            ): root.model_dump(mode="json")
        },
    )
    service.migrate()
    service.delegation.grants.target_validator = SimpleNamespace(
        is_known_exact_target=lambda *a, **k: True
    )
    e.repo.bounded_task_authorization_enabled = True
    e.tasks = service
    e.task_spec = TaskAuthorizationRequest(
        purpose="SAME_CASE_DELIVERY",
        root=root,
        source_snapshot=root,
        determination_date="2026-09-22",
        idempotency_key="one",
        permissions=(
            TaskPermission(
                owner="BUSINESS_PROBLEM",
                action="READ",
                exact_resource="business-problem:test-root",
            ),
        ),
    )
    try:
        yield e
    finally:
        problems.pool.close()


def signature(row, key="signature"):
    now = datetime.now(UTC)
    return TaskSignature(
        request_digest=row["digest"],
        idempotency_key=key,
        not_before=now - timedelta(seconds=1),
        expires_at=now + timedelta(hours=1),
    )


@pytest.mark.skipif(
    not os.environ.get("AUTHORITY_I1_TEST_DATABASE_URL"),
    reason="exclusive PostgreSQL required",
)
def test_independent_signature_current_reads_revoke_and_immutable_history(task_env):
    e = task_env
    row = e.tasks.prepare(e.business, e.task_spec)
    assert e.tasks.prepare(e.business, e.task_spec) == row
    assert e.tasks.read(e.business, row["request_id"])["status"] == "NOT_ADMITTED"
    with pytest.raises(AuthorityError):
        e.tasks.approve(e.business, row["request_id"], signature(row))
    cmd = signature(row)
    decision = e.tasks.approve(e.reviewer, row["request_id"], cmd)
    assert e.tasks.approve(e.reviewer, row["request_id"], cmd) == decision
    grant = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:test-root")
    reader = e.tasks.delegation.grants.authorization
    assert (
        reader.authorize_current(e.business, grant, now=datetime.now(UTC)).decision_id
        == decision["decision_id"]
    )
    assert reader.has_current_grants(
        e.business, (grant,), now=datetime.now(UTC), generation=1, recovery_epoch=1
    ) == (True,)
    assert reader.authorize_current(e.reviewer, grant, now=datetime.now(UTC)) is None
    e.tasks.revoke(e.reviewer, row["request_id"], decision["decision_id"])
    assert reader.authorize_current(e.business, grant, now=datetime.now(UTC)) is None
    from psycopg import errors

    with pytest.raises(errors.RaiseException), e.repo.connection_scope() as c:
        c.execute("DELETE FROM authorization_admin.bounded_task_decisions")


@pytest.mark.skipif(
    not os.environ.get("AUTHORITY_I1_TEST_DATABASE_URL"),
    reason="exclusive PostgreSQL required",
)
def test_exact_root_payload_conflict_and_foreign_scope(task_env):
    e = task_env
    row = e.tasks.prepare(e.business, e.task_spec)
    changed = e.task_spec.model_copy(update={"determination_date": "2026-09-23"})
    with pytest.raises(AuthorityError, match="IDEMPOTENCY_PAYLOAD_CONFLICT"):
        e.tasks.prepare(e.business, changed)
    foreign = replace(
        e.business, scope=replace(e.business.scope, security_domain="other")
    )
    with pytest.raises(AuthorityError, match="NOT_FOUND"):
        e.tasks.read(foreign, row["request_id"])


@pytest.mark.skipif(
    not os.environ.get("AUTHORITY_I1_TEST_DATABASE_URL"),
    reason="exclusive PostgreSQL required",
)
def test_expired_signature_and_changed_account_deny_without_deleting(task_env):
    e = task_env
    row = e.tasks.prepare(e.business, e.task_spec)
    decision = e.tasks.approve(e.reviewer, row["request_id"], signature(row))
    with e.repo.connection_scope() as c:
        c.execute(
            "UPDATE browser_identity.local_accounts SET revision=revision+1 "
            "WHERE account_id=%s",
            (row["account_id"],),
        )
    assert (
        e.tasks.read(e.business, row["request_id"])["reasonCode"]
        == "TASK_AUTHORIZATION_ACCOUNT_INACTIVE"
    )
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT decision_id FROM authorization_admin.bounded_task_decisions"
            ).fetchone()["decision_id"]
            == decision["decision_id"]
        )


@pytest.mark.skipif(
    not os.environ.get("AUTHORITY_I1_TEST_DATABASE_URL"),
    reason="exclusive PostgreSQL required",
)
def test_revoked_successor_does_not_revive_previous_window(task_env):
    e = task_env
    first = e.tasks.prepare(e.business, e.task_spec)
    e.tasks.approve(e.reviewer, first["request_id"], signature(first, "first"))
    second = e.tasks.prepare(
        e.business, e.task_spec.model_copy(update={"idempotency_key": "second"})
    )
    decision = e.tasks.approve(
        e.reviewer, second["request_id"], signature(second, "second")
    )
    e.tasks.revoke(e.reviewer, second["request_id"], decision["decision_id"])
    assert (
        e.tasks.read(e.business, first["request_id"])["reasonCode"]
        == "TASK_AUTHORIZATION_SUPERSEDED"
    )
    assert (
        e.tasks.delegation.grants.authorization.authorize_current(
            e.business,
            ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:test-root"),
            now=datetime.now(UTC),
        )
        is None
    )
