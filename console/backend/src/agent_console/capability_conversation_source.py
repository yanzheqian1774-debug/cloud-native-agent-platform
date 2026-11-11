"""Exact published capability preparation; no model or execution admission."""

from pydantic import BaseModel, ConfigDict, Field

from .private_conversation import ConversationError


def verify_work_association(call, resolved, target):
    from psycopg.types.json import Jsonb

    from .workbench_owner_authorization import WorkbenchOwnerError

    contract = resolved["contract"]
    owner_ref = {
        "kind": "PROBLEM",
        "target": {
            "problemId": target["resource_id"],
            "revisionId": target["revision_id"],
            "problemDigest": target["digest"],
        },
    }
    rows = call.connection.execute(
        "SELECT intent_id FROM private_conversation.action_intents WHERE "
        "tenant_id=%s AND security_domain=%s AND conversation_id=%s "
        "AND message_id=%s AND action='CREATE_PROBLEM' AND claimed_at IS NOT NULL "
        "AND owner_ref=%s",
        (
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
            contract["conversationId"],
            contract["sourceMessageId"],
            Jsonb(owner_ref),
        ),
    ).fetchall()
    if len(rows) != 1:
        raise WorkbenchOwnerError("CAPABILITY_WORK_ASSOCIATION_REQUIRED", 409)


class CapabilityConversationTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    capabilityId: str = Field(min_length=1, max_length=200)
    revisionId: str = Field(min_length=1, max_length=200)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    objective: str = Field(min_length=1, max_length=2000)
    inputNotes: str = Field(min_length=1, max_length=6000)


def read_capability_source(context, source, owner_read):
    target = CapabilityConversationTarget.model_validate(source["target"])
    value = owner_read(
        context,
        "READ_CAPABILITY_REVISION",
        {"capability_id": target.capabilityId, "revision_id": target.revisionId},
    )
    revision = value["revision"]
    if (
        revision["capability_id"] != target.capabilityId
        or revision["revision_id"] != target.revisionId
        or value["digest"] != target.digest
    ):
        raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
    if value["state"] != "PUBLISHED":
        raise ConversationError("CAPABILITY_SOURCE_NOT_PUBLISHED", 409)
    return {
        "title": revision["title"],
        "state": "PREPARED_NOT_EXECUTED",
        "receiptState": "NOT_STARTED",
        "executionAuthorized": False,
        "objective": target.objective,
        "inputNotes": target.inputNotes,
        "capability": {
            "capabilityId": target.capabilityId,
            "revisionId": target.revisionId,
            "digest": target.digest,
            "inputs": revision["inputs"],
            "outputs": revision["outputs"],
            "acceptanceCriteria": revision["acceptance_criteria"],
            "manualInvolvement": revision["manual_involvement"],
            "exclusions": revision["exclusions"],
            "businessScope": revision["business_scope"],
            "knownLimitations": revision["known_limitations"],
            "bindings": revision["bindings"],
            "members": value.get("members", []),
        },
    }


def execution_contract(context, conversation_id, message_id, source, observation):
    """Resolved immutable constraints, never admission or a runtime receipt."""
    from .private_conversation import digest

    if source.get("kind") != "CAPABILITY":
        raise ConversationError("CAPABILITY_SOURCE_REQUIRED", 409)
    target = CapabilityConversationTarget.model_validate(source["target"])
    capability = observation["capability"]
    contract = {
        "schemaVersion": "capability-execution-constraints.v1",
        "scope": {
            "tenantId": context.scope.tenant_id,
            "securityDomain": context.scope.security_domain,
        },
        "conversationId": conversation_id,
        "sourceMessageId": message_id,
        "capability": {
            "resource_id": target.capabilityId,
            "revision_id": target.revisionId,
            "digest": target.digest,
        },
        "objective": target.objective,
        "inputNotes": target.inputNotes,
        "inputs": capability["inputs"],
        "outputs": capability["outputs"],
        "acceptanceCriteria": capability["acceptanceCriteria"],
        "businessScope": capability["businessScope"],
        "exclusions": capability["exclusions"],
        "manualInvolvement": capability["manualInvolvement"],
        "knownLimitations": capability["knownLimitations"],
        "bindings": capability["bindings"],
    }
    resolved = {
        "contract": contract,
        "contractDigest": digest(contract),
        "admissionState": "NOT_ADMITTED",
        "executionAuthorized": False,
        "executionStarted": False,
    }
    from .capability_work_input import work_input

    return {**resolved, "workInput": work_input(resolved)}
