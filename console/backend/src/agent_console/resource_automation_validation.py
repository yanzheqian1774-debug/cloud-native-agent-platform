"""Technical checks before policy publication; never infer readiness from approval."""

import json

from .authority_contracts import AuthorityError
from .prepared_native_composition import POLICY
from .resource_automation_policy import source_digest
from .sales_diagnostic_skill import SalesDiagnosticSkillExecutor
from .skill_executor import SkillExecutorRegistry
from .skill_invocation_domain import ExecutorRevision
from .synthetic_cost_skill import SyntheticCostSkillExecutor
from .synthetic_delivery_skill import SyntheticDeliverySkillExecutor
from .synthetic_delivery_skill_v2 import SyntheticDeliverySkillExecutorV2

EXECUTORS = SkillExecutorRegistry(
    (
        SalesDiagnosticSkillExecutor(),
        SyntheticDeliverySkillExecutor(),
        SyntheticDeliverySkillExecutorV2(),
        SyntheticCostSkillExecutor(),
    )
)
SCHEMAS = {
    SalesDiagnosticSkillExecutor.revision.executor_id: "sales-diagnostic",
    SyntheticDeliverySkillExecutor.revision.executor_id: "synthetic-delivery",
    SyntheticCostSkillExecutor.revision.executor_id: "synthetic-cost",
}


def validate(kind, content, work, *, expected_source_schema=None):
    if kind == "knowledge":
        digest = source_digest(content)
        if digest not in work.sourceContentDigests:
            raise AuthorityError("RESOURCE_SOURCE_OUTSIDE_WORK_SCOPE")
        return {
            "sourceContentDigest": digest,
            "sourceSchema": json.loads(content["documents"][0]["chunks"][0]["content"])[
                "schemaVersion"
            ],
            "check": "EXACT_SOURCE_SCOPE_AND_SCHEMA",
        }
    if kind == "skill":
        operations = content.get("operations", [])
        if not operations:
            raise AuthorityError("RESOURCE_OPERATION_CONTRACT_REQUIRED")
        for op in operations:
            revision = ExecutorRevision(
                op["executorId"],
                op["executorRevision"],
                op["executorConfigurationDigest"],
            )
            EXECUTORS.resolve(revision)
            if (
                revision.executor_id
                == SyntheticDeliverySkillExecutor.revision.executor_id
            ):
                from .synthetic_delivery_skill import OPERATIONS as V1_OPERATIONS
                from .synthetic_delivery_skill_v2 import OPERATIONS as V2_OPERATIONS

                allowed = (
                    V2_OPERATIONS
                    if revision.executor_revision == "2"
                    else V1_OPERATIONS
                )
                if op["name"] not in allowed:
                    raise AuthorityError("RESOURCE_EXECUTOR_OPERATION_UNAVAILABLE")
                if revision.executor_revision == "2":
                    from .planning_contracts import OUTPUTS

                    output = op.get("outputSchema", {})
                    for key, value in (
                        ("operation", op["name"]),
                        ("outputKind", OUTPUTS[op["name"]]),
                        ("executorRevision", "2"),
                        ("executorConfigurationDigest", revision.configuration_digest),
                    ):
                        if key not in output.get("required", []) or output.get(
                            "properties", {}
                        ).get(key, {}).get("enum") != [value]:
                            raise AuthorityError(
                                "RESOURCE_EXECUTOR_TYPED_SCHEMA_MISMATCH"
                            )
            prefix = SCHEMAS[revision.executor_id]
            if (
                expected_source_schema
                and expected_source_schema != prefix + "-source.v1"
            ):
                raise AuthorityError("RESOURCE_EXECUTOR_SOURCE_MISMATCH")
            if op.get("sideEffectClass") != "READ_ONLY" or op.get(
                "sideEffectPolicy"
            ) != {
                "policyId": POLICY.policy_id,
                "policyRevision": POLICY.policy_revision,
                "policyDigest": POLICY.policy_digest,
            }:
                raise AuthorityError("RESOURCE_SIDE_EFFECT_NOT_ALLOWED")
            for key, suffix in (("inputSchema", "input"), ("outputSchema", "output")):
                if op.get(key, {}).get("properties", {}).get("schemaVersion", {}).get(
                    "enum"
                ) != [prefix + "-" + suffix + ".v1"]:
                    raise AuthorityError("RESOURCE_EXECUTOR_SCHEMA_MISMATCH")
        return {
            "check": "REGISTERED_READ_ONLY_EXECUTOR_AND_IO",
            "operations": [op["name"] for op in operations],
        }
    if kind == "mcp":
        # Metadata READ has its own exact target. Endpoint credentials/tool/runtime
        # evidence are not implied by metadata publication or a Skill grant.
        raise AuthorityError("MCP_CREDENTIAL_AND_TOOL_VALIDATION_REQUIRED")
    if kind == "runtime":
        if content.get("provider") != "NATIVE_KUBERNETES":
            raise AuthorityError("RESOURCE_RUNTIME_PROVIDER_UNSUPPORTED")
        return {"check": "NATIVE_PROFILE_REQUIRES_LIVE_NAMESPACE_PROBE"}
    if kind == "agent":
        if set(content.get("runtimes", [])) != {"NATIVE_KUBERNETES"}:
            raise AuthorityError("RESOURCE_AGENT_RUNTIME_UNSUPPORTED")
        return {"check": "AGENT_BINDINGS_VALIDATED_BY_OWNER"}
    raise AuthorityError("RESOURCE_KIND_UNSUPPORTED")
