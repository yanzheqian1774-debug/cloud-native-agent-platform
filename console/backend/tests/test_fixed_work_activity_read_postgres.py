# ruff: noqa: F401,F811,E501 -- Reuse isolated original owner fixtures.
"""Real browser session, immutable work and original issuer, isolated DB only."""

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
import test_fixed_work_cycle_host_postgres as host
from agent_console.authority_configuration import (
    CredentialConfiguration,
    RequestabilityRule,
    StaticGrant,
)
from agent_console.authority_contracts import CredentialId, ExactGrant, GrantSource
from agent_console.browser_session_application import (
    BrowserSessionPolicy,
    BrowserSessionService,
    StaticGenerationAuthenticator,
)
from agent_console.execution_domain import ScopeIdentity
from agent_console.fixed_work_activity_read import FixedWorkActivityReadOwner
from agent_console.team_definition import TeamMember, TeamRevision
from agent_console.team_definition_postgres import PostgresTeamDefinitionRepository
from agent_console.workbench_fixed_work import FixedWorkAuthoringOwner
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from psycopg.rows import dict_row
from test_fixed_work_cycle_host_postgres import case, repository, services


@pytest.fixture
def automation(repository, case, services, tmp_path, request, monkeypatch):
    original = host.resources.StaticAuthorityGeneration

    def generation(*args, **kwargs):
        value = original(*args, **kwargs)
        source = case.p.source_snapshot
        members = (
            ExactGrant("TEAM", "READ", "team:fixed-team:r"),
            ExactGrant(
                "BUSINESS_PROBLEM",
                "READ",
                "business-problem:" + case.p.semantics.target.problem.resource_id,
            ),
            ExactGrant(
                "KNOWLEDGE",
                "READ_RESOURCE",
                "knowledge:prepared-resource:"
                + source.resource_id
                + ":"
                + source.revision_id,
            ),
        )
        viewer = CredentialConfiguration(
            CredentialId("viewer"),
            hashlib.sha256(b"viewer-secret").hexdigest(),
            "human:fixed-viewer",
            value.credentials[0].scope,
            datetime.now(UTC) + timedelta(hours=1),
            GrantSource.BROWSER_BOOTSTRAP,
            tuple(StaticGrant(g, GrantSource.BROWSER_BOOTSTRAP) for g in members),
        )
        return replace(
            value,
            credentials=(*value.credentials, viewer),
            requestability=(
                *value.requestability,
                RequestabilityRule(
                    "EXECUTION",
                    "READ",
                    "governed-execution:prepared:",
                    "RESOURCE_PREPARATION",
                ),
                RequestabilityRule(
                    "EVIDENCE",
                    "READ_REFERENCE",
                    "evidence-reference:prepared:",
                    "RESOURCE_PREPARATION",
                ),
            ),
        )

    monkeypatch.setattr(host.resources, "StaticAuthorityGeneration", generation)
    gen = host.automation.__wrapped__(
        repository, case, services, tmp_path, request, monkeypatch
    )
    a = next(gen)
    try:
        yield a
    finally:
        gen.close()


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
def test_real_viewer_read_policy_issuer_replay_and_scope_refusal(
    automation, monkeypatch, tmp_path
):
    a = automation
    teams = PostgresTeamDefinitionRepository(a.repository.pool)
    teams.migrate(host.M / "0051_team_definition.sql")
    original_save = host.drafts.save
    team_holder = {}

    def save(c, scope, actor, data, team, *args):
        # Test-only exact team fixture. The real configuration/reader still verifies
        # the immutable team record and digest; no product authority is bypassed.
        revision = TeamRevision(
            ScopeIdentity(*scope),
            "fixed-team",
            "r",
            "Fixed team",
            "Read fixed results",
            "human:fixed-viewer",
            (TeamMember("test-member", "r", "a" * 64, "test fixture"),),
        )
        teams.save(
            c,
            revision,
            expected_version=0,
            command_id="team-fixture",
            actor_id="human:fixture",
            decision_id="fixture-team-create",
        )
        team_holder["value"] = revision
        return original_save(
            c, scope, actor, data, {**team, "digest": revision.content_digest}, *args
        )

    monkeypatch.setattr(host.drafts, "save", save)
    from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
    from agent_console.execution_preparation import ArtifactDocument
    from agent_console.execution_preparation_postgres import PreparedExecutionStore

    original_unknown = PostgresExecutionAuthorityRepository.record_uncertain

    def record_unknown(repository, claim, observation):
        with a.repository.pool.connection() as c, c.transaction():
            run = c.execute(
                "SELECT workflow_run_id FROM execution_authority.run_preparations"
            ).fetchone()["workflow_run_id"]
            preparation, progress = PreparedExecutionStore(c).read(
                a.e.scope.namespace, a.e.scope.security_domain, run
            )
            task = next(t for t in progress.tasks if t.state == "RUNNING")
            definition = next(
                t for t in preparation.semantics.tasks if t.task_id == task.task_id
            )
            content = "isolated retained diagnostic artifact, not a successful outcome"
            from agent_console.prepared_skill_invocation import planned_outputs

            artifact_id = planned_outputs(preparation, progress)[0]["artifactId"]
            PreparedExecutionStore(c).append_artifact(
                a.e.scope.namespace,
                a.e.scope.security_domain,
                run,
                ArtifactDocument(
                    artifact_id=artifact_id,
                    task_id=task.task_id,
                    attempt_id=task.attempt_id,
                    kind=definition.output_kind,
                    schema_version="test.v1",
                    content=content,
                    digest=hashlib.sha256(content.encode()).hexdigest(),
                ),
            )
        return original_unknown(repository, claim, observation)

    monkeypatch.setattr(
        PostgresExecutionAuthorityRepository, "record_uncertain", record_unknown
    )
    host.test_host_restarts_saved_event_through_existing_owners(
        a, monkeypatch, "UNKNOWN"
    )
    # Original UNKNOWN is kept; read access must not START/retry/alter it.
    policy_work = a.automation.policy.workScopes[0]
    a.automation.policy = a.automation.policy.model_copy(
        update={
            "workScopes": (
                policy_work,
                policy_work.model_copy(update={"subject": "human:fixed-viewer"}),
            )
        }
    )
    sessions = BrowserSessionService(
        a.authority,
        StaticGenerationAuthenticator(a.gen, source=GrantSource.BROWSER_BOOTSTRAP),
        BrowserSessionPolicy(
            timedelta(minutes=5),
            timedelta(minutes=30),
            timedelta(hours=1),
            timedelta(minutes=10),
        ),
        csrf_signing_key=b"v" * 32,
        recovery_epoch=1,
    )
    secret = sessions.create_session(sessions.issue_login_nonce(), "viewer-secret")
    _, context = sessions.authenticate_session(secret.value)
    team = team_holder["value"]
    policy = dict(
        schemaVersion="fixed-work-authoring-policy.v1",
        policyId="read-fixture",
        enabled=True,
        expiresAt=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        scopes=[
            dict(
                tenantId=context.scope.tenant_id,
                securityDomain=context.scope.security_domain,
                subjectId=context.principal_id,
                teamId=team.team_id,
                teamRevisionId=team.revision_id,
                teamDigest=team.content_digest,
                operations=["READ"],
            )
        ],
    )
    path = tmp_path / "read-authoring.json"
    path.write_text(json.dumps(policy))
    path.chmod(0o600)
    owner = FixedWorkActivityReadOwner(
        FixedWorkAuthoringOwner(path, a.automation.grants.clock), a.automation
    )
    with a.repository.pool.connection() as c:
        row = c.execute(
            "SELECT record,digest FROM fixed_work_authoring.revisions"
        ).fetchone()
        before = c.execute(
            "SELECT count(*) n FROM fixed_work_triggers.receipts"
        ).fetchone()["n"]

    def invoke(key="read-once"):
        with a.repository.pool.connection() as c, c.transaction():
            c.row_factory = dict_row
            auth = AuthorizedOwnerAuthority(a.adapter, context, c, 1, ())
            return owner(
                AuthorizedOwnerCall(
                    "PREPARE_FIXED_WORK_ACTIVITY_READ",
                    context,
                    c,
                    {"workDigest": row["digest"], "commandId": key},
                    {
                        "team_id": team.team_id,
                        "team_revision_id": team.revision_id,
                        "work_id": row["record"]["workId"],
                        "revision_id": row["record"]["revisionId"],
                    },
                    {},
                    (),
                    auth,
                    1,
                )
            )

    original_proof = a.automation.proof_grants

    def fail_after_decision(*args):
        original_proof(*args)
        raise RuntimeError("isolated read decision rollback")

    monkeypatch.setattr(a.automation, "proof_grants", fail_after_decision)
    with pytest.raises(RuntimeError, match="read decision rollback"):
        invoke()
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_requests WHERE subject_principal_id=%s",
                (context.principal_id,),
            ).fetchone()["n"]
            == 0
        )
    monkeypatch.setattr(a.automation, "proof_grants", original_proof)
    result = invoke()
    assert result["state"] == "READ_READY"
    assert invoke() == result
    original_decide = a.automation.decide

    def changed_members(call, members, *args, **kwargs):
        return original_decide(call, members[:1], *args, **kwargs)

    monkeypatch.setattr(a.automation, "decide", changed_members)
    from agent_console.authority_contracts import AuthorityError

    with pytest.raises(AuthorityError, match="IDEMPOTENCY_PAYLOAD_MISMATCH"):
        invoke()
    monkeypatch.setattr(a.automation, "decide", original_decide)
    from agent_console.workbench_business_problem import OwnerPrincipal
    from agent_console.workbench_prepared_execution import PreparedExecutionOwner

    with a.repository.pool.connection() as c, c.transaction():
        auth = AuthorizedOwnerAuthority(a.adapter, context, c, 1, ())
        auth.require(
            OwnerPrincipal(
                context.principal_id,
                context.scope.tenant_id,
                context.scope.security_domain,
            ),
            "EXECUTION",
            "READ",
            "governed-execution:prepared:" + result["preparationDigest"],
        )
        read = PreparedExecutionOwner()(
            AuthorizedOwnerCall(
                "READ_PREPARED_EXECUTION",
                context,
                c,
                {},
                {"digest": result["preparationDigest"]},
                {},
                (),
                auth,
                1,
            )
        )
        assert read["artifacts"][0]["contentAccess"] == "AUTHORIZED"
        assert "not a successful outcome" in read["artifacts"][0]["content"]
        assert read["progress"]["state"] == "RECOVERY_REQUIRED"
    with a.repository.pool.connection() as c:
        assert (
            c.execute("SELECT count(*) n FROM fixed_work_triggers.receipts").fetchone()[
                "n"
            ]
            == before
        )
        rows = c.execute(
            "SELECT owner,action FROM authorization_admin.grant_request_members m JOIN authorization_admin.grant_requests r USING(request_id) WHERE r.subject_principal_id=%s",
            (context.principal_id,),
        ).fetchall()
        assert {(r["owner"], r["action"]) for r in rows} == {
            ("EXECUTION", "READ"),
            ("EVIDENCE", "READ_REFERENCE"),
        }
    a.automation.policy = a.automation.policy.model_copy(
        update={"workScopes": (policy_work,)}
    )
    with pytest.raises(Exception, match="WORK_SCOPE_DENIED"):
        invoke("scope-refused")

    a.automation.policy = a.automation.policy.model_copy(
        update={
            "workScopes": (
                policy_work,
                policy_work.model_copy(update={"subject": context.principal_id}),
            )
        }
    )
    sessions.logout(secret.value, actor_id=context.principal_id)
    from agent_console.authority_contracts import AuthorityError

    with pytest.raises(AuthorityError):
        invoke("after-logout")
