"""Governed confirmed-Problem suggestion; crash/replay never redispatches."""

import hmac
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from pydantic import ValidationError

from .authority_contracts import AuthorityError
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
from .plan_suggestion_invocation import (
    FlexiblePlanningProviderResult,
    PlanningInvocationTarget,
    PlanningProviderResult,
)
from .plan_suggestion_policy import POLICY_DIGEST, V2_POLICY_DIGEST, VERSION


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
        identity_factory=lambda: str(uuid4()),
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
        self.identity_factory = identity_factory
        if len(commitment_key) < 32:
            raise PlanningError("PLANNING_COMMITMENT_KEY_REQUIRED")

    def begin(self, principal, request, *, diagnostic_layer=None):
        app = self.application
        scope = app.scope(principal)
        # Purpose permission is exact to the confirmed Problem, before owner lookup.
        app.authority.require(
            principal,
            "PLAN",
            "PREPARE",
            f"plan:prepare:{request.target.problem.resource_id}",
        )
        document = request.model_dump(
            mode="json", exclude={"policy"} if request.policy is None else set()
        )
        if diagnostic_layer is not None:
            from .planning_diagnostics import LAYERS

            authorize = getattr(self.budget, "require_diagnostic", None)
            if diagnostic_layer not in LAYERS or authorize is None:
                raise AuthorityError("PLANNING_DIAGNOSTIC_NOT_AUTHORIZED")
            authorize(principal, request)
            if (
                request.answers
                or request.source_proposal
                or request.predecessor_invocation_id
                or request.policy
            ):
                raise PlanningError("PLANNING_DIAGNOSTIC_INPUT_INVALID")
            document["diagnostic_layer"] = diagnostic_layer
        encoded = canonical_bytes(document)
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
            business_context = app.current_input(
                principal, request.target.problem.resource_id, cursor.connection
            )
        if len(encoded) + len(canonical_bytes(business_context)) > (
            self.profile.maximum_input_bytes
        ):
            raise PlanningError("PLANNING_INPUT_TOO_LARGE")
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
        previous_questions = []
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
        if source is not None and (
            source.semantics.target.problem.resource_id
            != request.target.problem.resource_id
        ):
            raise PlanningConflict("PLANNING_SOURCE_TARGET_CONFLICT")
        resource_snapshot = self.prepare_resources(principal, request.target)
        invocation_id = self.identity_factory()
        context_id = source.proposal_id if source else self.identity_factory()
        request_revision = 1
        predecessor_id = source.invocation_id if source else None
        if request.predecessor_invocation_id is not None:
            previous = self.read(principal, request.predecessor_invocation_id)
            previous_target = PlanningInvocationTarget.model_validate(
                previous["invocation"]["target"]
            )
            if (previous_target.problem != request.target and source is None) or (
                source is not None
                and source.proposal_id != previous_target.suggestion_context_id
            ):
                raise PlanningConflict("PLANNING_PREDECESSOR_TARGET_CONFLICT")
            if previous["result"]["technical_status"] != "SUCCEEDED":
                raise PlanningConflict("PLANNING_PREDECESSOR_NOT_TERMINAL")
            if source is None and previous["result"]["kind"] != "NEEDS_CLARIFICATION":
                raise PlanningConflict("PLANNING_PREDECESSOR_REQUIRES_SOURCE")
            if previous_target.request_revision >= 8:
                raise PlanningConflict("PLANNING_CLARIFICATION_LIMIT")
            previous_questions = previous["result"].get("questions", [])
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
            policy_version=("planning-suggestion.v2" if request.policy else VERSION)
            if diagnostic_layer is None
            else "planning-diagnostic.v1",
            output_schema=(
                "plan-suggestion-output.v2"
                if request.policy
                else "plan-suggestion-output.v1"
            )
            if diagnostic_layer is None
            else "planning-diagnostic-output.v1",
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
            "policy_digest": V2_POLICY_DIGEST if request.policy else POLICY_DIGEST,
            "call_path": "CONFIRMED_PROBLEM_PLAN_SUGGESTION",
            "provider_configuration": getattr(self.provider, "diagnostics", {}),
        }
        if request.policy:
            record["request"] = document
            record["submitted_at"] = datetime.now(UTC).isoformat()
        if diagnostic_layer is not None:
            from .planning_diagnostics import policy_digest

            record["policy_digest"] = policy_digest(diagnostic_layer)
            record["diagnostic_layer"] = diagnostic_layer
            record["call_path"] = "S5_323_DEVELOPMENT_DIAGNOSTIC"
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
        reservation_id = self.budget.reserve(
            invocation_id + ":budget", identity, self.quote
        )
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
        business_context = {
            **business_context,
            "planning_context": {
                "invocation_id": invocation_id,
                "previous_questions": previous_questions,
                "source_proposal": source.model_dump(mode="json") if source else None,
            },
        }
        if request.policy:
            business_context["planning_policy"] = request.policy.model_dump(mode="json")
        if diagnostic_layer is not None:
            business_context["diagnostic_layer"] = diagnostic_layer
        # Recheck current Problem/Criteria immediately before the network boundary.
        with app.repository.transaction(scope, context_id, authorized=True) as cursor:
            app.validate_target(principal, request.target, cursor.connection)
        provider_entered = False
        try:
            from contextlib import nullcontext

            guard = getattr(self.budget, "dispatch_guard", None)
            with guard(identity, self.quote) if guard else nullcontext():
                provider_entered = True
                raw = self.provider.suggest(
                    request, resolved, self.profile, business_context
                )
        except AuthorityError:
            result = {
                "technical_status": "OUTCOME_UNKNOWN" if provider_entered else "FAILED",
                "kind": None,
                "reason": "PROVIDER_OUTCOME_UNKNOWN"
                if provider_entered
                else "DISPATCH_ADMISSION_DENIED",
            }
            self.invocations.finish(scope, invocation_id, result)
            self.model_use_owner.observed(scope, record, result)
            return self.read(principal, invocation_id)
        except (TimeoutError, ConnectionError):
            result = {
                "technical_status": "OUTCOME_UNKNOWN",
                "kind": None,
                "reason": "PROVIDER_OUTCOME_UNKNOWN",
            }
            self.invocations.finish(scope, invocation_id, result)
            self.model_use_owner.observed(scope, record, result)
            return self.read(principal, invocation_id)
        except PlanningError as exc:
            # Only provider-owned fixed codes are surfaced, never exception bodies.
            from .plan_suggestion_runtime import PlanningProviderFailure

            if not isinstance(exc, PlanningProviderFailure):
                raise
            result = {"technical_status": "FAILED", "kind": None, "reason": str(exc)}
            self.invocations.finish(scope, invocation_id, result)
            self.model_use_owner.observed(scope, record, result)
            return self.read(principal, invocation_id)
        if isinstance(raw, dict):
            # Durable metering is independent of business validity and target CAS.
            receipt = {
                "schema_version": "planning-provider-receipt.v1",
                "invocation_id": invocation_id,
                "target_digest": record["target_digest"],
                "reservation_id": reservation_id,
                "measurement": raw.get("measurement", {}),
                "deadline": raw.get("deadline"),
                "pricing": self.budget.pricing(),
            }
            if raw.get("validation_diagnostic") is not None:
                receipt["validation_diagnostic"] = raw["validation_diagnostic"]
            self.invocations.save_receipt(scope, invocation_id, receipt)
            from .planning_measurement import settle

            settle(self.budget, invocation_id, receipt)
            failure = raw.get("failure")
            if failure:
                status = (
                    "OUTCOME_UNKNOWN"
                    if failure == "PROVIDER_OUTCOME_UNKNOWN"
                    else "SUCCEEDED"
                    if failure == "PLANNING_OUTPUT_SCHEMA_INVALID"
                    else "FAILED"
                )
                result = {
                    "technical_status": status,
                    "kind": "INVALID" if status == "SUCCEEDED" else None,
                    "reason": failure,
                }
                self.invocations.finish(scope, invocation_id, result)
                self.model_use_owner.observed(scope, record, result)
                return self.read(principal, invocation_id)
            if diagnostic_layer is not None:
                result = {
                    "technical_status": "SUCCEEDED",
                    "kind": "DIAGNOSTIC",
                    "diagnostic_layer": diagnostic_layer,
                    "passed": raw.get("diagnostic_passed") is True,
                    "reason": "DIAGNOSTIC_ONLY_NOT_A_BUSINESS_PLAN",
                }
                self.invocations.finish(scope, invocation_id, result)
                self.model_use_owner.observed(scope, record, result)
                return self.read(principal, invocation_id)
            raw = raw["text"]
        if diagnostic_layer is not None:
            raise PlanningError("PLANNING_DIAGNOSTIC_RESPONSE_INVALID")
        proposal = None
        try:
            if not isinstance(raw, str) or len(raw.encode()) > 131072:
                raise ValueError("PLANNING_OUTPUT_TOO_LARGE")
            parsed = (
                FlexiblePlanningProviderResult
                if request.policy
                else PlanningProviderResult
            ).model_validate_json(raw)
            if parsed.semantics is not None:
                if parsed.semantics.target != request.target:
                    raise ValueError("PLANNING_OUTPUT_TARGET_MISMATCH")
                if request.policy and parsed.semantics.policy != request.policy:
                    raise ValueError("PLANNING_OUTPUT_POLICY_MISMATCH")
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
            if request.policy:
                from .planning_contracts import validation_report

                result["generated_at"] = datetime.now(UTC).isoformat()
                result["validation"] = (
                    validation_report(parsed.semantics) if parsed.semantics else None
                )
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

    def read_usage(self, principal, invocation_id):
        from .provider_usage import authorize, projection, unavailable

        app = self.application
        authorize(
            lambda *grant: app.authority.require(principal, *grant),
            "planning",
            invocation_id,
        )
        scope = app.scope(principal)
        receipt = self.invocations.receipt(scope, invocation_id)
        if receipt is None:
            raise unavailable()
        if receipt["pricing"] != self.budget.pricing():
            raise unavailable()
        return projection(
            receipt.get("measurement"),
            receipt["pricing"],
            receipt["reservation_id"],
            self.budget.owner.read_settlement(receipt["reservation_id"]),
            local_cleanup=receipt.get("deadline"),
        )

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
        if hasattr(self.invocations, "receipt"):
            receipt = self.invocations.receipt(scope, invocation_id)
            if receipt is not None:
                from .planning_measurement import settle

                # Authorization above precedes recovery of an already authorized effect.
                if receipt["pricing"] != self.budget.pricing():
                    raise PlanningConflict("PLANNING_PRICE_VERSION_CONFLICT")
                settle(self.budget, invocation_id, receipt)
                # PLAN READ does not grant disclosure of provider IDs or pricing.
        result["facts_status"] = self.model_use_owner.status(scope, invocation_id)
        return result
