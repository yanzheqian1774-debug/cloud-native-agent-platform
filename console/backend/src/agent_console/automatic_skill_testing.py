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
        from .delivery_evaluation import CHECKS, checks

        # This is resource-level isolated computation, not a formal criterion
        # claiming NATIVE_EXECUTION_ARTIFACT or published-source evidence kinds.
        observed = checks(source, report, reference)
        return [
            {
                "check": check,
                "result": "SATISFIED" if observed[check] else "NOT_SATISFIED",
                "reason": "ISOLATED_DELIVERY_COMPUTATION_MATCHED"
                if observed[check]
                else "ISOLATED_DELIVERY_COMPUTATION_MISMATCH",
            }
            for check in CHECKS
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
    from .synthetic_delivery_skill_v2 import (
        OPERATIONS as DELIVERY_V2_OPERATIONS,
    )
    from .synthetic_delivery_skill_v2 import SyntheticDeliverySkillExecutorV2

    v2 = SyntheticDeliverySkillExecutorV2.revision
    typed_delivery = all(
        (op["executorId"], op["executorRevision"], op["executorConfigurationDigest"])
        == (v2.executor_id, v2.executor_revision, v2.configuration_digest)
        for op in revision["content"].get("operations", [])
    )
    if not {"READ_DATA", "RENDER_REPORT"}.issubset(names):
        raise AuthorityError("RESOURCE_TEST_REPORT_OPERATION_REQUIRED")
    ordered = [
        "READ_DATA",
        *sorted(set(names) - {"READ_DATA", "RENDER_REPORT"}),
        "RENDER_REPORT",
    ]
    if typed_delivery:
        ordered = [name for name in DELIVERY_V2_OPERATIONS if name in names]
    reference = source_ref.model_dump(mode="json")
    read = None
    outputs = {}
    tests = []
    for operation in ordered:
        record = service.repository.get(scope, "skill", ref.resource_id)
        dependencies = {"read": read} if read else {}
        if typed_delivery:
            from .planning_contracts import INPUTS

            dependencies = {
                name: output
                for name, output in outputs.items()
                if output["outputKind"] in INPUTS[operation]
            }
        inputs = {
            "schemaVersion": prefix + "-input.v1",
            "synthetic": True,
            "sourceSnapshot": reference,
            "source": source,
            "dependencies": dependencies,
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
        outputs[operation] = result["actual"]
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
