# ruff: noqa: E501 -- Exact message-owned link and current authority.
"""Current question input and historical answer provenance are distinct reads."""

from .authority_contracts import ExactGrant
from .fixed_question_context import from_presentation
from .fixed_question_facts import require
from .fixed_question_store import FixedQuestionStore
from .workbench_owner_authorization import AuthorizedOwnerAuthority, AuthorizedOwnerCall


class FixedQuestionReader:
    def __init__(self, records, authorizer, delivery_factory, owner_factory):
        self.records, self.authorizer = records, authorizer
        self.delivery_factory, self.owner_factory = delivery_factory, owner_factory

    def in_transaction(
        self, c, context, conversation, target, *, message_id="", current=False
    ):
        require(set(target) == {"fixedCycleQuestion"})
        ref = target["fixedCycleQuestion"]
        require(set(ref) == {"conversationId", "presentationId", "presentationDigest"})
        require(ref["conversationId"] == conversation)
        store = FixedQuestionStore(c, self.records.scope(context))
        p = store.presentation(ref["presentationId"])
        require(p is not None and p.digest == ref["presentationDigest"])
        require(
            p.actorId == context.principal_id
            and p.identity.conversationId == conversation
        )
        self.records.owned(c, context, conversation, lock=True)
        a = self.authorizer
        with a.controller.protected_request() as generation:
            a.authorization.require_current_context(
                context,
                (
                    ExactGrant(
                        "EXECUTION",
                        "READ",
                        "governed-execution:prepared:" + p.identity.preparationDigest,
                    ),
                ),
                now=a.clock(),
                generation=generation.generation,
                recovery_epoch=a.controller.readiness.recovery_epoch,
                connection=c,
            )
            authority = AuthorizedOwnerAuthority(
                a, context, c, generation.generation, ()
            )
            call = AuthorizedOwnerCall(
                "READ_FIXED_CYCLE_QUESTION",
                context,
                c,
                {},
                {},
                {},
                (),
                authority,
                generation.generation,
                a.controller.readiness.recovery_epoch,
            )
            presentations, _ = self.owner_factory(self.delivery_factory())
            if current:
                presentations.require_current(call, p)
            else:
                presentations.require_read(call, p)
        return p, from_presentation(p, message_id)

    def read(
        self, context, conversation, *, target=None, message_id=None, current=False
    ):
        # Barrier precedes the transaction/chat lock, including read recovery.
        with (
            self.authorizer.controller.protected_request(),
            self.records.connect() as c,
        ):
            self.records.owned(c, context, conversation, lock=True)
            if message_id is not None:
                row = c.execute(
                    "SELECT l.target FROM private_conversation.messages m LEFT JOIN private_conversation.links l ON l.tenant_id=m.tenant_id AND l.security_domain=m.security_domain AND l.conversation_id=m.conversation_id AND l.link_id=m.focus_link_id WHERE m.tenant_id=%s AND m.security_domain=%s AND m.conversation_id=%s AND m.message_id=%s AND m.author_id=%s AND NOT EXISTS(SELECT 1 FROM private_conversation.message_facts f WHERE f.tenant_id=m.tenant_id AND f.security_domain=m.security_domain AND f.conversation_id=m.conversation_id AND f.message_id=m.message_id)",
                    (
                        *self.records.scope(context),
                        conversation,
                        message_id,
                        context.principal_id,
                    ),
                ).fetchone()
                require(row is not None)
                target = row["target"]
                if not target or "fixedCycleQuestion" not in target:
                    return None
            require(target is not None)
            return self.in_transaction(
                c,
                context,
                conversation,
                target,
                message_id=message_id or "",
                current=current,
            )

    @staticmethod
    def target(p):
        return {
            "fixedCycleQuestion": dict(
                conversationId=p.identity.conversationId,
                presentationId=p.presentationId,
                presentationDigest=p.digest,
            )
        }


def connect(app, reader):
    """Called only by a complete enabled composition, never by a request."""
    app.state.fixed_question_reader = reader
    actions = app.state.conversation_actions
    actions.fixed_question_for_message = lambda ctx, chat, message: reader.read(
        ctx, chat, message_id=message
    )
    actions.fixed_question_read = lambda ctx, chat, target: reader.read(
        ctx, chat, target=target
    )
    actions.fixed_question_read_in_transaction = reader.in_transaction
