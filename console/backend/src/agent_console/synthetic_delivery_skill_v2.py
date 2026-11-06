"""Exact v2 delivery capability with typed classification; v1 stays immutable."""

from .planning_contracts import INPUTS, OUTPUTS
from .resource_use_domain import canonical_digest
from .skill_executor import SkillExecutorResult
from .skill_invocation_domain import ExecutorRevision
from .synthetic_delivery_skill import CONFIGURATION as V1_CONFIGURATION
from .synthetic_delivery_skill import analyze, fail

OPERATIONS = (
    "READ_DATA",
    "VALIDATE_DATA",
    "CLASSIFY_OVERDUE",
    "SUMMARIZE",
    "ANALYZE_DATA",
    "RECOMMEND",
    "RENDER_REPORT",
)
CONFIGURATION = {
    **V1_CONFIGURATION,
    "schemaVersion": "synthetic-delivery-skill.v2",
    "operations": list(OPERATIONS),
    "outputs": {name: OUTPUTS[name] for name in OPERATIONS},
    "dependencyKinds": {name: sorted(INPUTS[name]) for name in OPERATIONS},
    "dependencyProvenance": "EXACT_V2_EXECUTOR_AND_SAME_SOURCE",
}


class SyntheticDeliverySkillExecutorV2:
    revision = ExecutorRevision(
        "synthetic-delivery-readonly", "2", canonical_digest(CONFIGURATION)
    )

    def invoke(self, invocation_id, operation, inputs, timeout_ms):
        del timeout_ms
        if (
            operation not in OPERATIONS
            or not isinstance(inputs, dict)
            or inputs.get("schemaVersion") != "synthetic-delivery-input.v1"
            or inputs.get("synthetic") is not True
            or not isinstance(inputs.get("sourceSnapshot"), dict)
            or not isinstance(inputs.get("dependencies"), dict)
        ):
            fail("DELIVERY_V2_BOUNDARY_REQUIRED")
        dependencies = list(inputs["dependencies"].values())
        if operation == "READ_DATA":
            if dependencies:
                fail("DELIVERY_V2_READ_DEPENDENCY_FORBIDDEN")
            source = inputs.get("source")
        else:
            if not dependencies:
                fail("DELIVERY_V2_TYPED_DEPENDENCY_REQUIRED")
            for item in dependencies:
                if (
                    not isinstance(item, dict)
                    or item.get("schemaVersion") != "synthetic-delivery-output.v1"
                    or item.get("synthetic") is not True
                    or item.get("sourceSnapshot") != inputs["sourceSnapshot"]
                    or item.get("executorRevision") != self.revision.executor_revision
                    or item.get("executorConfigurationDigest")
                    != self.revision.configuration_digest
                    or item.get("operation") not in OPERATIONS
                    or item.get("outputKind") != OUTPUTS[item["operation"]]
                    or item["outputKind"] not in INPUTS[operation]
                ):
                    fail("DELIVERY_V2_TYPED_DEPENDENCY_MISMATCH")
            source = dependencies[0].get("source")
            if any(
                item.get("source") != source
                or item.get("sourceDigest") != canonical_digest(source)
                for item in dependencies
            ):
                fail("DELIVERY_V2_SOURCE_CONFLICT")
        analysis = analyze(source)
        output = {
            "schemaVersion": "synthetic-delivery-output.v1",
            "synthetic": True,
            "operation": operation,
            "outputKind": OUTPUTS[operation],
            "executorRevision": self.revision.executor_revision,
            "executorConfigurationDigest": self.revision.configuration_digest,
            "sourceSnapshot": inputs["sourceSnapshot"],
            "sourceDigest": canonical_digest(source),
            "source": source,
            "limitations": [
                "SYNTHETIC_ONLY",
                "DEMO_RANKING_NOT_BUSINESS_LOSS",
                "REAL_BUSINESS_OUTCOME_UNPROVEN",
            ],
            **analysis,
        }
        if operation == "RENDER_REPORT":
            output.update(
                title="供应商交付及时性 · 合成订单分析",
                businessConclusion="UNDETERMINED",
            )
        return SkillExecutorResult(
            True, output, "synthetic-delivery-v2:" + invocation_id
        )


def resource_content():
    """A new draft payload; never modifies a v1 resource or its published digest."""
    from copy import deepcopy

    from .delivery_resource_bundle import resource_content as v1_content
    from .skill_mcp_schemas import ResourceContent

    bundle = v1_content()
    skill = bundle["skill"]
    template = skill["operations"][0]
    operations = []
    for name in OPERATIONS:
        op = deepcopy(template)
        op.update(
            name=name,
            executorRevision="2",
            executorConfigurationDigest=SyntheticDeliverySkillExecutorV2.revision.configuration_digest,
        )
        output = op["outputSchema"]
        output["properties"]["operation"]["enum"] = [name]
        for key, value in (
            ("outputKind", OUTPUTS[name]),
            ("executorRevision", "2"),
            (
                "executorConfigurationDigest",
                SyntheticDeliverySkillExecutorV2.revision.configuration_digest,
            ),
        ):
            output["properties"][key] = {"type": "string", "enum": [value]}
            output["required"].append(key)
        operations.append(op)
    skill.update(capabilities=list(OPERATIONS), operations=operations)
    bundle["skill"] = ResourceContent.model_validate(skill).model_dump(
        mode="json", exclude_none=True
    )
    bundle["agent"]["capabilities"] = list(OPERATIONS)
    return bundle
