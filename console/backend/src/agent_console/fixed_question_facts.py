# ruff: noqa: E501 -- Exact original-owner identity queries.
"""Read a presented question from its original BOUND/service/WAIT facts only."""

import json
from datetime import datetime

from agent_runtime.native_loop import digest as native_digest

from .authority_contracts import AuthorityError, ExactGrant
from .fixed_question_types import QuestionIdentity
from .native_progress_projection import projection_read_grants
from .native_wait_store import NativeWaitStore
from .native_wait_types import WaitCheckpoint
from .workbench_business_problem import OwnerPrincipal


def require(ok):
    if not ok:
        raise AuthorityError("FIXED_QUESTION_FACT_BINDING_INVALID")


def read_question(call, delivery, policy, conversation, identity, now):
    """No grant, link, model, answer or continuation write. Caller holds barrier.

    The input identity is a claim to compare, never a replacement for stored
    records. Current READ is necessary to present the question; it is not ANSWER.
    """
    require(isinstance(identity, QuestionIdentity))
    permit = policy.require(call, conversation, now)
    require(
        (
            identity.tenantId,
            identity.securityDomain,
            identity.conversationId,
            identity.bindingDigest,
            identity.work,
            identity.executionSubject,
            identity.serviceCredentialId,
            identity.generation,
            identity.recoveryEpoch,
        )
        == (
            permit.tenantId,
            permit.securityDomain,
            permit.conversationId,
            permit.bindingDigest,
            permit.work,
            permit.executionSubject,
            permit.serviceCredentialId,
            policy.generation,
            policy.recoveryEpoch,
        )
    )
    read_permit, _, event, prepared = delivery.selected(
        call, conversation, identity.eventId, identity.receiptDigest
    )
    require(
        read_permit.bindingDigest == identity.bindingDigest
        and read_permit.work == identity.work
    )
    require(
        prepared.digest == identity.preparationDigest
        and prepared.run_id == identity.runId
    )
    require(prepared.source_snapshot == identity.sourceSnapshot)
    task = next(
        (t for t in prepared.participants if t.task_id == identity.taskId), None
    )
    require(task is not None)
    principal = OwnerPrincipal(
        call.context.principal_id, identity.tenantId, identity.securityDomain
    )
    members = set(projection_read_grants(prepared, task))
    members.add(
        ExactGrant(
            "EXECUTION", "READ", "governed-execution:prepared:" + prepared.digest
        )
    )
    for member in members:
        require(member.action in {"READ", "READ_RESOURCE", "READ_REFERENCE"})
        call.authority.require(
            principal, member.owner, member.action, member.exact_resource
        )
    c = call.connection
    from .execution_preparation_postgres import PreparedExecutionStore

    _, progress = PreparedExecutionStore(c).read(
        identity.tenantId, identity.securityDomain, identity.runId
    )
    active = next((t for t in progress.tasks if t.task_id == identity.taskId), None)
    require(progress.state == "RUNNING" and not progress.cancellation_request_id)
    require(
        active is not None
        and active.state == "RUNNING"
        and active.attempt_id == identity.attemptId
    )
    row = c.execute(
        "SELECT h.checkpoint_digest,h.state,cp.record FROM skill_invocation.native_wait_heads h "
        "JOIN skill_invocation.native_wait_checkpoints cp USING(namespace,security_domain,skill_invocation_id,checkpoint_digest) "
        "WHERE h.namespace=%s AND h.security_domain=%s AND h.skill_invocation_id=%s",
        (identity.tenantId, identity.securityDomain, identity.invocationId),
    ).fetchone()
    require(row is not None and row["checkpoint_digest"] == identity.checkpointDigest)
    cp = WaitCheckpoint.model_validate_json(json.dumps(row["record"]))
    require(cp.digest == identity.checkpointDigest)
    i = cp.identity
    require(
        (
            i.namespace,
            i.security_domain,
            i.conversation_id,
            i.preparation_digest,
            i.workflow_run_id,
            i.task_id,
            i.attempt_id,
            i.command_id,
            i.skill_invocation_id,
            i.principal_id,
            cp.question_key,
            cp.question_digest,
            cp.source_digest,
        )
        == (
            identity.tenantId,
            identity.securityDomain,
            conversation,
            identity.preparationDigest,
            identity.runId,
            identity.taskId,
            identity.attemptId,
            identity.commandId,
            identity.invocationId,
            identity.executionSubject,
            identity.questionKey,
            identity.questionDigest,
            identity.sourceSnapshot.digest,
        )
    )
    command = c.execute(
        "SELECT principal_id,credential_id,authority_generation,recovery_epoch,attempt_id,state,terminal_record "
        "FROM execution_authority.native_dispatch_commands WHERE namespace=%s AND security_domain=%s AND command_id=%s",
        (identity.tenantId, identity.securityDomain, identity.commandId),
    ).fetchone()
    require(
        command
        == dict(
            principal_id=identity.executionSubject,
            credential_id=identity.serviceCredentialId,
            authority_generation=identity.generation,
            recovery_epoch=identity.recoveryEpoch,
            attempt_id=identity.attemptId,
            state="EFFECT_STARTED",
            terminal_record=None,
        )
    )
    require(row["state"] in {"QUIESCING", "WAITING_FOR_USER", "ANSWER_SAVED"})
    require(now < min(cp.human_expires_at, cp.authority_expires_at, policy.expiresAt))
    question = c.execute(
        "SELECT request_digest,result FROM skill_invocation.native_loop_records "
        "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND record_key=%s",
        (*i.skill_key, cp.question_key + ":question"),
    ).fetchone()
    require(question is not None and question["request_digest"] == cp.question_digest)
    value = question["result"]
    require(native_digest(value) == cp.question_digest)
    require(
        value["principal"] == identity.executionSubject
        and value["workflowRunId"] == identity.runId
    )
    require(
        value["questionKey"] == identity.questionKey
        and value["kind"] == "NATIVE_QUESTION"
    )
    require(datetime.fromisoformat(value["expiresAt"]) == cp.human_expires_at)
    # Validate persisted checkpoint through the original store too; never trust a
    # rehashed caller copy for remaining budget or continuation scope evidence.
    require(NativeWaitStore(c, i).checkpoint(cp.digest) == cp)
    return cp, value, prepared, event
