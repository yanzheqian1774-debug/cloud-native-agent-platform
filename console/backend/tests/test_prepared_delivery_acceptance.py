# ruff: noqa: F401,F811 -- Shared disposable PostgreSQL fixture.
"""Real prepared result/acceptance facts; authority port explicitly controlled."""

import hashlib
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.execution_preparation import (
    ArtifactDocument,
    ExecutionPreparationError,
    ProgressEvent,
)
from agent_console.execution_preparation_postgres import PreparedExecutionStore
from agent_console.prepared_delivery_acceptance import (
    PreparedDeliveryAcceptance,
    migrate,
)
from agent_console.prepared_execution_application import PreparedExecutionApplication
from agent_console.prepared_result_review import PreparedResultReview
from agent_console.prepared_skill_invocation import planned_outputs
from prepared_execution_support import ExactTestAuthority
from psycopg.rows import dict_row
from test_plan_suggestion_v2 import repository
from test_prepared_result_review import setup_case


class Authority:
    denied = None

    def require(self, principal, owner, action, target):
        if (owner, action) == self.denied:
            raise AuthorityError("AUTHORIZATION_REVOKED")
        return SimpleNamespace(decision_id="controlled-exact-delivery-authority")


def delivered(c, p, principal):
    app = PreparedExecutionApplication(c, principal, ExactTestAuthority(p))
    attempt = str(app.queue_attempt(p, "t1-read").attempt.attempt_id)
    store = PreparedExecutionStore(c)
    key = p.namespace, p.security_domain, p.run_id

    def emit(action):
        return store.apply(
            *key,
            ProgressEvent(
                action=action,
                task_id="t1-read",
                attempt_id=attempt,
                evidence_id="delivery-test:" + action,
            ),
            expected_version=store.read(*key)[1].version,
        )

    emit("STARTED")
    identity = planned_outputs(p, store.read(*key)[1])[0]["artifactId"]
    content = '{"synthetic":true,"limitation":"partial delivery"}'
    store.append_artifact(
        *key,
        ArtifactDocument(
            artifact_id=identity,
            task_id="t1-read",
            attempt_id=attempt,
            kind="SOURCE_SNAPSHOT",
            schema_version="synthetic.v1",
            content=content,
            digest=hashlib.sha256(content.encode()).hexdigest(),
        ),
    )
    emit("FAILED")
    emit("FINALIZE_FAILURE")
    PreparedResultReview(c, principal, Authority()).evaluate(p, "delivery-evaluate")


def command(view, key="accept", action="ACCEPT_DELIVERY", **extra):
    return {
        "idempotencyKey": key,
        "action": action,
        "packageDigest": view["packageDigest"],
        "expectedVersion": view["version"],
        "targetEventId": None,
        "reason": "",
        **extra,
    }


def test_accept_retract_immutable_and_read_only_authority(repository):
    p, principal = setup_case(repository)
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        migrate(c)
        migrate(c)
        delivered(c, p, principal)
        authority = Authority()
        owner = PreparedDeliveryAcceptance(c, principal, authority)
        initial = owner.read(p)
        assert initial["status"] == "NOT_RECORDED", initial
        body = command(initial)
        outcome = c.execute(
            "SELECT record FROM product_outcome.outcomes ORDER BY outcome_id"
        ).fetchall()
        receipt = owner.decide(p, body)
        assert owner.decide(p, body) == receipt
        assert owner.read(p)["status"] == "ACCEPTED"
        authority.denied = ("EXECUTION", "ACCEPT_DELIVERY")
        assert owner.read(p)["canAccept"] is False
        with pytest.raises(AuthorityError):
            owner.decide(p, body)
        authority.denied = None
        other = SimpleNamespace(**{**vars(principal), "principal_id": "human:other"})
        assert (
            PreparedDeliveryAcceptance(c, other, authority).read(p)["status"]
            == "ACCEPTED"
        )
        retract = command(
            owner.read(p),
            "retract",
            "RETRACT_DELIVERY",
            targetEventId=receipt["event"]["eventId"],
            reason="撤回当前交付接受",
        )
        with pytest.raises(ExecutionPreparationError, match="RETRACTION_NOT_ALLOWED"):
            PreparedDeliveryAcceptance(c, other, authority).decide(p, retract)
        owner.decide(p, retract)
        assert owner.read(p)["status"] == "RETRACTED"
        assert owner.receipt(p, "accept") == receipt
        assert (
            c.execute("SELECT count(*) n FROM prepared_delivery.events").fetchone()["n"]
            == 2
        )
        assert (
            c.execute(
                "SELECT record FROM product_outcome.outcomes ORDER BY outcome_id"
            ).fetchall()
            == outcome
        )
        assert all(
            x["record"]["businessResolution"] != "CONFIRMED_SOLVED" for x in outcome
        )


@pytest.mark.parametrize(
    "mode",
    [
        "denied-read",
        "denied-evidence",
        "wrong-scope",
        "stale",
        "payload-conflict",
        "unknown-no-replay",
    ],
)
def test_acceptance_boundaries_no_extra_events(repository, mode):
    p, principal = setup_case(repository)
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        migrate(c)
        delivered(c, p, principal)
        authority = Authority()
        owner = PreparedDeliveryAcceptance(c, principal, authority)
        view = owner.read(p)
        body = command(view)
        if mode in {"denied-read", "denied-evidence"}:
            authority.denied = (
                ("EXECUTION", "READ")
                if mode == "denied-read"
                else ("EVIDENCE", "READ_REFERENCE")
            )
            assert owner.read(p) == {"status": "UNAVAILABLE"}
            with pytest.raises(AuthorityError):
                owner.decide(p, body)
        elif mode == "wrong-scope":
            other = SimpleNamespace(**{**vars(principal), "security_domain": "other"})
            with pytest.raises(ExecutionPreparationError, match="NOT_FOUND"):
                PreparedDeliveryAcceptance(c, other, authority).decide(p, body)
        elif mode == "stale":
            with pytest.raises(ExecutionPreparationError, match="TARGET_CHANGED"):
                owner.decide(p, {**body, "packageDigest": "0" * 64})
        else:
            original = owner.decide(p, body)
            if mode == "payload-conflict":
                with pytest.raises(ExecutionPreparationError, match="COMMAND_CONFLICT"):
                    owner.decide(p, {**body, "reason": "changed"})
            else:
                assert owner.receipt(p, body["idempotencyKey"]) == original
                assert owner.decide(p, body) == original
        n = c.execute("SELECT count(*) n FROM prepared_delivery.events").fetchone()["n"]
        assert n == (1 if mode in {"payload-conflict", "unknown-no-replay"} else 0)


def test_concurrent_accept_and_changed_limitations_do_not_inherit(repository):
    from concurrent.futures import ThreadPoolExecutor

    p, principal = setup_case(repository)
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        migrate(c)
        delivered(c, p, principal)
        view = PreparedDeliveryAcceptance(c, principal, Authority()).read(p)

    def accept(key):
        try:
            with repository.pool.connection() as c, c.transaction():
                c.row_factory = dict_row
                return PreparedDeliveryAcceptance(c, principal, Authority()).decide(
                    p, command(view, key)
                )
        except ExecutionPreparationError as e:
            return str(e)

    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(accept, ["race-a", "race-b"]))
    assert sum(isinstance(x, dict) for x in results) == 1
    assert "DELIVERY_TARGET_CHANGED" in results
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        review = PreparedResultReview(c, principal, Authority())
        outcome = c.execute(
            "SELECT record,digest FROM product_outcome.outcomes "
            "ORDER BY (record->>'version')::int DESC"
        ).fetchone()["record"]
        review.confirm(
            p,
            evaluation_id=outcome["evaluation"]["evaluationId"],
            evaluation_digest=outcome["evaluationDigest"],
            expected_version=outcome["version"],
            decision="ACKNOWLEDGE_UNDETERMINED",
            reason="新增明确核阅限制",
            command_key="review-after-accept",
        )
        owner = PreparedDeliveryAcceptance(c, principal, Authority())
        assert owner.read(p)["status"] == "SUPERSEDED"
        assert (
            c.execute("SELECT count(*) n FROM prepared_delivery.events").fetchone()["n"]
            == 1
        )


def test_decision_rollback_does_not_create_half_receipt(repository):
    p, principal = setup_case(repository)
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        migrate(c)
        delivered(c, p, principal)
    with (
        pytest.raises(RuntimeError, match="after-owner"),
        repository.pool.connection() as c,
        c.transaction(),
    ):
        c.row_factory = dict_row
        owner = PreparedDeliveryAcceptance(c, principal, Authority())
        owner.decide(p, command(owner.read(p)))
        raise RuntimeError("after-owner")
    with repository.pool.connection() as c:
        c.row_factory = dict_row
        for table in ["events", "packages", "heads"]:
            assert (
                c.execute(
                    "SELECT count(*) n FROM prepared_delivery." + table
                ).fetchone()["n"]
                == 0
            )


def test_current_browser_authority_read_never_grants_acceptance(repository):
    """Real current-grant/BrowserSession owner; generation configuration is fixture."""
    from contextlib import contextmanager
    from datetime import UTC, datetime, timedelta
    from pathlib import Path

    from agent_console.authority_configuration import (
        CredentialConfiguration,
        StaticAuthorityGeneration,
        StaticGrant,
    )
    from agent_console.authority_contracts import (
        AuthenticationSource,
        AuthorityScope,
        BrowserSession,
        CredentialId,
        ExactGrant,
        GrantSource,
        SessionId,
        TrustedRequestContext,
        VerifiedPrincipal,
    )
    from agent_console.authority_postgres import PostgresAuthorityRepository
    from agent_console.grant_administration_application import (
        GenerationAuthorizationReader,
    )
    from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization

    p, principal = setup_case(repository)
    captured = set()

    class CapturingAuthority(Authority):
        def require(self, principal, owner, action, target):
            captured.add(ExactGrant(owner, action, target))
            return super().require(principal, owner, action, target)

    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        migrate(c)
        delivered(c, p, principal)
        view = PreparedDeliveryAcceptance(c, principal, CapturingAuthority()).read(p)
    scope = AuthorityScope(p.namespace, p.security_domain)
    now = datetime.now(UTC)
    target = "governed-execution:prepared:" + p.digest
    read = ExactGrant("EXECUTION", "READ", target)
    accept = ExactGrant("EXECUTION", "ACCEPT_DELIVERY", target)
    reads = captured - {
        g for g in captured if g.action in {"ACCEPT_DELIVERY", "RETRACT_DELIVERY"}
    }
    configs = tuple(
        CredentialConfiguration(
            CredentialId(name),
            "7" * 64,
            principal.principal_id,
            scope,
            now + timedelta(hours=1),
            GrantSource.BROWSER_BOOTSTRAP,
            tuple(StaticGrant(g, GrantSource.BROWSER_BOOTSTRAP) for g in grants),
        )
        for name, grants in (("read-only", reads), ("accepting", reads | {accept}))
    )
    generation = StaticAuthorityGeneration(
        1, "a" * 64, "test-delivery", "test", configs, (), frozenset()
    )
    authority = PostgresAuthorityRepository(
        repository.pool.conninfo,
        migration_path=Path(__file__).parents[1]
        / "migrations/0018_browser_session_grant_authority.sql",
    )
    try:
        authority.migrate()
        authority.activate_generation(
            1,
            generation.digest,
            1,
            operator_id="operator:test",
            revoked_credentials=(),
            now=now,
        )

        class Controller:
            readiness = SimpleNamespace(recovery_epoch=1)

            @contextmanager
            def protected_request(self):
                yield generation

        contexts = []
        for config in configs:
            session = BrowserSession(
                SessionId("delivery-" + config.credential_id),
                VerifiedPrincipal(
                    principal.principal_id,
                    scope,
                    config.credential_id,
                    config.expires_at,
                    generation.policy_version,
                ),
                now,
                now,
                now + timedelta(minutes=30),
                now + timedelta(hours=1),
                1,
                1,
            )
            authority.create_session(
                session, hashlib.sha256(config.credential_id.encode()).hexdigest()
            )
            contexts.append(
                TrustedRequestContext(
                    principal.principal_id,
                    scope,
                    session.session_id,
                    AuthenticationSource.BROWSER_SESSION,
                    generation.policy_version,
                )
            )
        adapter = WorkbenchOwnerAuthorization(
            Controller(),
            authority,
            GenerationAuthorizationReader(
                generation, authority, authority, recovery_epoch=1
            ),
        )

        def invoke(context, grant, handler):
            return adapter.execute(
                context,
                (grant,),
                operation="DECIDE_PREPARED_DELIVERY",
                payload={},
                path={},
                query={},
                handler=lambda call: handler(
                    PreparedDeliveryAcceptance(
                        call.connection, principal, call.authority
                    )
                ),
            )

        assert (
            invoke(contexts[0], read, lambda owner: owner.read(p))["canAccept"] is False
        )
        with pytest.raises(AuthorityError):
            invoke(contexts[0], accept, lambda owner: owner.decide(p, command(view)))
        receipt = invoke(
            contexts[1], accept, lambda owner: owner.decide(p, command(view))
        )
        assert (
            invoke(contexts[1], read, lambda owner: owner.receipt(p, "accept"))
            == receipt
        )
        assert authority.revoke_session(
            SessionId(contexts[1].session_id_or_service_credential_id),
            reason="TEST_SESSION_REVOKED",
            actor_id=principal.principal_id,
            now=datetime.now(UTC),
        )
        with pytest.raises(AuthorityError):
            invoke(contexts[1], accept, lambda owner: owner.decide(p, command(view)))
        with authority.connection_scope() as c:
            assert (
                c.execute("SELECT count(*) n FROM prepared_delivery.events").fetchone()[
                    "n"
                ]
                == 1
            )
    finally:
        authority.close()


def test_immutable_columns_and_optional_projection_savepoint(repository):
    """Corruption is explicit isolated fault injection, not a supported write path."""
    from psycopg import Error as PsycopgError

    p, principal = setup_case(repository)
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        migrate(c)
        delivered(c, p, principal)
        owner = PreparedDeliveryAcceptance(c, principal, Authority())
        view = owner.read(p)
        receipt = owner.decide(p, command(view))
        assert receipt["event"]["commandKey"] == "accept"
        assert receipt["event"]["commandDigest"]
        for table in ("events", "packages"):
            with pytest.raises(PsycopgError), c.transaction():
                c.execute("DELETE FROM prepared_delivery." + table)
        assert owner.read(p)["status"] == "ACCEPTED"
        corruptions = (
            ("prepared_delivery.events", "command_key='wrong-command'"),
            ("prepared_delivery.events", "command_digest=repeat('0',64)"),
            ("prepared_delivery.events", "actor_id='human:foreign'"),
            ("prepared_delivery.packages", "workflow_run_id='foreign-run'"),
            (
                "prepared_delivery.packages",
                "record=jsonb_set(record,'{namespace}','\"foreign\"')",
            ),
            ("product_outcome.heads", "version=version+1"),
            ("product_outcome.outcomes", "resolution='NOT_SOLVED'"),
            ("success_criteria_evaluation.results", "predecessor_id=evaluation_id"),
        )
        for table, assignment in corruptions:
            with c.transaction(force_rollback=True):
                c.execute("ALTER TABLE " + table + " DISABLE TRIGGER USER")
                c.execute("UPDATE " + table + " SET " + assignment)
                assert owner.read(p) == {"status": "UNAVAILABLE"}, (table, assignment)
                assert c.execute("SELECT 1 n").fetchone()["n"] == 1
        for table in ("heads", "events", "packages"):
            with c.transaction(force_rollback=True):
                c.execute(
                    "ALTER TABLE prepared_delivery."
                    + table
                    + " RENAME TO unavailable_table"
                )
                assert owner.read(p) == {"status": "UNAVAILABLE"}
                assert c.execute("SELECT 1 n").fetchone()["n"] == 1
        assert owner.receipt(p, "accept") == receipt
