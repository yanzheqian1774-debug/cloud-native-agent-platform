"""323 controlled PostgreSQL continuity; never touches deployment credentials."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from agent_console.authority_contracts import AuthorityError, ControlState
from agent_console.authority_foundation import (
    ActivationBarrier,
    AuthorityGenerationController,
    AuthorityReadiness,
)
from agent_console.authority_recovery import HostControlRecord, HostRecoveryControl
from agent_console.task_delegation import active
from agent_console.task_development import revise
from agent_console.task_identity_continuity import (
    ContinuityApproval,
    approve,
    preflight,
    revoke,
)
from test_task_delegation import assembled as assembled
from test_task_delegation import env as env
from test_task_delegation import repository as repository
from test_task_delegation import submit
from test_task_development import planning, setup


def rotate(e, tmp_path, *, revoked=False, policy_changed=False):
    old = e.grants.generation
    extra = tuple(
        replace(
            c,
            credential_id=str(c.credential_id) + "-new",
            credential_sha256=hashlib.sha256(
                (str(c.principal_id) + "-new-secret").encode()
            ).hexdigest(),
        )
        for c in old.credentials
    )
    candidate = replace(
        old,
        generation=old.generation + 1,
        digest="e" * 64,
        credentials=old.credentials + extra,
        policy_version="changed" if policy_changed else old.policy_version,
        credential_revocation_tombstones=frozenset({"credential-reader"})
        if revoked
        else old.credential_revocation_tombstones,
    )
    control = HostRecoveryControl(tmp_path / "controlled-transition.json")
    control.replace(
        HostControlRecord(
            control_epoch=1,
            recovery_epoch=1,
            state=ControlState.ACTIVE,
            database_fingerprint="controlled-db",
            generation=old.generation,
            generation_digest=old.digest,
            operator_id="controlled-operator",
        )
    )
    controller = AuthorityGenerationController(
        ActivationBarrier(old),
        e.service.repository,
        control,
        AuthorityReadiness(old.generation, old.digest, 1, "controlled-db"),
    )
    controller.activate(
        candidate,
        control_epoch=2,
        operator_id="controlled-operator",
        now=datetime.now(UTC),
    )
    # Response-loss replay: same candidate does not append another transition.
    controller.activate(
        candidate,
        control_epoch=2,
        operator_id="controlled-operator",
        now=datetime.now(UTC),
    )
    e.grants._generation_provider = lambda: candidate
    e.grants.authorization._generation_provider = lambda: candidate
    e.sessions.authenticator._generation_provider = lambda: candidate
    for name in ("reader", "approver", "other"):
        secret = e.sessions.create_session(
            e.sessions.issue_login_nonce(), f"human:{name}-new-secret"
        )
        _, e.contexts[name] = e.sessions.authenticate_session(secret.value)
    return candidate


def prepared(e, tmp_path, **kw):
    identity, development = setup(e)
    revise(e.service, e.contexts["approver"], identity, development)
    original_request = submit(e)
    e.service.authorize(e.contexts["reader"], identity, original_request.request_id)
    budget, quote, claim = planning(e, identity)
    with e.service.repository.connection_scope() as c:
        before = c.execute(
            "SELECT * FROM authorization_admin.task_delegations WHERE delegation_id=%s",
            (identity,),
        ).fetchone()
        reserved = c.execute(
            "SELECT * FROM draft_provider_budget.reservations"
        ).fetchall()
    rotate(e, tmp_path, **kw)
    info = preflight(e.service, e.contexts["approver"], identity)
    spec = ContinuityApproval(
        original_digest=info["original_digest"],
        transition_id=info["transition"]["transition_id"],
        transition_digest=info["transition"]["digest"],
        binding_digest=info["binding_digest"],
        old_subject_credential_id="credential-reader",
        old_issuer_credential_id="credential-approver",
        subject_credential_id="credential-reader-new",
        issuer_credential_id="credential-approver-new",
        expires_at=datetime.now(UTC) + timedelta(minutes=50),
        idempotency_key="continuity-1",
    )
    return identity, spec, before, reserved, budget, quote, claim, original_request


def test_independent_append_only_replay_preserves_unknown_and_grants(env, tmp_path):
    e = env
    identity, spec, before, reserved, *_ = prepared(e, tmp_path)
    with (
        e.service.repository.connection_scope() as c,
        pytest.raises(AuthorityError, match="INACTIVE"),
    ):
        active(c, identity)
    with pytest.raises(AuthorityError, match="SELF_APPROVAL"):
        approve(e.service, e.contexts["reader"], identity, spec)
    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(
            pool.map(
                lambda _: approve(e.service, e.contexts["approver"], identity, spec),
                range(2),
            )
        )
    assert records[0] == records[1]
    with e.service.repository.connection_scope() as c:
        row, _ = active(c, identity)
        assert row["generation"] == before["generation"] == 1
        assert row["_continuity"]["generation"] == 2
        assert (
            c.execute(
                "SELECT * FROM authorization_admin.task_delegations "
                "WHERE delegation_id=%s",
                (identity,),
            ).fetchone()
            == before
        )
        assert (
            c.execute("SELECT * FROM draft_provider_budget.reservations").fetchall()
            == reserved
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM "
                "authorization_admin.task_identity_transitions"
            ).fetchone()["n"]
            == 1
        )
    # The former delegation grant cannot become effective under the new credential.
    assert not e.grants.authorization.has_current_grant(
        e.contexts["reader"],
        submit(e).members[0],
        now=datetime.now(UTC),
        generation=2,
        recovery_epoch=1,
    )
    with pytest.raises(AuthorityError, match="CONFLICT"):
        approve(
            e.service,
            e.contexts["approver"],
            identity,
            spec.model_copy(
                update={"expires_at": spec.expires_at + timedelta(seconds=1)}
            ),
        )
    revoke(e.service, e.contexts["approver"], identity, records[0]["continuity_id"])
    with (
        e.service.repository.connection_scope() as c,
        pytest.raises(AuthorityError, match="INACTIVE"),
    ):
        active(c, identity)


@pytest.mark.parametrize(
    "change",
    [
        {"original_digest": "a" * 64},
        {"binding_digest": "a" * 64},
        {"transition_digest": "a" * 64},
        {"subject_credential_id": "credential-other-new"},
        {"old_subject_credential_id": "credential-other"},
        {"issuer_credential_id": "credential-reader-new"},
        {"predecessor_digest": "a" * 64},
        {"expires_at": datetime(2000, 1, 1, tzinfo=UTC)},
        {"expires_at": datetime(2099, 1, 1, tzinfo=UTC)},
    ],
)
def test_mismatch_expiry_and_stale_predecessor_fail_closed(env, tmp_path, change):
    identity, spec, *_ = prepared(env, tmp_path)
    with pytest.raises(AuthorityError):
        approve(
            env.service,
            env.contexts["approver"],
            identity,
            spec.model_copy(update=change),
        )
    with env.service.repository.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM "
                "authorization_admin.task_identity_continuities"
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize("change", [{"revoked": True}, {"policy_changed": True}])
def test_revoked_identity_and_changed_authority_policy_cannot_continue(
    env, tmp_path, change
):
    identity, spec, *_ = prepared(env, tmp_path, **change)
    with pytest.raises(AuthorityError):
        approve(env.service, env.contexts["approver"], identity, spec)


def test_concurrent_distinct_signatures_require_one_chain_head(env, tmp_path):
    identity, spec, *_ = prepared(env, tmp_path)

    def sign(key):
        try:
            return approve(
                env.service,
                env.contexts["approver"],
                identity,
                spec.model_copy(update={"idempotency_key": key}),
            )
        except AuthorityError as e:
            return e.reason_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(sign, ["one", "two"]))
    assert sum(isinstance(x, dict) for x in results) == 1
    assert "TASK_CONTINUITY_PREDECESSOR_CONFLICT" in results


def test_fresh_exact_request_is_required_and_expiry_fences_it(env, tmp_path):
    from agent_console.grant_administration_application import GrantRequestCommand

    identity, spec, *_ = prepared(env, tmp_path)
    record = approve(env.service, env.contexts["approver"], identity, spec)
    member = submit(env).members[0]
    request = env.grants.submit_request(
        env.contexts["reader"],
        GrantRequestCommand(
            purpose="PROBLEM_DRAFT_ASSISTANCE",
            requested_grants=(member,),
            idempotency_key="current-generation-exact-request",
        ),
    )
    env.service.authorize(env.contexts["reader"], identity, request.request_id)
    assert env.grants.authorization.has_current_grant(
        env.contexts["reader"],
        member,
        now=datetime.now(UTC),
        generation=2,
        recovery_epoch=1,
    )
    with env.service.repository.connection_scope() as c:
        grants = c.execute(
            "SELECT expires_at FROM authorization_admin.grants WHERE request_id=%s",
            (request.request_id,),
        ).fetchall()
        assert grants and all(g["expires_at"] <= record["expires_at"] for g in grants)
        with pytest.raises(AuthorityError, match="INACTIVE"):
            from agent_console.task_identity_continuity import effective

            row, _ = active(c, identity)
            generation = c.execute(
                "SELECT * FROM authorization_admin.active_generation"
            ).fetchone()
            effective(c, row, generation, record["expires_at"])
    revoke(env.service, env.contexts["approver"], identity, record["continuity_id"])
    assert not env.grants.authorization.has_current_grant(
        env.contexts["reader"],
        member,
        now=datetime.now(UTC),
        generation=2,
        recovery_epoch=1,
    )
    with pytest.raises(AuthorityError, match="REVOKED"):
        approve(
            env.service,
            env.contexts["approver"],
            identity,
            spec.model_copy(
                update={
                    "idempotency_key": "after-revocation",
                    "predecessor_digest": record["digest"],
                }
            ),
        )


def test_revoked_exact_grant_cannot_be_restored_by_new_identity(env, tmp_path):
    from agent_console.grant_administration_application import (
        GrantRequestCommand,
        GrantRevocationCommand,
    )
    from agent_console.task_identity_continuity import require_unrevoked_member

    identity, development = setup(env)
    revise(env.service, env.contexts["approver"], identity, development)
    request = submit(env)
    env.service.authorize(env.contexts["reader"], identity, request.request_id)
    with env.service.repository.connection_scope() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE request_id=%s",
            (request.request_id,),
        ).fetchone()["grant_id"]
    env.grants.revoke_grant(
        env.contexts["reader"],
        GrantRevocationCommand(
            grant, "USER_REQUEST", "surrender-before-rotation", True
        ),
    )
    rotate(env, tmp_path)
    info = preflight(env.service, env.contexts["approver"], identity)
    spec = ContinuityApproval(
        original_digest=info["original_digest"],
        binding_digest=info["binding_digest"],
        transition_id=info["transition"]["transition_id"],
        transition_digest=info["transition"]["digest"],
        old_subject_credential_id="credential-reader",
        old_issuer_credential_id="credential-approver",
        subject_credential_id="credential-reader-new",
        issuer_credential_id="credential-approver-new",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        idempotency_key="revoked-permission-remains-revoked",
    )
    approve(env.service, env.contexts["approver"], identity, spec)
    with (
        env.service.repository.connection_scope() as c,
        pytest.raises(AuthorityError, match="REVOKED_PERMISSION"),
    ):
        row, _ = active(c, identity)
        require_unrevoked_member(c, row, request.members[0])
    fresh = env.grants.submit_request(
        env.contexts["reader"],
        GrantRequestCommand(
            "PROBLEM_DRAFT_ASSISTANCE", request.members, "fresh-revoked"
        ),
    )
    with pytest.raises(AuthorityError, match="REVOKED_PERMISSION"):
        env.service.authorize(env.contexts["reader"], identity, fresh.request_id)


@pytest.mark.parametrize("operation", ["revoke", "stop"])
def test_owner_read_then_active_and_revocation_share_one_lock_order(
    env, tmp_path, operation
):
    from threading import Event
    from time import monotonic

    from agent_console.grant_administration_application import GrantRequestCommand

    identity, spec, *_ = prepared(env, tmp_path)
    record = approve(env.service, env.contexts["approver"], identity, spec)
    member = submit(env).members[0]
    request = env.grants.submit_request(
        env.contexts["reader"],
        GrantRequestCommand("PROBLEM_DRAFT_ASSISTANCE", (member,), "owner-lock-order"),
    )
    env.service.authorize(env.contexts["reader"], identity, request.request_id)
    read_ready, revoke_started = Event(), Event()

    def owner():
        with env.service.repository.connection_scope() as c:
            assert env.grants.authorization.has_current_grants(
                env.contexts["reader"],
                (member,),
                now=datetime.now(UTC),
                generation=2,
                recovery_epoch=1,
                connection=c,
            ) == (True,)
            read_ready.set()
            assert revoke_started.wait(5)
            deadline = monotonic() + 5
            waiting = False
            while monotonic() < deadline:
                waiting = c.execute(
                    "SELECT 1 FROM pg_locks WHERE locktype='advisory' "
                    "AND objid=3230028 AND NOT granted AND pid<>pg_backend_pid() "
                    "AND database=(SELECT oid FROM pg_database "
                    "WHERE datname=current_database())"
                ).fetchone()
                if waiting:
                    break
                Event().wait(0.02)
            assert waiting, "revocation must wait at governance, before control locks"
            # This later owner binding used to risk control -> governance inversion.
            assert (
                active(c, identity)[0]["_continuity"]["continuity_id"]
                == record["continuity_id"]
            )
        return "committed-before-revocation"

    def revoker():
        assert read_ready.wait(5)
        revoke_started.set()
        if operation == "revoke":
            revoke(
                env.service, env.contexts["approver"], identity, record["continuity_id"]
            )
        else:
            from agent_console.task_development import DevelopmentStop, stop

            stop(
                env.service,
                env.contexts["approver"],
                identity,
                DevelopmentStop(reason="PAUSED"),
            )
        return "revoked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(owner), pool.submit(revoker)
        assert a.result(10) == "committed-before-revocation"
        assert b.result(10) == "revoked"
