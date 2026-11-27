# ruff: noqa: E501 -- Atomic exact owner bindings; no model port.
"""Adopt one saved INDEPENDENT task result without another understanding call."""

import os
from types import SimpleNamespace

from psycopg.types.json import Jsonb
from pydantic import Field

from . import conversation_goal_origin as origin
from . import conversation_goal_slots as slots
from .context_call_admission import lock, request_row
from .conversation_answer_retention import (
    read_retained,
    require_target,
)
from .draft_assistance import DraftInvocationState, DraftResultKind, DraftScope
from .draft_assistance_postgres import PostgresDraftAssistanceRepository
from .owned_business_policy import OwnedBusinessPolicyV3
from .private_conversation import digest
from .task_identity_continuity import lock_owner_generation
from .understanding_adoption_evidence import retained_evidence
from .understanding_result_adoption import successful_cleanup
from .workbench_bff_schemas import StrictWorkbenchModel


class AdoptGoal(StrictWorkbenchModel):
    commandId: str = Field(min_length=1, max_length=128)
    messageId: str = Field(min_length=1, max_length=128)
    requestKey: str = Field(min_length=1, max_length=128)
    expectedConversationVersion: int = Field(ge=0)


class GoalAdoption:
    def __init__(self, existing):
        self.existing = existing
        self.records = existing.actions.records
        self.business = existing.primary.authorization.context_admission.owned_business

    def available(self):
        expected = getattr(self.business.policy, "independentGoalProfile", None)
        actual = getattr(self.existing.routing, "profile", None)
        return (
            slots.enabled()
            and os.environ.get("CONVERSATION_GOAL_NATURAL_ENABLED") == "1"
            and isinstance(self.business.policy, OwnedBusinessPolicyV3)
            and actual is not None
            and (
                actual.profile_revision_id,
                actual.profile_digest,
                actual.adapter_revision,
            )
            == (
                expected.profileRevisionId,
                expected.profileDigest,
                expected.adapterRevision,
            )
        )

    def result(self, context, conversation, body):
        slots.require(self.available(), "CONVERSATION_GOAL_ADOPTION_UNAVAILABLE")
        a = self.existing
        require_target(a.actions, context, conversation, body.messageId)
        value = a.primary.repository.get_by_key(
            DraftScope.from_context(context),
            context.principal_id,
            "conversation:" + digest([conversation, body.messageId, body.requestKey]),
        )
        slots.require(value is not None, "CONVERSATION_GOAL_RESULT_NOT_FOUND")
        service = a.service_for(context, value.invocation_id)
        slots.require(service is a.routing, "CONVERSATION_GOAL_PROFILE_CHANGED")
        response = service.read(context, value.invocation_id)
        value = response.invocation
        profile = self.business.policy.independentGoalProfile
        metadata = value.conversation_context or {}
        slots.require(
            value.state is DraftInvocationState.SUCCEEDED
            and value.result_kind
            in {
                DraftResultKind.DRAFT_READY,
                DraftResultKind.NEEDS_DATA,
                DraftResultKind.NEEDS_CLARIFICATION,
            }
            and value.snapshot is not None
            and (
                value.profile_revision_id,
                value.snapshot.profile_digest,
                value.snapshot.adapter_revision,
            )
            == (
                profile.profileRevisionId,
                profile.profileDigest,
                profile.adapterRevision,
            )
            and (metadata.get("conversationId"), metadata.get("messageId"))
            == (conversation, body.messageId)
            and metadata.get("goalId") is None
            and metadata.get("target") is None
            and metadata.get("currentQuestionToken") is None
            and metadata.get("naturalGoalIntentVersion") == "v1"
            and (value.conversation_route or {}).get("intent") == "TASK"
            and (value.conversation_route or {}).get("relation") == "INDEPENDENT"
            and (value.conversation_route or {}).get("currentQuestionToken") is None
            and successful_cleanup(value.local_cleanup),
            "CONVERSATION_GOAL_RESULT_NOT_ADOPTABLE",
        )
        view = read_retained(
            a.actions,
            context,
            conversation,
            a.payload(response)["result"],
            request_key=body.requestKey,
            message_id=body.messageId,
        )
        slots.require(
            view.get("conversationDelivery", {}).get("state") == "SAVED",
            "CONVERSATION_GOAL_RESULT_NOT_RETAINED",
        )
        return service, value, view

    def apply(self, context, conversation, body):
        service, value, view = self.result(context, conversation, body)
        a = self.existing
        with a.source_transaction(), self.records.connect() as c:
            lock_owner_generation(c)
            slots.require_schema(c)
            chat = self.records.owned(c, context, conversation, lock=True)
            slots.require(
                chat["owner_id"] == context.principal_id and not chat["archived_at"]
            )
            _, now, expires = self.business._policy(c, context)
            self.business._reads(c, context, (value,), now)
            admission = service.authorization.context_admission
            admission.experience._require(admission, c, context)
            lock(c, value.context_id)
            request = request_row(c, value.context_id)
            slots.require(
                request
                and request["record"]["configuration"] == admission.configuration
                and request["subject_id"] == context.principal_id
                and request["record"].get("conversation_id") == conversation,
                "CONVERSATION_GOAL_CONTEXT_CHANGED",
            )
            admission.experience.require_record(c, context, request)
            slots.require(
                not c.execute(
                    "SELECT 1 FROM authorization_admin.context_call_decisions d JOIN "
                    "authorization_admin.context_call_revocations r USING(admission_id) WHERE d.context_id=%s",
                    (value.context_id,),
                ).fetchone(),
                "CONVERSATION_GOAL_CONTEXT_REVOKED",
            )
            c.execute(
                "SELECT context_id FROM draft_assistance.contexts WHERE namespace=%s "
                "AND security_domain=%s AND context_id=%s FOR UPDATE",
                (*self.records.scope(context), value.context_id),
            ).fetchone()
            latest = PostgresDraftAssistanceRepository._latest(
                c, value.scope, value.invocation_id
            )
            slots.require(latest == value, "CONVERSATION_GOAL_RESULT_CHANGED")
            settlement = service.budget.read_invocation_settlement(c, value)
            slots.require(
                settlement.get("status") == "ESTIMATE_SETTLED"
                and settlement.get("reservation_retained") is False,
                "CONVERSATION_GOAL_BUDGET_UNRESOLVED",
            )
            facts_rows = c.execute(
                "SELECT facts FROM private_conversation.message_facts WHERE tenant_id=%s "
                "AND security_domain=%s AND conversation_id=%s AND facts#>>'{source,invocationId}'=%s "
                "AND facts->>'assistantResponse'='true' LIMIT 2",
                (*self.records.scope(context), conversation, value.invocation_id),
            ).fetchall()
            slots.require(len(facts_rows) == 1, "CONVERSATION_GOAL_RESULT_NOT_RETAINED")
            facts = facts_rows[0]["facts"]
            retained_evidence(
                value,
                SimpleNamespace(
                    subject_id=context.principal_id, message_id=body.messageId
                ),
                facts,
                body.requestKey,
            )
            if facts.get("fixedCycleFocus") is not None:
                read_basis = getattr(a.actions, "fixed_focus_read_in_transaction", None)
                slots.require(read_basis is not None, "CONVERSATION_SOURCE_UNAVAILABLE")
                read_basis(
                    c,
                    context,
                    conversation,
                    {"fixedCycleFocus": facts["fixedCycleFocus"]},
                )
            prior = origin.saved(c, context, value.invocation_id)
            request_digest = digest(body.model_dump(mode="json"))
            if prior:
                slots.require(
                    prior["command_key"] == body.commandId
                    and prior["request_digest"] == request_digest,
                    "CONVERSATION_GOAL_COMMAND_CONFLICT",
                )
                origin.validate(c, context, value, self.business.policy)
                return self.projection(c, context, prior, view, replayed=True)
            slots.require(
                chat["version"] == body.expectedConversationVersion,
                "CONVERSATION_VERSION_CONFLICT",
            )
            slots.require(
                value.problem_id is None, "CONVERSATION_GOAL_RESULT_ALREADY_BOUND"
            )
            slots.require(
                slots.message_goal(
                    c, self.records, context, conversation, body.messageId
                )
                is None,
                "CONVERSATION_GOAL_MESSAGE_ALREADY_USED",
            )
            head = c.execute(
                "SELECT i.invocation_id FROM draft_assistance.invocations i JOIN draft_assistance.turns t "
                "USING(namespace,security_domain,context_id,turn_id) WHERE i.namespace=%s "
                "AND i.security_domain=%s AND i.context_id=%s ORDER BY t.ordinal DESC LIMIT 1",
                (*self.records.scope(context), value.context_id),
            ).fetchone()
            slots.require(
                head and head["invocation_id"] == value.invocation_id,
                "CONVERSATION_GOAL_RESULT_SUPERSEDED",
            )
            created = slots.append_verified(
                c, self.records, context, conversation, body, request_digest
            )
            goal = created["goalId"]
            message = c.execute(
                "SELECT content FROM private_conversation.messages WHERE tenant_id=%s "
                "AND security_domain=%s AND conversation_id=%s AND message_id=%s",
                (*self.records.scope(context), conversation, body.messageId),
            ).fetchone()
            state = {
                "key": "goal:" + goal,
                "phase": "CREATE"
                if value.result_kind is DraftResultKind.DRAFT_READY
                and value.input_source
                else "CLARIFY",
                "userMessageId": body.messageId,
                "question": message["content"],
                "draft": view,
                "source": value.input_source,
                "messages": [
                    {"id": "user:" + body.messageId, "text": message["content"]}
                ],
            }
            slots.save(c, self.records, context, conversation, goal, 0, state)
            record = {
                "schemaVersion": "conversation-independent-goal-adoption.v1",
                "tenantId": context.scope.tenant_id,
                "securityDomain": context.scope.security_domain,
                "conversationId": conversation,
                "invocationId": value.invocation_id,
                "ownerId": context.principal_id,
                "messageId": body.messageId,
                "commandId": body.commandId,
                "requestDigest": request_digest,
                "requestKey": body.requestKey,
                "expectedConversationVersion": body.expectedConversationVersion,
                "goalId": goal,
                "goalDigest": created["goalDigest"],
                "ownedPolicyDigest": self.business.policy.digest,
                "aggregateVersion": value.aggregate_version,
                "result": origin.result_identity(value),
                "retainedFactsDigest": digest(facts),
                "settlement": settlement,
                "recordedAt": now.isoformat(),
                "expiresAt": expires.isoformat(),
            }
            c.execute(
                "INSERT INTO conversation_goals.result_adoptions VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    *self.records.scope(context),
                    conversation,
                    value.invocation_id,
                    goal,
                    context.principal_id,
                    body.messageId,
                    body.commandId,
                    request_digest,
                    Jsonb(record),
                    digest(record),
                ),
            )
            return self.projection(
                c,
                context,
                origin.validate(c, context, value, self.business.policy),
                view,
                replayed=False,
            )

    def projection(self, c, context, row, view, *, replayed):
        r = row["record"]
        return {
            "state": "RECORDED",
            "conversationId": r["conversationId"],
            "commandId": r["commandId"],
            "messageId": r["messageId"],
            "requestKey": r["requestKey"],
            "goalId": r["goalId"],
            "goalDigest": r["goalDigest"],
            "adoptionDigest": row["record_digest"],
            "invocationId": r["invocationId"],
            "understanding": view,
            "journal": slots.read(
                c, self.records, context, r["conversationId"], r["goalId"]
            ),
            "modelDispatched": False,
            "replayed": replayed,
        }

    def read(self, context, conversation, command):
        slots.require(self.available(), "CONVERSATION_GOAL_ADOPTION_UNAVAILABLE")
        with self.records.connect() as c:
            slots.require_schema(c)
            chat = self.records.owned(c, context, conversation)
            slots.require(
                chat["owner_id"] == context.principal_id and not chat["archived_at"]
            )
            row = c.execute(
                "SELECT record FROM conversation_goals.result_adoptions WHERE tenant_id=%s "
                "AND security_domain=%s AND conversation_id=%s AND command_key=%s",
                (*self.records.scope(context), conversation, command),
            ).fetchone()
            if row is None:
                return {
                    "state": "NOT_RECORDED",
                    "conversationId": conversation,
                    "commandId": command,
                }
            r = row["record"]
        body = AdoptGoal(
            commandId=command,
            messageId=r["messageId"],
            requestKey=r["requestKey"],
            expectedConversationVersion=r["expectedConversationVersion"],
        )
        _service, value, view = self.result(context, conversation, body)
        with self.existing.source_transaction(), self.records.connect() as c:
            lock_owner_generation(c)
            _, now, _ = self.business._policy(c, context)
            self.business._reads(c, context, (value,), now)
            slots.require(
                not c.execute(
                    "SELECT 1 FROM authorization_admin.context_call_decisions d JOIN "
                    "authorization_admin.context_call_revocations r USING(admission_id) WHERE d.context_id=%s",
                    (value.context_id,),
                ).fetchone(),
                "CONVERSATION_GOAL_CONTEXT_REVOKED",
            )
            checked = origin.validate(c, context, value, self.business.policy)
            slots.require(
                checked and checked["record"] == r, "CONVERSATION_GOAL_ADOPTION_CHANGED"
            )
            return self.projection(c, context, checked, view, replayed=True)


def from_app(app):
    existing = getattr(getattr(app, "state", None), "understanding_adoption", None)
    admission = getattr(
        getattr(getattr(existing, "primary", None), "authorization", None),
        "context_admission",
        None,
    )
    if getattr(admission, "owned_business", None) is None:
        return None
    return GoalAdoption(existing)
