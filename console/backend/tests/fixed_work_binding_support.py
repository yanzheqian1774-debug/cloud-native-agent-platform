"""Real authoring/binding owners on the retained-understanding fixture.

The team and pre-message handoff are immutable setup records. Their creation
paths are tested separately; no authorization or source reader is replaced.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from agent_console import fixed_work_authoring_postgres as authoring_store
from agent_console import fixed_work_sources_postgres as source_store
from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import ExactGrant
from agent_console.digital_employee_definition import digest
from agent_console.execution_domain import ScopeIdentity
from agent_console.grant_administration_application import (
    GrantDecisionCommand,
    GrantRequestCommand,
)
from agent_console.private_conversation import PrivateConversations
from agent_console.team_definition_postgres import PostgresTeamDefinitionRepository
from agent_console.workbench_fixed_work import FixedWorkAuthoringOwner
from agent_console.workbench_fixed_work_source import FixedWorkSourceOwner
from fastapi.encoders import jsonable_encoder
from psycopg.types.json import Jsonb
from test_fixed_work_authoring import body
from test_local_accounts_postgres import login
from test_team_definition import team


def setup(e, tmp_path, state, instruction):
    root = Path(__file__).parents[1] / "migrations"
    scope = e.context.scope
    identity = ScopeIdentity(scope.tenant_id, scope.security_domain)
    revision = replace(team(), scope=identity)
    repository = PostgresTeamDefinitionRepository(e.repo.pool)
    repository.migrate(root / "0051_team_definition.sql")
    with e.repo.connection_scope() as c:
        repository.save(
            c,
            revision,
            expected_version=0,
            command_id="source-team",
            actor_id=e.context.principal_id,
            decision_id="fixture-team-setup",
        )
        authoring_store.migrate(c)
        source_store.migrate(c)
    members = (
        ExactGrant("TEAM", "READ", f"team:{revision.team_id}:{revision.revision_id}"),
        ExactGrant("TEAM", "REVISE", f"team:{revision.team_id}:aggregate"),
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
            "RESOURCE_PREPARATION", members, "fixed-source-team-read-revise"
        ),
    )
    _, admin = e.routing_sessions.authenticate_session(
        login(e.routing_sessions, "devadmin").value
    )
    decision = grants.decide_request(
        admin,
        GrantDecisionCommand(
            pending.request_id,
            True,
            "ISOLATED_READ",
            "TICKET",
            "source-binding-test",
            None,
            datetime.now(UTC) + timedelta(hours=1),
            "fixed-source-team-decision",
        ),
    )
    path = tmp_path / "fixed-authoring.json"
    path.write_text(
        json.dumps(
            dict(
                schemaVersion="fixed-work-authoring-policy.v1",
                policyId="fixed-source-test",
                enabled=True,
                expiresAt=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                scopes=[
                    dict(
                        tenantId=scope.tenant_id,
                        securityDomain=scope.security_domain,
                        subjectId=e.context.principal_id,
                        teamId=revision.team_id,
                        teamRevisionId=revision.revision_id,
                        teamDigest=revision.content_digest,
                        operations=["READ", "SAVE"],
                    )
                ],
            )
        )
    )
    path.chmod(0o600)
    authoring = FixedWorkAuthoringOwner(path, lambda: datetime.now(UTC))
    owner = FixedWorkSourceOwner(authoring, e.business_owner, e.business_repository)
    owner.conversations = PrivateConversations(e.repo.pool.conninfo, None)
    route = dict(
        team_id=revision.team_id,
        team_revision_id=revision.revision_id,
        work_id="work:1",
        revision_id="revision:1",
    )
    authority = e.draft.authorization.owner_authorization

    def invoke(operation, payload=None, *, context=None, fail=False):
        def handle(call):
            result = (authoring if operation == "SAVE_FIXED_WORK_DRAFT" else owner)(
                call
            )
            if fail:
                raise RuntimeError("after-binding-rollback")
            return result

        return authority.execute(
            context or e.context,
            members,
            operation=operation,
            payload=payload or {},
            path=route,
            query={},
            handler=handle,
        )

    saved = invoke("SAVE_FIXED_WORK_DRAFT", {**body(), "instruction": instruction})
    work = dict(resource_id="work:1", revision_id="revision:1", digest=saved["digest"])
    with e.repo.connection_scope() as c:
        # Fixture represents the already-tested earlier empty-conversation handoff.
        source_store.append(
            c,
            (scope.tenant_id, scope.security_domain),
            "handoffs",
            dict(
                schemaVersion="fixed-work-conversation.v1",
                work=work,
                team=saved["draft"]["team"],
                subjectId=e.context.principal_id,
                conversationId=e.conv,
                commandId="source-handoff",
                instructionDigest=digest(instruction),
                mode="TARGET_REVIEW_ONLY",
                executionEnabled=False,
            ),
        )
        c.execute(
            "UPDATE private_conversation.journeys SET state=%s WHERE "
            "tenant_id=%s AND security_domain=%s AND conversation_id=%s",
            (
                Jsonb(jsonable_encoder(state)),
                scope.tenant_id,
                scope.security_domain,
                e.conv,
            ),
        )
    return invoke, saved, grants, decision
