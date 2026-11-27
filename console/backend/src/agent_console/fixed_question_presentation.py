# ruff: noqa: E501 -- Explicit immutable receipt and private-link SQL.
"""Explicit presented-question authority, separate from ordinary cycle reading."""

from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import Field

from .fixed_question_facts import read_question, require
from .fixed_question_grants import issue, member
from .fixed_question_store import FixedQuestionStore
from .fixed_question_types import QuestionIdentity, QuestionPresentation, StrictValue
from .private_conversation import ConversationError
from .resource_use_domain import canonical_digest
from .workbench_business_problem import OwnerPrincipal


class PresentQuestion(StrictValue):
    identity: QuestionIdentity
    expectedConversationVersion: int = Field(strict=True, ge=0)
    commandId: str = Field(min_length=1, max_length=128)


class FixedQuestionPresentations:
    def __init__(self, delivery, policy, *, clock, validate_execution):
        # validate_execution must recheck the original service command's current
        # authority without creating/faking a BrowserSession for that subject.
        if not callable(validate_execution):
            raise TypeError("FIXED_QUESTION_EXECUTION_AUTHORITY_REQUIRED")
        self.delivery, self.policy = delivery, policy
        self.clock, self.validate_execution = clock, validate_execution

    def read(self, call, conversation, identity):
        cp, question, prepared, event = read_question(
            call, self.delivery, self.policy, conversation, identity, self.clock()
        )
        self.validate_execution(call.connection, cp)
        return cp, question, prepared, event

    def observe(
        self, call, conversation, event_id, receipt_digest, invocation_id, question_key
    ):
        import json

        from .native_wait_types import WaitCheckpoint

        permit = self.policy.require(call, conversation, self.clock())
        _, _, _, prepared = self.delivery.selected(
            call, conversation, event_id, receipt_digest
        )
        row = call.connection.execute(
            "SELECT cp.record FROM skill_invocation.native_wait_heads h "
            "JOIN skill_invocation.native_wait_checkpoints cp USING(namespace,security_domain,skill_invocation_id,checkpoint_digest) "
            "WHERE h.namespace=%s AND h.security_domain=%s AND h.skill_invocation_id=%s",
            (permit.tenantId, permit.securityDomain, invocation_id),
        ).fetchone()
        require(row is not None)
        cp = WaitCheckpoint.model_validate_json(json.dumps(row["record"]))
        require(cp.question_key == question_key)
        i = cp.identity
        identity = QuestionIdentity(
            tenantId=permit.tenantId,
            securityDomain=permit.securityDomain,
            conversationId=conversation,
            bindingDigest=permit.bindingDigest,
            work=permit.work,
            eventId=event_id,
            receiptDigest=receipt_digest,
            preparationDigest=prepared.digest,
            runId=prepared.run_id,
            taskId=i.task_id,
            attemptId=i.attempt_id,
            commandId=i.command_id,
            invocationId=invocation_id,
            questionKey=cp.question_key,
            questionDigest=cp.question_digest,
            checkpointDigest=cp.digest,
            sourceSnapshot=prepared.source_snapshot,
            executionSubject=permit.executionSubject,
            serviceCredentialId=permit.serviceCredentialId,
            generation=self.policy.generation,
            recoveryEpoch=self.policy.recoveryEpoch,
        )
        _, question, _, _ = self.read(call, conversation, identity)
        return identity, question

    def require_read(self, call, value):
        from agent_runtime.native_loop import digest as native_digest

        from .native_progress_projection import projection_read_grants

        i, ctx = value.identity, call.context
        require(value.actorId == ctx.principal_id)
        permit, _, _, prepared = self.delivery.selected(
            call, i.conversationId, i.eventId, i.receiptDigest
        )
        require(permit.bindingDigest == i.bindingDigest and permit.work == i.work)
        require(
            prepared.digest == i.preparationDigest
            and prepared.run_id == i.runId
            and prepared.source_snapshot == i.sourceSnapshot
        )
        task = next((t for t in prepared.participants if t.task_id == i.taskId), None)
        require(task is not None)
        principal = OwnerPrincipal(
            ctx.principal_id, ctx.scope.tenant_id, ctx.scope.security_domain
        )
        call.authority.require(
            principal,
            "EXECUTION",
            "READ",
            "governed-execution:prepared:" + prepared.digest,
        )
        for g in projection_read_grants(prepared, task):
            call.authority.require(principal, g.owner, g.action, g.exact_resource)
        row = call.connection.execute(
            "SELECT request_digest,result FROM skill_invocation.native_loop_records WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND record_key=%s",
            (i.tenantId, i.securityDomain, i.invocationId, i.questionKey + ":question"),
        ).fetchone()
        require(
            row is not None
            and row["request_digest"] == i.questionDigest
            and row["result"] == value.question
            and native_digest(row["result"]) == i.questionDigest
        )
        import json

        from .native_wait_types import WaitCheckpoint

        saved = call.connection.execute(
            "SELECT record FROM skill_invocation.native_wait_checkpoints WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND checkpoint_digest=%s",
            (i.tenantId, i.securityDomain, i.invocationId, i.checkpointDigest),
        ).fetchone()
        require(saved is not None)
        checkpoint = WaitCheckpoint.model_validate_json(json.dumps(saved["record"]))
        value.require_checkpoint(checkpoint)
        command = call.connection.execute(
            "SELECT principal_id,credential_id,authority_generation,recovery_epoch,attempt_id FROM execution_authority.native_dispatch_commands WHERE namespace=%s AND security_domain=%s AND command_id=%s",
            (i.tenantId, i.securityDomain, i.commandId),
        ).fetchone()
        require(
            command
            == dict(
                principal_id=i.executionSubject,
                credential_id=i.serviceCredentialId,
                authority_generation=i.generation,
                recovery_epoch=i.recoveryEpoch,
                attempt_id=i.attemptId,
            )
        )
        skill = call.connection.execute(
            "SELECT workflow_run_id,attempt_id,executor_id,executor_revision,executor_configuration_digest FROM skill_invocation.invocations WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s",
            (i.tenantId, i.securityDomain, i.invocationId),
        ).fetchone()
        require(
            skill
            == dict(
                workflow_run_id=i.runId,
                attempt_id=i.attemptId,
                executor_id=checkpoint.executor_id,
                executor_revision=checkpoint.executor_revision,
                executor_configuration_digest=checkpoint.executor_configuration_digest,
            )
        )
        return value

    def require_current(self, call, value):
        self.read(call, value.identity.conversationId, value.identity)
        require(value.policyDigest == self.policy.digest)
        require(value.actorId == call.context.principal_id)
        require(self.clock() < value.expiresAt)
        g = member(value.identity)
        ctx = call.context
        call.authority.require(
            OwnerPrincipal(
                ctx.principal_id, ctx.scope.tenant_id, ctx.scope.security_domain
            ),
            g.owner,
            g.action,
            g.exact_resource,
        )

    def prepare(self, call, conversation, command):
        c, ctx = call.connection, call.context
        cp, question, _, _ = self.read(call, conversation, command.identity)
        records = self.delivery.records
        owned = records.owned(c, ctx, conversation, lock=True)
        require(owned["owner_id"] == ctx.principal_id and owned["archived_at"] is None)
        store = FixedQuestionStore(c, records.scope(ctx))
        request_digest = canonical_digest(command.model_dump(mode="json"))
        old = store.presentation_command(
            conversation, ctx.principal_id, command.commandId
        )
        if old:
            require(
                old.requestDigest == request_digest and old.identity == command.identity
            )
            self.require_current(call, old)
            return old, True
        if owned["version"] != command.expectedConversationVersion:
            raise ConversationError("CONVERSATION_VERSION_CONFLICT")
        # Actor/chat lock serializes every tab. Anchor and independent issuer
        # decision are in this transaction, so no dangling grant on failure.
        prior = c.execute(
            "SELECT presentation_id FROM fixed_question.presentations WHERE tenant_id=%s AND security_domain=%s AND identity_digest=%s AND actor_id=%s",
            (*records.scope(ctx), command.identity.digest, ctx.principal_id),
        ).fetchone()
        if prior:
            raise ConversationError("FIXED_QUESTION_ALREADY_PRESENTED", 409)
        store.anchor(command.identity)
        request_id, decision_id, grant_id, expiry = issue(
            call, self.delivery.automation, self.policy, command.identity, cp
        )
        identity, focus = str(uuid4()), str(uuid4())
        from .fixed_question_context import snapshot

        token = snapshot(identity, command.identity, question, "")[
            "currentQuestionToken"
        ]
        value = QuestionPresentation(
            presentationId=identity,
            identity=command.identity,
            actorId=ctx.principal_id,
            commandId=command.commandId,
            requestDigest=request_digest,
            policyDigest=self.policy.digest,
            issuerId=self.policy.issuerId,
            grantRequestId=request_id,
            grantDecisionId=decision_id,
            grantId=grant_id,
            focusLinkId=focus,
            currentQuestionToken=token,
            question=question,
            createdAt=self.clock(),
            expiresAt=expiry,
        )
        value.require_checkpoint(cp)
        store.append_presentation(value)
        target = {
            "fixedCycleQuestion": {
                "conversationId": conversation,
                "presentationId": value.presentationId,
                "presentationDigest": value.digest,
            }
        }
        c.execute(
            "INSERT INTO private_conversation.links(tenant_id,security_domain,conversation_id,link_id,target,created_by,request_key,request_digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *records.scope(ctx),
                conversation,
                focus,
                Jsonb(target),
                ctx.principal_id,
                "fixed-question:" + canonical_digest(command.commandId),
                request_digest,
            ),
        )
        c.execute(
            "UPDATE private_conversation.conversations SET version=version+1 WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s",
            (*records.scope(ctx), conversation),
        )
        return value, False

    def status(self, call, conversation, command_id):
        self.delivery.records.owned(
            call.connection, call.context, conversation, lock=True
        )
        store = FixedQuestionStore(
            call.connection, self.delivery.records.scope(call.context)
        )
        old = store.presentation_command(
            conversation, call.context.principal_id, command_id
        )
        if old is None:
            return None
        self.require_read(call, old)
        return old
