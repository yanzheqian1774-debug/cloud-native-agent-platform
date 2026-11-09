"""D12 draft role admission against disposable PostgreSQL, no provider calls."""

from dataclasses import replace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.draft_assistance import AuthorizationState
from agent_console.draft_assistance_authorization import (
    GrantAdministrationDraftAuthorization,
)
from agent_console.grant_administration_application import GenerationAuthorizationReader
from test_context_call_admission import env as env
from test_development_administrator import URL, login
from test_development_administrator import setup as setup

pytestmark = pytest.mark.skipif(not URL, reason="exclusive PostgreSQL required")


def test_admin_draft_admission_is_current_audited_and_has_no_resource_requests(
    env, setup
):
    repo, generation, sessions, _reader = setup
    _, context = sessions.authenticate_session(login(sessions, "devadmin").value)
    invocation = env.draft.begin(
        context, key="admin-unseen", content="new work order question"
    ).invocation
    authorization = GrantAdministrationDraftAuthorization(
        env.admission.delegation.grants, None
    )
    authorization.context_admission = env.admission
    with repo.connection_scope() as c:
        before = c.execute(
            "SELECT count(*) n FROM authorization_admin.grant_requests"
        ).fetchone()["n"]
    result = authorization.resolve(context, invocation)
    assert result.state is AuthorizationState.ALLOWED
    assert result.request_decision_id.startswith("development-role:")
    assert authorization.resolve(context, invocation) == result
    state = env.admission.read(context, invocation.context_id)
    assert state["status"] == "ACTIVE"
    assert state["request"]["subject_id"] == context.principal_id
    assert state["decision"]["issuer_id"] == "policy:development-administrator:D12"
    assert state["decision"]["record"]["budget_limits_unchanged"] is True
    assert state["request"]["record"]["configuration"] == env.limits
    with repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_requests"
            ).fetchone()["n"]
            == before
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.context_call_decisions "
                "WHERE context_id=%s",
                (invocation.context_id,),
            ).fetchone()["n"]
            == 1
        )
        c.execute(
            "INSERT INTO authorization_admin.context_call_revocations"
            "(admission_id,actor_id) VALUES(%s,%s)",
            (state["decision"]["admission_id"], context.principal_id),
        )
    with pytest.raises(AuthorityError, match="CONTEXT_ADMISSION_REQUIRED"):
        env.admission.prepare(context, invocation)
    disabled = replace(generation, development_administrator=False)
    env.admission.delegation.grants.authorization = GenerationAuthorizationReader(
        disabled, repo, repo, recovery_epoch=1
    )
    with pytest.raises(AuthorityError, match="CONTEXT_ADMISSION_SCOPE_DENIED"):
        env.admission.prepare(context, invocation)
