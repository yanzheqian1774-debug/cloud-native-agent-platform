"""Exact-source actual verification in the existing D11 preparation transaction."""

import json

from .authority_contracts import AuthorityError
from .resource_use_domain import canonical_digest
from .skill_resource_testing import coverage, run
from .workbench_prepared_resources import bind_service


def independent(source, report, reference):
    schema = source.get("schemaVersion")
    if schema == "sales-diagnostic-source.v1":
        from .sales_evaluation import CHECKS, evaluate_sales

        return [
            {"check": check, "result": result, "reason": reason}
            for check in CHECKS
            for result, reason in [evaluate_sales(check, source, report, reference)]
        ]
    if schema == "synthetic-delivery-source.v1":
        from .delivery_evaluation import CHECKS, evaluate

        return [
            {"check": check, "result": result, "reason": reason}
            for check in CHECKS
            for result, reason in [
                evaluate(
                    {
                        "evaluator_type": "SYNTHETIC_DELIVERY",
                        "evaluator_version": "1",
                        "criterion_type": "DETERMINISTIC_BOOLEAN",
                        "measurement": {"expected": True},
                        "applicability": {
                            "check": check,
                            "sourceContentDigest": canonical_digest(source),
                        },
                    },
                    source,
                    report,
                    reference,
                )
            ]
        ]
    raise AuthorityError("RESOURCE_INDEPENDENT_EVALUATOR_UNAVAILABLE")


def verify_skill(call, service, ref, source_ref, source_revision, proof, *, persist):
    raw = source_revision["content"]["documents"][0]["chunks"][0]["content"]
    source = json.loads(raw)
    schema = source.get("schemaVersion")
    prefix = {
        "sales-diagnostic-source.v1": "sales-diagnostic",
        "synthetic-delivery-source.v1": "synthetic-delivery",
    }.get(schema)
    if prefix is None:
        raise AuthorityError("RESOURCE_INDEPENDENT_EVALUATOR_UNAVAILABLE")
    service = bind_service(service, call.connection)
    scope = service.scope(
        call.context.scope.tenant_id, call.context.scope.security_domain
    )
    record = service.repository.get(scope, "skill", ref.resource_id)
    revision = next(
        r for r in record["revisions"] if r["revisionId"] == ref.revision_id
    )
    names = [x["name"] for x in revision["content"].get("operations", [])]
    if not {"READ_DATA", "RENDER_REPORT"}.issubset(names):
        raise AuthorityError("RESOURCE_TEST_REPORT_OPERATION_REQUIRED")
    ordered = [
        "READ_DATA",
        *sorted(set(names) - {"READ_DATA", "RENDER_REPORT"}),
        "RENDER_REPORT",
    ]
    reference = source_ref.model_dump(mode="json")
    read = None
    tests = []
    for operation in ordered:
        record = service.repository.get(scope, "skill", ref.resource_id)
        inputs = {
            "schemaVersion": prefix + "-input.v1",
            "synthetic": True,
            "sourceSnapshot": reference,
            "source": source,
            "dependencies": {"read": read} if read else {},
        }
        result = run(
            service,
            scope,
            ref.resource_id,
            proof.issuer,
            record["aggregateVersion"],
            operation=operation,
            name="自动核验·" + operation,
            inputs=inputs,
            expected_output={
                "schemaVersion": prefix + "-output.v1",
                "synthetic": True,
                "operation": operation,
                "sourceSnapshot": reference,
                **(
                    {"businessConclusion": "UNDETERMINED"}
                    if operation == "RENDER_REPORT"
                    else {}
                ),
            },
            comparison="subset",
            revision_id=ref.revision_id,
            persist=persist,
            verify=(lambda output: independent(source, output, reference))
            if operation == "RENDER_REPORT"
            else None,
            verification_context={
                "source": reference,
                "sourceContentDigest": canonical_digest(source),
                "policyDecisionId": proof.decision_id,
            },
        )["testResult"]
        tests.append(
            {
                k: result.get(k)
                for k in [
                    "resultId",
                    "operation",
                    "revisionId",
                    "revisionDigest",
                    "status",
                    "actualExecution",
                    "reasonCode",
                    "inputDigest",
                    "outputDigest",
                    "independentChecks",
                    "verificationContext",
                ]
            }
        )
        if result["status"] != "PASSED" or not result["actualExecution"]:
            return {
                "check": "EXACT_SOURCE_ACTUAL_TESTS",
                "passed": False,
                "tests": tests,
                "reason": result["reasonCode"],
                "source": reference,
                "ownerTestRecordsWritten": persist,
            }
        if operation == "READ_DATA":
            read = result["actual"]
    record = service.repository.get(scope, "skill", ref.resource_id)
    if persist and not coverage(record, revision)["ready"]:
        return {
            "check": "EXACT_SOURCE_ACTUAL_TESTS",
            "passed": False,
            "tests": tests,
            "reason": "RESOURCE_CURRENT_TEST_COVERAGE_FAILED",
            "ownerTestRecordsWritten": True,
        }
    return {
        "check": "EXACT_SOURCE_ACTUAL_TESTS",
        "passed": True,
        "operations": names,
        "tests": tests,
        "source": reference,
        "independentChecks": tests[-1]["independentChecks"],
        "ownerTestRecordsWritten": persist,
        "businessRunStarted": False,
        "modelCalls": 0,
    }
