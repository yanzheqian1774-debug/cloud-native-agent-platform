"""Distinct published executor revision; no fallback from live model to fixtures."""

from .resource_use_domain import canonical_digest
from .skill_executor import SkillExecutorFailure, SkillExecutorResult
from .skill_invocation_domain import ExecutorRevision
from .tabular_diagnostic_skill import TabularDiagnosticSkillExecutor

CONFIGURATION = {
    "schemaVersion": "native-diagnostic-loop.v1",
    "base": TabularDiagnosticSkillExecutor.revision.configuration_digest,
    "decision": "GOVERNED_REAL_MODEL",
    "maximumDecisions": 8,
    "operations": ["READ_DATA", "ANALYZE_DATA", "RENDER_REPORT"],
    "tools": ["inspect_data", "check_limits", "inspect_records", "build_report"],
    "effects": "SYNTHETIC_READ_ONLY",
    "finish": "INDEPENDENT_VERIFICATION",
}


class NativeLoopSkillExecutor(TabularDiagnosticSkillExecutor):
    revision = ExecutorRevision(
        "tabular-diagnostic-readonly", "2", canonical_digest(CONFIGURATION)
    )

    def __init__(self, runner=None):
        self.runner = runner

    def invoke(self, invocation_id, operation, inputs, timeout_ms):
        base = super().invoke(invocation_id, operation, inputs, timeout_ms)
        output = base.output
        prior = [
            d["nativeLoop"]
            for d in inputs.get("dependencies", {}).values()
            if "nativeLoop" in d
        ]
        if prior:
            output["nativeLoop"] = prior[-1]
        elif operation in {"ANALYZE_DATA", "RENDER_REPORT"}:
            if self.runner is None:
                raise SkillExecutorFailure(
                    "NATIVE_LOOP_MODEL_NOT_CONFIGURED", outcome_unknown=False
                )
            loop = self.runner(invocation_id, output, timeout_ms)
            if loop["status"] != "SUCCEEDED":
                raise SkillExecutorFailure(
                    "NATIVE_LOOP_" + loop["reason"],
                    outcome_unknown=loop["status"] == "OUTCOME_UNKNOWN",
                )
            output["nativeLoop"] = loop
        return SkillExecutorResult(True, output, "native-loop-skill:" + invocation_id)


VALIDATED_CONFIGURATION = {
    **CONFIGURATION,
    "operations": ["READ_DATA", "VALIDATE_DATA", "ANALYZE_DATA", "RENDER_REPORT"],
}


class NativeValidatedLoopSkillExecutor(NativeLoopSkillExecutor):
    """Compatible successor exposes the existing computation's typed validation."""

    revision = ExecutorRevision(
        "tabular-diagnostic-readonly", "3", canonical_digest(VALIDATED_CONFIGURATION)
    )


def executor_revision(operations):
    revisions = {
        (x["executorId"], x["executorRevision"], x["executorConfigurationDigest"])
        for x in operations
    }
    for revision in (
        TabularDiagnosticSkillExecutor.revision,
        NativeLoopSkillExecutor.revision,
        NativeValidatedLoopSkillExecutor.revision,
    ):
        if revisions == {
            (
                revision.executor_id,
                revision.executor_revision,
                revision.configuration_digest,
            )
        }:
            return revision
    raise ValueError("TABULAR_EXECUTOR_REVISION_MIXED_OR_UNSUPPORTED")
