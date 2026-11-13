"""Disabled successor owner: references a saved result, never dispatches a model."""

from contextlib import nullcontext
from datetime import UTC, datetime

from .conversation_answer_retention import read_retained, require_target
from .conversation_relation_context import metadata_for_snapshot
from .draft_assistance import DraftScope
from .private_conversation import digest
from .understanding_adoption_evidence import retained_evidence, target_from_result
from .understanding_adoption_postgres import adopt, read_chain
from .understanding_result_adoption import require


class UnderstandingAdoptionApplication:
    def __init__(
        self,
        actions,
        primary,
        routing,
        service_for,
        reader,
        source_reader,
        payload,
        *,
        source_transaction=None,
        retained=(),
    ):
        self.actions, self.primary, self.routing = actions, primary, routing
        self.service_for, self.reader, self.source_reader = (
            service_for,
            reader,
            source_reader,
        )
        self.payload = payload
        self.source_transaction = source_transaction or nullcontext
        self.retained = tuple(retained)

    def result(self, context, conversation, message, key):
        require(
            self.routing.profile.adapter_revision
            in {
                "v3-relation-adoption",
                "v3-relation-adoption-source",
                "v3-relation-adoption-source-answers",
            },
            "UNAVAILABLE",
        )
        require(isinstance(key, str) and 0 < len(key) <= 128, "KEY_INVALID")
        require_target(self.actions, context, conversation, message)
        invocation = self.primary.repository.get_by_key(
            DraftScope.from_context(context),
            context.principal_id,
            "conversation:" + digest([conversation, message, key]),
        )
        require(invocation is not None, "RESULT_NOT_FOUND")
        owner = self.service_for(context, invocation.invocation_id)
        require(
            any(owner is candidate for candidate in (self.routing, *self.retained)),
            "PROFILE_MISMATCH",
        )
        invocation = owner.read(context, invocation.invocation_id).invocation
        require(
            invocation.snapshot is not None
            and invocation.snapshot.profile_digest == owner.profile.profile_digest,
            "PROFILE_MISMATCH",
        )
        target = target_from_result(invocation)
        require(
            (target.conversation_id, target.message_id, target.subject_id)
            == (conversation, message, context.principal_id),
            "SUBJECT_MISMATCH",
        )
        value = read_retained(
            self.actions,
            context,
            conversation,
            self.payload(owner.read(context, invocation.invocation_id))["result"],
            request_key=key,
            message_id=message,
        )
        require(
            value.get("conversationDelivery", {}).get("state") == "SAVED",
            "RETAINED_RESULT_MISMATCH",
        )
        return invocation, target, value

    def authorize(self, connection, context, original, result):
        # Owner reads do not settle, repair, observe or dispatch. Recheck both profiles.
        for invocation in (original, result):
            owner = self.service_for(context, invocation.invocation_id)
            current = owner.read(context, invocation.invocation_id).invocation
            require(current == invocation, "REFERENCE_CHANGED")
            if owner is not self.primary:
                require(
                    any(
                        owner is candidate
                        for candidate in (self.routing, *self.retained)
                    ),
                    "PROFILE_MISMATCH",
                )
                admission = owner.authorization.context_admission
                admission.experience._require(admission, connection, context)

    def read(self, context, conversation, message, key):
        result, _target, value = self.result(context, conversation, message, key)
        with self.actions.records.connect() as c:
            self.actions.records.owned(c, context, conversation)
            chain = read_chain(c, context, result.invocation_id, self.authorize)
            require(bool(chain), "NOT_FOUND")
            row = c.execute(
                "SELECT request_key FROM draft_assistance.result_adoptions WHERE "
                "namespace=%s AND security_domain=%s AND result_invocation_id=%s",
                (
                    result.scope.namespace,
                    result.scope.security_domain,
                    result.invocation_id,
                ),
            ).fetchone()
            require(row and row["request_key"] == key, "KEY_INVALID")
        return {"adoption": chain[0], "understanding": value, "modelDispatched": False}

    def apply(self, context, conversation, message, key):
        result, target, value = self.result(context, conversation, message, key)
        # Acquire the existing generation barrier before any owner DB locks;
        # hold it through commit so nested source verification cannot invert it.
        with self.source_transaction(), self.actions.records.connect() as c:
            # Same order as journal writes: conversation row, then draft context.
            owned = self.actions.records.owned(c, context, conversation, lock=True)
            require(not owned["archived_at"], "CONVERSATION_ARCHIVED")
            row = c.execute(
                "SELECT version,state FROM private_conversation.journeys WHERE "
                "tenant_id=%s AND security_domain=%s AND conversation_id=%s",
                (*self.actions.records.scope(context), conversation),
            ).fetchone()
            require(
                row
                and row["version"] == target.journal_version
                and row["state"].get("key") == target.journey_key
                and row["state"].get("phase") == "CLARIFY"
                and not row["state"].get("pending")
                and not row["state"].get("error")
                and not row["state"].get("problem")
                and (row["state"].get("draft") or {}).get("invocationId")
                == target.original_invocation_id,
                "QUESTION_CHANGED",
            )

            def verify(connection, ctx, expected, original, actual):
                self.authorize(connection, ctx, original, actual)
                snapshot = self.reader(ctx, conversation, message, self.primary)
                current = metadata_for_snapshot(
                    snapshot,
                    include_source_branch="sourceInputBranch"
                    in (actual.conversation_context or {}),
                )
                selected = self.source_reader(
                    ctx, conversation, message, connection=connection
                )
                require(selected == actual.input_source, "SOURCE_CHANGED")
                if (actual.conversation_context or {}).get("failedRetryOf"):
                    from .conversation_understanding_failure import (
                        verified_retry_metadata,
                    )

                    current = verified_retry_metadata(connection, actual, current)
                facts = connection.execute(
                    "SELECT facts FROM private_conversation.message_facts WHERE "
                    "tenant_id=%s AND security_domain=%s AND conversation_id=%s AND "
                    "facts#>>'{source,invocationId}'=%s AND "
                    "facts->>'assistantResponse'='true' LIMIT 2",
                    (
                        *self.actions.records.scope(ctx),
                        conversation,
                        actual.invocation_id,
                    ),
                ).fetchall()
                require(len(facts) == 1, "RETAINED_RESULT_MISMATCH")
                retained = retained_evidence(actual, expected, facts[0]["facts"], key)
                settled = set()
                for invocation in (original, actual):
                    owner = self.service_for(ctx, invocation.invocation_id)
                    read = getattr(owner.budget, "read_settlement", None)
                    require(
                        read is not None and invocation.budget_reservation_id,
                        "BUDGET_UNRESOLVED",
                    )
                    observation = read(invocation.budget_reservation_id)
                    if (
                        observation.get("status") == "ESTIMATE_SETTLED"
                        and observation.get("reservation_retained") is False
                    ):
                        settled.add(invocation.invocation_id)
                return dict(
                    current_snapshot=current,
                    retained_source=retained,
                    expected_profile_revision=self.service_for(
                        ctx, actual.invocation_id
                    ).profile.profile_revision_id,
                    settled_invocations=frozenset(settled),
                    now=datetime.now(UTC),
                    selected_source=selected,
                )

            record = adopt(c, context, target, result.invocation_id, key, verify)
        return {"adoption": record, "understanding": value, "modelDispatched": False}
