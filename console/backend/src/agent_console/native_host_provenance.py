"""Claim-owner source lineage; never independent execution authorization."""

import hashlib
import json
import re

from .execution_domain import ExecutionConflict


def validate(value, worker_id):
    try:
        record = value["observation"]
        expected = hashlib.sha256(
            json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if (
            value["digest"] != expected
            or record["schema"] != "native-host-startup.v1"
            or record["workerId"] != worker_id
        ):
            raise ValueError()
        resources = record["authorizationResources"]
        predecessors = record.get("predecessorDigests", [])
        if (
            not isinstance(resources, list)
            or not 1 <= len(resources) <= 128
            or any(not isinstance(x, str) or not x for x in resources)
            or not isinstance(predecessors, list)
            or len(predecessors) > 32
            or any(
                not isinstance(x, str) or not re.fullmatch("[0-9a-f]{64}", x)
                for x in predecessors
            )
            or len(predecessors) != len(set(predecessors))
            or value["digest"] in predecessors
        ):
            raise ValueError()
        if any(
            not isinstance(record[k], str) or not record[k]
            for k in ("startupId", "namespace", "securityDomain", "principalId")
        ):
            raise ValueError()
    except (KeyError, TypeError, ValueError) as exc:
        raise ExecutionConflict("NATIVE_HOST_PROVENANCE_INVALID") from exc
    return record


def lineage(value):
    return [value["digest"], *value["observation"].get("predecessorDigests", [])]


def lock_identity(connection, value, worker_id):
    if value is not None:
        validate(value, worker_id)
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("native-host:" + worker_id,),
    )
    rows = connection.execute(
        "SELECT DISTINCT record->'hostStartup' AS startup "
        "FROM execution_authority.native_dispatch_facts WHERE kind='CLAIMED' "
        "AND record->>'workerId'=%s",
        (worker_id,),
    ).fetchall()
    for row in rows:
        previous = row["startup"]
        if value is None:
            if previous is not None:
                raise ExecutionConflict("NATIVE_HOST_WORKER_ID_REUSED")
        elif previous is None or previous["digest"] not in lineage(value):
            raise ExecutionConflict("NATIVE_HOST_WORKER_ID_REUSED")
        else:
            validate(previous, worker_id)
            if any(
                previous["observation"][k] != value["observation"][k]
                for k in (
                    "namespace",
                    "securityDomain",
                    "principalId",
                    "authorizationResources",
                )
            ):
                raise ExecutionConflict("NATIVE_HOST_PREDECESSOR_SCOPE_MISMATCH")


def require_claim(connection, claim, value, *, observe_only=False):
    if value is not None:
        record = validate(value, claim.worker_id)
        if (
            record["namespace"] != claim.command.scope.namespace
            or record["securityDomain"] != claim.command.scope.security_domain
            or record["principalId"] != claim.command.principal_id
            or claim.command.authorization_resource
            not in record["authorizationResources"]
        ):
            raise ExecutionConflict("NATIVE_HOST_CLAIM_SCOPE_MISMATCH")
    row = connection.execute(
        "SELECT record FROM execution_authority.native_dispatch_facts "
        "WHERE namespace=%s AND security_domain=%s AND command_id=%s "
        "AND kind='CLAIMED' "
        "AND (record->>'claimGeneration')::bigint=%s ORDER BY ordinal DESC LIMIT 1",
        (
            claim.command.scope.namespace,
            claim.command.scope.security_domain,
            str(claim.command.command_id),
            claim.claim_generation.value,
        ),
    ).fetchone()
    recorded = None if row is None else row["record"].get("hostStartup")
    allowed = recorded == value
    if observe_only and value is not None and recorded is not None:
        allowed = recorded["digest"] in lineage(value)
    if not allowed:
        raise ExecutionConflict("NATIVE_HOST_CLAIM_BINDING_MISMATCH")
