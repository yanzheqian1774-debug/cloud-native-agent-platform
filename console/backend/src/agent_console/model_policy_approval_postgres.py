# ruff: noqa: E501
"""Atomic policy decision + publication; no provider or execution operation."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from psycopg.types.json import Jsonb

from .draft_provider_budget_postgres import _digest as budget_digest
from .model_binding_resolution import ExactModelBinding
from .model_governance import (
    ModelEligibilityState,
    ModelLifecycleAction,
    ModelLifecycleFact,
    ModelScope,
    canonical_payload,
)
from .model_governance_authorization import (
    CallerOwnedPostgresModelGovernanceReader,
    ModelManagementOperation,
    model_management_grant,
    model_revision_grant,
)
from .model_policy_approval import ExactModel, ModelPublicationPolicy, digest, require
from .task_identity_continuity import lock_owner_generation


def migrate(repository):
    path = (
        Path(__file__).resolve().parents[2]
        / "migrations/0071_model_policy_approval.sql"
    )
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    with repository.pool.connection() as c, c.transaction():
        c.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,308))",
            ("model-governance-policy-v71",),
        )
        row = c.execute(
            "SELECT checksum,adapter FROM model_governance.schema_migrations WHERE version=71"
        ).fetchone()
        if row:
            require(
                row == dict(checksum=checksum, adapter="model-policy-approval-v1"),
                "SCHEMA_INCOMPATIBLE",
            )
            return
        c.execute(path.read_text())
        c.execute(
            "INSERT INTO model_governance.schema_migrations(version,checksum,adapter) VALUES(71,%s,%s)",
            (checksum, "model-policy-approval-v1"),
        )


def validate_history(c, revision, facts):
    """Historical integrity only. Expired publication permission is not read denial."""
    policy = next(
        (f for f in facts if f.action == ModelLifecycleAction.POLICY_APPROVED), None
    )
    if policy is None:
        return
    row = c.execute(
        "SELECT record,digest FROM model_governance.policy_approval_decisions WHERE namespace=%s AND security_domain=%s AND decision_id=%s",
        (revision.scope.namespace, revision.scope.security_domain, policy.decision_id),
    ).fetchone()
    require(
        row is not None and row["digest"] == digest(row["record"]), "DECISION_INVALID"
    )
    r = row["record"]
    stored_policy = ModelPublicationPolicy.model_validate(r["policy"])
    require(
        stored_policy.enabled and policy.occurred_at < stored_policy.expiresAt,
        "DECISION_EXPIRED_AT_PUBLICATION",
    )
    require(
        r["policyDigest"] == stored_policy.digest
        and r["budget"]["allowanceDigest"] == stored_policy.allowanceDigest,
        "DECISION_POLICY_INVALID",
    )
    require(
        r["budget"]["calls"] <= stored_policy.cumulativeCallCap
        and r["budget"]["reservedOrSettledCostMicrousd"]
        <= stored_policy.cumulativeCostMicrousd,
        "DECISION_BUDGET_INVALID",
    )
    require(
        r["candidate"]
        == dict(
            modelId=revision.model_id,
            revisionId=revision.revision_id,
            digest=revision.digest,
        )
        and r["profileDigest"] == revision.connection_profile.digest
        and stored_policy.candidate == ExactModel.model_validate(r["candidate"])
        and stored_policy.provider.providerId == revision.provider.provider_id
        and stored_policy.provider.revisionId == revision.provider.revision_id
        and stored_policy.provider.digest == revision.provider.digest
        and r["codeVerificationDigest"] == stored_policy.codeVerification.sha256
        and r["schemaArtifactDigest"] == stored_policy.schemaArtifact.sha256
        and r["candidateEvidenceDigest"] == stored_policy.candidateEvidence.sha256
        and r["sourcePolicyDigest"] == stored_policy.sourcePolicy.sha256
        and r["actorId"] == policy.actor_id
        and r["policyDigest"] == digest(r["policy"])
        and r["standingAuthorizationDigest"]
        == r["policy"]["standingAuthorization"]["sha256"],
        "DECISION_BINDING_INVALID",
    )
    for fact in facts:
        if fact.action in {
            ModelLifecycleAction.POLICY_APPROVED,
            ModelLifecycleAction.PUBLISHED,
        }:
            require(
                fact.decision_id == policy.decision_id
                and r["facts"].get(fact.action.value) == fact.digest,
                "DECISION_FACT_MISMATCH",
            )
    require(policy.occurred_at.isoformat() == r["approvedAt"], "DECISION_TIME_MISMATCH")


class ModelPolicyPublicationOwner:
    def __init__(self, repository, authorization, policy_path=None):
        self.repository, self.authorization, self.policy_path = (
            repository,
            authorization,
            policy_path,
        )

    def _authority(self, c, context, candidate, *, write):
        require(
            (context.scope.tenant_id, context.scope.security_domain) != ("", ""),
            "SCOPE_INVALID",
        )
        grant = (
            model_management_grant(
                ModelManagementOperation.PUBLISH,
                candidate.modelId,
                candidate.revisionId,
            )
            if write
            else model_revision_grant(
                ExactModelBinding(
                    candidate.modelId, candidate.revisionId, candidate.digest
                )
            )
        )
        reader = self.authorization.bind_current_exact_decisions(
            c, generation=self.authorization.generation.generation
        )
        now = c.execute("SELECT clock_timestamp() now").fetchone()["now"]
        decision = reader.authorize_current(context, grant, now=now)
        require(decision is not None, "PUBLISH_DENIED" if write else "READ_DENIED")
        return decision, now

    @staticmethod
    def _saved(c, context, key):
        return c.execute(
            "SELECT record,digest FROM model_governance.policy_approval_decisions WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
            (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
                key,
            ),
        ).fetchone()

    def read_receipt(self, context, candidate, key):
        require(isinstance(candidate, ExactModel), "EXACT_CANDIDATE_REQUIRED")
        with self.repository.pool.connection() as c, c.transaction():
            self._authority(c, context, candidate, write=False)
            row = self._saved(c, context, key)
            require(
                row is not None
                and row["digest"] == digest(row["record"])
                and row["record"]["candidate"] == candidate.model_dump(),
                "RECEIPT_NOT_FOUND",
            )
            return row["record"]

    def publish(self, context, candidate, command_key, expected_ordinal):
        require(
            isinstance(candidate, ExactModel)
            and isinstance(command_key, str)
            and 1 <= len(command_key) <= 200,
            "COMMAND_INVALID",
        )
        require(
            type(expected_ordinal) is int and expected_ordinal >= 1, "COMMAND_INVALID"
        )
        with self.repository.pool.connection() as c, c.transaction():
            lock_owner_generation(c)
            c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,308))",
                (
                    json.dumps(
                        [
                            context.scope.tenant_id,
                            context.scope.security_domain,
                            context.principal_id,
                            "policy-command",
                            command_key,
                        ]
                    ),
                ),
            )
            # Original Model revision lock; policy command locks follow governance.
            c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,308))",
                (
                    json.dumps(
                        [
                            context.scope.tenant_id,
                            context.scope.security_domain,
                            candidate.modelId,
                            candidate.revisionId,
                        ]
                    ),
                ),
            )
            prior = self._saved(c, context, command_key)
            if prior:
                self._authority(c, context, candidate, write=False)
                require(
                    prior["digest"] == digest(prior["record"])
                    and prior["record"]["candidate"] == candidate.model_dump()
                    and prior["record"]["expectedOrdinal"] == expected_ordinal,
                    "COMMAND_CONFLICT",
                )
                return prior["record"]
            require(self.policy_path is not None, "DISABLED")
            policy = ModelPublicationPolicy.load(self.policy_path)
            require(
                (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    context.principal_id,
                )
                == (policy.namespace, policy.securityDomain, policy.publisherId)
                and candidate == policy.candidate,
                "SCOPE_DENIED",
            )
            decision, now = self._authority(c, context, candidate, write=True)
            require(now < policy.expiresAt, "EXPIRED")
            evidence = policy.evidence()
            scope = ModelScope(policy.namespace, policy.securityDomain)
            reader = CallerOwnedPostgresModelGovernanceReader(self.repository, c)
            revision = reader.get_revision(
                scope, candidate.modelId, candidate.revisionId
            )
            configuration = reader.resolve_exact(
                scope, revision.provider, revision.endpoint, revision.connection_profile
            )
            baseline = reader.get_revision(
                scope, policy.baseline.modelId, policy.baseline.revisionId
            )
            require(
                revision.digest == candidate.digest
                and baseline.digest == policy.baseline.digest
                and baseline.provider_native_model_id
                == revision.provider_native_model_id
                == policy.nativeModel
                and revision.provider.provider_id == baseline.provider.provider_id
                and revision.provider.provider_id == policy.provider.providerId
                and revision.provider.revision_id == policy.provider.revisionId
                and revision.provider.digest == policy.provider.digest
                and configuration.provider.adapter_contract_id
                == policy.provider.adapterContractId
                and configuration.provider.adapter_contract_revision_id
                == policy.provider.adapterContractRevisionId
                and revision.endpoint == baseline.endpoint
                and revision.connection_profile.digest == policy.profileDigest
                and revision.predecessor_revision_id == baseline.revision_id,
                "CANDIDATE_CHANGED",
            )
            require(
                reader.read_lifecycle(
                    scope, baseline.model_id, baseline.revision_id
                ).state
                is ModelEligibilityState.PUBLISHED_ENABLED,
                "BASELINE_UNAVAILABLE",
            )
            eligibility = reader.read_lifecycle(
                scope, revision.model_id, revision.revision_id
            )
            require(
                eligibility.state is ModelEligibilityState.VALIDATED
                and eligibility.high_water.ordinal == expected_ordinal,
                "LIFECYCLE_CONFLICT",
            )
            budget = self._budget(c, policy)
            # Re-read pinned private policy/evidence immediately before append.
            require(
                ModelPublicationPolicy.load(self.policy_path) == policy,
                "POLICY_CHANGED",
            )
            require(policy.evidence() == evidence, "EVIDENCE_CHANGED")
            decision, now = self._authority(c, context, candidate, write=True)
            require(now < policy.expiresAt, "EXPIRED")
            decision_id = "model-policy:" + digest(
                [
                    policy.namespace,
                    policy.securityDomain,
                    context.principal_id,
                    command_key,
                    candidate.model_dump(),
                ]
            )
            facts = [
                ModelLifecycleFact(
                    scope,
                    decision_id + ":" + action.value,
                    revision.identity,
                    expected_ordinal + offset,
                    action,
                    context.principal_id,
                    decision_id,
                    now,
                )
                for offset, action in enumerate(
                    (
                        ModelLifecycleAction.POLICY_APPROVED,
                        ModelLifecycleAction.PUBLISHED,
                    ),
                    1,
                )
            ]
            record = dict(
                schemaVersion="model-policy-publication-receipt.v1",
                decisionId=decision_id,
                actorId=context.principal_id,
                candidate=candidate.model_dump(),
                profileDigest=revision.connection_profile.digest,
                policy=policy.model_dump(mode="json"),
                policyDigest=policy.digest,
                expectedOrdinal=expected_ordinal,
                approvedAt=now.isoformat(),
                publishAuthority=asdict(decision),
                budget=budget,
                facts={f.action.value: f.digest for f in facts},
                **evidence,
            )
            # Canonicalize trusted domain dataclasses/timestamps for immutable JSON.
            record = json.loads(canonical_payload(record))
            c.execute(
                "INSERT INTO model_governance.policy_approval_decisions(namespace,security_domain,decision_id,actor_id,command_key,model_id,revision_id,model_digest,record,digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    policy.namespace,
                    policy.securityDomain,
                    decision_id,
                    context.principal_id,
                    command_key,
                    candidate.modelId,
                    candidate.revisionId,
                    candidate.digest,
                    Jsonb(record),
                    digest(record),
                ),
            )
            for fact in facts:
                validate_history(
                    c,
                    revision,
                    [fact]
                    if fact.action == ModelLifecycleAction.POLICY_APPROVED
                    else facts,
                )
                c.execute(
                    "INSERT INTO model_governance.lifecycle_facts(namespace,security_domain,model_id,revision_id,model_digest,ordinal,fact_id,action,actor_id,decision_id,occurred_at,digest,record) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        policy.namespace,
                        policy.securityDomain,
                        candidate.modelId,
                        candidate.revisionId,
                        candidate.digest,
                        fact.ordinal,
                        fact.fact_id,
                        fact.action.value,
                        fact.actor_id,
                        fact.decision_id,
                        fact.occurred_at,
                        fact.digest,
                        Jsonb(self.repository._record(fact)),
                    ),
                )
            return record

    @staticmethod
    def _budget(c, policy):
        from .provider_budget_allowance import require as require_allowance

        owner = SimpleNamespace(
            allowance_id=policy.allowanceId,
            ledger_id=policy.ledgerId,
            profile=SimpleNamespace(
                scope=SimpleNamespace(
                    namespace=policy.namespace, security_domain=policy.securityDomain
                )
            ),
        )
        c.execute(
            "SELECT ledger_id FROM draft_provider_budget.policies WHERE namespace=%s AND security_domain=%s AND ledger_id=%s FOR SHARE",
            (policy.namespace, policy.securityDomain, policy.ledgerId),
        ).fetchone()
        value = require_allowance(c, owner)
        require(
            value is not None
            and budget_digest(value.model_dump(mode="json")) == policy.allowanceDigest
            and value.callCap == policy.cumulativeCallCap
            and value.totalCostCapMicrousd == policy.cumulativeCostMicrousd
            and value.expiresAt == policy.expiresAt
            and value.externalWrites is False,
            "ALLOWANCE_CHANGED",
        )
        totals = c.execute(
            "SELECT count(*) calls,COALESCE(sum(COALESCE(s.actual_cost_microusd,r.worst_case_cost_microusd)),0) cost FROM draft_provider_budget.reservations r LEFT JOIN draft_provider_budget.settlements s USING(namespace,security_domain,ledger_id,reservation_id) WHERE r.namespace=%s AND r.security_domain=%s AND r.ledger_id=%s",
            (policy.namespace, policy.securityDomain, policy.ledgerId),
        ).fetchone()
        require(
            totals["calls"] <= value.callCap
            and totals["cost"] <= value.totalCostCapMicrousd,
            "ALLOWANCE_EXCEEDED",
        )
        return dict(
            allowanceDigest=policy.allowanceDigest,
            ledgerId=policy.ledgerId,
            allowanceId=policy.allowanceId,
            calls=totals["calls"],
            reservedOrSettledCostMicrousd=int(totals["cost"]),
            expiresAt=value.expiresAt.isoformat(),
        )
