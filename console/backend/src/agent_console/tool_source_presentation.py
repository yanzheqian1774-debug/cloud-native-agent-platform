"""Allowlisted past Source facts for display; never a lifecycle decision."""


def _time(value):
    return value.isoformat() if value is not None else None


def _attempt(row):
    if row is None:
        return None
    return {
        "commandKey": row["command_key"],
        "revisionId": row["revision_id"],
        "digest": row["digest"],
        "sourceDigest": row["source_digest"],
        "startedAt": _time(row["started_at"]),
        "recordedAt": _time(row["recorded_at"]),
        "status": row["status"] or "UNKNOWN",
        "reasonCode": row["reason_code"],
        "runtime": row["runtime"],
        "runtimeRevision": row["runtime_revision"],
        "expectationMismatch": row["status"] == "FAILED"
        and row["reason_code"] == "TOOL_SOURCE_EXPECTATION_MISMATCH"
        and row["actual_execution"] is True
        and row["source_invoked"] is True
        and row["verification_level"] == "ISOLATED_EXACT_TOOL_SOURCE_EXECUTION",
    }


def read_source_presentation(connection, scope, current, resolution, subject):
    # Called only after the BFF's current exact Tool READ. Optional 0081 is not
    # installed merely by opening this page, and old mapping receipts are not read.
    tables = connection.execute(
        "SELECT to_regclass('tool_definition.source_test_requests') requests, "
        "to_regclass('tool_definition.source_test_facts') facts"
    ).fetchone()
    if not tables["requests"] or not tables["facts"]:
        return None

    def read(command_key):
        row = connection.execute(
            "SELECT r.command_key,r.request->>'revisionId' revision_id, "
            "r.request->>'digest' digest,r.request->>'sourceDigest' source_digest, "
            "r.created_at started_at,f.recorded_at,f.fact->>'status' status, "
            "f.fact->>'reasonCode' reason_code, "
            "f.fact->'sourceExecution'->>'runtime' runtime, "
            "f.fact->'sourceExecution'->>'runtimeRevision' runtime_revision, "
            "f.fact->'actualExecution' actual_execution, "
            "f.fact->'toolSourceInvoked' source_invoked, "
            "f.fact->>'verificationLevel' verification_level "
            "FROM tool_definition.source_test_requests r "
            "JOIN tool_definition.source_test_facts c USING "
            "(namespace,security_domain,subject_id,command_key) "
            "LEFT JOIN tool_definition.source_test_facts f ON "
            "(f.namespace,f.security_domain,f.subject_id,f.command_key,f.kind)="
            "(r.namespace,r.security_domain,r.subject_id,r.command_key,'RESULT') "
            "WHERE c.kind='DISPATCH_CLAIM' AND r.namespace=%s "
            "AND r.security_domain=%s AND r.subject_id=%s "
            "AND r.request->>'toolId'=%s AND r.request->>'revisionId'=%s "
            "AND r.request->>'digest'=%s AND r.request->>'sourceDigest'=%s "
            "AND (%s::text IS NULL OR r.command_key=%s) "
            "ORDER BY r.created_at DESC,r.command_key LIMIT 1",
            (
                scope.namespace,
                scope.security_domain,
                subject,
                current["toolId"],
                current["revisionId"],
                current["digest"],
                current["sourceDigest"],
                command_key,
                command_key,
            ),
        ).fetchone()
        return _attempt(row)

    proof = resolution.get("runtimeEvidence") if resolution else None
    return {
        "basis": read(proof["commandKey"]) if proof else None,
        "latest": read(None),
        "currentAvailability": "NOT_ESTABLISHED",
        "allTestsPassed": "NOT_ESTABLISHED",
        "executionAuthorized": False,
    }
