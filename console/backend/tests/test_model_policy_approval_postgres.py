# ruff: noqa: E501
import json
import os
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import (
    AuthorityScope,
    ExactGrant,
    GrantDecision,
    GrantId,
    GrantRequest,
    GrantRequestStatus,
)
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.draft_assistance import ProviderBudgetQuote
from agent_console.draft_provider_budget_postgres import (
    PostgresProviderCallBudget,
    _digest,
)
from agent_console.grant_administration_application import GenerationAuthorizationReader
from agent_console.model_binding_resolution import ExactModelBinding
from agent_console.model_governance import (
    ModelEligibilityState,
    ModelGovernanceError,
    ModelLifecycleAction,
)
from agent_console.model_governance_authorization import (
    ModelManagementOperation,
    model_management_grant,
    model_revision_grant,
)
from agent_console.model_governance_postgres import PostgresModelGovernanceRepository
from agent_console.model_policy_approval import (
    ExactModel,
    ModelPublicationPolicy,
)
from agent_console.model_policy_approval_postgres import (
    ModelPolicyPublicationOwner,
    migrate,
)
from agent_console.provider_budget_allowance import prepare
from test_draft_provider_budget_postgres import _profile
from test_model_authorization_postgres import activate_authority
from test_model_authorization_postgres import isolated_database as isolated_database
from test_model_governance_postgres import fact, persist_exact_graph, records
from test_model_policy_approval import verification_files

pytestmark = pytest.mark.skipif(
    not os.environ.get("MODEL_AUTHORIZATION_TEST_DATABASE_URL"),
    reason="isolated PG required",
)
M = Path(__file__).parents[1] / "migrations"


@pytest.fixture
def ready(isolated_database, tmp_path):
    models = PostgresModelGovernanceRepository(
        isolated_database, migration_path=M / "0019_model_governance.sql"
    )
    models.migrate()
    # Long-lived bootstrap can point at an older source migration directory.
    models.migration_path = tmp_path / "old-installed-source/0019_model_governance.sql"
    migrate(models)
    models.migration_path = M / "0019_model_governance.sql"
    models.compatibility()
    values = list(records(uuid.uuid4().hex))
    values[-1] = replace(values[-1], provider_native_model_id="gpt-6.1-sol", digest="")
    persist_exact_graph(models, values)
    scope, _, _, _, _, base = values
    for n, a in enumerate(
        (
            ModelLifecycleAction.VALIDATED,
            ModelLifecycleAction.HUMAN_REVIEWED,
            ModelLifecycleAction.PUBLISHED,
        ),
        1,
    ):
        models.append_fact(fact(base, n, a))
    provider = replace(
        values[2],
        revision_id=values[2].revision_id + "-typed",
        adapter_contract_revision_id="typed-successor",
        digest="",
    )
    models.add_provider_revision(provider)
    candidate = replace(
        base,
        revision_id=base.revision_id + "-next",
        revision=2,
        provider=provider.identity,
        predecessor_revision_id=base.revision_id,
        digest="",
    )
    models.add_revision(candidate)
    models.append_fact(fact(candidate, 1, ModelLifecycleAction.VALIDATED))
    exact = ExactModel(
        modelId=candidate.model_id,
        revisionId=candidate.revision_id,
        digest=candidate.digest,
    )
    authority = PostgresAuthorityRepository(
        isolated_database, migration_path=M / "0018_browser_session_grant_authority.sql"
    )
    authority.migrate()
    clock = datetime.now(UTC) - timedelta(minutes=1)
    asc = AuthorityScope(scope.namespace, scope.security_domain)
    generation, context = activate_authority(
        authority,
        asc,
        ExactGrant("MODEL_GOVERNANCE", "READ_MODEL", "model:catalog"),
        now=clock,
    )
    grants = (
        model_management_grant(
            ModelManagementOperation.PUBLISH, exact.modelId, exact.revisionId
        ),
        model_revision_grant(
            ExactModelBinding(exact.modelId, exact.revisionId, exact.digest)
        ),
    )
    request = GrantRequest(
        "policy-request",
        "human:alice",
        asc,
        grants,
        "MODEL_PUBLICATION",
        GrantRequestStatus.PENDING,
        clock,
    )
    authority.submit_request(
        request,
        actor_id="human:alice",
        idempotency_key="req",
        payload_digest="1" * 64,
        target_validation=lambda _: True,
        recovery_epoch=1,
    )
    authority.decide_request(
        GrantDecision(
            "policy-decision",
            request.request_id,
            "human:admin",
            "meta-admin",
            True,
            "ASSIGNED_DUTY",
            "TICKET",
            "2" * 64,
            "policy-issued",
            "test",
            clock,
        ),
        grants=tuple(
            (GrantId("grant-" + str(i)), g, clock, clock + timedelta(hours=1))
            for i, g in enumerate(grants)
        ),
        expected_status=GrantRequestStatus.PENDING,
        idempotency_key="decision",
        payload_digest="3" * 64,
        recovery_epoch=1,
    )
    auth = GenerationAuthorizationReader(
        generation, authority, authority, recovery_epoch=1
    )
    profile = replace(
        _profile(),
        scope=replace(
            _profile().scope,
            namespace=scope.namespace,
            security_domain=scope.security_domain,
        ),
    )
    budget = PostgresProviderCallBudget(
        isolated_database,
        migration_path=M / "0024_draft_provider_budget.sql",
        profile=profile,
        ledger_id="existing",
        call_cap=20,
        total_cost_cap_microusd=1000000,
        input_price_microusd_per_million_tokens=1000000,
        output_price_microusd_per_million_tokens=1000000,
    )
    budget.migrate_and_configure()
    with budget._connection() as c:
        root = c.execute(
            "SELECT record FROM draft_provider_budget.policies"
        ).fetchone()["record"]
    expiry = datetime.now(UTC) + timedelta(days=1)
    allowance = prepare(
        budget,
        dict(
            schemaVersion="provider-budget-allowance.v1",
            allowanceId="original",
            ledgerId="existing",
            namespace=scope.namespace,
            securityDomain=scope.security_domain,
            rootPolicyDigest=_digest(root),
            authorizationDigest="a" * 64,
            callCap=100,
            totalCostCapMicrousd=10000000,
            notBefore=clock.isoformat(),
            expiresAt=expiry.isoformat(),
            externalWrites=False,
        ),
    )
    budget.allowance_id = "original"
    budget.reserve(
        "pending",
        SimpleNamespace(
            scope=profile.scope,
            profile_revision_id=profile.profile_revision_id,
            invocation_id="pending",
        ),
        ProviderBudgetQuote(100, 100, 200),
    )

    def pin(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value))
        return dict(path=str(path), sha256=sha256(path.read_bytes()).hexdigest())

    standing = pin(
        "standing.json",
        dict(
            doesNotAssertIndividualReview=True,
            budgetIncreaseAuthorized=False,
            externalBusinessWritesAuthorized=False,
        ),
    )
    sources = pin("sources.json", dict(existingSource="unchanged"))
    proof = verification_files(
        pin,
        model=candidate.digest,
        profile=candidate.connection_profile.digest,
        provider=dict(
            providerId=provider.provider_id,
            revisionId=provider.revision_id,
            digest=provider.digest,
            adapterContractId=provider.adapter_contract_id,
            adapterContractRevisionId=provider.adapter_contract_revision_id,
        ),
        standing=standing,
        source=sources,
    )
    ev = pin(
        "evidence.json",
        dict(
            modelDigest=candidate.digest,
            profileDigest=candidate.connection_profile.digest,
            adapterDigest="d" * 64,
            schemaDigest=proof["schemaDigest"],
            codeVerificationDigest=proof["codeVerification"]["sha256"],
            sourcePolicyDigest=sources["sha256"],
            validationState="PASSED",
            externalWrites=False,
        ),
    )
    policy = dict(
        schemaVersion="model-standing-publication.v1",
        enabled=True,
        policyId="bounded",
        policyVersion="1",
        namespace=scope.namespace,
        securityDomain=scope.security_domain,
        publisherId=context.principal_id,
        nativeModel="gpt-6.1-sol",
        purpose="F3_ORIGINAL_CONVERSATION_CLOSURE",
        baseline=dict(
            modelId=base.model_id, revisionId=base.revision_id, digest=base.digest
        ),
        candidate=exact.model_dump(),
        profileDigest=candidate.connection_profile.digest,
        adapterDigest="d" * 64,
        **proof,
        standingAuthorization=standing,
        candidateEvidence=ev,
        sourcePolicy=sources,
        ledgerId="existing",
        allowanceId="original",
        allowanceDigest=_digest(allowance),
        cumulativeCallCap=100,
        cumulativeCostMicrousd=10000000,
        expiresAt=expiry.isoformat(),
        externalWrites=False,
    )
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy))
    path.chmod(0o600)
    ModelPublicationPolicy.load(path)
    owner = ModelPolicyPublicationOwner(models, auth, path)
    yield SimpleNamespace(
        owner=owner,
        models=models,
        authority=authority,
        context=context,
        exact=exact,
        candidate=candidate,
        path=path,
        policy=policy,
        budget=budget,
        scope=scope,
    )
    budget.close()
    models.close()
    authority.close()


def test_real_authority_policy_publication_and_restart_readback(ready):
    e = ready
    receipt = e.owner.publish(e.context, e.exact, "publish", 1)
    assert (
        receipt["budget"]["calls"] == 1
        and receipt["budget"]["reservedOrSettledCostMicrousd"] == 200
    )
    assert (
        e.models.read_lifecycle(e.scope, e.exact.modelId, e.exact.revisionId).state
        is ModelEligibilityState.PUBLISHED_ENABLED
    )
    assert e.owner.publish(e.context, e.exact, "publish", 1) == receipt
    restarted = ModelPolicyPublicationOwner(e.models, e.owner.authorization)
    assert restarted.read_receipt(e.context, e.exact, "publish") == receipt
    e.path.write_text("{}")
    assert restarted.read_receipt(e.context, e.exact, "publish") == receipt
    with e.models.pool.connection() as c:
        actions = [
            r["action"]
            for r in c.execute(
                "SELECT action FROM model_governance.lifecycle_facts WHERE revision_id=%s ORDER BY ordinal",
                (e.exact.revisionId,),
            ).fetchall()
        ]
        assert actions == ["VALIDATED", "POLICY_APPROVED", "PUBLISHED"]
    with pytest.raises(ModelGovernanceError, match="COMMAND_CONFLICT"):
        e.owner.publish(e.context, e.exact, "publish", 2)


def test_raw_append_cannot_claim_policy_approval(ready):
    e = ready
    with pytest.raises(ModelGovernanceError, match="MODEL_POLICY_OWNER_REQUIRED"):
        e.models.append_fact(fact(e.candidate, 2, ModelLifecycleAction.POLICY_APPROVED))
    assert (
        e.models.read_lifecycle(e.scope, e.exact.modelId, e.exact.revisionId).state
        is ModelEligibilityState.VALIDATED
    )


def test_changed_evidence_and_missing_current_publish_denied(ready):
    e = ready
    original = e.owner.authorization
    # Existing authority owner ends the real session; no test flag in publisher.
    assert e.authority.revoke_session(
        "session-alice",
        reason="LOGOUT",
        actor_id=e.context.principal_id,
        now=datetime.now(UTC),
    )
    with pytest.raises(ModelGovernanceError, match="PUBLISH_DENIED"):
        e.owner.publish(e.context, e.exact, "publish", 1)
    assert original is e.owner.authorization
    assert (
        e.models.read_lifecycle(e.scope, e.exact.modelId, e.exact.revisionId).state
        is ModelEligibilityState.VALIDATED
    )


def test_changed_pins_and_disabled_policy_do_not_append(ready):
    e = ready
    source = Path(e.policy["sourcePolicy"]["path"])
    original = source.read_text()
    source.write_text("{}")
    with pytest.raises(ModelGovernanceError, match="EVIDENCE_CHANGED"):
        e.owner.publish(e.context, e.exact, "pin", 1)
    source.write_text(original)
    data = dict(e.policy, enabled=False)
    e.path.write_text(json.dumps(data))
    with pytest.raises(ModelGovernanceError, match="DISABLED"):
        e.owner.publish(e.context, e.exact, "disabled", 1)
    with e.models.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM model_governance.policy_approval_decisions"
            ).fetchone()["n"]
            == 0
        )


def test_atomic_rollback_and_concurrent_same_command(ready, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    e = ready
    original = e.models._record

    def fail(value):
        if getattr(value, "action", None) is ModelLifecycleAction.PUBLISHED:
            raise RuntimeError("controlled publication persistence failure")
        return original(value)

    monkeypatch.setattr(e.models, "_record", fail)
    with pytest.raises(RuntimeError, match="controlled publication"):
        e.owner.publish(e.context, e.exact, "atomic", 1)
    with e.models.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM model_governance.policy_approval_decisions"
            ).fetchone()["n"]
            == 0
        )
    assert (
        e.models.read_lifecycle(e.scope, e.exact.modelId, e.exact.revisionId).state
        is ModelEligibilityState.VALIDATED
    )
    monkeypatch.setattr(e.models, "_record", original)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(e.owner.publish, e.context, e.exact, "atomic", 1)
            for _ in range(2)
        ]
        results = [f.result(timeout=10) for f in futures]
    assert results[0] == results[1]
    with e.models.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM model_governance.policy_approval_decisions"
            ).fetchone()["n"]
            == 1
        )


def test_current_publish_revocation_does_not_erase_successful_receipt(ready):
    e = ready
    receipt = e.owner.publish(e.context, e.exact, "saved", 1)
    # Original grant owner revocation, retaining distinct READ permission.
    assert e.authority.revoke_grant(
        GrantId("grant-0"),
        actor_id="human:admin",
        reason="REVOKED",
        idempotency_key="revoke-publish",
        payload_digest="a" * 64,
        now=datetime.now(UTC),
    )
    assert e.owner.read_receipt(e.context, e.exact, "saved") == receipt
    assert e.owner.publish(e.context, e.exact, "saved", 1) == receipt
    with pytest.raises(ModelGovernanceError, match="PUBLISH_DENIED"):
        e.owner.publish(e.context, e.exact, "new-write", 1)


def test_reader_rejects_policy_fact_without_immutable_decision(ready):
    from psycopg.types.json import Jsonb

    e = ready
    f = fact(e.candidate, 2, ModelLifecycleAction.POLICY_APPROVED)
    # Corrupt-store simulation, bypassing owner intentionally; reader must reject.
    with e.models.pool.connection() as c:
        c.execute(
            "INSERT INTO model_governance.lifecycle_facts(namespace,security_domain,model_id,revision_id,model_digest,ordinal,fact_id,action,actor_id,decision_id,occurred_at,digest,record) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                e.scope.namespace,
                e.scope.security_domain,
                e.exact.modelId,
                e.exact.revisionId,
                e.exact.digest,
                f.ordinal,
                f.fact_id,
                f.action.value,
                f.actor_id,
                f.decision_id,
                f.occurred_at,
                f.digest,
                Jsonb(e.models._record(f)),
            ),
        )
    with pytest.raises(ModelGovernanceError, match="DECISION_INVALID"):
        e.models.read_lifecycle(e.scope, e.exact.modelId, e.exact.revisionId)
