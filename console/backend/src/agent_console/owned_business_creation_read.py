"""Read committed CREATE facts for one current conversation command; never retry."""

from dataclasses import asdict

from .authority_contracts import AuthorityError, ExactGrant
from .business_problem_application import BusinessProblemApplication
from .business_problem_schemas import CreateBusinessProblem
from .execution_domain import ScopeIdentity
from .private_conversation import ConversationError
from .workbench_business_problem import OwnerPrincipal


class OwnedBusinessCreationRead:
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
                "CONVERSATION_CREATE_STATUS_ACCESS_DENIED", 403
            ) from exc

    def _read(self, c, ctx, conversation, invocation_id, key):
        source, _, now, _, value, _, _ = self.owner._source(c, ctx, invocation_id)
        if source["record"].get("conversation_id") != conversation:
            raise ConversationError("CONVERSATION_CREATE_STATUS_TARGET_CHANGED", 409)
        scope = (ctx.scope.tenant_id, ctx.scope.security_domain)
        journal = c.execute(
            "SELECT version,state FROM private_conversation.journeys WHERE "
            "tenant_id=%s AND security_domain=%s AND conversation_id=%s",
            (*scope, conversation),
        ).fetchone()
        state = journal["state"] if journal else {}
        draft = state.get("draft") or {}
        if not (
            state.get("phase") == "CREATE"
            and state.get("pending") in (None, "create-problem")
            and not state.get("problem")
            and draft.get("invocationId") == invocation_id
            and draft.get("inputSource") == value.input_source
            and isinstance(state.get("key"), str)
            and key == state["key"] + ":problem"
        ):
            raise ConversationError("CONVERSATION_CREATE_STATUS_TARGET_CHANGED", 409)
        command = CreateBusinessProblem.model_validate(
            {
                **(draft.get("draft") or {}),
                "ownerId": ctx.principal_id,
                "idempotencyKey": key,
            }
        )
        principal = OwnerPrincipal(ctx.principal_id, *scope)
        identity = BusinessProblemApplication.identity(principal, "CREATE_PROBLEM", key)
        payload = BusinessProblemApplication.payload(command)
        base = {
            "draftInvocationId": invocation_id,
            "requestKey": key,
            "journeyKey": state["key"],
            "journalVersion": journal["version"],
            "aggregateVersion": value.aggregate_version,
        }
        claim = c.execute(
            "SELECT * FROM business_problem_authority.idempotency_claims WHERE "
            "namespace=%s AND security_domain=%s AND actor_id=%s "
            "AND command_type='CREATE_BUSINESS_PROBLEM' AND idempotency_key=%s",
            (*scope, ctx.principal_id, key),
        ).fetchone()
        receipt = c.execute(
            "SELECT * FROM business_problem_authority.creator_receipts WHERE "
            "namespace=%s AND security_domain=%s AND creator_principal_id=%s "
            "AND originating_command_type='CREATE_BUSINESS_PROBLEM' "
            "AND originating_command_idempotency_key=%s",
            (*scope, ctx.principal_id, key),
        ).fetchone()
        bindings = c.execute(
            "SELECT * FROM authorization_admin.context_call_objects WHERE "
            "tenant_id=%s AND security_domain=%s AND owner='BUSINESS_PROBLEM' "
            "AND (context_id=%s OR resource_id=%s)",
            (*scope, value.context_id, identity),
        ).fetchall()
        problem = c.execute(
            "SELECT 1 FROM business_problem_authority.problems WHERE namespace=%s "
            "AND security_domain=%s AND business_problem_id=%s",
            (*scope, identity),
        ).fetchone()
        if not any((claim, receipt, bindings, problem)):
            # A concurrent transaction can subsequently commit. The caller must
            # retain the same key; only the CREATE owner's idempotency settles it.
            return {**base, "state": "NOT_CREATED"}
        if not (
            claim
            and receipt
            and problem
            and len(bindings) == 1
            and claim["payload_digest"] == payload
            and receipt["originating_command_payload_digest"] == payload
            and receipt["business_problem_id"] == identity
            and claim["result_kind"] == "PROBLEM_REVISION"
            and claim["result_id"] == receipt["revision_id"]
            and bindings[0]["resource_id"] == identity
            and bindings[0]["context_id"] == value.context_id
            and bindings[0]["invocation_id"] == invocation_id
        ):
            return {**base, "state": "UNKNOWN"}
        grant = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:" + identity)
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
            raise ConversationError("CONVERSATION_CREATE_STATUS_ACCESS_DENIED", 403)
        revisions = self.problems.get_problem(
            ScopeIdentity(*scope),
            identity,
            authorized=True,
            connection=c,
        )
        revision = next(
            (r for r in revisions if r.revision_id == receipt["revision_id"]), None
        )
        if not (
            revision
            and revision.digest == receipt["revision_digest"]
            and revision.created_by == ctx.principal_id
            and revision.owner_id == command.ownerId
            and revision.title == command.title
            and revision.description == command.description
        ):
            return {**base, "state": "UNKNOWN"}
        return {**base, "state": "CREATED", "revision": asdict(revision)}
