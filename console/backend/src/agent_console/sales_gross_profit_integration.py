"""Explicit composition-only same-source candidate gate; no lifecycle effects."""

from copy import deepcopy

from .resource_use_domain import canonical_digest
from .sales_gross_profit_contract import INPUT_SCHEMA, OUTPUT_SCHEMA

SOURCE_DIGEST = "8e3dfeabb34cdcee26d523e8a94b46e93c5c4338c43f33ce81e2b1f1ce925391"
IO_LIMITS = {
    "policyId": "sales-gross-profit-existing-bounds",
    "policyRevision": "2",
    "maxInputBytes": 524288,
    "maxOutputBytes": 262144,
    "maxObjectDepth": 16,
    "maxProperties": 4096,
    "timeoutMs": 5000,
}


def revision():
    # Lazy: producer's schema checking imports the existing resource tester.
    from .sales_gross_profit_skill import SalesGrossProfitSkillExecutor

    return SalesGrossProfitSkillExecutor.revision


def is_v2(identity, version, digest):
    v = revision()
    return (identity, version, digest) == (
        v.executor_id,
        v.executor_revision,
        v.configuration_digest,
    )


def require_source(source):
    if canonical_digest(source) != SOURCE_DIGEST:
        raise ValueError("SALES_V2_CANDIDATE_EXACT_SOURCE_REQUIRED")


def bounded_content(content):
    """Narrow the ab348fc local proposal; never mutate or publish its predecessor."""
    result = deepcopy(content)
    if not result.get("operations"):
        raise ValueError("SALES_V2_CANDIDATE_OPERATION_REQUIRED")
    for op in result["operations"]:
        validate_operation(op)
        op["ioLimits"] = deepcopy(IO_LIMITS)
    return result


def validate_operation(op, *, bounded=False):
    if not is_v2(
        op.get("executorId"),
        op.get("executorRevision"),
        op.get("executorConfigurationDigest"),
    ):
        raise ValueError("SALES_V2_CANDIDATE_EXECUTOR_REQUIRED")
    from .sales_diagnostic_skill import OPERATIONS

    if op.get("name") not in OPERATIONS:
        raise ValueError("SALES_V2_CANDIDATE_OPERATION_REQUIRED")
    expected_in, expected_out = deepcopy(INPUT_SCHEMA), deepcopy(OUTPUT_SCHEMA)
    observed_in = deepcopy(op.get("inputSchema", {}))
    observed_in.pop("description", None)
    expected_out["properties"]["operation"] = {"type": "string", "enum": [op["name"]]}
    if observed_in != expected_in or op.get("outputSchema") != expected_out:
        raise ValueError("SALES_V2_CANDIDATE_EXACT_SCHEMA_REQUIRED")
    if bounded and op.get("ioLimits") != IO_LIMITS:
        raise ValueError("SALES_V2_CANDIDATE_EXISTING_BOUNDS_REQUIRED")
