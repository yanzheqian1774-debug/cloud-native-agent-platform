"""Exact Tool-owned synthetic source test; claim is committed before HTTP."""

import json
from datetime import UTC, datetime

from .authority_contracts import ExactGrant
from .execution_domain import ScopeIdentity, record_digest
from .skill_resource_testing import exact, schema_check, subset
from .tool_definition_authorization import require_tool_grant
from .tool_definition_postgres import ToolStorageError
from .tool_source_journal import SourceJournal, check_schema
from .tool_source_policy import PrivateSourcePolicy
from .tool_source_runtime import invoke, source_request


class ToolSourceTesting:
    def __init__(self, path, repository, *, clock=lambda: datetime.now(UTC)):
        self.policy = PrivateSourcePolicy(path)
        self.repository = repository
        self.journal = SourceJournal(repository.pool)
        self.clock = clock
        if self.policy.policy.enabled:
            with repository.pool.connection() as c:
                check_schema(c)

    @staticmethod
    def base(current):
        return {
            "status": "NOT_EXECUTED",
            "actual": None,
            "actualExecution": False,
            "toolSourceInvoked": False,
            "revisionId": current["revisionId"],
            "revisionDigest": current["digest"],
            "sourceDigest": current["sourceDigest"],
            "modelCalls": 0,
            "businessRunStarted": False,
            "automaticRetry": False,
            "verificationLevel": "ISOLATED_EXACT_TOOL_SOURCE_EXECUTION",
        }

    def authorize(self, call, current, command):
        for action, resource in (
            ("READ", current["toolId"] + ":" + current["revisionId"]),
            ("TEST", current["toolId"] + ":aggregate"),
        ):
            require_tool_grant(call, ExactGrant("TOOL", action, resource))
        scope = ScopeIdentity(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )
        latest = self.repository.read(
            call.connection, scope, current["toolId"], current["revisionId"]
        )
        head = self.repository.head(call.connection, scope, current["toolId"])
        if (
            latest != current
            or current["revisionId"]
            not in {head["draft_revision_id"], head["published_revision_id"]}
            or current["aggregateVersion"] != command.expectedVersion
        ):
            raise ValueError("TOOL_SOURCE_CURRENT_EXACT_REVISION_REQUIRED")
        return self.policy.binding(call.context, current, self.clock())

    def run(self, call, current, command):
        base = self.base(current)
        try:
            b = self.authorize(call, current, command)
            operation = current["record"]["operation"]
            if operation["source"]["kind"] != "PLUGIN":
                raise ValueError("TOOL_SOURCE_PLUGIN_ZIP_REQUIRED")

            if (
                len(json.dumps(command.input, ensure_ascii=False).encode())
                > b.maximumInputBytes
            ):
                raise ValueError("TOOL_SOURCE_INPUT_LIMIT")
            schema_check(
                command.input, operation["inputSchema"], "TOOL_SOURCE_INPUT_INVALID"
            )
            request = source_request(self.repository, call, current, b, command.input)
            request_digest = record_digest(request)
            identity = {
                k: request[k]
                for k in (
                    "toolId",
                    "revisionId",
                    "revisionDigest",
                    "sourceDigest",
                    "runtime",
                    "runtimeRevision",
                    "entrypoint",
                    "entrypointDigest",
                )
            }
            identity["endpoint"] = b.endpoint
            binding_digest = record_digest(identity)
            saved = {
                "toolId": current["toolId"],
                "revisionId": current["revisionId"],
                "digest": current["digest"],
                "sourceDigest": current["sourceDigest"],
                "command": command.model_dump(),
                "executionRequestDigest": request_digest,
                "policyDigest": self.policy.digest,
            }
            fresh, old = self.journal.claim(
                call.context, command.commandId, binding_digest, saved, b.maximumCalls
            )
        except (ValueError, OSError) as exc:
            return {**base, "reasonCode": str(exc)}
        if not fresh:
            return old["result"] or {
                **base,
                "status": "UNKNOWN",
                "reasonCode": "TOOL_SOURCE_PRIOR_CLAIM_UNRESOLVED",
            }
        # All exceptions after committed claim are conservative: never redispatch.
        result = {
            **base,
            "status": "UNKNOWN",
            "reasonCode": "TOOL_SOURCE_OUTCOME_UNKNOWN",
        }
        try:
            # Recheck original Tool authorization, policy bytes, source and revision;
            # no foreign owner grant or request-supplied endpoint is used.
            if self.authorize(call, current, command) != b:
                raise ValueError("TOOL_SOURCE_POLICY_CHANGED")
            if (
                source_request(self.repository, call, current, b, command.input)
                != request
            ):
                raise ValueError("TOOL_SOURCE_CHANGED")
            actual, evidence = invoke(b, "tool-source:" + record_digest(saved), request)
            result.update(
                status="FAILED",
                reasonCode="TOOL_SOURCE_EXPECTATION_MISMATCH",
                actual=actual,
                actualExecution=True,
                toolSourceInvoked=True,
                sourceExecution=evidence,
                policyDigest=self.policy.digest,
            )
            if (
                len(json.dumps(actual, ensure_ascii=False).encode())
                > b.maximumOutputBytes
            ):
                result["reasonCode"] = "TOOL_SOURCE_OUTPUT_LIMIT"
                result["actual"] = None
            else:
                schema_check(
                    actual, operation["outputSchema"], "TOOL_SOURCE_OUTPUT_INVALID"
                )
                matches = (
                    subset(command.expectedOutput, actual)
                    if command.comparison == "subset"
                    else exact(command.expectedOutput, actual)
                )
                if matches:
                    result.update(
                        status="PASSED", reasonCode="TOOL_SOURCE_EXPECTATION_MATCHED"
                    )
        except Exception:
            # Even malformed evidence or a timeout can follow a real source effect.
            # Actual already observed is retained if output contract validation fails.
            if result["actualExecution"]:
                result["reasonCode"] = "TOOL_SOURCE_OUTPUT_INVALID"
        self.journal.finish(call.context, command.commandId, result)
        return result

    def validate_runtime(self, call, current, command):
        from .tool_source_validation import runtime_evidence

        return runtime_evidence(self, call, current, command)

    def receipt(self, call, key):
        old = self.journal.read(call.context, key)
        if old is None:
            raise ToolStorageError("TOOL_COMMAND_NOT_FOUND")
        r = old["request"]
        require_tool_grant(
            call, ExactGrant("TOOL", "READ", r["toolId"] + ":" + r["revisionId"])
        )
        current = {
            "toolId": r["toolId"],
            "revisionId": r["revisionId"],
            "digest": r["digest"],
            "sourceDigest": r["sourceDigest"],
        }
        result = old["result"] or {
            **self.base(current),
            "status": "UNKNOWN",
            "reasonCode": "TOOL_SOURCE_PRIOR_CLAIM_UNRESOLVED",
        }
        cmd = r.get("command", {})
        return {
            "commandKind": "TEST",
            "commandId": key,
            "items": [
                {
                    "toolId": r["toolId"],
                    "revisionId": r["revisionId"],
                    "digest": r["digest"],
                    "aggregateVersion": cmd.get("expectedVersion"),
                    "changed": False,
                    "testResult": result,
                }
            ],
            "testResult": result,
            "testCase": {
                "name": cmd.get("testName"),
                "input": cmd.get("input"),
                "expected": cmd.get("expectedOutput"),
                "comparison": cmd.get("comparison"),
                "revisionId": r["revisionId"],
                "revisionDigest": r["digest"],
            },
            "executionAuthorized": False,
            "actorId": call.context.principal_id,
            "automaticRetry": False,
            "recoveredSourceClaim": True,
        }
