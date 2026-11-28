"""Exact imported Tool lifecycle; existing immutable revisions and command ledger."""

from copy import deepcopy
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import Field, model_validator

from .execution_domain import record_digest
from .skill_invocation_domain import SkillInvocationError
from .skill_resource_testing import redact, schema_check
from .tool_definition_postgres import ToolStorageError
from .workbench_bff_schemas import StrictWorkbenchModel


class ToolCommand(StrictWorkbenchModel):
    action: Literal["validate", "successor", "test", "publish"]
    commandId: str = Field(min_length=1, max_length=200)
    expectedVersion: int = Field(strict=True, ge=1)
    revisionId: str = Field(min_length=1, max_length=200)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    testName: str | None = Field(default=None, min_length=1, max_length=120)
    input: dict | None = None
    expectedOutput: dict | None = None
    comparison: Literal["exact", "subset"] = "exact"

    @model_validator(mode="after")
    def fields_for_action(self):
        if self.action == "test":
            if not self.testName or self.input is None or self.expectedOutput is None:
                raise ValueError("TOOL_TEST_CASE_REQUIRED")
        elif (
            self.testName is not None
            or self.input is not None
            or self.expectedOutput is not None
            or self.comparison != "exact"
        ):
            raise ValueError("TOOL_COMMAND_FIELDS_INVALID")
        return self


def validate_contract(record, runtime_evidence=None):
    original = record["operation"].get("blockingIssues", [])
    resolved = ["PLUGIN_RUNTIME_VALIDATION_REQUIRED"] if runtime_evidence else []
    issues = [issue for issue in original if issue not in resolved]
    if issues:
        raise ToolStorageError("TOOL_UNSUPPORTED_SOURCE_CONTRACT")
    for name in ("inputSchema", "outputSchema"):
        schema = record["operation"].get(name)
        if not isinstance(schema, dict) or not schema:
            raise ToolStorageError("TOOL_CONTRACT_REQUIRED")
        try:
            schema_check({}, schema, "TOOL_SCHEMA_PROBE")
        except SkillInvocationError as exc:
            if str(exc) != "TOOL_SCHEMA_PROBE":
                raise ToolStorageError("TOOL_CONTRACT_UNSUPPORTED") from exc
    if record["operation"].get("sideEffect") == "UNCONFIRMED":
        raise ToolStorageError("TOOL_SIDE_EFFECT_UNCONFIRMED")
    return {
        "status": "VALIDATED",
        "scope": "DEFINITION_CONTRACT_ONLY",
        "executionVerified": False,
        "blockingIssues": issues,
        "originalBlockingIssues": original,
        "resolvedIssues": [issue for issue in original if issue in resolved],
        "runtimeEvidence": runtime_evidence,
        "sourceExecutionVerified": runtime_evidence is not None,
    }


def history(repository, conn, scope, tool_id):
    rows = conn.execute(
        (
            "SELECT revision_id FROM tool_definition.revisions WHERE namespace=%s "
            "AND security_domain=%s AND tool_id=%s ORDER BY revision_id"
        ),
        (*repository._scope(scope), tool_id),
    ).fetchall()
    revisions = [
        repository.read(conn, scope, tool_id, row["revision_id"]) for row in rows
    ]
    receipts = conn.execute(
        (
            "SELECT result FROM tool_definition.receipts WHERE namespace=%s AND "
            "security_domain=%s AND EXISTS(SELECT 1 FROM "
            "jsonb_array_elements(result->'items') i WHERE i->>'toolId'=%s) ORDER "
            "BY recorded_at,command_id"
        ),
        (*repository._scope(scope), tool_id),
    ).fetchall()
    return revisions, [row["result"] for row in receipts]


def command(
    repository,
    conn,
    scope,
    tool_id,
    cmd,
    *,
    actor_id,
    decision_id,
    run_test=None,
    validate_runtime=None,
):
    key = repository._scope(scope)
    payload = record_digest(
        {"toolId": tool_id, "actorId": actor_id, "command": cmd.model_dump(mode="json")}
    )
    conn.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,61))",
        (record_digest(list(key)),),
    )
    old = conn.execute(
        (
            "SELECT payload_digest,result FROM tool_definition.receipts WHERE "
            "namespace=%s AND security_domain=%s AND command_id=%s"
        ),
        (*key, cmd.commandId),
    ).fetchone()
    if old:
        if old["payload_digest"] != payload:
            raise ToolStorageError("TOOL_COMMAND_CONFLICT")
        return {**old["result"], "replayed": True}
    current = repository.read(conn, scope, tool_id, cmd.revisionId)
    if current["aggregateVersion"] != cmd.expectedVersion:
        raise ToolStorageError("TOOL_VERSION_CONFLICT")
    if current["digest"] != cmd.digest:
        raise ToolStorageError("TOOL_EXACT_DIGEST_REQUIRED")
    head = repository.head(conn, scope, tool_id)
    extra = {}
    version = cmd.expectedVersion
    revision = current["revisionId"]
    digest = current["digest"]
    if cmd.action == "successor":
        if head["draft_revision_id"] or head["published_revision_id"] != revision:
            raise ToolStorageError("TOOL_PUBLISHED_WITHOUT_DRAFT_REQUIRED")
        record = deepcopy(current["record"])
        record.update(state="DRAFT", validation=None)
        revision = "tool-revision:" + str(uuid4())
        digest = record_digest(record)
        conn.execute(
            "INSERT INTO tool_definition.revisions VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *key,
                tool_id,
                revision,
                current["revisionId"],
                current["sourceDigest"],
                digest,
                Jsonb(record),
            ),
        )
        version += 1
        conn.execute(
            (
                "UPDATE tool_definition.definitions SET "
                "draft_revision_id=%s,aggregate_version=%s WHERE namespace=%s AND "
                "security_domain=%s AND tool_id=%s"
            ),
            (revision, version, *key, tool_id),
        )
    elif cmd.action == "test":
        if revision not in {head["draft_revision_id"], head["published_revision_id"]}:
            raise ToolStorageError("TOOL_CURRENT_TEST_TARGET_REQUIRED")
        if (
            redact(cmd.input) != cmd.input
            or redact(cmd.expectedOutput) != cmd.expectedOutput
        ):
            raise ToolStorageError("TOOL_TEST_REDACTED_INPUT_DENIED")
        extra["testCase"] = {
            "name": cmd.testName,
            "input": cmd.input,
            "expected": cmd.expectedOutput,
            "comparison": cmd.comparison,
            "revisionId": revision,
            "revisionDigest": digest,
        }
        extra["testResult"] = (
            run_test(current, cmd)
            if run_test
            else {
                "status": "NOT_EXECUTED",
                "actual": None,
                "actualExecution": False,
                "toolSourceInvoked": False,
                "reasonCode": "TOOL_EXECUTOR_NOT_CONFIGURED",
                "modelCalls": 0,
                "revisionId": revision,
                "revisionDigest": digest,
            }
        )
    else:
        if head["draft_revision_id"] != revision:
            raise ToolStorageError("TOOL_CURRENT_DRAFT_REQUIRED")
        runtime = None
        if "PLUGIN_RUNTIME_VALIDATION_REQUIRED" in current["record"]["operation"].get(
            "blockingIssues", []
        ):
            runtime = validate_runtime(current, cmd) if validate_runtime else None
        extra["validation"] = validate_contract(current["record"], runtime)
        if cmd.action == "publish":
            _, previous = history(repository, conn, scope, tool_id)
            if not any(
                r.get("commandKind") == "VALIDATE"
                and any(
                    i["revisionId"] == revision and i["digest"] == digest
                    for i in r["items"]
                )
                for r in previous
            ):
                raise ToolStorageError("TOOL_VALIDATION_REQUIRED")
            # Publication fixes this exact immutable revision. Test evidence remains
            # separately visible and never grants execution or fabricates output.
            version += 1
            conn.execute(
                (
                    "UPDATE tool_definition.definitions SET "
                    "published_revision_id=%s,draft_revision_id=NULL"
                    ",aggregate_version=%s "
                    "WHERE namespace=%s AND security_domain=%s AND tool_id=%s"
                ),
                (revision, version, *key, tool_id),
            )
    result = {
        "commandKind": cmd.action.upper(),
        "items": [
            {
                "toolId": tool_id,
                "revisionId": revision,
                "digest": digest,
                "aggregateVersion": version,
                "changed": cmd.action in {"publish", "successor"},
            }
        ],
        **extra,
        "actorId": actor_id,
        "recordedAt": datetime.now(UTC).isoformat(),
        "replayed": False,
        "executionAuthorized": False,
    }
    conn.execute(
        (
            "INSERT INTO "
            "tool_definition.receipts(namespace,security_domain,command_id,actor_id"
            ",decision_id,payload_digest,result) VALUES (%s,%s,%s,%s,%s,%s,%s)"
        ),
        (*key, cmd.commandId, actor_id, decision_id, payload, Jsonb(result)),
    )
    return result
