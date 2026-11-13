# ruff: noqa: E501 -- Exact scoped authority and immutable receipt SQL.
"""Explicit retained draft READ preparation; no ontology lifecycle command."""

import json
from types import SimpleNamespace
from typing import Literal

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError, ExactGrant
from .ontology_domain import OntologyError
from .ontology_maintenance_binding import REQUEST_PREFIX, command_key
from .ontology_service import OntologyService, resource
from .read_access_recovery import current
from .resource_automation import ResourceAutomation, bound_grants
from .resource_use_domain import canonical_digest
from .test_resource_read_access import was_denied

SCHEMA = "ontology-maintenance-read.v1"


class PrepareRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    action: Literal["PREPARE_READ"]
    commandKey: str = Field(min_length=8, max_length=120)
    ontologyId: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
    )
    revision: str = Field(min_length=1, max_length=128)
    expectedVersion: int | None = Field(default=None, ge=1)
    digest: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")


def receipt(manager, call, record):
    if record.get("actor") != call.context.principal_id or record.get("scope") != [
        call.context.scope.tenant_id,
        call.context.scope.security_domain,
    ]:
        raise AuthorityError("ONTOLOGY_READ_RECEIPT_NOT_FOUND")
    manager.read_required(call, record["ontologyId"], record["revision"])
    return {
        "schemaVersion": SCHEMA,
        "commandKey": record["command"]["commandKey"],
        "ontologyId": record["ontologyId"],
        "revision": record["revision"],
        "digest": record["digest"],
        "version": record["version"],
        "policyDecisionId": record["policyDecisionId"],
        "executionStarted": False,
        "modelCalls": 0,
    }


def prepare(manager, call):
    cmd = PrepareRead.model_validate(call.payload)
    issuer = manager.policy.authenticate(manager.grants, call.context)
    if manager.grants.generation.generation != call.policy_generation:
        raise AuthorityError("ONTOLOGY_MANAGEMENT_GENERATION_CHANGED")
    creator = manager.creator(call, cmd.ontologyId)
    work = None
    for action in ("REVISE", "VALIDATE", "TEST", "REVIEW", "PUBLISH", "DEPRECATE"):
        try:
            work = manager.policy.work(
                call.context,
                cmd.ontologyId,
                action,
                manager.grants.clock(),
                created_by=creator,
            )
            break
        except AuthorityError:
            continue
    if work is None:
        raise AuthorityError("ONTOLOGY_MAINTENANCE_SCOPE_DENIED")
    scope = [call.context.scope.tenant_id, call.context.scope.security_domain]
    actor, c = call.context.principal_id, call.connection
    key = command_key(cmd.commandKey)
    commitment = canonical_digest(cmd.model_dump(mode="json"))
    for lock in sorted(
        (
            [*scope, actor, REQUEST_PREFIX + canonical_digest(cmd.commandKey)],
            [*scope, cmd.ontologyId],
        )
    ):
        c.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (json.dumps(lock),)
        )
    prior_command = manager._row(call, cmd.commandKey)
    if prior_command:
        if (
            prior_command["digest"] != commitment
            or prior_command["result"].get("schemaVersion") != SCHEMA
        ):
            raise OntologyError("ONTOLOGY_MANAGEMENT_COMMAND_CONFLICT")
        return receipt(manager, call, prior_command["result"])
    grant = ExactGrant(
        "BUSINESS_ONTOLOGY", "READ", resource(cmd.ontologyId, cmd.revision)
    )
    grants = bound_grants(manager.grants, c)
    state = current(grants, call.context, (grant,))
    if state in {"REVOKED", "UNAVAILABLE"} or was_denied(c, call.context, grant):
        raise AuthorityError("ONTOLOGY_RETAINED_READ_DENIED")
    prior = c.execute(
        "SELECT grant_id FROM authorization_admin.grants WHERE tenant_id=%s AND security_domain=%s AND subject_principal_id=%s AND owner='BUSINESS_ONTOLOGY' AND action='READ' AND exact_resource=%s ORDER BY created_at DESC,grant_id LIMIT 1",
        (*scope, actor, grant.exact_resource),
    ).fetchone()
    if not prior:
        raise AuthorityError("ONTOLOGY_RETAINED_READ_NOT_FOUND")
    # Serialize against owner revision/lifecycle changes before binding metadata.
    c.execute(
        "SELECT ontology_id FROM business_ontology.definitions WHERE namespace=%s AND security_domain=%s AND ontology_id=%s FOR SHARE",
        (*scope, cmd.ontologyId),
    ).fetchone()
    value = OntologyService(call).repo.read(tuple(scope), cmd.ontologyId, cmd.revision)
    if (
        cmd.expectedVersion is not None and cmd.expectedVersion != value["version"]
    ) or (cmd.digest is not None and cmd.digest != value["digest"]):
        raise OntologyError("ONTOLOGY_RETAINED_READ_VERSION_CONFLICT")
    proof = ResourceAutomation.decide(
        SimpleNamespace(policy=manager.policy, grants=grants),
        call,
        (grant,),
        key + ":" + commitment,
        work,
        issuer,
        purpose="ONTOLOGY_MAINTENANCE",
    )
    record = {
        "schemaVersion": SCHEMA,
        "scope": scope,
        "actor": actor,
        "ontologyId": cmd.ontologyId,
        "revision": cmd.revision,
        "digest": value["digest"],
        "version": value["version"],
        "command": cmd.model_dump(mode="json"),
        "policyDigest": manager.policy.digest,
        "generation": call.policy_generation,
        "priorReadGrant": prior["grant_id"],
        "policyDecisionId": proof.decision_id,
    }
    c.execute(
        "INSERT INTO execution_authority.prepared_resource_commands(namespace,security_domain,actor_id,command_key,digest,result) VALUES(%s,%s,%s,%s,%s,%s)",
        (*scope, actor, key, commitment, Jsonb(record)),
    )
    return receipt(manager, call, record)
