# ruff: noqa: E501 -- Exact same-connection owner queries.
"""Server-produced fixed-cycle observations for ordinary single-C1 followup."""

import json
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import Field

from .digital_employee_definition import digest
from .fixed_chat_facts import require
from .fixed_chat_read_access import members_for
from .private_conversation import ConversationError
from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_business_problem import OwnerPrincipal


class FocusCommand(StrictWorkbenchModel):
    bindingDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    workDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    eventId: str = Field(min_length=1, max_length=200)
    receiptDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    preparationDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    runId: str = Field(min_length=1, max_length=200)
    expectedConversationVersion: int = Field(ge=0)
    commandId: str = Field(min_length=1, max_length=128)


def principal(call):
    return OwnerPrincipal(
        call.context.principal_id,
        call.context.scope.tenant_id,
        call.context.scope.security_domain,
    )


def checked(call, owner, conversation, identity):
    permit, bound, event, prepared = owner.selected(
        call, conversation, identity["eventId"], identity["receiptDigest"]
    )
    require(
        identity["bindingDigest"] == permit.bindingDigest
        and identity["workDigest"] == permit.work.digest
        and identity["preparationDigest"] == prepared.digest
        and identity["runId"] == prepared.run_id
    )
    return permit, bound, event, prepared


def read_basis(call, owner, conversation, target):
    require(set(target) == {"fixedCycleFocus"})
    basis = target["fixedCycleFocus"]
    require(
        basis["schemaVersion"] == "fixed-cycle-focus.v1"
        and basis["conversationId"] == conversation
        and basis["focusDigest"]
        == digest({k: v for k, v in basis.items() if k != "focusDigest"})
    )
    _, _, _, p = checked(call, owner, conversation, basis["identity"])
    for grant in basis["grants"]:
        require(grant["action"] in {"READ", "READ_REFERENCE", "READ_RESOURCE"})
        call.authority.require(
            principal(call), grant["owner"], grant["action"], grant["exactResource"]
        )
    outputs = []
    remaining = 12000
    complete = True
    for ref in basis["artifacts"]:
        row = call.connection.execute(
            "SELECT artifact_id,task_id,attempt_id,digest,content,record FROM execution_authority.run_artifacts WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s AND artifact_id=%s",
            (p.namespace, p.security_domain, p.run_id, ref["artifactId"]),
        ).fetchone()
        require(row is not None and row["digest"] == ref["digest"])
        from .execution_preparation import ArtifactDocument

        try:
            artifact = ArtifactDocument.model_validate(row["record"])
        except (ValueError, TypeError, KeyError) as exc:
            raise ConversationError(
                "CONVERSATION_ARTIFACT_INTEGRITY_INVALID", 409
            ) from exc
        require(
            all(
                row[field] == getattr(artifact, field)
                for field in (
                    "artifact_id",
                    "task_id",
                    "attempt_id",
                    "digest",
                    "content",
                )
            )
            and artifact.artifact_id == ref["artifactId"]
        )
        text = row["content"]
        require(isinstance(text, str))
        excerpt = text[: min(2000, remaining)]
        remaining -= len(excerpt)
        full = len(excerpt) == len(text)
        complete = complete and full
        outputs.append(
            {
                "artifactId": ref["artifactId"],
                "textExcerpt": excerpt,
                "totalCharacters": len(text),
                "complete": full,
            }
        )
    result = {
        "observation": basis["observation"],
        "outputs": outputs,
        "contentComplete": complete,
        "readingLimit": "Only the saved text excerpts shown here were supplied; do not infer omitted text.",
    }
    if len(json.dumps(result, ensure_ascii=False, sort_keys=True)) > 24000:
        raise ConversationError("CONVERSATION_ROUTING_CONTEXT_TOO_LARGE", 422)
    return basis, result


def create(call, owner, conversation, body):
    identity = body.model_dump(exclude={"expectedConversationVersion", "commandId"})
    _permit, _bound, event, p = checked(call, owner, conversation, identity)
    records, c = owner.records, call.connection
    owned = records.owned(c, call.context, conversation, lock=True)
    key = "fixed-cycle-focus:" + digest(body.commandId)
    hashed = digest(body.model_dump())
    prior = c.execute(
        "SELECT * FROM private_conversation.links WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND request_key=%s",
        (*records.scope(call.context), conversation, key),
    ).fetchone()
    if records.replay(prior, hashed):
        basis, observed = read_basis(call, owner, conversation, prior["target"])
        return {
            **coverage(observed),
            **basis["identity"],
            "conversationId": conversation,
            "focusLinkId": prior["link_id"],
            "focusDigest": basis["focusDigest"],
            "conversationVersion": owned["version"],
            "commandId": body.commandId,
            "state": "RECORDED",
            "replayed": True,
        }
    if owned["archived_at"] or owned["version"] != body.expectedConversationVersion:
        raise ConversationError("CONVERSATION_VERSION_CONFLICT")
    grants = members_for(call, p, owner.automation.grants.target_validator)
    for g in grants:
        call.authority.require(principal(call), g.owner, g.action, g.exact_resource)
    artifacts = c.execute(
        "SELECT artifact_id,digest FROM execution_authority.run_artifacts WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s ORDER BY artifact_id",
        (p.namespace, p.security_domain, p.run_id),
    ).fetchall()
    # Every actual artifact must independently be readable, even if not in a planned output.
    from .authority_contracts import ExactGrant

    grants = set(grants)
    for a in artifacts:
        g = ExactGrant(
            "EVIDENCE",
            "READ_REFERENCE",
            f"evidence-reference:prepared:{p.digest}:" + a["artifact_id"],
        )
        call.authority.require(principal(call), g.owner, g.action, g.exact_resource)
        grants.add(g)
    require(len(artifacts) <= 32 and len(grants) <= 224)
    basis = {
        "schemaVersion": "fixed-cycle-focus.v1",
        "conversationId": conversation,
        "identity": identity,
        "grants": [
            {"owner": g.owner, "action": g.action, "exactResource": g.exact_resource}
            for g in sorted(grants, key=lambda g: (g.owner, g.action, g.exact_resource))
        ],
        "artifacts": [
            {"artifactId": a["artifact_id"], "digest": a["digest"]} for a in artifacts
        ],
        "observation": {
            "eventId": event["eventId"],
            "scheduledAt": event["scheduledAt"],
            "recordedAt": event["recordedAt"],
            "state": event["execution"],
        },
    }
    basis["focusDigest"] = digest(basis)
    target = {"fixedCycleFocus": basis}
    _, observed = read_basis(call, owner, conversation, target)
    link = str(uuid4())
    c.execute(
        "INSERT INTO private_conversation.links(tenant_id,security_domain,conversation_id,link_id,target,created_by,request_key,request_digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            *records.scope(call.context),
            conversation,
            link,
            Jsonb(target),
            call.context.principal_id,
            key,
            hashed,
        ),
    )
    c.execute(
        "UPDATE private_conversation.conversations SET version=version+1 WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s",
        (*records.scope(call.context), conversation),
    )
    return {
        **coverage(observed),
        **identity,
        "conversationId": conversation,
        "focusLinkId": link,
        "focusDigest": basis["focusDigest"],
        "conversationVersion": owned["version"] + 1,
        "commandId": body.commandId,
        "state": "RECORDED",
        "replayed": False,
    }


def status(call, owner, conversation, command_id):
    owner.binding(call, conversation)
    row = call.connection.execute(
        "SELECT * FROM private_conversation.links WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND request_key=%s",
        (
            *owner.records.scope(call.context),
            conversation,
            "fixed-cycle-focus:" + digest(command_id),
        ),
    ).fetchone()
    if row is None:
        return {
            "conversationId": conversation,
            "commandId": command_id,
            "state": "NOT_RECORDED",
        }
    basis, observed = read_basis(call, owner, conversation, row["target"])
    return {
        **coverage(observed),
        **basis["identity"],
        "conversationId": conversation,
        "commandId": command_id,
        "state": "RECORDED",
        "focusLinkId": row["link_id"],
        "focusDigest": basis["focusDigest"],
        "replayed": True,
    }


def coverage(observed):
    return {
        "contentComplete": observed["contentComplete"],
        "excerptedArtifactCount": sum(not x["complete"] for x in observed["outputs"]),
    }
