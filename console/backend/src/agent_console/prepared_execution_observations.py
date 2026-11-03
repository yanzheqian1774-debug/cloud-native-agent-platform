# ruff: noqa: E501 -- Explicit transactional SQL statements.
"""Translate durable Native/Skill owner facts within their original transactions."""

import hashlib
import json

from psycopg.errors import RaiseException

from .execution_preparation import (
    ArtifactDocument,
    ExecutionPreparationError,
    ProgressEvent,
)
from .execution_preparation_postgres import PreparedExecutionStore
from .prepared_execution_lineage import prepared_attempt
from .resource_use_domain import stable_id


def apply_native(connection, command, observation=None):
    row = prepared_attempt(connection, command.scope, command.attempt_id)
    if row is None:
        return
    key = (
        command.scope.namespace,
        command.scope.security_domain,
        row["workflow_run_id"],
    )
    store = PreparedExecutionStore(connection)
    _, progress = store.read(*key, lock=True)
    artifacts = ()
    if observation is None:
        action, evidence = "STARTED", "native-start:" + str(command.command_id)
    else:
        action = observation.kind.value
        evidence = "native-terminal:" + observation.digest
        if action == "RECOVERY_REQUIRED":
            action = "UNKNOWN"
        if action == "SUCCEEDED":
            rows = connection.execute(
                "SELECT artifact_id,digest FROM execution_authority.run_artifacts "
                "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s "
                "AND task_id=%s AND attempt_id=%s ORDER BY artifact_id",
                (*key, row["task_id"], str(command.attempt_id)),
            ).fetchall()
            try:
                reference = json.loads(observation.output)
            except (ValueError, TypeError) as exc:
                raise ExecutionPreparationError(
                    "NATIVE_OUTPUT_ARTIFACT_MISMATCH"
                ) from exc
            if len(rows) != 1 or reference != {
                "schemaVersion": "prepared-output-reference.v1",
                "artifactId": rows[0]["artifact_id"],
                "digest": rows[0]["digest"],
            }:
                raise ExecutionPreparationError("NATIVE_OUTPUT_ARTIFACT_MISMATCH")
            artifacts = (rows[0]["artifact_id"],)
        elif action not in {"FAILED", "UNKNOWN"}:
            raise ExecutionPreparationError("NATIVE_OBSERVATION_NOT_SUPPORTED")
    result = store.apply(
        *key,
        ProgressEvent(
            action=action,
            evidence_id=evidence,
            task_id=row["task_id"],
            attempt_id=str(command.attempt_id),
            artifact_ids=artifacts,
        ),
        expected_version=progress.version,
    )
    sync_projection(connection, key, result)


def sync_projection(connection, key, progress):
    connection.execute(
        "UPDATE execution_authority.workflow_runs SET control_state=%s,"
        "aggregate_version=%s WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
        (
            "CANCELLATION_PENDING"
            if progress.state == "CANCEL_REQUESTED"
            else progress.state,
            progress.version,
            *key,
        ),
    )
    states = {
        "WAITING": "PENDING",
        "QUEUED": "READY",
        "RETRY_WAIT": "BLOCKED",
        "FINAL_FAILED": "FAILED",
        "UNKNOWN": "BLOCKED",
    }
    for task in progress.tasks:
        connection.execute(
            "UPDATE execution_authority.task_runs SET control_state=%s,aggregate_version=%s "
            "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s AND workflow_node_id=%s",
            (states.get(task.state, task.state), progress.version, *key, task.task_id),
        )


def store_skill_output(connection, request, output):
    row = prepared_attempt(connection, request.scope, request.attempt_id)
    if row is None:
        return
    key = (
        request.scope.namespace,
        request.scope.security_domain,
        row["workflow_run_id"],
    )
    store = PreparedExecutionStore(connection)
    preparation, _ = store.read(*key, lock=True)
    task = next(t for t in preparation.semantics.tasks if t.task_id == row["task_id"])
    content = json.dumps(
        output, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    try:
        artifact = ArtifactDocument(
            artifact_id=stable_id("native-skill-artifact", request.invocation_id),
            task_id=task.task_id,
            attempt_id=request.attempt_id,
            kind=task.output_kind,
            schema_version="prepared-skill-output.v1",
            content=content,
            digest=hashlib.sha256(content.encode()).hexdigest(),
        )
    except ValueError as exc:
        raise ExecutionPreparationError("ARTIFACT_SIZE_OR_DIGEST_INVALID") from exc
    try:
        # Capacity failure rolls back only this append, allowing a durable Skill failure.
        with connection.transaction():
            store.append_artifact(*key, artifact)
    except RaiseException as exc:
        if "ARTIFACT_HISTORY_CAPACITY_EXCEEDED" not in str(exc):
            raise
        raise ExecutionPreparationError("ARTIFACT_HISTORY_CAPACITY_EXCEEDED") from exc
