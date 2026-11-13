"""One PG owner chain; model content controlled, no real execution dispatched."""

# ruff: noqa: F401,F811 -- Explicit shared isolated fixture registration.
import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.execution_domain import ScopeIdentity
from agent_console.owned_business_resource_adapter import (
    derive_work,
    evidence,
    readonly_work,
    require_reference,
)
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.planning_candidates import read_published
from owned_business_consumer_support import configure_scope, prepare_source
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark as pgmark
from test_conversation_relation_bff import routed
from test_owned_business_admission import owned_created, owned_ready
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted

pytestmark = [
    pgmark,
    pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True),
    pytest.mark.parametrize(
        "owned_ready",
        [
            dict(
                mode=mode,
                prepare_source=prepare_source,
                configure_scope=configure_scope,
            )
            for mode in (None, "SOURCE_SUCCESSOR")
        ],
        indirect=True,
    ),
]


@pytest.fixture(autouse=True)
def cleanup_consumer_resources(adopted):
    yield
    cleanup = getattr(adopted, "consumer_cleanup", None)
    if cleanup is not None:
        cleanup()


def test_published_resources_feed_same_created_problem_and_readonly_scope(
    owned_created,
):
    e = owned_created
    revision = e.created["revision"]
    problem = ExactReference(
        resource_id=revision["business_problem_id"],
        revision_id=revision["revision_id"],
        digest=revision["digest"],
    )
    scope = ScopeIdentity(e.context.scope.tenant_id, e.context.scope.security_domain)
    with e.repo.connection_scope() as c:
        work = derive_work(e.business_owner, c, e.context, problem)
        for kind, ref in {**e.consumer_refs, "employee": e.consumer_employee}.items():
            require_reference(work, kind, ref)
            read_published(
                c, scope, "RUNTIME" if kind == "runtime" else kind.upper(), ref
            )
        readonly = readonly_work(work)
        assert readonly.problem == problem
        assert readonly.documentRules.ontology == e.consumer_ontology
        assert readonly.documentRules.source == e.consumer_refs["knowledge"]
        assert readonly.sourceContentDigests == (
            e.business_result["inputSource"]["sourceContentDigest"],
        )
        proof = evidence(work)
        row = c.execute(
            "SELECT record FROM authorization_admin.owned_business_admissions "
            "WHERE admission_id=%s",
            (proof["admissionId"],),
        ).fetchone()["record"]
        assert row["inputSource"] == e.business_result["inputSource"]
        count = c.execute(
            "SELECT count(*) n FROM authorization_admin.grant_decisions"
        ).fetchone()["n"]
        with pytest.raises(AuthorityError, match="RESOURCE_NOT_AUTHORIZED"):
            require_reference(
                work,
                "skill",
                e.consumer_refs["skill"].model_copy(
                    update={"revision_id": "unapproved"}
                ),
            )
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_decisions"
            ).fetchone()["n"]
            == count
        )
        c.execute(
            "INSERT INTO authorization_admin.owned_business_revocations"
            "(admission_id,actor_id,reason_code) VALUES(%s,%s,%s)",
            (proof["admissionId"], e.context.principal_id, "USER_REQUESTED"),
        )
    with (
        e.repo.connection_scope() as c,
        pytest.raises(AuthorityError, match="ADMISSION_REVOKED"),
    ):
        derive_work(e.business_owner, c, e.context, problem)
    assert len(e.calls) == e.business_model_call_count


def test_same_owned_problem_confirms_prepares_and_worker_reads(
    owned_created, tmp_path, request
):
    from pathlib import Path

    from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
    from agent_console.policy_plan_confirmation import PolicyPlanConfirmation
    from agent_console.prepared_native_coordinator import PreparedNativeCoordinator
    from agent_console.prepared_result_review import migrate
    from agent_console.readonly_continuation import ReadonlyContinuation
    from agent_console.readonly_continuation_policy import ReadonlyContinuationPolicy
    from agent_console.readonly_continuation_worker import ContinuationWork
    from agent_console.workbench_owner_authorization import (
        AuthorizedOwnerAuthority,
        AuthorizedOwnerCall,
    )
    from owned_business_consumer_support import (
        check_question_input_bff,
        prepare_current_resource_reads,
        resource_automation,
    )
    from owned_business_planning_support import generate_proposal

    e = owned_created
    revision = e.created["revision"]
    calls = len(e.calls)
    linked = e.draft.link_problem(
        e.context,
        e.business_result["invocationId"],
        problem_id=revision["business_problem_id"],
        problem_revision_id=revision["revision_id"],
        problem_digest=revision["digest"],
    ).invocation
    assert linked.aggregate_version == e.business_result["aggregateVersion"] + 1
    consumers = {}

    def before_planning(e, current):
        automation, adapter = resource_automation(e, e.consumer_planning_app, tmp_path)
        prepare_current_resource_reads(e, automation)
        routed = check_question_input_bff(
            e, automation, adapter, current["target"]["problem"]
        )
        observed = routed["activityRequirement"]["memberCapabilityObservation"]
        assert observed["operations"]
        assert {item["operation"] for item in observed["operations"]} == set(
            e.business_owner.policy.scopes[0].operations
        )
        assert len(e.calls) == calls
        e.consumer_question_input = routed
        consumers.update(automation=automation, adapter=adapter)

    generate_proposal(e, before_planning=before_planning)
    automation, adapter = consumers["automation"], consumers["adapter"]
    from agent_console.plan_suggestion_domain import ProposalRevision

    proposal = e.consumer_proposal
    proposal_digest = ProposalRevision.model_validate(proposal).digest
    identity = proposal["proposal_id"]
    problem = proposal["semantics"]["target"]["problem"]
    generation = automation.grants.generation.generation

    def invoke(handler, operation, payload, query=None):
        with e.repo.connection_scope() as c:
            return handler(
                AuthorizedOwnerCall(
                    operation,
                    e.context,
                    c,
                    payload,
                    {"proposal_id": identity},
                    query or {},
                    (),
                    AuthorizedOwnerAuthority(adapter, e.context, c, generation, ()),
                    generation,
                    1,
                )
            )

    confirm = {
        "problem": problem,
        "revision": proposal["revision"],
        "digest": proposal_digest,
        "expectedPlanVersion": 0,
        "idempotencyKey": "joint-confirm",
    }
    confirmed = invoke(
        PolicyPlanConfirmation(automation), "CONFIRM_POLICY_PLAN", confirm
    )
    assert (
        invoke(PolicyPlanConfirmation(automation), "CONFIRM_POLICY_PLAN", confirm)
        == confirmed
    )
    version = confirmed["confirmation"]["plan"]["version"]
    native = PostgresExecutionAuthorityRepository(
        e.repo.pool.conninfo,
        migration_path=Path(__file__).parents[1]
        / "migrations/0008_execution_runtime_authority.sql",
    )
    request.addfinalizer(native.pool.close)
    policy = ReadonlyContinuationPolicy(
        policyId="joint-readonly", policyVersion="1", enabled=True, works=()
    )
    handler = ReadonlyContinuation(
        automation, policy, PreparedNativeCoordinator(native)
    )
    automation.continuation = handler
    ready = invoke(
        automation,
        "PREPARE_RESOURCE_AUTOMATION",
        {"version": version, "idempotencyKey": "joint-prepare"},
    )
    import json

    assert ready["state"] == "READY", json.dumps(ready, ensure_ascii=False, indent=2)
    assert (
        invoke(
            automation,
            "READ_RESOURCE_AUTOMATION",
            {},
            {"version": version, "key": "joint-prepare"},
        )
        == ready
    )
    try:
        native.migrate_native_dispatch(
            Path(__file__).parents[1] / "migrations/0022_native_execution_dispatch.sql"
        )
        with e.repo.connection_scope() as c:
            migrate(c)
        policy = ReadonlyContinuationPolicy(
            policyId="joint-readonly", policyVersion="1", enabled=True, works=()
        )
        handler = ReadonlyContinuation(
            automation, policy, PreparedNativeCoordinator(native)
        )
        value = invoke(handler, "CONTINUE_READONLY_WORK", {"version": version})
        assert (
            invoke(handler, "READ_READONLY_CONTINUATION", {}, {"version": version})[
                "receipt"
            ]
            == value["receipt"]
        )
        assert (
            invoke(handler, "CONTINUE_READONLY_WORK", {"version": version})["receipt"]
            == value["receipt"]
        )
        assert value["receipt"]["ownedBusiness"] == ready["ownedBusiness"]

        def authority(c, command):
            assert command.principal_id == e.context.principal_id
            return e.context, AuthorizedOwnerAuthority(
                adapter, e.context, c, generation, ()
            )

        worker = ContinuationWork(
            native, policy, authority, owned_business=e.business_owner
        )
        expected = (
            (
                e.context.scope.tenant_id,
                e.context.scope.security_domain,
                "governed-execution:prepared:" + value["receipt"]["preparationDigest"],
            ),
        )
        assert worker.dispatches() == expected
        assert ContinuationWork(native, policy, authority).dispatches() == ()
        observer = getattr(e, "consumer_execution_observer", None)
        if observer is not None:
            observer(worker, native, value["receipt"], ready)
        with e.repo.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM execution_authority.workflow_runs"
                ).fetchone()["n"]
                == 1
            )
            c.execute(
                "INSERT INTO authorization_admin.owned_business_revocations"
                "(admission_id,actor_id,reason_code) VALUES(%s,%s,%s)",
                (
                    ready["ownedBusiness"]["admissionId"],
                    e.context.principal_id,
                    "USER_REQUESTED",
                ),
            )
        assert worker.dispatches() == ()
        after_revoke = getattr(e, "consumer_after_revoke", None)
        if after_revoke is not None:
            after_revoke()
        assert len(e.calls) == e.business_model_call_count
    finally:
        native.pool.close()


def test_successor_retains_old_policy_history_without_execution(
    owned_created, tmp_path, monkeypatch
):
    import json
    from datetime import datetime, timedelta

    from agent_console import owned_business_work_reader
    from agent_console.owned_business_admission import OwnedBusinessAdmission

    e = owned_created
    prior = e.business_owner
    value = prior.policy.model_dump(mode="json")
    value.update(
        policyVersion="history-window-successor",
        expiresAt=(prior.policy.expiresAt + timedelta(hours=1)).isoformat(),
    )
    path = tmp_path / "successor.json"
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    successor = OwnedBusinessAdmission(
        prior.root, path, retained_history_paths=[prior.path]
    )
    revision = e.created["revision"]
    problem = ExactReference(
        resource_id=revision["business_problem_id"],
        revision_id=revision["revision_id"],
        digest=revision["digest"],
    )
    after_expiry = prior.policy.expiresAt + timedelta(seconds=1)

    class AfterExpiry(datetime):
        @classmethod
        def now(cls, tz=None):
            return after_expiry

    monkeypatch.setattr(owned_business_work_reader, "datetime", AfterExpiry)
    from test_local_accounts_postgres import login

    monkeypatch.setattr(e.routing_sessions, "clock", lambda: after_expiry)
    renewed = login(e.routing_sessions, "reviewer324")
    _, current_context = e.routing_sessions.authenticate_session(renewed.value)
    with e.repo.connection_scope() as c:
        history = successor.work(c, current_context, problem, history=True)
        assert history.history_only
        assert history.policy_digest == prior.policy.digest
        assert history.expires_at <= prior.policy.expiresAt < after_expiry
    with (
        e.repo.connection_scope() as c,
        pytest.raises(AuthorityError, match="POLICY_BINDING_CHANGED"),
    ):
        successor.work(c, current_context, problem)
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO authorization_admin.owned_business_revocations"
            "(admission_id,actor_id,reason_code) VALUES(%s,%s,%s)",
            (history.admission_id, e.context.principal_id, "USER_REQUESTED"),
        )
    with (
        e.repo.connection_scope() as c,
        pytest.raises(AuthorityError, match="ADMISSION_REVOKED"),
    ):
        successor.work(c, current_context, problem, history=True)
    assert len(e.calls) == e.business_model_call_count
