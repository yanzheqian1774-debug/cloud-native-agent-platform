"""Observe the exact original criterion command; never create or authorize it."""

# ruff: noqa: RUF001 -- Match the existing user-facing completion rubric exactly.

from dataclasses import asdict

from .authority_contracts import AuthorityError, ExactGrant
from .business_problem_application import BusinessProblemApplication
from .business_problem_authorization import criterion_resource, problem_resource
from .business_problem_schemas import CreateCriterionRevision
from .execution_domain import ScopeIdentity
from .plan_suggestion_domain import ExactReference
from .private_conversation import ConversationError
from .workbench_business_problem import OwnerPrincipal


def criterion_command(state):
    problem, source = state["problem"], state["source"]
    criteria = source.get("completionCriteria")
    if criteria is None:
        criteria = ["展示来源依据、异常与资料缺口；区分观察和推测。"]
    description = problem.get("description")
    return CreateCriterionRevision.model_validate(
        {
            "criterionType": "HUMAN_EVALUATED",
            "measurement": {
                "rubric": "回答已确认的用户目标："
                + (description if description is not None else state["question"])
                + "。"
                + "".join(criteria)
                + "仅作为测试资料分析，不代表真实业务问题已经解决。"
            },
            "requiredEvidenceKinds": [],
            "evaluatorType": "HUMAN",
            "evaluatorVersion": "v1",
            "applicability": {"sourceReference": source["source"]},
            "idempotencyKey": state["key"] + ":criterion",
        }
    )


class OwnedBusinessCriterionRead:
    def __init__(self, owner, authorizer, problems):
        self.owner, self.authorizer, self.problems = owner, authorizer, problems

    def read(self, context, conversation, invocation_id, request_key):
        try:
            with (
                self.authorizer.controller.protected_request(),
                self.owner.root.repository.connection_scope() as c,
            ):
                return self._read(c, context, conversation, invocation_id, request_key)
        except AuthorityError as exc:
            raise ConversationError(
                "CONVERSATION_CRITERION_STATUS_ACCESS_DENIED", 403
            ) from exc

    def _read(self, c, ctx, conversation, invocation_id, key):
        row, _, now, _, value, _, _ = self.owner._source(c, ctx, invocation_id)
        scope = (ctx.scope.tenant_id, ctx.scope.security_domain)
        from .conversation_goal_selection import selected_journal

        journal = selected_journal(c, ctx, conversation, invocation=value)
        state = journal["state"] if journal else {}
        draft, problem, source = (
            state.get("draft") or {},
            state.get("problem") or {},
            state.get("source") or {},
        )
        if not (
            row["record"].get("conversation_id") == conversation
            and state.get("phase") == "CRITERION"
            and state.get("pending") == "criterion"
            and not state.get("criterion")
            and draft.get("invocationId") == invocation_id
            and draft.get("inputSource") == value.input_source
            and source.get("source") == (value.input_source or {}).get("source")
            and source.get("sourceContentDigest")
            == (value.input_source or {}).get("sourceContentDigest")
            and isinstance(state.get("key"), str)
            and key == state["key"] + ":criterion"
        ):
            raise ConversationError("CONVERSATION_CRITERION_STATUS_TARGET_CHANGED", 409)
        try:
            target = ExactReference(
                resource_id=problem["business_problem_id"],
                revision_id=problem["revision_id"],
                digest=problem["digest"],
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ConversationError(
                "CONVERSATION_CRITERION_STATUS_TARGET_CHANGED", 409
            ) from exc
        binding = self.owner.work(c, ctx, target)
        if binding.history_only:
            raise ConversationError("CONVERSATION_CRITERION_STATUS_ACCESS_DENIED", 403)
        from .owned_business_admission_successor import read_exact

        admission = read_exact(
            c,
            binding.admission_id,
            ctx.scope.tenant_id,
            ctx.scope.security_domain,
            ctx.principal_id,
            expected_digest=binding.record_digest,
        )
        # work() proved current value is the exact original or its lawful link.
        # The journal may retain that original version, never an arbitrary echo.
        if not (
            admission
            and admission["record"]["invocationId"] == invocation_id
            and type(draft.get("aggregateVersion")) is int
            and draft["aggregateVersion"]
            in (admission["record"]["aggregateVersion"], value.aggregate_version)
        ):
            raise ConversationError("CONVERSATION_CRITERION_STATUS_TARGET_CHANGED", 409)

        self._require_read(
            c,
            ctx,
            now,
            ExactGrant(
                "BUSINESS_PROBLEM", "READ", problem_resource(target.resource_id)
            ),
        )
        revisions = self.problems.get_problem(
            ScopeIdentity(*scope), target.resource_id, authorized=True, connection=c
        )
        actual_problem = next(
            (
                p
                for p in revisions
                if p.revision_id == target.revision_id and p.digest == target.digest
            ),
            None,
        )
        if actual_problem is None or actual_problem.description != problem.get(
            "description"
        ):
            raise ConversationError("CONVERSATION_CRITERION_STATUS_TARGET_CHANGED", 409)
        try:
            command = criterion_command(state)
        except (KeyError, ValueError, TypeError) as exc:
            raise ConversationError(
                "CONVERSATION_CRITERION_STATUS_TARGET_CHANGED", 409
            ) from exc
        principal = OwnerPrincipal(ctx.principal_id, *scope)
        identity = BusinessProblemApplication.identity(
            principal, "CREATE_CRITERION", key
        )
        revision_id = BusinessProblemApplication.identity(
            principal, "CRITERION_REVISION", key
        )
        claim = c.execute(
            "SELECT * FROM business_problem_authority.idempotency_claims "
            "WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND "
            "command_type='CREATE_CRITERION_REVISION' AND idempotency_key=%s",
            (*scope, ctx.principal_id, key),
        ).fetchone()
        aggregate = c.execute(
            "SELECT * FROM business_problem_authority.criteria WHERE "
            "namespace=%s AND security_domain=%s AND success_criterion_id=%s",
            (*scope, identity),
        ).fetchone()
        stored = c.execute(
            "SELECT * FROM business_problem_authority.criterion_revisions "
            "WHERE namespace=%s AND security_domain=%s AND revision_id=%s",
            (*scope, revision_id),
        ).fetchone()
        bindings = c.execute(
            "SELECT * FROM authorization_admin.context_call_objects WHERE "
            "tenant_id=%s AND security_domain=%s AND "
            "owner='SUCCESS_CRITERION' AND resource_id=ANY(%s)",
            (*scope, [identity, revision_id]),
        ).fetchall()
        base = {
            "draftInvocationId": invocation_id,
            "draftAggregateVersion": draft.get("aggregateVersion"),
            "observedAggregateVersion": value.aggregate_version,
            "requestKey": key,
            "journeyKey": state["key"],
            "journalVersion": journal["version"],
            "problem": target.model_dump(),
        }
        if not any((claim, aggregate, stored, bindings)):
            return {**base, "state": "NOT_WRITTEN"}
        if not (
            claim
            and aggregate
            and stored
            and len(bindings) == 2
            and {b["resource_id"] for b in bindings} == {identity, revision_id}
            and all(
                b["context_id"] == value.context_id
                and b["invocation_id"] == invocation_id
                for b in bindings
            )
            and claim["payload_digest"] == BusinessProblemApplication.payload(command)
            and claim["result_kind"] == "CRITERION_REVISION"
            and claim["result_id"] == revision_id
            and claim["result_record"] == {"revision_id": revision_id}
            and stored["success_criterion_id"] == identity
            and stored["created_by"] == ctx.principal_id
        ):
            return {**base, "state": "UNKNOWN"}
        grant = ExactGrant("SUCCESS_CRITERION", "READ", criterion_resource())
        self._require_read(c, ctx, now, grant)
        revision = self.problems.get_criterion_revision(
            ScopeIdentity(*scope), revision_id, authorized=True, connection=c
        )
        if not (
            revision.criterion_type == command.criterionType
            and revision.revision == 1
            and revision.predecessor_revision_id is None
            and revision.measurement == command.measurement
            and revision.applicability == command.applicability
            and revision.evaluator_type == command.evaluatorType
            and revision.evaluator_version == command.evaluatorVersion
            and revision.required_evidence_kinds == tuple(command.requiredEvidenceKinds)
        ):
            return {**base, "state": "UNKNOWN"}
        return {**base, "state": "WRITTEN", "revision": asdict(revision)}

    def _require_read(self, c, ctx, now, grant):
        allowed = self.owner.grants.authorization.has_current_grants(
            ctx,
            (grant,),
            now=now,
            generation=self.owner.grants.generation.generation,
            recovery_epoch=self.owner.grants.recovery_epoch,
            connection=c,
            configure_transaction=False,
        )
        if len(allowed) != 1 or not allowed[0]:
            raise ConversationError("CONVERSATION_CRITERION_STATUS_ACCESS_DENIED", 403)
