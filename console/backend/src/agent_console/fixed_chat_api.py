"""Bounded original-chat READ endpoints; no generic empty-grant owner bypass."""

from fastapi import Request

from .authority_contracts import ExactGrant
from .fixed_chat_delivery import FixedChatDelivery
from .fixed_chat_read_access import FixedChatReadAccess, ReadAccess
from .workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)


def install_fixed_chat(policy, authorizer, automation, cursors):
    def install(app, authenticate, require_csrf, boundary_policy):
        app.state.fixed_work_activity_available = lambda context: bool(
            policy.enabled
            and automation.grants.clock() < policy.expiresAt
            and any(
                (scope.tenantId, scope.securityDomain, scope.subjectId)
                == (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    context.principal_id,
                )
                for scope in policy.scopes
            )
        )

        def execute(request, conversation, invoke, *, write=False):
            session, context = authenticate(request)
            if write:
                require_csrf(request, session)
            actions = getattr(app.state, "conversation_actions", None)
            if actions is None:
                raise WorkbenchOwnerError("FIXED_CHAT_READ_UNAVAILABLE", 503)
            if not policy.enabled or automation.grants.clock() >= policy.expiresAt:
                raise WorkbenchOwnerError("FIXED_CHAT_READ_POLICY_UNAVAILABLE", 503)
            with (
                authorizer.controller.protected_request() as generation,
                authorizer.repository.connection_scope() as c,
            ):
                c.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                # A registered probe checks current identity only, not broad LIST.
                # Every data/command authority remains exact in the handler.
                authorizer.authorization.require_current_context(
                    context,
                    (
                        ExactGrant(
                            "BUSINESS_PROBLEM", "LIST", "business-problem:collection"
                        ),
                    ),
                    now=authorizer.clock(),
                    generation=generation.generation,
                    recovery_epoch=authorizer.controller.readiness.recovery_epoch,
                    connection=c,
                )
                authority = AuthorizedOwnerAuthority(
                    authorizer, context, c, generation.generation, ()
                )
                call = AuthorizedOwnerCall(
                    "READ_FIXED_CHAT_ACTIVITY",
                    context,
                    c,
                    {},
                    {},
                    {},
                    (),
                    authority,
                    generation.generation,
                    authorizer.controller.readiness.recovery_epoch,
                )
                delivery = FixedChatDelivery(
                    policy, actions.records, automation, cursors
                )
                return {"result": invoke(call, delivery)}

        @app.get("/api/workbench/v1/conversations/{conversation}/fixed-work-activity")
        def read(conversation: str, request: Request, cursor: str | None = None):
            if set(request.query_params) - {"cursor"}:
                raise WorkbenchOwnerError("FIXED_CHAT_QUERY_INVALID", 400)
            return execute(
                request,
                conversation,
                lambda call, owner: owner.read(call, conversation, cursor),
            )

        @app.get(
            "/api/workbench/v1/conversations/{conversation}/fixed-work-activity/read-access"
        )
        def read_access_status(
            conversation: str,
            request: Request,
            commandId: str,
            eventId: str,
            receiptDigest: str,
        ):
            if (
                set(request.query_params) != {"commandId", "eventId", "receiptDigest"}
                or not 1 <= len(commandId) <= 160
                or not 1 <= len(eventId) <= 200
                or len(receiptDigest) != 64
            ):
                raise WorkbenchOwnerError("FIXED_CHAT_QUERY_INVALID", 400)
            return execute(
                request,
                conversation,
                lambda call, owner: FixedChatReadAccess(owner).status(
                    call, conversation, eventId, receiptDigest, commandId
                ),
            )

        @app.post(
            "/api/workbench/v1/conversations/{conversation}/fixed-work-activity/read-access"
        )
        def prepare(conversation: str, request: Request, body: ReadAccess):
            if request.query_params:
                raise WorkbenchOwnerError("FIXED_CHAT_QUERY_INVALID", 400)
            return execute(
                request,
                conversation,
                lambda call, owner: FixedChatReadAccess(owner).prepare(
                    call, conversation, body
                ),
                write=True,
            )

        import os

        from .fixed_chat_focus_api import install as install_focus

        if os.environ.get("FIXED_CHAT_FOLLOWUP_ENABLED") == "1":
            install_focus(app, execute, policy, authorizer, automation, cursors)

    return install
