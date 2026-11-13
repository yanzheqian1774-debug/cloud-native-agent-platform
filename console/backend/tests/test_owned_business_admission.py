"""Isolated real conversation/adoption/grant owners; provider output is controlled."""

# ruff: noqa: F401,F811 -- Reuse isolated fixtures, never deployed credentials.
import json
from datetime import UTC, datetime, timedelta

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.draft_assistance import DraftResultKind
from agent_console.owned_business_admission import OwnedBusinessAdmission
from agent_console.owned_business_postgres import migrate
from agent_console.understanding_adoption_origin import AdoptionOrigin
from agent_console.workbench_bff import PREFIX
from psycopg.types.json import Jsonb
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_conversation_relation_bff import routed
from test_owned_business_policy import document
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted, answer
from test_understanding_adoption_source import select

pytestmark = [
    pytestmark,
    pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True),
]


@pytest.fixture
def owned_ready(adopted, tmp_path, request):
    e = adopted
    options = getattr(request, "param", None)
    mode = options.get("mode") if isinstance(options, dict) else options
    mixed = mode == "SOURCE_SUCCESSOR"
    if isinstance(options, dict) and options.get("prepare_source") is not None:
        options["prepare_source"](e)
    if mixed:
        from test_understanding_source_successor_bff import (
            test_selected_old_c2_question_continues_with_exact_successor,
        )

        captured = []
        test_selected_old_c2_question_continues_with_exact_successor(
            e, tmp_path, None, on_ready=lambda *values: captured.append(values)
        )
        e, result, previous, routing = captured[0]
        root = e.admission
        retained = (
            AdoptionOrigin(
                root,
                previous.authorization.context_admission,
                previous.profile,
                enabled=True,
            ),
        )
    else:
        select(e)
        e.kind = DraftResultKind.DRAFT_READY
        path, result = answer(e)
        response = e.adoption_client.post(
            PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
        )
        assert response.status_code == 200, response.text
        root = e.admission
        routing = e.adoption_client.app.state.understanding_adoption.routing
        retained = ()
    root.understanding_adoption = AdoptionOrigin(
        root,
        routing.authorization.context_admission,
        routing.profile,
        enabled=True,
        retained=retained,
    )
    e.business_model_call_count = len(e.calls)
    policy = document()
    policy.update(
        enabled=True,
        rootPolicyDigest=root.experience.policy_digest,
        rootUnderstandingPolicyDigest=root.experience.understanding_policy_digest,
        adoptionPolicyDigest=root.understanding_adoption.routing.experience.understanding_policy_digest,
        allowanceId=root.experience.document.allowanceId,
        expiresAt=(datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
    )
    scope = policy["scopes"][0]
    scope["source"] = result["inputSource"]["source"]
    scope["sourceContentDigest"] = result["inputSource"]["sourceContentDigest"]
    scope["documentRules"]["source"] = scope["source"]
    if isinstance(options, dict) and options.get("configure_scope") is not None:
        options["configure_scope"](e, result, policy)
    p = tmp_path / "owned-business.json"
    p.write_text(json.dumps(policy))
    p.chmod(0o600)
    owner = OwnedBusinessAdmission(root, p)
    root.owned_business = owner
    migrate(root.repository)
    with e.repo.connection_scope() as c:
        c.execute(
            "UPDATE private_conversation.journeys SET state=%s WHERE "
            "tenant_id=%s AND security_domain=%s AND conversation_id=%s",
            (
                Jsonb(dict(phase="CREATE", key="initial-work", draft=result)),
                e.context.scope.tenant_id,
                e.context.scope.security_domain,
                e.conv,
            ),
        )
    e.business_owner, e.business_result = owner, result
    return e


def test_owned_adopted_ready_requires_new_basis_and_is_idempotent(owned_ready):
    e = owned_ready
    owner, result = e.business_owner, e.business_result
    with e.repo.connection_scope() as c:
        before = c.execute(
            "SELECT count(*) n FROM draft_provider_budget.reservations"
        ).fetchone()
        assert owner.supports(c, e.context, result["invocationId"])
        first = owner.admit(c, e.context, result["invocationId"])
        replay = owner.admit(c, e.context, result["invocationId"])
        assert (replay[0], replay[1], replay[3]) == (first[0], first[1], first[3])
        assert (
            replay[2] >= first[2]
        )  # Current authorization observation, not saved time.
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.owned_business_admissions"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()
            == before
        )
        row = c.execute(
            "SELECT record FROM authorization_admin.owned_business_admissions"
        ).fetchone()["record"]
        assert row["ancestryDigests"] and row["inputSource"] == result["inputSource"]
    assert len(e.calls) == e.business_model_call_count


@pytest.mark.parametrize("prepared_before_correction", [False, True])
def test_ready_result_with_replaced_current_goal_is_not_admitted(
    owned_ready, prepared_before_correction
):
    e = owned_ready
    if prepared_before_correction:
        with e.repo.connection_scope() as c:
            e.business_owner.admit(c, e.context, e.business_result["invocationId"])
    with e.repo.connection_scope() as c:
        c.execute(
            "UPDATE private_conversation.journeys SET state=%s "
            "WHERE conversation_id=%s",
            (Jsonb(dict(phase="UNDERSTAND", key="another-question")), e.conv),
        )
    with (
        e.repo.connection_scope() as c,
        pytest.raises(AuthorityError, match="CURRENT_GOAL_CHANGED"),
    ):
        e.business_owner.admit(c, e.context, e.business_result["invocationId"])


def test_context_revocation_blocks_retained_result_business_admission(owned_ready):
    e = owned_ready
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO authorization_admin.context_call_revocations "
            "(admission_id,actor_id) "
            "SELECT admission_id,%s FROM authorization_admin.context_call_decisions "
            "WHERE context_id=%s ORDER BY ordinal DESC LIMIT 1",
            (e.context.principal_id, e.original["contextId"]),
        )
    with (
        e.repo.connection_scope() as c,
        pytest.raises(AuthorityError, match="CONTEXT_REVOKED"),
    ):
        e.business_owner.admit(c, e.context, e.business_result["invocationId"])


@pytest.fixture
def owned_created(owned_ready, request):
    from dataclasses import replace
    from pathlib import Path
    from types import SimpleNamespace as NS

    from agent_console.authority_configuration import RequestabilityRule
    from agent_console.authority_contracts import ExactGrant
    from agent_console.business_plan_postgres import PostgresProblemPlanUnitOfWork
    from agent_console.business_problem_application import BusinessProblemApplication
    from agent_console.business_problem_authorization import problem_resource
    from agent_console.business_problem_postgres import (
        PostgresBusinessProblemRepository,
    )
    from agent_console.business_problem_schemas import CreateBusinessProblem
    from agent_console.context_call_admission import bind_problem
    from agent_console.conversation_planning_admission import (
        ConversationPlanningAdmission,
    )
    from agent_console.conversation_work_authorization import (
        ConversationWorkAuthorization,
    )
    from agent_console.workbench_business_problem import OwnerPrincipal

    e = owned_ready
    if getattr(request, "param", None) == "EXPIRED_CALL":
        expired_call_evidence(e)
    with e.repo.connection_scope() as c:
        e.before_problems = c.execute(
            "SELECT business_problem_id,current_revision_id,owner_id "
            "FROM business_problem_authority.problems ORDER BY business_problem_id"
        ).fetchall()
    root, value = e.admission, e.business_result
    selected = value["inputSource"]["source"]
    model = e.draft.profile.binding
    planning = NS(
        configuration={
            **root.configuration,
            "model_target": (
                "model:invocation:plan-suggestion:"
                f"{model.resource_id}:{model.revision_id}:{model.digest}"
            ),
        },
        repository=e.repo,
        delegation=root.delegation,
    )
    planning.conversation_experience = ConversationPlanningAdmission(
        root, planning.configuration
    )
    work = ConversationWorkAuthorization(planning)
    create_grant = ExactGrant("BUSINESS_PROBLEM", "CREATE", problem_resource())
    members = {create_grant}
    grants = work.grants
    generation = grants.generation
    grants._generation_provider = lambda: replace(
        generation,
        requestability=(
            *generation.requestability,
            *(
                RequestabilityRule(
                    g.owner, g.action, g.exact_resource, work._purpose(g)
                )
                for g in members
            ),
        ),
    )
    previous = grants.target_validator
    grants.target_validator = NS(
        is_known_exact_target=lambda ctx, g, **kw: (
            g in members or previous.is_known_exact_target(ctx, g, **kw)
        )
    )
    command = CreateBusinessProblem(
        title=value["draft"]["title"],
        description=value["draft"]["description"],
        ownerId=e.context.principal_id,
        idempotencyKey="initial-work:problem",
    )
    payload = {**command.model_dump(), "draftInvocationId": value["invocationId"]}
    work.before(e.context, "CREATE_PROBLEM", payload, {}, (create_grant,))
    migration = Path(__file__).parents[1] / "migrations"
    repository = PostgresBusinessProblemRepository(
        e.repo.pool.conninfo,
        migration_path=migration / "0013_business_problem_authority.sql",
        creator_receipt_migration_path=migration
        / "0020_business_problem_creator_receipt.sql",
    )
    app = BusinessProblemApplication(
        PostgresProblemPlanUnitOfWork(repository, None), None, None, None, None
    )

    def create(call):
        app.authority = call.authority
        principal = OwnerPrincipal(
            e.context.principal_id,
            e.context.scope.tenant_id,
            e.context.scope.security_domain,
        )
        created = app.create_problem(
            principal,
            command,
            connection=call.connection,
            receipt_policy_generation=call.policy_generation,
            receipt_recovery_epoch=call.recovery_epoch,
        )
        assert bind_problem(
            call.connection,
            e.context,
            created,
            value["invocationId"],
            retained_authorization=e.business_owner.admit,
        )
        return created

    try:
        created = e.draft.authorization.owner_authorization.execute(
            e.context,
            (create_grant,),
            operation="CREATE_PROBLEM",
            payload=payload,
            path={},
            query={},
            handler=create,
        )
        identity = created["revision"]["business_problem_id"]
        members.update(
            (
                ExactGrant("BUSINESS_PROBLEM", "READ", problem_resource(identity)),
                ExactGrant("PLAN", "PREPARE", "plan:prepare:" + identity),
                ExactGrant("PLAN", "READ", "plan:prepared:" + identity),
                ExactGrant(
                    "MODEL_GOVERNANCE",
                    "INVOKE_MODEL",
                    planning.configuration["model_target"],
                ),
            )
        )
        work.after(e.context, "CREATE_PROBLEM", payload, created)
        with e.repo.connection_scope() as c:
            bound = planning.conversation_experience.require_source(
                planning, c, e.context, identity
            )[0]
            assert bound["understanding_input_source"]["source"] == selected
            assert bound["context_id"] == value["contextId"]
            assert bound["context_id"] != e.original["contextId"]
        assert created["revision"]["description"] == value["draft"]["description"]
        assert len(e.calls) == e.business_model_call_count
        e.adopted_result, e.created = value, created
        e.business_app, e.business_repository = app, repository
        e.business_work, e.business_planning = work, planning
        e.business_members = members
        yield e
    finally:
        repository.pool.close()


@pytest.mark.parametrize("owned_ready", [None, "SOURCE_SUCCESSOR"], indirect=True)
@pytest.mark.parametrize("owned_created", [None, "EXPIRED_CALL"], indirect=True)
def test_new_owned_problem_uses_current_standing_basis_and_shared_reader(owned_created):
    from agent_console.plan_suggestion_domain import ExactReference

    e = owned_created
    revision = e.created["revision"]
    root = ExactReference(
        resource_id=revision["business_problem_id"],
        revision_id=revision["revision_id"],
        digest=revision["digest"],
    )
    with e.repo.connection_scope() as c:
        first = e.business_owner.work(c, e.context, root)
        history = e.business_owner.work(c, e.context, root, history=True)
        if hasattr(e, "expired_decisions"):
            assert (
                c.execute(
                    "SELECT admission_id,expires_at FROM "
                    "authorization_admin.context_call_decisions ORDER BY admission_id"
                ).fetchall()
                == e.expired_decisions
            )
        assert first.admission_id == history.admission_id
        assert first.history_only is False and history.history_only is True
        assert (
            first.scope.source.model_dump()
            == e.business_result["inputSource"]["source"]
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM business_problem_authority.problems"
            ).fetchone()["n"]
            == len(e.before_problems) + 1
        )
        assert all(
            row
            in c.execute(
                "SELECT business_problem_id,current_revision_id,owner_id "
                "FROM business_problem_authority.problems"
            ).fetchall()
            for row in e.before_problems
        )
    assert len(e.calls) == e.business_model_call_count


def expired_call_evidence(e):
    """Controlled historical decision timestamps; original rows are not rewritten."""
    from agent_console.context_call_admission import active, request_row

    with e.repo.connection_scope() as c:
        for context_id in (e.original["contextId"], e.business_result["contextId"]):
            c.execute(
                "INSERT INTO authorization_admin.context_call_decisions "
                "SELECT 'historical-expired:'||admission_id,context_id,ordinal+1,"
                "issuer_id,subject_id,generation,recovery_epoch,"
                "'historical-expired:'||idempotency_key,payload_digest,record,"
                "now()-interval '2 hours',now()-interval '1 hour' "
                "FROM authorization_admin.context_call_decisions WHERE context_id=%s "
                "ORDER BY ordinal DESC LIMIT 1",
                (context_id,),
            )
            row = request_row(c, context_id)
            with pytest.raises(AuthorityError, match="CONTEXT_ADMISSION_REQUIRED"):
                active(c, row, row["record"]["configuration"])
        e.expired_decisions = c.execute(
            "SELECT admission_id,expires_at FROM "
            "authorization_admin.context_call_decisions "
            "ORDER BY admission_id"
        ).fetchall()


def test_owned_work_history_renews_only_prior_problem_plan_and_source_reads(
    owned_created,
):
    from agent_console.business_problem_authorization import problem_resource
    from agent_console.workbench_prepared_resources import reference
    from test_conversation_work_history import snapshot

    e = owned_created
    problem = json.loads(json.dumps(e.created["revision"], default=str))
    source = e.business_result["inputSource"]["source"]
    expected = {
        ("BUSINESS_PROBLEM", "READ", problem_resource(problem["business_problem_id"])),
        ("PLAN", "READ", "plan:prepared:" + problem["business_problem_id"]),
        (
            "KNOWLEDGE",
            "READ_RESOURCE",
            reference("knowledge", source["resource_id"], source["revision_id"]),
        ),
    }
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO private_conversation.links "
            "(tenant_id,security_domain,conversation_id,link_id,target,created_by,"
            "request_key,request_digest) "
            "VALUES(%s,%s,%s,'owned-work-history',%s,%s,'owned-work-history','fixture')",
            (
                e.context.scope.tenant_id,
                e.context.scope.security_domain,
                e.conv,
                Jsonb(
                    {
                        "problemId": problem["business_problem_id"],
                        "revisionId": problem["revision_id"],
                        "problemDigest": problem["digest"],
                    }
                ),
                e.context.principal_id,
            ),
        )
        c.execute(
            "UPDATE private_conversation.journeys SET state=%s "
            "WHERE conversation_id=%s",
            (
                Jsonb(
                    {"phase": "PLAN", "key": "owned-work-history", "problem": problem}
                ),
                e.conv,
            ),
        )
        for owner, action, resource in expected:
            c.execute(
                "UPDATE authorization_admin.grants "
                "SET not_before=now()-interval '9 hours',"
                "expires_at=now()-interval '1 hour' WHERE subject_principal_id=%s "
                "AND owner=%s AND action=%s AND exact_resource=%s",
                (e.context.principal_id, owner, action, resource),
            )
    before = snapshot(e)
    for _ in range(2):
        result = e.adoption_client.post(
            PREFIX + f"/conversations/{e.conv}/history-access",
            headers=e.adoption_headers,
            json={},
        )
        assert result.status_code == 200, result.text
    assert snapshot(e) == before
    with e.repo.connection_scope() as c:
        renewed = c.execute(
            "SELECT owner,action,exact_resource FROM authorization_admin.grants "
            "WHERE subject_principal_id=%s AND issuer_principal_id=%s",
            (e.context.principal_id, "policy:f3-conversation-history-read"),
        ).fetchall()
        assert {
            (r["owner"], r["action"], r["exact_resource"]) for r in renewed
        } == expected
        assert len(renewed) == len(expected)
    assert len(e.calls) == e.business_model_call_count
    assert len(e.initial_calls) == 1


@pytest.mark.parametrize("owned_ready", [None, "SOURCE_SUCCESSOR"], indirect=True)
@pytest.mark.parametrize("owned_created", ["EXPIRED_CALL"], indirect=True)
def test_planning_preparation_preserves_exact_new_basis_and_original_allowance(
    owned_created,
):
    from types import SimpleNamespace as NS

    from agent_console.context_call_admission import request_row
    from agent_console.conversation_planning_admission import (
        ConversationPlanningAdmission,
        limits,
    )
    from agent_console.planning_call_admission import PlanningCallAdmission
    from test_conversation_planning_admission import planned
    from test_conversation_planning_source import boundary

    e = owned_created
    service = PlanningCallAdmission(
        e.admission.delegation, e.business_planning.configuration
    )
    service.migrate()
    service.conversation_experience = ConversationPlanningAdmission(
        e.admission, service.configuration
    )
    e.planning, e.reviewer = service, e.context
    root = e.created["revision"]["business_problem_id"]
    result = planned(
        e, problem=root, answers=(boundary(e.business_result["inputSource"]["source"]),)
    )
    assert (
        planned(
            e,
            problem=root,
            answers=(boundary(e.business_result["inputSource"]["source"]),),
        )
        == result
    )
    with e.repo.connection_scope() as c:
        row = request_row(c, result["admission"]["context_id"])
        proof = row["record"]["owned_business"]
        assert proof["admissionId"] and proof["recordDigest"]
        assert row["record"]["source_context_id"] == e.business_result["contextId"]
        budget = NS(
            ledger_id=e.business_owner.policy.ledgerId,
            allowance_id=e.business_owner.policy.allowanceId,
            owned_business=e.business_owner.work_reader,
        )
        assert limits(c, row, budget) == (100, 10_000_000)
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )
        c.execute(
            "INSERT INTO authorization_admin.owned_business_revocations "
            "(admission_id,actor_id,reason_code) VALUES(%s,%s,%s)",
            (proof["admissionId"], e.context.principal_id, "USER_REQUESTED"),
        )
    with (
        e.repo.connection_scope() as c,
        pytest.raises(AuthorityError, match="ADMISSION_REVOKED"),
    ):
        row = request_row(c, result["admission"]["context_id"])
        limits(c, row, budget)
    assert len(e.calls) == e.business_model_call_count
    assert len(e.initial_calls) == 1


@pytest.mark.parametrize(
    "changed",
    [
        "subject",
        "tenant",
        "service_credential",
        "source",
        "revision",
        "revoked",
        "context_configuration",
        "context_policy",
    ],
)
def test_shared_reader_rejects_identity_source_and_revocation_changes(
    owned_created, changed
):
    from dataclasses import replace

    from agent_console.authority_contracts import AuthenticationSource, AuthorityScope
    from agent_console.plan_suggestion_domain import ExactReference

    e = owned_created
    revision = e.created["revision"]
    root = ExactReference(
        resource_id=revision["business_problem_id"],
        revision_id=revision["revision_id"],
        digest=revision["digest"],
    )
    context = e.context
    source_digest = None
    if changed == "subject":
        context = replace(context, principal_id="human:unrelated")
    elif changed == "tenant":
        context = replace(
            context, scope=AuthorityScope("different", context.scope.security_domain)
        )
    elif changed == "service_credential":
        context = replace(
            context,
            authentication_source=AuthenticationSource.SERVICE_CREDENTIAL,
            session_id_or_service_credential_id="not-a-real-credential",
        )
    elif changed == "source":
        source_digest = "0" * 64
    elif changed == "revision":
        root = root.model_copy(update={"revision_id": "not-the-bound-revision"})
    elif changed in {"context_configuration", "context_policy"}:
        path = (
            ["configuration", "profile_digest"]
            if changed == "context_configuration"
            else ["owned_understanding_policy_digest"]
        )
        with e.repo.connection_scope() as c:
            c.execute(
                "UPDATE authorization_admin.context_call_requests "
                "SET record=jsonb_set(record,%s,%s) WHERE context_id=%s",
                (path, Jsonb("0" * 64), e.original["contextId"]),
            )
    elif changed == "revoked":
        with e.repo.connection_scope() as c:
            binding = e.business_owner.work(c, e.context, root)
            c.execute(
                "INSERT INTO authorization_admin.owned_business_revocations "
                "(admission_id,actor_id,reason_code) VALUES(%s,%s,%s)",
                (binding.admission_id, e.context.principal_id, "USER_REQUESTED"),
            )
    for historical in (False, True):
        with e.repo.connection_scope() as c, pytest.raises(AuthorityError):
            e.business_owner.work(
                c, context, root, source_digest=source_digest, history=historical
            )
    assert len(e.calls) == e.business_model_call_count
    assert len(e.initial_calls) == 1


@pytest.mark.parametrize("owned_ready", ["SOURCE_SUCCESSOR"], indirect=True)
@pytest.mark.parametrize("owned_created", ["EXPIRED_CALL"], indirect=True)
def test_mixed_retained_result_activates_same_problem_with_owner_criteria(
    owned_created,
):
    from owned_business_planning_support import activate_created

    e = activate_created(owned_created)
    assert e.business_detail["problem"]["current_state"] == "ACTIVE"
    assert (
        e.business_criteria["revision"]["business_problem_id"]
        == (e.created["revision"]["business_problem_id"])
    )
    assert len(e.calls) == e.business_model_call_count
    assert len(e.initial_calls) == 1
