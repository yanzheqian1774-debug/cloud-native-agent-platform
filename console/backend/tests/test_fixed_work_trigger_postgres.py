# ruff: noqa: F811, E501 -- Isolated shared fixture.
"""Real PG START/coordinator transaction, synthetic grants, no Native effects."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from agent_console import fixed_work_authoring_postgres as drafts
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityScope,
    TrustedRequestContext,
)
from agent_console.execution_domain import ScopeIdentity, VersionedAggregate
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.fixed_work_authoring import SaveDraft
from agent_console.fixed_work_trigger import TriggerPolicy
from agent_console.fixed_work_trigger_postgres import compatible, migrate
from agent_console.prepared_native_coordinator import PreparedNativeCoordinator
from agent_console.workbench_fixed_work_trigger import FixedWorkTriggerOwner
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from prepared_execution_support import ExactTestAuthority, seed
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_fixed_work_authoring import body
from test_plan_suggestion_v2 import repository  # noqa: F401

MIGRATIONS = Path(__file__).parents[1] / "migrations"


@pytest.fixture
def fixture(repository, request):
    p = seed(repository)
    scope = ScopeIdentity(p.namespace, p.security_domain)
    native = PostgresExecutionAuthorityRepository(
        repository.pool.conninfo,
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
    )
    request.addfinalizer(native.pool.close)
    native.migrate_native_dispatch(MIGRATIONS / "0022_native_execution_dispatch.sql")
    native.create_aggregate(
        "runtime_instance",
        VersionedAggregate(scope, "native", 1, {"current_generation": 1}),
    )
    native.create_aggregate(
        "agent_instance",
        VersionedAggregate(
            scope,
            "agent",
            1,
            dict(
                agent_revision_id="1",
                agent_definition_id="agent-definition",
                agent_digest="a" * 64,
                runtime_instance_id="native",
                kubernetes_agent_name="fixture-cost-agent",
            ),
        ),
    )
    authority = ExactTestAuthority(p)
    authority.allowed.update(
        f"skill-invocation:prepared:{p.digest}:{t.task_id}:1" for t in p.participants
    )

    class Authority:
        denied = False

        def require(self, principal, owner, action, resource):
            if self.denied:
                raise PermissionError("REVOKED")
            if (owner, action, resource) == ("TEAM", "READ", "team:team:revision") or (
                owner,
                action,
                resource,
            ) == ("EXECUTION", "READ", "governed-execution:prepared:" + p.digest):
                return None
            return authority.require(principal, owner, action, resource)

    current = Authority()
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        drafts.migrate(c)
        migrate(c)
        compatible(c)
        team = dict(teamId="team", revisionId="revision", digest="a" * 64)
        saved, _ = drafts.save(
            c,
            (p.namespace, p.security_domain),
            "human:alice",
            SaveDraft.model_validate(body()),
            team,
            "b" * 64,
            "fixture-only-decision",
            datetime.now(UTC),
        )
        c.execute(
            "INSERT INTO execution_authority.prepared_candidates VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                p.namespace,
                p.security_domain,
                p.digest,
                p.plan_id,
                p.plan_version,
                Jsonb(p.model_dump(mode="json")),
                "human:alice",
            ),
        )
    record = saved["record"]
    policy = TriggerPolicy.model_validate(
        dict(
            schemaVersion="fixed-work-one-use-policy.v1",
            policyId="fixture",
            enabled=True,
            expiresAt=datetime.now(UTC) + timedelta(hours=1),
            bindings=[
                dict(
                    tenantId=p.namespace,
                    securityDomain=p.security_domain,
                    subjectId="human:alice",
                    workId=record["workId"],
                    revisionId=record["revisionId"],
                    workDigest=saved["digest"],
                    preparationDigest=p.digest,
                    mode="EXPLICIT_ORIGINAL_SUBJECT",
                )
            ],
        )
    )
    owner = FixedWorkTriggerOwner(lambda: policy, PreparedNativeCoordinator(native))

    def call(c, event="event-one", operation="TRIGGER_FIXED_WORK_ONCE"):
        return AuthorizedOwnerCall(
            operation,
            TrustedRequestContext(
                "human:alice",
                AuthorityScope(*(p.namespace, p.security_domain)),
                "fixture-session",
                AuthenticationSource.BROWSER_SESSION,
                "fixture",
            ),
            c,
            {"idempotencyKey": "original-key"},
            dict(
                work_id=record["workId"],
                revision_id=record["revisionId"],
                digest=p.digest,
                event_id=event,
            ),
            {},
            (),
            current,
            policy_generation=1,
            recovery_epoch=1,
        )

    try:
        yield repository, owner, call, policy, p, current
    finally:
        native.pool.close()


def test_owner_start_replay_and_expired_read(fixture):
    repo, owner, call, policy, _p, authority = fixture
    with repo.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        first = owner(call(c))
    with repo.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        assert owner(call(c)) == first
        assert (
            c.execute(
                "SELECT count(*) AS n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM fixed_work_triggers.receipts"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM execution_authority.native_dispatch_commands"
            ).fetchone()["n"]
            >= 1
        )
    # A new preparation key cannot bypass this work's unresolved queued Run.
    alternate = policy.model_copy(
        update={
            "bindings": (
                policy.bindings[0].model_copy(update={"preparationDigest": "c" * 64}),
            )
        }
    )
    original_require = authority.require

    def allow_candidate(principal, owner_name, action, resource):
        if (owner_name, action, resource) == (
            "EXECUTION",
            "START",
            "governed-execution:prepared:" + "c" * 64,
        ):
            return None
        return original_require(principal, owner_name, action, resource)

    authority.require = allow_candidate
    owner.policy_reader = lambda: alternate
    with repo.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        pending = call(c, event="new-event")
        with pytest.raises(WorkbenchOwnerError, match="PREVIOUS_RUN_UNRESOLVED"):
            owner(replace(pending, path={**pending.path, "digest": "c" * 64}))
    authority.require = original_require
    owner.policy_reader = lambda: policy.model_copy(update={"enabled": False})
    with repo.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        assert owner(call(c, operation="READ_FIXED_WORK_TRIGGER")) == first
        with pytest.raises(WorkbenchOwnerError, match="UNAVAILABLE"):
            owner(call(c))
    authority.denied = True
    with (
        repo.pool.connection() as c,
        c.transaction(),
        pytest.raises(PermissionError, match="REVOKED"),
    ):
        owner(call(c, operation="READ_FIXED_WORK_TRIGGER"))


def test_coordinator_error_rolls_back_and_no_new_event_reuse(fixture):
    repo, owner, call, _policy, _p, _ = fixture
    original = owner.owner.coordinator

    def failed(call, p):
        original(call, p)
        raise RuntimeError("fixture-after-enqueue")

    owner.owner.coordinator = failed
    with (
        repo.pool.connection() as c,
        pytest.raises(RuntimeError, match="after-enqueue"),
        c.transaction(),
    ):
        c.row_factory = dict_row
        owner(call(c))
    with repo.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        for table in [
            "workflow_runs",
            "native_dispatch_commands",
            "prepared_start_commands",
        ]:
            assert (
                c.execute(
                    "SELECT count(*) AS n FROM execution_authority." + table
                ).fetchone()["n"]
                == 0
            )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM fixed_work_triggers.receipts"
            ).fetchone()["n"]
            == 0
        )
        owner.owner.coordinator = original
        owner(call(c))
    with (
        repo.pool.connection() as c,
        c.transaction(),
        pytest.raises(WorkbenchOwnerError, match="ALREADY_BOUND"),
    ):
        c.row_factory = dict_row
        owner(call(c, event="other-event"))


def test_same_event_concurrency_and_wrong_payload(fixture):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    repo, owner, call, _policy, _p, _authority = fixture
    barrier = Barrier(2)

    def run():
        with repo.pool.connection() as c, c.transaction():
            c.row_factory = dict_row
            barrier.wait(timeout=5)
            return owner(call(c))

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run(), range(2)))
    assert results[0] == results[1]
    with repo.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        assert (
            c.execute(
                "SELECT count(*) AS n FROM fixed_work_triggers.receipts"
            ).fetchone()["n"]
            == 1
        )
        with pytest.raises(WorkbenchOwnerError, match="CONFLICT"):
            owner(replace(call(c), payload={"idempotencyKey": "different"}))


def test_existing_owner_run_never_relabelled_as_new_trigger(fixture):
    repo, owner, call, _policy, p, _authority = fixture
    with repo.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        original = call(c)
        owner.owner(
            replace(
                original,
                operation="START_PREPARED_EXECUTION",
                path={"digest": p.digest},
                payload={"idempotencyKey": "ordinary-existing-start"},
            )
        )
    with repo.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        with pytest.raises(WorkbenchOwnerError, match="STATE_REQUIRES_REVIEW"):
            owner(call(c))
        assert (
            c.execute(
                "SELECT count(*) AS n FROM fixed_work_triggers.receipts"
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 1
        )
