# ruff: noqa: E501 -- Exact scoped SQL.
"""Persisted cancellation intent and Native owner's proof of no permitted effect."""

from datetime import UTC, datetime

from psycopg.types.json import Jsonb

from .execution_preparation import ExecutionPreparationError, ProgressEvent
from .execution_preparation_postgres import PreparedExecutionStore
from .prepared_execution_lineage import prepared_attempt
from .prepared_execution_observations import sync_projection
from .resource_use_domain import canonical_digest, stable_id


def request_cancel(connection, principal, authority, p, command_key):
    authority.require(
        principal, "EXECUTION", "CANCEL", "governed-execution:prepared:" + p.digest
    )
    store = PreparedExecutionStore(connection)
    key = p.namespace, p.security_domain, p.run_id
    _, progress = store.read(*key, lock=True)
    request_id = stable_id(
        "prepared-cancel-request", p.run_id, principal.principal_id, command_key
    )
    result = store.apply(
        *key,
        ProgressEvent(action="REQUEST_CANCEL", evidence_id=request_id),
        expected_version=progress.version,
    )
    sync_projection(connection, key, result)
    return result


def stop_before_effect(connection, claim, command_row):
    command = claim.command
    row = prepared_attempt(connection, command.scope, command.attempt_id)
    if row is None:
        return False
    key = command.scope.namespace, command.scope.security_domain, row["workflow_run_id"]
    store = PreparedExecutionStore(connection)
    _, progress = store.read(*key, lock=True)
    if not progress.cancellation_request_id:
        return False
    prior = connection.execute(
        "SELECT 1 FROM execution_authority.prepared_stop_receipts WHERE namespace=%s AND security_domain=%s AND command_id=%s",
        (*key[:2], str(command.command_id)),
    ).fetchone()
    if prior:
        return True
    # EFFECT_STARTED is irrevocable permission; an expired local lease proves no stop.
    if command_row["state"] == "EFFECT_STARTED":
        return False
    if command_row["state"] != "CLAIMED" or command_row[
        "lease_expires_at"
    ] <= datetime.now(UTC):
        raise ExecutionPreparationError("CANCELLATION_NATIVE_CLAIM_STALE")
    receipt_id = stable_id(
        "prepared-native-stop",
        str(command.command_id),
        progress.cancellation_request_id,
    )
    record = {
        "receiptId": receipt_id,
        "commandId": str(command.command_id),
        "commandDigest": command.digest,
        "attemptId": str(command.attempt_id),
        "cancellationRequestId": progress.cancellation_request_id,
        "claimGeneration": claim.claim_generation.value,
        "proof": "NATIVE_EFFECT_PERMISSION_NOT_ISSUED",
    }
    connection.execute(
        "INSERT INTO execution_authority.prepared_stop_receipts "
        "(namespace,security_domain,receipt_id,command_id,attempt_id,request_id,digest,record) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            *key[:2],
            receipt_id,
            str(command.command_id),
            str(command.attempt_id),
            progress.cancellation_request_id,
            canonical_digest(record),
            Jsonb(record),
        ),
    )
    # The supplemental immutable receipt fences future claims; do not fabricate a
    # legacy Native terminal observation for an effect that never started.
    connection.execute(
        "UPDATE execution_authority.attempts SET control_state='CANCELLED',aggregate_version=aggregate_version+1 WHERE namespace=%s AND security_domain=%s AND attempt_id=%s",
        (*key[:2], str(command.attempt_id)),
    )
    result = store.apply(
        *key,
        ProgressEvent(
            action="STOP_CONFIRMED",
            evidence_id=receipt_id,
            task_id=row["task_id"],
            attempt_id=str(command.attempt_id),
        ),
        expected_version=progress.version,
    )
    sync_projection(connection, key, result)
    return True
