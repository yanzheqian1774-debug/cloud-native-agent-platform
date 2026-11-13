"""Real isolated PostgreSQL admission; no provider calls or deployed authority."""

import json
import os
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.conversation_experience_admission import (
    LEDGER,
    ConversationExperienceAdmission,
    begin_bound,
)
from test_context_call_admission import env  # noqa: F401
from test_local_accounts_postgres import setup  # noqa: F401

pytestmark = pytest.mark.skipif(
    not os.environ.get("AUTHORITY_I1_TEST_DATABASE_URL"),
    reason="exclusive PostgreSQL required",
)


def configure(e, tmp_path, *, expired=False):
    invocation = e.draft.begin(
        e.reviewer, key="experience", content="synthetic review"
    ).invocation
    e.admission.configuration = {
        **e.limits,
        "ledger_id": LEDGER,
        "calls": 20,
        "cost_microusd": 1_000_000,
        "profile_revision_id": invocation.profile_revision_id,
    }
    document = {
        "schemaVersion": "f3-conversation-experience.v1",
        "tenantId": "s5-323-demo",
        "securityDomain": "isolated-real-demo",
        "subjectId": e.reviewer.principal_id,
        "accountId": "local-account:reviewer324",
        "authorizationDigest": "a" * 64,
        "configuration": e.admission.configuration,
        "conversations": {"approved-conversation": "SYNTHETIC_DOCUMENT_REVIEW"},
        "externalWrites": False,
    }
    path = tmp_path / "experience.json"
    path.write_text(json.dumps(document))
    path.chmod(0o600)
    e.admission.experience = ConversationExperienceAdmission(
        path, e.admission.configuration
    )
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO draft_provider_budget.policies "
            "VALUES('s5-323-demo','isolated-real-demo',%s,%s,%s,'USD',20,1000000,0,0,'{}',"
            "now() - (%s * interval '1 hour'))",
            (LEDGER, invocation.profile_revision_id, "b" * 64, 25 if expired else 0),
        )
    owner = SimpleNamespace(
        begin=lambda context, **kw: e.admission.prepare(context, invocation)
    )
    return invocation, owner, path, document


def prepare(e, invocation, owner, conversation="approved-conversation"):
    return begin_bound(
        owner,
        e.reviewer,
        conversation=conversation,
        message_id="actual-user-message",
        key=invocation.scoped_idempotency_key,
    )


def test_ordinary_exact_binding_idempotency_and_revocation(env, tmp_path):  # noqa: F811
    e = env
    invocation, owner, _, _ = configure(e, tmp_path)
    with pytest.raises(AuthorityError, match="CONVERSATION_BINDING_REQUIRED"):
        e.admission.prepare(e.reviewer, invocation)
    with pytest.raises(AuthorityError, match="CONVERSATION_BINDING_REQUIRED"):
        prepare(e, invocation, owner, "another-conversation")
    assert prepare(e, invocation, owner)
    assert prepare(e, invocation, owner)
    assert e.admission.ready(e.reviewer, invocation)
    with e.repo.connection_scope() as c:
        rows = c.execute(
            "SELECT * FROM authorization_admin.context_call_decisions"
        ).fetchall()
        assert len(rows) == 1
        policy = c.execute(
            "SELECT * FROM draft_provider_budget.policies WHERE ledger_id=%s", (LEDGER,)
        ).fetchone()
        assert rows[0]["expires_at"] <= policy["created_at"] + timedelta(hours=24)
        assert (rows[0]["expires_at"] - rows[0]["created_at"]).total_seconds() <= 28800
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )
        c.execute(
            "INSERT INTO authorization_admin.context_call_revocations "
            "(admission_id,actor_id) VALUES(%s,%s)",
            (rows[0]["admission_id"], "operator:test"),
        )
    with pytest.raises(AuthorityError, match="ADMISSION_REQUIRED"):
        prepare(e, invocation, owner)
    assert not e.admission.ready(e.reviewer, invocation)


def test_expired_budget_cannot_restart_window(env, tmp_path):  # noqa: F811
    e = env
    invocation, owner, path, document = configure(e, tmp_path, expired=True)
    with pytest.raises(AuthorityError, match="EXPERIENCE_EXPIRED"):
        prepare(e, invocation, owner)
    # Re-loading/re-writing identical runtime configuration never starts a new day.
    path.write_text(json.dumps(document))
    e.admission.experience = ConversationExperienceAdmission(
        path, e.admission.configuration
    )
    with pytest.raises(AuthorityError, match="EXPERIENCE_EXPIRED"):
        prepare(e, invocation, owner)


def test_policy_change_and_account_disable_close_admission(env, tmp_path):  # noqa: F811
    e = env
    invocation, owner, path, document = configure(e, tmp_path)
    document["authorizationDigest"] = "c" * 64
    path.write_text(json.dumps(document))
    with pytest.raises(AuthorityError, match="POLICY_CHANGED"):
        prepare(e, invocation, owner)
    document["authorizationDigest"] = "a" * 64
    path.write_text(json.dumps(document))
    # A successor cannot substitute a second ledger or increase this allowance.
    for field, value in [
        ("ledger_id", "another-ledger"),
        ("calls", 40),
        ("cost_microusd", 2_000_000),
    ]:
        changed = {
            **document,
            "configuration": {**document["configuration"], field: value},
        }
        path.write_text(json.dumps(changed))
        with pytest.raises(AuthorityError, match="CONFIGURATION_MISMATCH"):
            ConversationExperienceAdmission(path, changed["configuration"])
    path.write_text(json.dumps(document))
    with e.repo.connection_scope() as c:
        c.execute(
            "UPDATE browser_identity.local_accounts SET status='DISABLED',"
            "revision=revision+1 WHERE username='reviewer324'"
        )
    with pytest.raises(AuthorityError, match="ACCOUNT_INACTIVE"):
        prepare(e, invocation, owner)


def test_existing_exact_grants_are_issued_and_replay_does_not_renew(env, tmp_path):  # noqa: F811
    from agent_console.authority_configuration import RequestabilityRule
    from agent_console.draft_assistance import AuthorizationState
    from agent_console.draft_assistance_authorization import (
        GrantAdministrationDraftAuthorization,
        cancel_grant,
        model_grant,
        read_grant,
        request_grant,
    )

    e = env
    invocation, _, _, _ = configure(e, tmp_path)
    invocation = replace(invocation, authorization=None)
    grants = e.admission.delegation.grants
    expected = (
        request_grant(invocation),
        read_grant(invocation),
        cancel_grant(invocation),
        model_grant(invocation),
    )
    generation = replace(
        grants.generation,
        requestability=tuple(
            RequestabilityRule(
                g.owner,
                g.action,
                g.exact_resource,
                "PROBLEM_DRAFT_MODEL_INVOKE"
                if g.owner == "MODEL_GOVERNANCE"
                else "PROBLEM_DRAFT_ASSISTANCE",
            )
            for g in expected
        ),
    )
    grants._generation_provider = lambda: generation
    grants.target_validator = SimpleNamespace(
        is_known_exact_target=lambda context, member, **kw: member in expected
    )
    authorization = GrantAdministrationDraftAuthorization(grants, None)
    authorization.context_admission = e.admission
    owner = SimpleNamespace(
        begin=lambda context, **kw: authorization.resolve(context, invocation)
    )
    first = prepare(e, invocation, owner)
    assert first.state is AuthorizationState.ALLOWED
    with e.repo.connection_scope() as c:
        before = c.execute(
            "SELECT * FROM authorization_admin.grant_decisions ORDER BY decision_id"
        ).fetchall()
    assert len(before) == 2
    assert prepare(e, invocation, owner).state is AuthorizationState.ALLOWED
    with e.repo.connection_scope() as c:
        after = c.execute(
            "SELECT * FROM authorization_admin.grant_decisions ORDER BY decision_id"
        ).fetchall()
    assert before == after


def configure_successor(e, tmp_path, *, allowance_expired=False):
    from pathlib import Path

    from agent_console.provider_budget_allowance import prepare as prepare_allowance
    from test_provider_budget_allowance import document as allowance_document

    invocation, owner, path, document = configure(e, tmp_path, expired=True)
    budget = SimpleNamespace(
        _connection=e.repo.connection_scope,
        migration_path=Path(__file__).parents[1]
        / "migrations/0024_draft_provider_budget.sql",
        profile=e.draft.profile,
        ledger_id=LEDGER,
    )
    allowance = allowance_document(
        budget, calls=100, cost=10_000_000, expired=allowance_expired
    )
    allowance["authorizationDigest"] = document["authorizationDigest"]
    saved = prepare_allowance(budget, allowance)
    e.admission.configuration = {
        **e.admission.configuration,
        "calls": 100,
        "cost_microusd": 10_000_000,
    }
    document.update(
        schemaVersion="f3-conversation-experience.v2",
        allowanceId=saved["allowanceId"],
        configuration=e.admission.configuration,
    )
    path.write_text(json.dumps(document))
    e.admission.experience = ConversationExperienceAdmission(
        path, e.admission.configuration
    )
    return invocation, owner, path, saved


def test_successor_uses_fixed_expiry_after_old_window_and_reload(env, tmp_path):  # noqa: F811
    from datetime import datetime

    e = env
    invocation, owner, path, allowance = configure_successor(e, tmp_path)
    assert prepare(e, invocation, owner)
    with e.repo.connection_scope() as c:
        before = c.execute(
            "SELECT * FROM authorization_admin.context_call_decisions"
        ).fetchall()
        assert len(before) == 1
        assert before[0]["expires_at"] <= datetime.fromisoformat(allowance["expiresAt"])
        row = c.execute(
            "SELECT record FROM authorization_admin.context_call_requests "
            "WHERE context_id=%s",
            (invocation.context_id,),
        ).fetchone()["record"]
        assert row["budget_allowance_id"] == allowance["allowanceId"]
        assert datetime.fromisoformat(
            row["ledger_expires_at"]
        ) == datetime.fromisoformat(allowance["expiresAt"])
    e.admission.experience = ConversationExperienceAdmission(
        path, e.admission.configuration
    )
    assert prepare(e, invocation, owner)
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT * FROM authorization_admin.context_call_decisions"
            ).fetchall()
            == before
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.policies"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )


def test_expired_successor_cannot_open_or_reload(env, tmp_path):  # noqa: F811
    e = env
    invocation, owner, path, _ = configure_successor(
        e, tmp_path, allowance_expired=True
    )
    for _ in range(2):
        with pytest.raises(AuthorityError, match="ALLOWANCE_EXPIRED"):
            prepare(e, invocation, owner)
        e.admission.experience = ConversationExperienceAdmission(
            path, e.admission.configuration
        )
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.context_call_decisions"
            ).fetchone()["n"]
            == 0
        )


def test_legacy_policy_digest_keeps_original_shape(env, tmp_path):  # noqa: F811
    from agent_console.task_delegation import digest

    _, _, _, document = configure(env, tmp_path)
    assert env.admission.experience.policy_digest == digest(document)


def test_history_read_selection_preserves_execution_policy_digest(env, tmp_path):  # noqa: F811
    _, _, path, document = configure(env, tmp_path)
    old = env.admission.experience.policy_digest
    document["historyReadEnabled"] = True
    path.write_text(json.dumps(document))
    selected = ConversationExperienceAdmission(path, env.admission.configuration)
    assert selected.policy_digest == old
    assert selected.history_policy_digest != old
