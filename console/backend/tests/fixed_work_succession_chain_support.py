"""Before-message real source owners; Team records are controlled owner fixtures.

The separate ordinary BFF test exercises complete Team creation. This fixture
uses the original immutable Team repository and formal grant request/decision,
then original authoring/handoff/succession before any message in the target chat.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from agent_console import fixed_work_authoring_postgres as authoring_store
from agent_console import fixed_work_sources_postgres as sources
from agent_console import fixed_work_succession_postgres as succession
from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import ExactGrant
from agent_console.execution_domain import ScopeIdentity
from agent_console.fixed_work_authoring import AuthoringPolicy
from agent_console.grant_administration_application import (
    GrantDecisionCommand,
    GrantRequestCommand,
)
from agent_console.private_conversation import PrivateConversations
from agent_console.team_definition_postgres import PostgresTeamDefinitionRepository
from agent_console.workbench_fixed_work import FixedWorkAuthoringOwner
from agent_console.workbench_fixed_work_source import FixedWorkSourceOwner
from agent_console.workbench_fixed_work_succession import FixedWorkSuccessionOwner
from test_fixed_work_authoring import body
from test_local_accounts_postgres import login
from test_team_definition import team


def before_message(e, tmp_path, sessions):
    created = e.post(
        "/conversations",
        {"title": "版本接续原会话", "idempotencyKey": "succession-before-target"},
    )
    assert created.status_code == 200, created.text
    e.conv = created.json()["result"]["conversation_id"]
    scope = (e.context.scope.tenant_id, e.context.scope.security_domain)
    old = replace(team(), scope=ScopeIdentity(*scope))
    new = replace(
        old,
        revision_id="team-revision:2",
        predecessor_revision_id=old.revision_id,
        goal="新版本合成材料核对",
    )
    repository = PostgresTeamDefinitionRepository(e.repo.pool)
    repository.migrate(
        Path(__file__).parents[1] / "migrations/0051_team_definition.sql"
    )
    with e.repo.connection_scope() as c:
        repository.save(
            c,
            old,
            expected_version=0,
            command_id="original-team",
            actor_id=e.context.principal_id,
            decision_id="controlled-team-fixture",
        )
        repository.save(
            c,
            new,
            expected_version=1,
            command_id="new-team",
            actor_id=e.context.principal_id,
            decision_id="controlled-team-fixture",
        )
        authoring_store.migrate(c)
        sources.migrate(c)
        succession.migrate(c)
    members = (
        ExactGrant("TEAM", "READ", f"team:{old.team_id}:{old.revision_id}"),
        ExactGrant("TEAM", "READ", f"team:{new.team_id}:{new.revision_id}"),
        ExactGrant("TEAM", "REVISE", f"team:{old.team_id}:aggregate"),
    )
    grants = e.admission.delegation.grants
    generation = grants.generation
    grants._generation_provider = lambda: replace(
        generation,
        requestability=(
            *generation.requestability,
            *(
                RequestabilityRule(
                    g.owner, g.action, g.exact_resource, "RESOURCE_PREPARATION"
                )
                for g in members
            ),
        ),
    )
    previous = grants.target_validator
    grants.target_validator = SimpleNamespace(
        is_known_exact_target=lambda ctx, g, **kw: (
            g in members or previous.is_known_exact_target(ctx, g, **kw)
        )
    )
    pending = grants.submit_request(
        e.context,
        GrantRequestCommand(
            "RESOURCE_PREPARATION", members, "succession-team-read-revise"
        ),
    )
    _, admin = sessions.authenticate_session(login(sessions, "devadmin").value)
    grants.decide_request(
        admin,
        GrantDecisionCommand(
            pending.request_id,
            True,
            "ISOLATED_READ",
            "TICKET",
            "succession-owner-test",
            None,
            datetime.now(UTC) + timedelta(hours=1),
            "succession-team-decision",
        ),
    )
    path = tmp_path / "source-succession-authoring.json"
    policy = {
        "schemaVersion": "fixed-work-authoring-policy.v1",
        "policyId": "succession-controlled",
        "enabled": True,
        "expiresAt": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "scopes": [
            {
                "tenantId": scope[0],
                "securityDomain": scope[1],
                "subjectId": e.context.principal_id,
                "teamId": t.team_id,
                "teamRevisionId": t.revision_id,
                "teamDigest": t.content_digest,
                "operations": ["READ", "SAVE"],
            }
            for t in (old, new)
        ],
    }
    path.write_text(json.dumps(policy))
    path.chmod(0o600)
    AuthoringPolicy.load(path)
    authoring = FixedWorkAuthoringOwner(path, lambda: datetime.now(UTC))
    source = FixedWorkSourceOwner(authoring, None, None)
    source.conversations = PrivateConversations(e.repo.pool.conninfo, None)
    successor = FixedWorkSuccessionOwner(source)
    route = {
        "team_id": old.team_id,
        "team_revision_id": old.revision_id,
        "work_id": "work:1",
        "revision_id": "revision:1",
    }

    def invoke(operation, payload=None, path=None):
        handler = (
            authoring
            if operation == "SAVE_FIXED_WORK_DRAFT"
            else successor
            if "SUCCESSION" in operation
            else source
        )
        return e.draft.authorization.owner_authorization.execute(
            e.context,
            members,
            operation=operation,
            payload=payload or {},
            path=path or route,
            query={},
            handler=handler,
        )

    saved = invoke("SAVE_FIXED_WORK_DRAFT", {**body(), "instruction": "你好"})
    handoff = invoke(
        "PREPARE_FIXED_WORK_CONVERSATION",
        {
            "conversationId": e.conv,
            "workDigest": saved["digest"],
            "commandId": "original-empty-handoff",
        },
    )
    command = {
        "predecessor": handoff["record"]["work"],
        "predecessorHandoffDigest": handoff["digest"],
        "team": {
            "resource_id": new.team_id,
            "revision_id": new.revision_id,
            "digest": new.content_digest,
        },
        "commandId": "same-original-chat-upgrade",
    }
    diff = invoke("PREVIEW_FIXED_WORK_SUCCESSION", command)
    result = invoke(
        "COMMIT_FIXED_WORK_SUCCESSION",
        {**command, "previewDigest": diff["previewDigest"]},
    )
    work = result["record"]["work"]
    next_route = {
        "team_id": new.team_id,
        "team_revision_id": new.revision_id,
        "work_id": work["resource_id"],
        "revision_id": work["revision_id"],
    }
    assert (
        invoke("READ_FIXED_WORK_SOURCE", path=next_route)["state"]
        == "AWAITING_CONFIRMED_TARGET"
    )
    msg = e.post(
        f"/conversations/{e.conv}/messages",
        {
            "content": "你好",
            "idempotencyKey": "first-after-update",
            "expectedVersion": 0,
        },
    )
    assert msg.status_code == 200, msg.text
    e.message = msg.json()["result"]["identity"]
    (
        e.succession_source,
        e.succession_invoke,
        e.succession_route,
        e.succession_receipt,
    ) = source, invoke, next_route, result


def check_service_source(e, bound):
    """Real current-service authorization reader; controlled static credential.

    This is source readiness only, not a service preparation/dispatch/model call.
    """
    import pytest
    from agent_console import fixed_work_authoring_postgres as store
    from agent_console.authority_configuration import (
        CredentialConfiguration,
        StaticGrant,
    )
    from agent_console.authority_contracts import (
        AuthenticationSource,
        AuthorityError,
        GrantSource,
        TrustedRequestContext,
    )
    from agent_console.fixed_work_bound_policy import (
        BoundServicePlanningPolicy,
        ScheduleWindow,
        compile_windows,
    )
    from agent_console.fixed_work_service_admission import ServicePlanningRegistry
    from agent_console.grant_administration_application import (
        GenerationAuthorizationReader,
    )
    from agent_console.plan_suggestion_domain import ExactReference
    from agent_console.workbench_owner_authorization import WorkbenchOwnerError
    from agent_console.workbench_prepared_resources import reference

    scope = (e.context.scope.tenant_id, e.context.scope.security_domain)
    work = ExactReference.model_validate(e.succession_receipt["record"]["work"])
    now = datetime.now(UTC)
    deadline = now + timedelta(days=7)
    with e.repo.connection_scope() as c:
        saved = store.read(c, scope, work.resource_id, work.revision_id)
    window = ScheduleWindow(notBefore=now, expiresAt=deadline, windowSeconds=60)
    windows = compile_windows(work, saved["record"]["trigger"], window)
    policy = BoundServicePlanningPolicy.model_validate(
        dict(
            schemaVersion="fixed-work-service-planning.v2",
            policyId="succession-source-test",
            enabled=True,
            tenantId=scope[0],
            securityDomain=scope[1],
            subjectId="service:succession-test",
            credentialId="succession-service-credential",
            work=work.model_dump(mode="json"),
            target=bound["preview"]["target"],
            resourceSnapshot={
                "resource_id": "controlled-catalog",
                "revision_id": "r",
                "digest": "c" * 64,
            },
            allowedEventIds=list(windows),
            eventWindows=windows,
            profileRevisionId="controlled-profile",
            profileDigest="a" * 64,
            model={
                "resource_id": "controlled-model",
                "revision_id": "r",
                "digest": "d" * 64,
            },
            ledgerId="controlled-unused-ledger",
            maximumInputTokens=100,
            maximumOutputTokens=100,
            expiresAt=deadline,
            sourceBindingDigest=bound["binding"]["digest"],
            scheduleWindow=window.model_dump(mode="json"),
        )
    )
    team = saved["record"]["team"]
    source = bound["preview"]["inputSource"]["source"]
    members = (
        ExactGrant("TEAM", "READ", f"team:{team['teamId']}:{team['revisionId']}"),
        ExactGrant(
            "PLAN", "PREPARE", "plan:prepare:" + policy.target.problem.resource_id
        ),
        ExactGrant("MODEL_GOVERNANCE", "INVOKE_MODEL", policy.model_target),
        ExactGrant(
            "KNOWLEDGE",
            "READ_RESOURCE",
            reference("knowledge", source["resource_id"], source["revision_id"]),
        ),
    )
    original = e.admission.delegation.grants.generation
    credential = CredentialConfiguration(
        policy.credentialId,
        "f" * 64,
        policy.subjectId,
        e.context.scope,
        deadline,
        GrantSource.SERVICE_ONLY,
        tuple(StaticGrant(g, GrantSource.SERVICE_ONLY) for g in members),
    )
    generation = replace(original, credentials=(*original.credentials, credential))
    reader = GenerationAuthorizationReader(generation, e.repo, e.repo, recovery_epoch=1)
    context = TrustedRequestContext(
        policy.subjectId,
        e.context.scope,
        policy.credentialId,
        AuthenticationSource.SERVICE_CREDENTIAL,
        generation.policy_version,
    )
    registry = ServicePlanningRegistry(e.repo, reader, lambda: policy)
    with e.repo.connection_scope() as c:
        before = c.execute(
            "SELECT count(*) n FROM draft_provider_budget.reservations"
        ).fetchone()["n"]
        assert registry._check(c, context, policy)
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == before
        )
    reader._generation_provider = lambda: replace(
        generation,
        credentials=(
            *original.credentials,
            replace(credential, grants=credential.grants[:-1]),
        ),
    )
    with e.repo.connection_scope() as c, pytest.raises(AuthorityError):
        registry._check(c, context, policy)
    reader._generation_provider = lambda: generation
    # The superseded physical predecessor cannot be used by a legacy service policy.
    oldwork = ExactReference.model_validate(
        e.succession_receipt["record"]["predecessor"]
    )
    oldteam = ExactGrant("TEAM", "READ", f"team:{team['teamId']}:team-revision:1")
    reader._generation_provider = lambda: replace(
        generation,
        credentials=(
            *original.credentials,
            replace(
                credential,
                grants=(
                    *credential.grants,
                    StaticGrant(oldteam, GrantSource.SERVICE_ONLY),
                ),
            ),
        ),
    )
    from agent_console.fixed_work_service_policy import ServicePlanningPolicy

    old = policy.model_dump(mode="json")
    old.pop("sourceBindingDigest")
    old.pop("scheduleWindow")
    old.update(
        schemaVersion="fixed-work-service-planning.v1",
        work=oldwork.model_dump(mode="json"),
    )
    old = ServicePlanningPolicy.model_validate(old)
    with (
        e.repo.connection_scope() as c,
        pytest.raises(WorkbenchOwnerError, match="SUPERSEDED"),
    ):
        registry._check(c, context, old)
