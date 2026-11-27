"""Exact original planning pre-dispatch observation, never a recovery command."""

from .authority_contracts import ExactGrant
from .business_problem_authorization import problem_resource
from .owned_business_criterion_read import OwnedBusinessCriterionRead
from .plan_suggestion_domain import ExactReference
from .private_conversation import ConversationError


class OwnedBusinessPlanningStartRead(OwnedBusinessCriterionRead):
    """Reuse protected ordinary-owner reads; no authorization issuance."""

    def _read(self, c, ctx, conversation, invocation_id, key):
        row, _, now, _, value, _, _ = self.owner._source(c, ctx, invocation_id)
        scope = (ctx.scope.tenant_id, ctx.scope.security_domain)
        from .conversation_goal_selection import selected_journal

        journal = selected_journal(c, ctx, conversation, invocation=value)
        state = journal["state"] if journal else {}
        draft, source = state.get("draft") or {}, state.get("source") or {}
        expected = str(state.get("key", "")) + ":planning"
        if state.get("cycle"):
            expected += ":" + str(state["cycle"])
        if state.get("planningReply"):
            expected += ":clarification:" + str(state["planningReply"])
        if not (
            row["record"].get("conversation_id") == conversation
            and state.get("phase") == "PLAN"
            and state.get("pending") == "planning"
            and state.get("planningRequestKey", expected) == key == expected
            and draft.get("invocationId") == invocation_id
            and draft.get("inputSource") == value.input_source
            and source.get("source") == (value.input_source or {}).get("source")
            and source.get("sourceContentDigest")
            == (value.input_source or {}).get("sourceContentDigest")
        ):
            raise ConversationError("PLANNING_START_TARGET_CHANGED", 409)
        try:
            p = state["problem"]
            target = ExactReference(
                resource_id=p["business_problem_id"],
                revision_id=p["revision_id"],
                digest=p["digest"],
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ConversationError("PLANNING_START_TARGET_CHANGED", 409) from exc
        binding = self.owner.work(c, ctx, target)
        if binding.history_only:
            raise ConversationError("PLANNING_START_ACCESS_DENIED", 403)
        for grant in (
            ExactGrant(
                "BUSINESS_PROBLEM", "READ", problem_resource(target.resource_id)
            ),
            ExactGrant("PLAN", "PREPARE", "plan:prepare:" + target.resource_id),
        ):
            self._require_read(c, ctx, now, grant)
        admission = c.execute(
            "SELECT record FROM authorization_admin.owned_business_admissions "
            "WHERE admission_id=%s AND record_digest=%s",
            (binding.admission_id, binding.record_digest),
        ).fetchone()
        problem = c.execute(
            "SELECT p.current_state,r.digest FROM "
            "business_problem_authority.problems p "
            "JOIN business_problem_authority.problem_revisions r ON "
            "r.namespace=p.namespace AND r.security_domain=p.security_domain AND "
            "r.revision_id=p.current_revision_id WHERE p.namespace=%s AND "
            "p.security_domain=%s AND p.business_problem_id=%s AND "
            "p.current_revision_id=%s",
            (*scope, target.resource_id, target.revision_id),
        ).fetchone()
        if not (
            admission
            and admission["record"]["invocationId"] == invocation_id
            and type(draft.get("aggregateVersion")) is int
            and draft["aggregateVersion"]
            in (admission["record"]["aggregateVersion"], value.aggregate_version)
            and problem
            and problem["digest"] == target.digest
            and problem["current_state"] == "ACTIVE"
        ):
            raise ConversationError("PLANNING_START_TARGET_CHANGED", 409)
        # These reads do not use recovery(), settle a receipt, or observe a provider.
        invocation = c.execute(
            "SELECT invocation_id FROM workflow_planning.invocations WHERE "
            "namespace=%s AND security_domain=%s AND actor_id=%s AND request_key=%s",
            (*scope, ctx.principal_id, key),
        ).fetchone()
        preparation = c.execute(
            "SELECT context_id FROM authorization_admin.planning_call_preparations "
            "WHERE tenant_id=%s AND security_domain=%s AND subject_id=%s "
            "AND request_key=%s",
            (*scope, ctx.principal_id, key),
        ).fetchone()
        recovery = c.execute(
            "SELECT recovery_id FROM "
            "authorization_admin.conversation_planning_recoveries "
            "WHERE tenant_id=%s AND security_domain=%s AND subject_id=%s "
            "AND (request_key=%s OR new_request_key=%s)",
            (*scope, ctx.principal_id, key, key),
        ).fetchone()
        return {
            "state": "RECORDED"
            if invocation or preparation or recovery
            else "NOT_STARTED",
            "draftInvocationId": invocation_id,
            "draftAggregateVersion": draft["aggregateVersion"],
            "observedAggregateVersion": value.aggregate_version,
            "requestKey": key,
            "journeyKey": state["key"],
            "journalVersion": journal["version"],
            "problem": target.model_dump(),
            "source": value.input_source,
        }
