"""Governed confirmed-Problem suggestion; crash/replay never redispatches."""

import hmac
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from pydantic import ValidationError

from .business_problem_domain import canonical_bytes, canonical_digest
from .model_binding_resolution import (
    ExactModelBinding,
    ExactModelUse,
    ModelConsumptionScope,
    ModelUseAction,
    ModelUseSubject,
    resolve_authorized_model_binding,
)
from .plan_suggestion_domain import PlanningConflict, PlanningError, ProposalRevision
from .plan_suggestion_invocation import PlanningInvocationTarget, PlanningProviderResult


@dataclass(frozen=True)
class PlanningBudgetIdentity:
    scope: object
    invocation_id: str
    profile_revision_id: str


class PlanningSuggestionService:
    def __init__(
        self,
        application,
        invocations,
        profile,
        *,
        model_authorizer,
        model_resolver,
        budget,
        quote,
        provider,
        model_use_owner,
        commitment_key,
        prepare_resources,
    ):
        self.application = application
        self.invocations = invocations
        self.profile = profile
        self.model_authorizer = model_authorizer
        self.model_resolver = model_resolver
        self.budget = budget
        self.quote = quote
        self.provider = provider
        self.model_use_owner = model_use_owner
        self.commitment_key = commitment_key
        self.prepare_resources = prepare_resources
        if len(commitment_key) < 32:
            raise PlanningError("PLANNING_COMMITMENT_KEY_REQUIRED")

    def begin(self, principal, request):
        app = self.application
        scope = app.scope(principal)
        # Purpose permission is exact to the confirmed Problem, before owner lookup.
        app.authority.require(
            principal,
            "PLAN",
            "PREPARE",
            f"plan:prepare:{request.target.problem.resource_id}",
        )
        encoded = canonical_bytes(request.model_dump(mode="json"))
        if len(encoded) > self.profile.maximum_input_bytes:
            raise PlanningError("PLANNING_INPUT_TOO_LARGE")
        commitment = hmac.new(self.commitment_key, encoded, sha256).hexdigest()
        replay = self.invocations.find_request(
            scope, principal.principal_id, request.idempotency_key, commitment
        )
        if replay:
            return self.read(principal, replay)
        with app.repository.transaction(
            scope, request.target.problem.resource_id, authorized=True
        ) as cursor:
            app.validate_target(principal, request.target, cursor.connection)
        synthetic = self.provider.synthetic
        if not synthetic and not self.profile.real_calls_enabled:
            raise PlanningError("PLANNING_REAL_CALLS_DISABLED")
        model = self.profile.model
        use = ExactModelUse(
            ExactModelBinding(model.resource_id, model.revision_id, model.digest),
            ModelUseAction.INVOKE_MODEL,
            f"model:invocation:plan-suggestion:{model.resource_id}:"
            f"{model.revision_id}:{model.digest}",
        )
        resolved = resolve_authorized_model_binding(
            ModelConsumptionScope(scope.namespace, scope.security_domain),
            ModelUseSubject(principal.principal_id),
            use,
            authorizer=self.model_authorizer,
            resolver=self.model_resolver,
            evaluation_time=datetime.now(UTC),
        )
        source = None
        if request.source_proposal is not None:
            source_ref = request.source_proposal
            app.require(principal, "READ", source_ref.resource_id)
            with app.repository.transaction(
                scope, source_ref.resource_id, authorized=True
            ) as cursor:
                try:
                    revision = int(source_ref.revision_id)
                except ValueError as exc:
                    raise PlanningError("PLANNING_SOURCE_INVALID") from exc
                source = app.repository.proposal(
                    cursor, scope, source_ref.resource_id, revision
                )
                if source.digest != source_ref.digest:
                    raise PlanningConflict("PLANNING_SOURCE_DIGEST_CONFLICT")
        resource_snapshot = self.prepare_resources(principal, request.target)
        invocation_id = str(uuid4())
        context_id = source.proposal_id if source else str(uuid4())
        request_revision = 1
        predecessor_id = source.invocation_id if source else None
        if request.predecessor_invocation_id is not None:
            previous = self.read(principal, request.predecessor_invocation_id)
            previous_target = PlanningInvocationTarget.model_validate(
                previous["invocation"]["target"]
            )
            if previous_target.problem != request.target or (
                source is not None
                and source.proposal_id != previous_target.suggestion_context_id
            ):
                raise PlanningConflict("PLANNING_PREDECESSOR_TARGET_CONFLICT")
            if previous["result"]["technical_status"] != "SUCCEEDED":
                raise PlanningConflict("PLANNING_PREDECESSOR_NOT_TERMINAL")
            context_id = previous_target.suggestion_context_id
            request_revision = previous_target.request_revision + 1
            predecessor_id = request.predecessor_invocation_id
        target = PlanningInvocationTarget(
            namespace=scope.namespace,
            security_domain=scope.security_domain,
            invocation_id=invocation_id,
            suggestion_context_id=context_id,
            request_revision=request_revision,
            predecessor_invocation_id=predecessor_id,
            problem=request.target,
            source_proposal=request.source_proposal,
            variant="SUCCESSOR_PROPOSAL" if source else "FIRST_PROPOSAL",
            resource_snapshot=resource_snapshot,
            input_commitment=commitment,
            policy_version="planning-validator.v1",
        )
        decision = app.authority.require(
            principal, "MODEL_GOVERNANCE", "INVOKE_MODEL", use.exact_resource
        )
        record = {
            "target": target.model_dump(mode="json"),
            "target_digest": canonical_digest(target.model_dump(mode="json")),
            "binding": json.loads(json.dumps(asdict(resolved), default=str)),
            "profile": self.profile.model_dump(mode="json"),
            "authorization_decision_id": decision.decision_id,
            "transport": "CONTROLLED_TEST_PROVIDER" if synthetic else "REAL_PROVIDER",
        }
        persisted, claimed = self.invocations.claim(
            scope, principal.principal_id, request.idempotency_key, commitment, record
        )
        if not claimed:
            return self.read(principal, persisted["target"]["invocation_id"])
        # Claim is durable before budget/resource-use/provider effects. A crash or
        # uncertain result keeps the claim and does not permit another dispatch.
        identity = PlanningBudgetIdentity(
            scope, invocation_id, self.profile.profile_revision_id
        )
        self.budget.reserve(invocation_id + ":budget", identity, self.quote)
        self.model_use_owner.requested(scope, record)
        app.authority.require(
            principal,
            "PLAN",
            "PREPARE",
            f"plan:prepare:{request.target.problem.resource_id}",
        )
        app.authority.require(
            principal, "MODEL_GOVERNANCE", "INVOKE_MODEL", use.exact_resource
        )
        try:
            raw = self.provider.suggest(request, resolved, self.profile)
        except (TimeoutError, ConnectionError):
            result = {
                "technical_status": "OUTCOME_UNKNOWN",
                "kind": None,
                "reason": "PROVIDER_OUTCOME_UNKNOWN",
            }
            self.invocations.finish(scope, invocation_id, result)
            self.model_use_owner.observed(scope, record, result)
            return self.read(principal, invocation_id)
        proposal = None
        try:
            if not isinstance(raw, str) or len(raw.encode()) > 131072:
                raise ValueError("PLANNING_OUTPUT_TOO_LARGE")
            parsed = PlanningProviderResult.model_validate_json(raw)
            if parsed.semantics is not None:
                if parsed.semantics.target != request.target:
                    raise ValueError("PLANNING_OUTPUT_TARGET_MISMATCH")
                proposal = ProposalRevision(
                    proposal_id=context_id,
                    revision=source.revision + 1 if source else 1,
                    predecessor_digest=source.digest if source else None,
                    invocation_id=invocation_id,
                    semantics=parsed.semantics,
                )
            result = {
                "technical_status": "SUCCEEDED",
                "kind": parsed.kind,
                "questions": list(parsed.questions),
                "proposal": proposal.model_dump(mode="json") if proposal else None,
                "proposal_digest": proposal.digest if proposal else None,
                "output_digest": canonical_digest(parsed.model_dump(mode="json")),
            }
        except (ValidationError, ValueError):
            result = {
                "technical_status": "SUCCEEDED",
                "kind": "INVALID",
                "reason": "PLANNING_OUTPUT_SCHEMA_INVALID",
            }
        self.invocations.finish(
            scope,
            invocation_id,
            result,
            proposal,
            validate=lambda connection: app.validate_target(
                principal, request.target, connection
            ),
        )
        self.model_use_owner.observed(scope, record, result)
        return self.read(principal, invocation_id)

    def read(self, principal, invocation_id):
        app = self.application
        scope = app.scope(principal)
        result = self.invocations.read(scope, invocation_id, principal.principal_id)
        target = PlanningInvocationTarget.model_validate(result["invocation"]["target"])
        app.authority.require(
            principal,
            "PLAN",
            "READ",
            f"plan:prepared:{target.problem.problem.resource_id}",
        )
        with app.repository.transaction(
            scope, target.suggestion_context_id, authorized=True
        ) as cursor:
            app.validate_target(
                principal, target.problem, cursor.connection, current=False
            )
        result["facts_status"] = self.model_use_owner.status(scope, invocation_id)
        return result
