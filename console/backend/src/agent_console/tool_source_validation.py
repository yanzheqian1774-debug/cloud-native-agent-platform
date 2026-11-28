"""Resolve one import blocker from exact Tool-owned facts, never expectations."""

import json

from .execution_domain import record_digest
from .skill_executor import HttpReadOnlySkillExecutor
from .skill_resource_testing import schema_check
from .tool_definition_postgres import ToolStorageError
from .tool_source_runtime import source_request

BLOCKER = "PLUGIN_RUNTIME_VALIDATION_REQUIRED"


def runtime_evidence(owner, call, current, command):
    """Only the already authorized owner calls this before VALIDATE/PUBLISH."""
    try:
        binding = owner.authorize(call, current, command)
        keys = call.connection.execute(
            "SELECT command_key FROM tool_definition.source_test_requests WHERE "
            "namespace=%s AND security_domain=%s AND subject_id=%s AND "
            "request->>'toolId'=%s AND request->>'revisionId'=%s "
            "ORDER BY created_at DESC,command_key LIMIT 200",
            (
                binding.namespace,
                binding.securityDomain,
                binding.subject,
                binding.toolId,
                binding.revisionId,
            ),
        ).fetchall()
        for row in keys:
            proof = _fact(owner, call, current, binding, row["command_key"])
            if proof is not None:
                return proof
    except (ValueError, OSError) as exc:
        raise ToolStorageError("TOOL_SOURCE_RUNTIME_VALIDATION_UNAVAILABLE") from exc
    raise ToolStorageError("TOOL_SOURCE_RUNTIME_EVIDENCE_REQUIRED")


def _fact(owner, call, current, binding, key):
    saved = owner.journal.read(call.context, key)
    if not saved or not saved["claimed"] or saved["result"] is None:
        return None
    request, result = saved["request"], saved["result"]
    # Only terminal source outcomes can establish a runtime fact. A failed
    # expectation comparison retains independent actual/contract evidence;
    # UNKNOWN/NOT_EXECUTED never does, even if a future producer includes proof.
    status = result.get("status")
    if status not in {"PASSED", "FAILED"} or (
        status == "FAILED"
        and result.get("reasonCode") != "TOOL_SOURCE_EXPECTATION_MISMATCH"
    ):
        return None
    cmd = request.get("command", {})
    if (
        cmd.get("action") != "test"
        or cmd.get("revisionId") != current["revisionId"]
        or cmd.get("digest") != current["digest"]
        or request.get("toolId") != current["toolId"]
        or request.get("revisionId") != current["revisionId"]
        or request.get("digest") != current["digest"]
        or request.get("sourceDigest") != current["sourceDigest"]
        or not result.get("actualExecution")
        or not result.get("toolSourceInvoked")
        or result.get("verificationLevel") != "ISOLATED_EXACT_TOOL_SOURCE_EXECUTION"
        or not isinstance(result.get("actual"), dict)
    ):
        return None
    inputs, actual = cmd.get("input"), result["actual"]
    if not isinstance(inputs, dict):
        return None
    if (
        len(json.dumps(inputs, ensure_ascii=False).encode()) > binding.maximumInputBytes
        or len(json.dumps(actual, ensure_ascii=False).encode())
        > binding.maximumOutputBytes
    ):
        return None
    operation = current["record"]["operation"]
    invocation = source_request(owner.repository, call, current, binding, inputs)
    expected = {
        k: invocation[k]
        for k in (
            "toolId",
            "revisionId",
            "revisionDigest",
            "sourceDigest",
            "entrypoint",
            "entrypointDigest",
            "runtime",
            "runtimeRevision",
            "operation",
            "inputDigest",
        )
    }
    execution = result.get("sourceExecution", {})
    executor = HttpReadOnlySkillExecutor(
        executor_id=binding.runtime,
        executor_revision=binding.runtimeRevision,
        endpoint=binding.endpoint,
    )
    if (
        request.get("executionRequestDigest") != record_digest(invocation)
        or any(execution.get(k) != v for k, v in expected.items())
        or execution.get("actualDigest") != record_digest(actual)
        or not isinstance(execution.get("observationId"), str)
        or not execution["observationId"]
        or execution.get("executorConfigurationDigest")
        != executor.revision.configuration_digest
    ):
        return None
    try:
        schema_check(inputs, operation["inputSchema"], "TOOL_SOURCE_INPUT_INVALID")
        schema_check(actual, operation["outputSchema"], "TOOL_SOURCE_OUTPUT_INVALID")
    except ValueError:
        return None
    # Terminal eligibility is checked above. Expectation contents or a PASSED
    # comparison alone never establish source execution or contract validity.
    return {
        **expected,
        "commandKey": key,
        "actualDigest": record_digest(actual),
        "executionRequestDigest": record_digest(invocation),
        "observationId": execution["observationId"],
        "currentPolicyDigest": owner.policy.digest,
        "verificationLevel": "ISOLATED_EXACT_TOOL_SOURCE_EXECUTION",
    }


def read_resolution(connection, scope, current):
    """Past exact validation fact for display; never a current invocation grant."""
    row = connection.execute(
        "SELECT result->'validation' validation FROM tool_definition.receipts "
        "WHERE namespace=%s AND security_domain=%s "
        "AND result->>'commandKind' IN ('VALIDATE','PUBLISH') "
        "AND EXISTS (SELECT 1 FROM jsonb_array_elements(result->'items') i "
        "WHERE i->>'toolId'=%s AND i->>'revisionId'=%s AND i->>'digest'=%s) "
        "ORDER BY recorded_at DESC,command_id DESC LIMIT 1",
        (
            scope.namespace,
            scope.security_domain,
            current["toolId"],
            current["revisionId"],
            current["digest"],
        ),
    ).fetchone()
    validation = row["validation"] if row else None
    if not validation or not validation.get("runtimeEvidence"):
        return None
    return {
        **validation,
        "executionAuthorized": False,
        "currentAuthorizationChecked": False,
    }
