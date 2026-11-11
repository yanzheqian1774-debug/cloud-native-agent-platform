"""Exact capability provenance for the existing bounded D12 planning admission."""

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError
from .capability_conversation_source import verify_work_association
from .capability_execution_constraints import verify_current
from .private_conversation import ConversationError
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)


def source_reader(automation, reader, authorizer):
    def read(context, connection, request):
        target = request.target.problem.model_dump(mode="json")
        owner = {
            "kind": "PROBLEM",
            "target": {
                "problemId": target["resource_id"],
                "revisionId": target["revision_id"],
                "problemDigest": target["digest"],
            },
        }
        rows = connection.execute(
            "SELECT conversation_id,message_id "
            "FROM private_conversation.action_intents "
            "WHERE tenant_id=%s AND security_domain=%s AND confirmed_by=%s "
            "AND action='CREATE_PROBLEM' AND claimed_at IS NOT NULL "
            "AND source->>'kind'='CAPABILITY' AND owner_ref=%s",
            (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
                Jsonb(owner),
            ),
        ).fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise AuthorityError("DEVELOPMENT_CAPABILITY_SOURCE_AMBIGUOUS")
        try:
            with authorizer.controller.protected_request() as generation:
                call = AuthorizedOwnerCall(
                    operation="CAPABILITY_PLANNING_PROVENANCE",
                    context=context,
                    connection=connection,
                    payload={},
                    path={},
                    query={},
                    decisions=(),
                    authority=AuthorizedOwnerAuthority(
                        authorizer, context, connection, generation.generation, ()
                    ),
                    policy_generation=generation.generation,
                    recovery_epoch=authorizer.controller.readiness.recovery_epoch,
                )
                row = rows[0]
                resolved = reader(call, row["conversation_id"], row["message_id"])
                principal = OwnerPrincipal(
                    context.principal_id,
                    context.scope.tenant_id,
                    context.scope.security_domain,
                )
                current = automation.bound_app(call).current_input(
                    principal, target["resource_id"], connection
                )
                verify_current(resolved, current)
                if current["target"] != request.target.model_dump(mode="json"):
                    raise AuthorityError("DEVELOPMENT_CAPABILITY_TARGET_CHANGED")
                verify_work_association(call, resolved, target)
                return {
                    "conversationId": row["conversation_id"],
                    "sourceMessageId": row["message_id"],
                    "contractDigest": resolved["contractDigest"],
                    "problem": target,
                }
        except (ConversationError, WorkbenchOwnerError) as exc:
            raise AuthorityError("DEVELOPMENT_CAPABILITY_SOURCE_INVALID") from exc

    return read
