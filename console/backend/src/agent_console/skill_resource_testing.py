"""Isolated deterministic resource tests, never production Attempt execution."""

import copy
import json
from time import monotonic

from .prepared_native_composition import POLICY
from .resource_automation_validation import EXECUTORS
from .resource_use_domain import canonical_digest
from .skill_invocation_application import _validate_shape
from .skill_invocation_domain import ExecutorRevision, SkillInvocationError
from .skill_invocation_postgres import _validate_json_schema
from .skill_mcp_service import SkillMcpFailure, _id, _now
from .skill_mcp_transport import redact


def exact(expected, actual):
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, dict):
        return set(expected) == set(actual) and all(
            exact(v, actual[k]) for k, v in expected.items()
        )
    if isinstance(expected, list):
        return len(expected) == len(actual) and all(
            exact(a, b) for a, b in zip(expected, actual, strict=True)
        )
    return expected == actual


def subset(expected, actual):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            k in actual and subset(v, actual[k]) for k, v in expected.items()
        )
    # Lists compare in full, including order and length; bool is not int.
    return exact(expected, actual)


def schema_check(value, schema, code):
    def inspect(rule):
        allowed = {
            "type",
            "properties",
            "required",
            "additionalProperties",
            "enum",
            "items",
            "minLength",
            "maxLength",
            "pattern",
            "description",
            "title",
        }
        if not isinstance(rule, dict) or set(rule) - allowed:
            raise SkillInvocationError("TEST_SCHEMA_KEYWORD_UNSUPPORTED")
        if "pattern" in rule and rule["pattern"] != "^[0-9a-f]{64}$":
            raise SkillInvocationError("TEST_SCHEMA_PATTERN_UNSUPPORTED")
        for child in rule.get("properties", {}).values():
            inspect(child)
        if "items" in rule:
            inspect(rule["items"])

    def patterns(item, rule):
        import re

        if "pattern" in rule and (
            not isinstance(item, str) or re.fullmatch("[0-9a-f]{64}", item) is None
        ):
            raise SkillInvocationError(code)
        if isinstance(item, dict):
            for k, child in item.items():
                if k in rule.get("properties", {}):
                    patterns(child, rule["properties"][k])
        elif isinstance(item, list):
            for child in item:
                patterns(child, rule["items"])

    inspect(schema)
    _validate_json_schema(value, schema, code)
    patterns(value, schema)


def run(
    service,
    scope,
    identity,
    actor,
    version,
    *,
    operation,
    name,
    inputs,
    expected_output,
    comparison,
    revision_id=None,
    persist=True,
    verify=None,
    verification_context=None,
    executor_registry=None,
):
    record = service._load(scope, "skill", identity)
    service._expected(record, version)
    revision = (
        service._draft(record)
        if record["currentDraftRevisionId"]
        else service._published(record)
    )
    if revision_id is not None:
        revision = next(
            (r for r in record["revisions"] if r["revisionId"] == revision_id), None
        )
        if revision is None:
            raise SkillMcpFailure("TEST_EXACT_REVISION_REQUIRED", 409)
    if not expected_output:
        raise SkillMcpFailure("TEST_EXPECTATION_REQUIRED")
    case = {
        "testId": _id("skill-test"),
        "name": name,
        "input": redact(inputs),
        "expected": redact(expected_output),
        "operation": operation,
        "comparison": comparison,
        "createdAt": _now(),
    }
    if case["input"] != inputs or case["expected"] != expected_output:
        raise SkillMcpFailure("TEST_REDACTED_INPUT_DENIED")
    encoded = json.dumps(inputs, ensure_ascii=False).encode()
    if len(encoded) > 64000:
        raise SkillMcpFailure("TEST_INPUT_TOO_LARGE")
    result = {
        "resultId": _id("skill-test-result"),
        "testId": case["testId"],
        "caseName": name,
        "revisionId": revision["revisionId"],
        "revisionDigest": revision["digest"],
        "operation": operation,
        "comparison": comparison,
        "inputDigest": canonical_digest(inputs),
        "expectedDigest": canonical_digest(expected_output),
        "status": "NOT_EXECUTED",
        "actual": None,
        "actualExecution": False,
        "verificationLevel": "ISOLATED_SYNTHETIC_EXECUTOR",
        "reasonCode": "TEST_EXECUTOR_NOT_CONFIGURED",
        "errors": [],
        "businessRunStarted": False,
        "recordedAt": _now(),
    }
    started = monotonic()
    try:
        op = next(
            (
                x
                for x in revision["content"].get("operations", [])
                if x["name"] == operation
            ),
            None,
        )
        if op is None:
            raise SkillInvocationError("TEST_OPERATION_UNAVAILABLE")
        if op["sideEffectClass"] != "READ_ONLY" or op["sideEffectPolicy"] != {
            "policyId": POLICY.policy_id,
            "policyRevision": POLICY.policy_revision,
            "policyDigest": POLICY.policy_digest,
        }:
            raise SkillInvocationError("TEST_SIDE_EFFECT_DENIED")
        executor = (executor_registry or EXECUTORS).resolve(
            ExecutorRevision(
                op["executorId"],
                op["executorRevision"],
                op["executorConfigurationDigest"],
            )
        )
        # Exact v2 resource testing covers the deterministic operation library.
        # Real decisions require a Native Attempt and its model admission; never
        # create that authority or call a model from the resource-test endpoint.
        from .native_document_skill import (
            DocumentComputationExecutor,
            NativeDocumentSkillExecutor,
        )
        from .native_loop_skill import NativeLoopSkillExecutor
        from .tabular_diagnostic_skill import TabularDiagnosticSkillExecutor

        document_executor = isinstance(executor, NativeDocumentSkillExecutor)
        if document_executor or isinstance(executor, NativeLoopSkillExecutor):
            executor = (
                DocumentComputationExecutor()
                if document_executor
                else TabularDiagnosticSkillExecutor()
            )
            verification_context = {
                **(verification_context or {}),
                "nativeDecisionValidation": "NOT_RUN_REQUIRES_NATIVE_ATTEMPT",
                "validationScope": "READ_ONLY_OPERATION_COMPUTATION",
            }
            result["verificationContext"] = verification_context
        limits = op["ioLimits"]
        if inputs.get("synthetic") is not True:
            raise SkillInvocationError("TEST_SYNTHETIC_INPUT_REQUIRED")
        _validate_shape(
            inputs,
            min(limits["maxObjectDepth"], 20),
            min(limits["maxProperties"], 20000),
        )
        if len(encoded) > limits["maxInputBytes"]:
            raise SkillInvocationError("TEST_INPUT_TOO_LARGE")
        schema_check(inputs, op["inputSchema"], "TEST_INPUT_CONTRACT_INVALID")
        result["status"] = "FAILED"
        result["actualExecution"] = True
        observed = executor.invoke(
            result["resultId"],
            operation,
            copy.deepcopy(inputs),
            min(limits["timeoutMs"], 5000),
        )
        if (monotonic() - started) * 1000 > min(limits["timeoutMs"], 5000):
            raise SkillInvocationError("TEST_TIMEOUT")
        output = observed.output
        if len(json.dumps(output, ensure_ascii=False).encode()) > min(
            limits["maxOutputBytes"], 512000
        ):
            raise SkillInvocationError("TEST_OUTPUT_TOO_LARGE")
        _validate_shape(
            output,
            min(limits["maxObjectDepth"], 20),
            min(limits["maxProperties"], 20000),
        )
        schema_check(output, op["outputSchema"], "TEST_OUTPUT_CONTRACT_INVALID")
        result["actual"] = redact(output)
        if result["actual"] != output:
            raise SkillInvocationError("TEST_OUTPUT_REDACTED")
        result["outputDigest"] = canonical_digest(output)
        result["executor"] = {
            "id": executor.revision.executor_id,
            "revision": executor.revision.executor_revision,
            "configurationDigest": executor.revision.configuration_digest,
        }
        result["observationId"] = observed.provider_observation_id
        matches = (
            subset(expected_output, output)
            if comparison == "subset"
            else exact(expected_output, output)
        )
        independent = verify(output) if verify is not None else []
        result["independentChecks"] = independent
        if verification_context is not None:
            result["verificationContext"] = verification_context
        passed = (
            observed.accepted
            and matches
            and all(x["result"] == "SATISFIED" for x in independent)
        )
        result["status"] = "PASSED" if passed else "FAILED"
        result["reasonCode"] = (
            "ACTUAL_OUTPUT_MATCHED" if passed else "ACTUAL_OUTPUT_MISMATCH"
        )
    except (SkillInvocationError, ValueError, TypeError, KeyError) as exc:
        result["reasonCode"] = (
            str(exc)
            if isinstance(exc, SkillInvocationError)
            else "TEST_INPUT_OR_CONTRACT_INVALID"
        )
        result["errors"] = [result["reasonCode"]]
    result["durationMs"] = round((monotonic() - started) * 1000, 3)
    if not persist:
        return {"testResult": result}
    record["savedTests"].append(case)
    record["testResults"].append(result)
    projected = service._replace(
        record, version, "ISOLATED_TEST_RECORDED", actor, result
    )
    projected["testResult"] = result
    return projected


def coverage(record, revision):
    latest = {}
    for result in record.get("testResults", []):
        if (
            result.get("verificationLevel") == "ISOLATED_SYNTHETIC_EXECUTOR"
            and result.get("revisionId") == revision["revisionId"]
            and result.get("revisionDigest") == revision["digest"]
        ):
            latest[(result["operation"], result["caseName"])] = result
    operations = [x["name"] for x in revision["content"].get("operations", [])]
    checks = []
    for name in operations:
        cases = [x for (op, _), x in latest.items() if op == name]
        checks.append(
            {
                "operation": name,
                "passed": bool(cases)
                and all(
                    x["status"] == "PASSED" and x["actualExecution"] for x in cases
                ),
                "cases": [
                    {
                        "name": x["caseName"],
                        "status": x["status"],
                        "resultId": x["resultId"],
                    }
                    for x in cases
                ],
            }
        )
    return {
        "ready": bool(checks) and all(x["passed"] for x in checks),
        "checks": checks,
        "revisionId": revision["revisionId"],
        "revisionDigest": revision["digest"],
        "scope": "ISOLATED_SYNTHETIC_ONLY_NOT_BUSINESS_ACCEPTANCE",
    }


def version_impact(record):
    revisions = record["revisions"]
    current = next(
        x
        for x in revisions
        if x["revisionId"]
        == (record["currentDraftRevisionId"] or record["publishedRevisionId"])
    )
    prior = next(
        (
            x
            for x in reversed(revisions)
            if x["state"] == "PUBLISHED" and x["revisionId"] != current["revisionId"]
        ),
        None,
    )

    def differences(a, b, path=""):
        if isinstance(a, dict) and isinstance(b, dict):
            changes = []
            for key in sorted(set(a) | set(b)):
                if key not in a or key not in b:
                    changes.append(
                        {
                            "path": path + "/" + key,
                            "before": a.get(key),
                            "after": b.get(key),
                            "beforePresent": key in a,
                            "afterPresent": key in b,
                        }
                    )
                else:
                    changes.extend(differences(a[key], b[key], path + "/" + key))
            return changes
        return [] if exact(a, b) else [{"path": path, "before": a, "after": b}]

    return {
        "current": {"revisionId": current["revisionId"], "digest": current["digest"]},
        "previousPublished": {
            "revisionId": prior["revisionId"],
            "digest": prior["digest"],
        }
        if prior
        else None,
        "changes": differences(prior["content"] if prior else {}, current["content"]),
        "testCoverage": coverage(record, current),
        "olderTestsNotCurrent": sum(
            x.get("revisionDigest") != current["digest"]
            or x.get("revisionId") != current["revisionId"]
            for x in record.get("testResults", [])
        ),
        "historyPreserved": True,
        "automaticMigration": False,
        "usageVisibility": "AUTHORIZED_FACTS_ONLY_NOT_COMPLETE_IMPACT",
    }
