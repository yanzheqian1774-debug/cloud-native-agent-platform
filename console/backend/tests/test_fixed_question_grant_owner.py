# ruff: noqa: F401,F811,E501 -- Original isolated owner fixtures.
"""Real GrantAdmin/BrowserSession; question provenance is an explicit anchor fixture.

This tests the independent authority port, not presentation/C1/WAIT composition.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_fixed_work_cycle_host_postgres as host
from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import AuthorityError, GrantSource
from agent_console.browser_session_application import (
    BrowserSessionPolicy,
    BrowserSessionService,
    StaticGenerationAuthenticator,
)
from agent_console.fixed_question_grants import QuestionGrantTargets, issue, member
from agent_console.fixed_question_store import FixedQuestionStore
from agent_console.fixed_question_types import QuestionIdentity
from agent_console.grant_administration_application import GrantRevocationCommand
from agent_console.private_conversation import PrivateConversations
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from test_fixed_work_activity_read_postgres import automation as original_automation
from test_fixed_work_activity_read_postgres import case, repository, services


@pytest.fixture
def automation(repository, case, services, tmp_path, request, monkeypatch):
    original = host.resources.StaticAuthorityGeneration

    def generation(*args, **kwargs):
        value = original(*args, **kwargs)
        return replace(
            value,
            requestability=(
                *value.requestability,
                RequestabilityRule(
                    "EXECUTION",
                    "QUESTION_ANSWER",
                    "governed-execution:question:",
                    "FIXED_QUESTION_ANSWER",
                ),
            ),
        )

    monkeypatch.setattr(host.resources, "StaticAuthorityGeneration", generation)
    fixture = original_automation.__wrapped__(
        repository, case, services, tmp_path, request, monkeypatch
    )
    value = next(fixture)
    targets = value.automation.grants.target_validator
    targets.additional = (*targets.additional, QuestionGrantTargets())
    try:
        yield value
    finally:
        fixture.close()


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
def test_original_issuer_exact_question_grant_replay_and_surrender(automation):
    a = automation
    sessions = BrowserSessionService(
        a.authority,
        StaticGenerationAuthenticator(a.gen, source=GrantSource.BROWSER_BOOTSTRAP),
        BrowserSessionPolicy(
            timedelta(minutes=5),
            timedelta(minutes=30),
            timedelta(hours=1),
            timedelta(minutes=10),
        ),
        csrf_signing_key=b"q" * 32,
        recovery_epoch=1,
    )
    secret = sessions.create_session(sessions.issue_login_nonce(), "viewer-secret")
    _, ctx = sessions.authenticate_session(secret.value)
    with a.authority.connection_scope() as c:
        c.execute(
            (
                Path(__file__).parents[1] / "migrations/0046_private_conversation.sql"
            ).read_text()
        )
        FixedQuestionStore.migrate(c)
    records = PrivateConversations(a.authority.pool.conninfo, lambda *args: None)
    chat = records.create(
        ctx, dict(title="Question grant fixture", idempotencyKey="question-grant")
    )["conversation_id"]
    source = a.e.p.source_snapshot
    identity = QuestionIdentity(
        tenantId=ctx.scope.tenant_id,
        securityDomain=ctx.scope.security_domain,
        conversationId=chat,
        bindingDigest="1" * 64,
        work=source,
        eventId="event",
        receiptDigest="2" * 64,
        preparationDigest=a.e.p.digest,
        runId="controlled-run",
        taskId="task",
        attemptId="attempt",
        commandId="dispatch",
        invocationId="skill",
        questionKey="question",
        questionDigest="3" * 64,
        checkpointDigest="4" * 64,
        sourceSnapshot=source,
        executionSubject="service:question-fixture",
        serviceCredentialId="user-test",
        generation=1,
        recoveryEpoch=1,
    )
    expiry = datetime.now(UTC) + timedelta(minutes=10)
    policy = SimpleNamespace(
        issuerId="service:resource-preparation-policy",
        issuerCredentialId="policy-test",
        expiresAt=expiry,
        grantTTLSeconds=600,
        digest="5" * 64,
    )
    checkpoint = SimpleNamespace(human_expires_at=expiry, authority_expires_at=expiry)

    def invoke(anchor=True):
        with a.authority.connection_scope() as c:
            if anchor:
                FixedQuestionStore(
                    c, (identity.tenantId, identity.securityDomain)
                ).anchor(identity)
            call = AuthorizedOwnerCall(
                "PRESENT_FIXED_QUESTION",
                ctx,
                c,
                {},
                {},
                {},
                (),
                AuthorizedOwnerAuthority(a.adapter, ctx, c, 1, ()),
                1,
                1,
            )
            return issue(call, a.automation, policy, identity, checkpoint)

    with pytest.raises(AuthorityError):
        invoke(False)
    first = invoke()
    assert invoke() == first
    assert a.automation.grants.authorization.has_current_grant(
        ctx, member(identity), now=datetime.now(UTC), generation=1, recovery_epoch=1
    )
    with a.authority.connection_scope() as c:
        rows = c.execute(
            "SELECT owner,action,exact_resource,subject_principal_id FROM authorization_admin.grants WHERE request_id=%s",
            (first[0],),
        ).fetchall()
        assert rows == [
            dict(
                owner="EXECUTION",
                action="QUESTION_ANSWER",
                exact_resource=identity.exact_resource,
                subject_principal_id=ctx.principal_id,
            )
        ]
        before = c.execute(
            "SELECT count(*) n FROM authorization_admin.grant_requests"
        ).fetchone()["n"]
    a.automation.grants.revoke_grant(
        ctx,
        GrantRevocationCommand(
            first[2], "TEST_WITHDRAWAL", "withdraw-answer", surrender=True
        ),
    )
    with pytest.raises(AuthorityError, match=r"DENIED|REVOKED"):
        invoke()
    with a.authority.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_requests"
            ).fetchone()["n"]
            == before
        )
        assert (
            c.execute("SELECT count(*) n FROM fixed_question.answers").fetchone()["n"]
            == 0
        )
