"""Owned conversation source reads; no collection, execution or grant writes."""

from contextlib import nullcontext

from .authority_contracts import AuthorityError, ExactGrant
from .private_conversation import ConversationError
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import AuthorizedOwnerAuthority, AuthorizedOwnerCall


class ConversationSourceAccess:
    def __init__(self, automation, authorizer, records, draft_service):
        self.automation = automation
        self.authorizer = authorizer
        self.records = records
        self.draft_service = draft_service

    def execute(self, context, conversation, handler, *, connection=None):
        admission = getattr(
            getattr(self.draft_service, "authorization", None),
            "context_admission",
            None,
        )
        experience = getattr(admission, "experience", None)
        owned_policy = bool(
            experience
            and experience.matches(context)
            and experience.document.ownedConversationUnderstanding
        )
        if not owned_policy and connection is None:

            def legacy(call):
                owned = self.records.owned(call.connection, context, conversation)
                if owned["archived_at"]:
                    raise ConversationError("CONVERSATION_ARCHIVED", 409)
                return handler(call)

            return self.authorizer.execute(
                context,
                (
                    ExactGrant(
                        "BUSINESS_PROBLEM", "LIST", "business-problem:collection"
                    ),
                ),
                operation="READ_CONVERSATION_SOURCES",
                payload={},
                path={},
                query={},
                handler=legacy,
            )
        authorizer = self.authorizer
        try:
            with (
                authorizer.controller.protected_request() as generation,
                (
                    nullcontext(connection)
                    if connection is not None
                    else authorizer.repository.connection_scope()
                ) as c,
            ):
                if connection is None:
                    c.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                owned = self.records.owned(c, context, conversation, lock=True)
                if owned_policy and owned["owner_id"] != context.principal_id:
                    raise ConversationError("CONVERSATION_NOT_FOUND", 404)
                if owned["archived_at"]:
                    raise ConversationError("CONVERSATION_ARCHIVED", 409)
                authority = AuthorizedOwnerAuthority(
                    authorizer, context, c, generation.generation, ()
                )
                if owned_policy:
                    _, now, _ = experience._require(admission, c, context)
                    credential = admission.repository._current_credential_id(
                        c,
                        context,
                        now=now,
                        recovery_epoch=authorizer.controller.readiness.recovery_epoch,
                        lock_session=True,
                    )
                    if credential != experience.document.accountId:
                        raise AuthorityError("CONTEXT_ADMISSION_ACCOUNT_INACTIVE")
                else:
                    authority.require(
                        OwnerPrincipal(
                            context.principal_id,
                            context.scope.tenant_id,
                            context.scope.security_domain,
                        ),
                        "BUSINESS_PROBLEM",
                        "LIST",
                        "business-problem:collection",
                    )
                # This entry is admitted by the current owned-conversation policy.
                # Every returned resource still independently requires exact READ.
                return handler(
                    AuthorizedOwnerCall(
                        operation="READ_OWNED_CONVERSATION_SOURCES",
                        context=context,
                        connection=c,
                        payload={},
                        path={"conversation": conversation},
                        query={},
                        decisions=(),
                        authority=authority,
                        policy_generation=generation.generation,
                        recovery_epoch=authorizer.controller.readiness.recovery_epoch,
                    )
                )
        except AuthorityError as exc:
            raise ConversationError("CONVERSATION_SOURCE_ACCESS_DENIED", 403) from exc

    def catalogue(self, context, conversation):
        from .conversation_sources import sources

        return self.execute(
            context,
            conversation,
            lambda call: {
                "items": sources(self.automation, call),
                "executionStarted": False,
            },
        )
