# ruff: noqa: F811, E501 -- Isolated PG fixture and explicit exact identities.
"""Real credential/grant, immutable preparation and original budget; no model IO."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console import fixed_work_authoring_postgres as work
from agent_console.authority_configuration import (
    CredentialConfiguration,
    StaticAuthorityGeneration,
    StaticGrant,
)
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    AuthorityScope,
    ExactGrant,
    GrantSource,
    TrustedRequestContext,
)
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget
from agent_console.fixed_work_authoring import SaveDraft
from agent_console.fixed_work_service_admission import (
    ServicePlanningRegistry,
    event_key,
    migrate,
)
from agent_console.fixed_work_service_policy import ServicePlanningPolicy
from agent_console.grant_administration_application import GenerationAuthorizationReader
from agent_console.plan_invocation_postgres import PostgresPlanningInvocations
from agent_console.plan_suggestion_invocation import PlanningRequest
from psycopg.rows import dict_row
from test_draft_assistance import profile
from test_fixed_work_authoring import body
from test_plan_suggestion_v2 import proposal, repository  # noqa: F401

M = Path(__file__).parents[1] / "migrations"


@pytest.fixture
def fixture(repository, request):
    now = datetime.now(UTC)
    authority = PostgresAuthorityRepository(
        repository.pool.conninfo,
        migration_path=M / "0018_browser_session_grant_authority.sql",
    )
    request.addfinalizer(authority.close)
    authority.migrate()
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        c.execute((M / "0023_draft_assistance.sql").read_text())
        work.migrate(c)
        saved, _ = work.save(
            c,
            ("tenant-a", "quality"),
            "human:alice",
            SaveDraft.model_validate(body()),
            dict(teamId="team", revisionId="r", digest="a" * 64),
            "b" * 64,
            "test-decision",
            now,
        )
        migrate(c)
    PostgresPlanningInvocations(repository).migrate()
    import test_model_binding_resolution as mf

    p = replace(profile(), binding=mf.BINDING)
    budget = PostgresProviderCallBudget(
        repository.pool.conninfo,
        migration_path=M / "0024_draft_provider_budget.sql",
        profile=p,
        ledger_id="original-ledger",
        call_cap=2,
        total_cost_cap_microusd=1000,
        input_price_microusd_per_million_tokens=0,
        output_price_microusd_per_million_tokens=0,
    )
    request.addfinalizer(budget.pool.close)
    budget.migrate_and_configure()
    policy = ServicePlanningPolicy.model_validate(
        dict(
            schemaVersion="fixed-work-service-planning.v1",
            policyId="service-test",
            enabled=True,
            tenantId="tenant-a",
            securityDomain="quality",
            subjectId="service:fixed-work",
            credentialId="service-credential",
            work=dict(
                resource_id="work:1", revision_id="revision:1", digest=saved["digest"]
            ),
            target=proposal().semantics.target.model_dump(mode="json"),
            resourceSnapshot=dict(
                resource_id="snapshot", revision_id="r", digest="c" * 64
            ),
            allowedEventIds=["slot:1", "slot:2", "slot:3"],
            eventWindows={
                x: (now - timedelta(minutes=1), now + timedelta(minutes=30))
                for x in ("slot:1", "slot:2", "slot:3")
            },
            profileRevisionId=p.profile_revision_id,
            profileDigest=p.profile_digest,
            model=dict(
                resource_id=p.binding.resource_id,
                revision_id=p.binding.revision_id,
                digest=p.binding.digest,
            ),
            ledgerId=budget.ledger_id,
            maximumInputTokens=100,
            maximumOutputTokens=100,
            expiresAt=now + timedelta(hours=1),
        )
    )
    grants = (
        ExactGrant("TEAM", "READ", "team:team:r"),
        ExactGrant("PLAN", "PREPARE", "plan:prepare:problem"),
        ExactGrant("MODEL_GOVERNANCE", "INVOKE_MODEL", policy.model_target),
    )
    generation = StaticAuthorityGeneration(
        1,
        "a" * 64,
        "test-policy",
        "isolated-test",
        (
            CredentialConfiguration(
                "service-credential",
                "f" * 64,
                policy.subjectId,
                AuthorityScope("tenant-a", "quality"),
                now + timedelta(hours=1),
                GrantSource.SERVICE_ONLY,
                tuple(StaticGrant(g, GrantSource.SERVICE_ONLY) for g in grants),
            ),
            CredentialConfiguration(
                "other-service-credential",
                "e" * 64,
                "service:other",
                AuthorityScope("tenant-a", "quality"),
                now + timedelta(hours=1),
                GrantSource.SERVICE_ONLY,
                tuple(StaticGrant(g, GrantSource.SERVICE_ONLY) for g in grants),
            ),
        ),
        (),
        frozenset(),
    )
    authority.activate_generation(
        1,
        generation.digest,
        1,
        operator_id="test-only",
        revoked_credentials=(),
        now=now,
    )
    reader = GenerationAuthorizationReader(
        generation, authority, authority, recovery_epoch=1
    )
    context = TrustedRequestContext(
        policy.subjectId,
        AuthorityScope("tenant-a", "quality"),
        "service-credential",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "test-policy",
    )
    current = [policy]
    registry = ServicePlanningRegistry(repository, reader, lambda: current[0])
    budget.service_planning_admission = registry
    req = PlanningRequest(
        target=policy.target, idempotency_key=event_key(policy.work, "slot:1")
    )
    record = dict(
        target=dict(
            namespace="tenant-a",
            security_domain="quality",
            invocation_id="call:1",
            problem=policy.target.model_dump(mode="json"),
            resource_snapshot=policy.resourceSnapshot.model_dump(mode="json"),
        ),
        profile=dict(
            profile_revision_id=p.profile_revision_id,
            profile_digest=p.profile_digest,
            model=policy.model.model_dump(mode="json"),
        ),
    )
    return SimpleNamespace(**locals())


def test_exact_service_preparation_replay_and_current_revocation(fixture):
    f = fixture
    first = f.registry.prepare(f.context, "slot:1", f.req, f.record)
    assert first["admission"]["ready"]
    alternate = {
        **f.record,
        "target": {**f.record["target"], "invocation_id": "discarded"},
    }
    assert f.registry.prepare(f.context, "slot:1", f.req, alternate) == first
    with pytest.raises(AuthorityError):
        f.registry.prepare(
            replace(
                f.context, authentication_source=AuthenticationSource.BROWSER_SESSION
            ),
            "slot:1",
            f.req,
            f.record,
        )
    f.authority.activate_generation(
        2,
        "b" * 64,
        1,
        operator_id="test-only",
        revoked_credentials=("service-credential",),
        now=f.now,
    )
    with pytest.raises(AuthorityError):
        f.registry.prepare(f.context, "slot:1", f.req, f.record)
    with f.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM fixed_work_service.planning_preparations"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )


def test_unclaimed_old_event_and_expiry_block_new_event(fixture):
    f = fixture
    f.registry.prepare(f.context, "slot:1", f.req, f.record)
    new = f.req.model_copy(
        update={"idempotency_key": event_key(f.policy.work, "slot:2")}
    )
    record = {**f.record, "target": {**f.record["target"], "invocation_id": "call:2"}}
    with pytest.raises(AuthorityError, match="PREVIOUS_OUTCOME_UNRESOLVED"):
        f.registry.prepare(f.context, "slot:2", new, record)
    f.current[0] = f.policy.model_copy(
        update={"expiresAt": f.now - timedelta(seconds=1)}
    )
    with pytest.raises(AuthorityError, match="POLICY_UNAVAILABLE"):
        f.registry.prepare(f.context, "slot:1", f.req, f.record)


def test_migration_rejects_missing_immutable_trigger(fixture):
    f = fixture
    with f.repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        migrate(c)
        c.execute(
            "DROP TRIGGER immutable_planning_preparations ON fixed_work_service.planning_preparations"
        )
        with pytest.raises(AuthorityError, match="SCHEMA_INCOMPATIBLE"):
            migrate(c)
        # Test transaction deliberately restored; no real DB involved.
        c.execute(
            "CREATE TRIGGER immutable_planning_preparations BEFORE UPDATE OR DELETE ON fixed_work_service.planning_preparations FOR EACH ROW EXECUTE FUNCTION fixed_work_service.reject_mutation()"
        )


@pytest.mark.parametrize("mode", ["cycles", "unknown", "budget_full"])
def test_normal_planning_claim_proposal_original_budget_and_replay(
    fixture, mode, first_event="slot:1"
):
    """Actual planning/PG budget owners; provider/model resolution and Problem input are controlled fixtures."""
    import json

    import test_model_binding_resolution as mf
    from agent_console.draft_assistance import ProviderBudgetQuote
    from agent_console.execution_domain import ScopeIdentity
    from agent_console.fixed_work_service_runtime import ServicePlanningRuntime
    from agent_console.plan_model_use_postgres import PostgresPlanModelUseOwner
    from agent_console.plan_suggestion_domain import ExactReference
    from agent_console.plan_suggestion_invocation import PlanningProfile
    from agent_console.plan_suggestion_service import PlanningSuggestionService

    f = fixture
    second_unknown = mode == "unknown"
    semantics = proposal().semantics

    # The original profile's output cap is retained, never raised by this adapter.
    f.current[0] = f.current[0].model_copy(
        update={"maximumOutputTokens": f.p.maximum_output_tokens}
    )

    class Authority:
        def require(self, principal, owner, action, resource):
            grant = ExactGrant(owner, action, resource)
            if (owner, action) == ("PLAN", "READ"):
                # Read fixture is separate from the actual service PREPARE/INVOKE checks.
                return SimpleNamespace(decision_id="fixture-read")
            allowed = f.reader.has_current_grants(
                f.context,
                (grant,),
                now=datetime.now(UTC),
                generation=1,
                recovery_epoch=1,
            )
            if allowed != (True,):
                raise AuthorityError("AUTHORIZATION_NOT_FOUND")
            return SimpleNamespace(decision_id="actual-current-grant")

    class ModelAuthority:
        def authorize_use(self, scope, subject, use):
            return mf.authorization(
                scope=scope,
                subject=subject,
                use=use,
                issued_at=datetime.now(UTC) - timedelta(minutes=1),
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )

    class Provider:
        synthetic = True
        calls = 0

        def suggest(self, *args):
            self.calls += 1
            if second_unknown:
                raise TimeoutError
            return {
                "text": json.dumps(
                    {
                        "kind": "VALID_SUGGESTION",
                        "semantics": semantics.model_dump(mode="json"),
                    }
                ),
                "measurement": {
                    "settleable": True,
                    "usage": {"input_tokens": 10, "output_tokens": 10},
                },
            }

    provider = Provider()
    # Match the fixture's published model binding; real resolver behavior is covered separately.
    model = ExactReference(
        resource_id="model:reviewer", revision_id="model-revision:7", digest="a" * 64
    )
    reader = f.reader
    f.budget.service_planning_admission = None
    if mode == "budget_full":
        # Existing unsettled calls on the same original ledger still consume cap.
        from agent_console.draft_assistance import DraftScope

        for identity in ("prior-held-call:1", "prior-held-call:2"):
            f.budget.reserve(
                identity,
                SimpleNamespace(
                    scope=DraftScope("tenant-a", "quality"),
                    invocation_id=identity,
                    profile_revision_id=f.p.profile_revision_id,
                ),
                ProviderBudgetQuote(100, f.p.maximum_output_tokens, 0),
            )
    app = SimpleNamespace(
        repository=f.repository,
        authority=Authority(),
        scope=lambda _: ScopeIdentity("tenant-a", "quality"),
        validate_target=lambda *a, **kw: None,
        current_input=lambda *a: {"title": "controlled confirmed problem"},
    )
    from agent_console.plan_suggestion_runtime import PlanningBudget

    service = PlanningSuggestionService(
        app,
        PostgresPlanningInvocations(f.repository),
        PlanningProfile(
            profile_revision_id=f.p.profile_revision_id,
            profile_digest=f.p.profile_digest,
            model=model,
            adapter_id="controlled-test",
            adapter_revision="1",
            maximum_input_bytes=65536,
            maximum_output_tokens=f.p.maximum_output_tokens,
        ),
        model_authorizer=ModelAuthority(),
        model_resolver=mf.RecordingResolver([]),
        budget=PlanningBudget(f.budget),
        quote=ProviderBudgetQuote(100, f.p.maximum_output_tokens, 0),
        provider=provider,
        model_use_owner=PostgresPlanModelUseOwner(f.repository),
        commitment_key=b"isolated-service-test-key-not-a-secret",
        prepare_resources=lambda *a: f.current[0].resourceSnapshot,
    )
    runtime = ServicePlanningRuntime(
        service, reader, lambda: f.current[0], enabled=True
    )
    prepared = runtime.begin(f.context, first_event, prepare_only=True)
    assert prepared["admission"]["ready"] and provider.calls == 0
    if mode == "budget_full":
        from agent_console.draft_assistance import DraftAssistanceError

        with pytest.raises(DraftAssistanceError, match="PROVIDER_BUDGET_EXHAUSTED"):
            runtime.begin(f.context, first_event)
        assert (
            runtime.begin(f.context, first_event)["result"]["technical_status"]
            == "OUTCOME_UNKNOWN"
        )
        assert provider.calls == 0
        with f.repository.pool.connection() as c:
            c.row_factory = dict_row
            assert (
                c.execute(
                    "SELECT count(*) n FROM draft_provider_budget.reservations"
                ).fetchone()["n"]
                == 2
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM draft_provider_budget.settlements"
                ).fetchone()["n"]
                == 0
            )
        return
    result = runtime.begin(f.context, first_event)
    if second_unknown:
        assert result["result"]["technical_status"] == "OUTCOME_UNKNOWN"
        with pytest.raises(AuthorityError, match="PREVIOUS_OUTCOME_UNRESOLVED"):
            runtime.begin(f.context, "slot:2")
        assert provider.calls == 1
        with f.repository.pool.connection() as c:
            c.row_factory = dict_row
            assert (
                c.execute(
                    "SELECT count(*) n FROM draft_provider_budget.reservations"
                ).fetchone()["n"]
                == 1
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM draft_provider_budget.settlements"
                ).fetchone()["n"]
                == 0
            )
        return
    assert result["result"]["technical_status"] == "SUCCEEDED"
    assert result["result"]["kind"] == "VALID_SUGGESTION"
    assert provider.calls == 1
    assert runtime.begin(f.context, first_event)["result"] == result["result"]
    assert provider.calls == 1
    with f.repository.pool.connection() as c:
        c.row_factory = dict_row
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.settlements"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute("SELECT call_cap FROM draft_provider_budget.policies").fetchone()[
                "call_cap"
            ]
            == 2
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM workflow_planning.invocations"
            ).fetchone()["n"]
            == 1
        )

    if mode == "bound_once":
        return  # One real bound model-owner call; no second due window fabricated.
    with pytest.raises(AuthorityError, match="PREVIOUS_CYCLE_AWAITS_CONTINUATION"):
        runtime.begin(f.context, "slot:2")
    assert provider.calls == 1


def test_unopened_event_window_has_zero_preparation_and_call(fixture):
    f = fixture
    f.current[0] = f.policy.model_copy(
        update={
            "eventWindows": {
                event: (f.now + timedelta(minutes=1), f.now + timedelta(minutes=5))
                for event in f.policy.allowedEventIds
            }
        }
    )
    with pytest.raises(AuthorityError, match="EVENT_NOT_DUE"):
        f.registry.prepare(f.context, "slot:1", f.req, f.record)
    with f.repository.pool.connection() as c:
        c.row_factory = dict_row
        assert (
            c.execute(
                "SELECT count(*) n FROM fixed_work_service.planning_preparations"
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM workflow_planning.invocations"
            ).fetchone()["n"]
            == 0
        )


def test_business_event_and_pending_work_are_not_reset_by_service_identity(fixture):
    f = fixture
    f.registry.prepare(f.context, "slot:1", f.req, f.record)
    other_policy = f.policy.model_copy(
        update={
            "subjectId": "service:other",
            "credentialId": "other-service-credential",
        }
    )
    other_context = replace(
        f.context,
        principal_id="service:other",
        session_id_or_service_credential_id="other-service-credential",
    )
    other = ServicePlanningRegistry(f.repository, f.reader, lambda: other_policy)
    with pytest.raises(AuthorityError, match="EVENT_CONFLICT"):
        other.prepare(other_context, "slot:1", f.req, f.record)
    new_request = f.req.model_copy(
        update={"idempotency_key": event_key(f.policy.work, "slot:2")}
    )
    new_record = {
        **f.record,
        "target": {**f.record["target"], "invocation_id": "other-call"},
    }
    with pytest.raises(AuthorityError, match="PREVIOUS_OUTCOME_UNRESOLVED"):
        other.prepare(other_context, "slot:2", new_request, new_record)
    with f.repository.pool.connection() as c:
        c.row_factory = dict_row
        assert (
            c.execute(
                "SELECT count(*) n FROM fixed_work_service.planning_preparations"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM workflow_planning.invocations"
            ).fetchone()["n"]
            == 0
        )
