"""Exact non-tabular executor; live decisions cannot fall back to test computation."""

from agent_runtime.native_loop import digest

from .native_document_tools import validate_source
from .skill_executor import SkillExecutorFailure, SkillExecutorResult
from .skill_invocation_domain import ExecutorRevision

OPERATIONS = ("READ_DATA", "VALIDATE_DATA", "ANALYZE_DATA", "RENDER_REPORT")
CONFIGURATION = {
    "schemaVersion": "native-document-review.v1",
    "operations": OPERATIONS,
    "tools": [
        "list_documents",
        "read_document",
        "search_documents",
        "review_document",
        "build_report",
    ],
    "model": "GOVERNED_REAL_MODEL",
    "interaction": "EXACT_OWNER_QUESTION_180_SECONDS",
    "effects": "SYNTHETIC_READ_ONLY",
    "verification": "EXACT_MARKDOWN_CITATIONS_AND_USER_SCOPE",
}


class DocumentComputationExecutor:
    revision = ExecutorRevision(
        "document-inventory-readonly",
        "1",
        digest({"implementation": "document-inventory.v1"}),
    )

    def invoke(self, invocation_id, operation, inputs, timeout_ms):
        if operation not in OPERATIONS or inputs.get("synthetic") is not True:
            raise SkillExecutorFailure(
                "DOCUMENT_OPERATION_INVALID", outcome_unknown=False
            )
        source = inputs.get("source")
        if operation != "READ_DATA":
            dependencies = list(inputs.get("dependencies", {}).values())
            if not dependencies or any(
                d.get("schemaVersion") != "document-review-output.v1"
                or d.get("sourceSnapshot") != inputs["sourceSnapshot"]
                for d in dependencies
            ):
                raise SkillExecutorFailure(
                    "DOCUMENT_DEPENDENCY_INVALID", outcome_unknown=False
                )
            source = dependencies[0]["source"]
            if any(digest(d["source"]) != digest(source) for d in dependencies):
                raise SkillExecutorFailure(
                    "DOCUMENT_SOURCE_MISMATCH", outcome_unknown=False
                )
        docs = validate_source(source)
        output = {
            "schemaVersion": "document-review-output.v1",
            "synthetic": True,
            "operation": operation,
            "sourceSnapshot": inputs["sourceSnapshot"],
            "source": source,
            "documentCount": len(docs),
            "limitations": [
                "SYNTHETIC_ONLY",
                "SECTION_COMPLETENESS_ONLY",
                "TECHNICAL_CORRECTNESS_UNVERIFIED",
                "NO_DEPLOYMENT_AUTHORITY",
            ],
            "businessConclusion": "UNDETERMINED",
        }
        return SkillExecutorResult(
            True, output, "document-computation:" + invocation_id
        )


class NativeDocumentSkillExecutor(DocumentComputationExecutor):
    revision = ExecutorRevision("native-document-review", "1", digest(CONFIGURATION))

    def __init__(self, runner=None):
        self.runner = runner

    def invoke(self, invocation_id, operation, inputs, timeout_ms):
        output = super().invoke(invocation_id, operation, inputs, timeout_ms).output
        prior = [
            d for d in inputs.get("dependencies", {}).values() if "nativeLoop" in d
        ]
        if prior:
            output.update(
                nativeLoop=prior[-1]["nativeLoop"],
                documentReview=prior[-1]["documentReview"],
            )
        elif operation in {"ANALYZE_DATA", "RENDER_REPORT"}:
            if self.runner is None:
                raise SkillExecutorFailure(
                    "DOCUMENT_MODEL_NOT_CONFIGURED", outcome_unknown=False
                )
            loop = self.runner(invocation_id, output, timeout_ms)
            if loop["status"] != "SUCCEEDED":
                raise SkillExecutorFailure(
                    "DOCUMENT_" + loop["reason"],
                    outcome_unknown=loop["status"] == "OUTCOME_UNKNOWN",
                )
            reports = [
                s["observation"]["output"]
                for s in loop["trace"]
                if s.get("observation", {}).get("tool") == "build_report"
            ]
            if not reports:
                raise SkillExecutorFailure(
                    "DOCUMENT_REPORT_MISSING", outcome_unknown=False
                )
            output.update(nativeLoop=loop, documentReview=reports[-1])
        return SkillExecutorResult(True, output, "native-document:" + invocation_id)


BOUND_EMPLOYEE_CONFIGURATION = {
    **CONFIGURATION,
    "schemaVersion": "native-document-review.v2",
    "decisionContext": "EXACT_AUTHORIZED_BOUND_EMPLOYEE_V1",
}


class NativeEmployeeDocumentSkillExecutor(NativeDocumentSkillExecutor):
    """Explicit successor; original document executor semantics remain pinned."""

    revision = ExecutorRevision(
        "native-document-review", "2", digest(BOUND_EMPLOYEE_CONFIGURATION)
    )


def document_executor_revision(operations):
    revisions = {
        (op["executorId"], op["executorRevision"], op["executorConfigurationDigest"])
        for op in operations
    }
    for executor in (NativeDocumentSkillExecutor, NativeEmployeeDocumentSkillExecutor):
        ref = executor.revision
        if revisions == {
            (ref.executor_id, ref.executor_revision, ref.configuration_digest)
        }:
            return ref
    raise ValueError("DOCUMENT_EXECUTOR_REVISION_MISMATCH")
