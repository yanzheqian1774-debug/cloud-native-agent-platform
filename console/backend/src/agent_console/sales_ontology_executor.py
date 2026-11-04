"""Managed read-only Skill consuming exact ontology definitions and bindings."""

from .ontology_domain import OntologyContent, OntologyError
from .ontology_execution import BusinessSemanticsBinding
from .ontology_query import query_sales
from .resource_use_domain import canonical_digest
from .skill_executor import SkillExecutorFailure, SkillExecutorResult
from .skill_invocation_domain import ExecutorRevision

CONFIG = {
    "schema": "ontology-sales-executor.v1",
    "operators": ["SUM", "SUBTRACT"],
    "effect": "READ_ONLY",
    "synthetic": True,
}


class SalesOntologyExecutor:
    revision = ExecutorRevision(
        "ontology-sales-readonly", "1", canonical_digest(CONFIG)
    )

    def invoke(self, invocation_id, operation, inputs, timeout_ms):
        del timeout_ms
        try:
            if (
                operation
                not in {"READ_DATA", "VALIDATE_DATA", "SUMMARIZE", "RENDER_REPORT"}
                or inputs.get("schemaVersion") != "ontology-sales-input.v1"
            ):
                raise OntologyError("ONTOLOGY_SKILL_CONTRACT_INVALID")
            content = OntologyContent.model_validate(inputs["ontologyContent"])
            binding = BusinessSemanticsBinding.model_validate(
                inputs["businessSemantics"]
            )
            source = inputs.get("source")
            if operation != "READ_DATA":
                dependencies = list(inputs.get("dependencies", {}).values())
                if (
                    len(dependencies) != 1
                    or dependencies[0].get("bindingDigest") != binding.digest
                    or dependencies[0].get("binding") != binding.model_dump(mode="json")
                    or (source is not None and source != dependencies[0].get("source"))
                ):
                    raise OntologyError("ONTOLOGY_DEPENDENCY_MISMATCH")
                source = dependencies[0]["source"]
            output = {
                "schemaVersion": "ontology-sales-output.v1",
                "operation": operation,
                "source": source,
                "sourceSnapshot": binding.source.model_dump(mode="json"),
                "binding": binding.model_dump(mode="json"),
                "bindingDigest": binding.digest,
                "reports": [query_sales(content, source, q) for q in binding.queries],
                "synthetic": True,
                "businessConclusion": "UNDETERMINED",
            }
            return SkillExecutorResult(True, output, "ontology-sales:" + invocation_id)
        except (ValueError, KeyError, TypeError) as exc:
            raise SkillExecutorFailure(
                "ONTOLOGY_SALES_INPUT_INVALID", outcome_unknown=False
            ) from exc
