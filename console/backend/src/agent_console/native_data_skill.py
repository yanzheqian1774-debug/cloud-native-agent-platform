"""Explicit registry-backed Native successor. No fallback to a deterministic result."""

from agent_runtime.native_loop import digest, snapshot

from .native_data_adapters import ADAPTERS, resolve
from .resource_use_domain import canonical_digest
from .skill_executor import SkillExecutorFailure, SkillExecutorResult
from .skill_invocation_domain import ExecutorRevision


def fail(reason):
    raise SkillExecutorFailure(reason, outcome_unknown=False)


class NativeDataSkillExecutor:
    def __init__(self, adapter, runner=None):
        if adapter not in ADAPTERS:
            raise ValueError("NATIVE_DATA_ADAPTER_NOT_REGISTERED")
        self.adapter, self.runner = adapter, runner
        self.revision = ExecutorRevision(
            adapter.adapter_id,
            "1",
            canonical_digest(
                {
                    "schemaVersion": "native-data-skill.v1",
                    "adapter": adapter.descriptor(),
                    "model": "ORIGINAL_GOVERNED_NATIVE_LOOP",
                    "effects": "READ_ONLY",
                    "finish": "EXACT_ADAPTER_INDEPENDENT_VERIFICATION",
                    "operations": adapter.operations,
                }
            ),
        )

    def invoke(self, invocation_id, operation, inputs, timeout_ms):
        if (
            operation not in self.adapter.operations
            or not isinstance(inputs, dict)
            or inputs.get("schemaVersion") != "native-data-input.v1"
            or inputs.get("synthetic") is not True
        ):
            fail("NATIVE_DATA_INPUT_INVALID")
        source = inputs.get("source")
        reference = inputs.get("sourceSnapshot")
        if not isinstance(reference, dict):
            fail("NATIVE_DATA_SOURCE_REFERENCE_REQUIRED")
        dependencies = inputs.get("dependencies", {})
        if operation != "READ_DATA":
            if not isinstance(dependencies, dict) or not dependencies:
                fail("NATIVE_DATA_DEPENDENCIES_REQUIRED")
            outputs = list(dependencies.values())
            if not all(isinstance(value, dict) for value in outputs):
                fail("NATIVE_DATA_DEPENDENCIES_CHANGED")
            source = outputs[0].get("source")
            if any(
                not isinstance(v, dict)
                or v.get("schemaVersion") != "native-data-output.v1"
                or v.get("sourceSnapshot") != reference
                or v.get("source") != source
                or v.get("sourceDigest") != canonical_digest(source)
                or v.get("adapter") != self.adapter.descriptor()
                for v in outputs
            ):
                fail("NATIVE_DATA_DEPENDENCIES_CHANGED")
        self.adapter.validate(source)
        output = {
            "schemaVersion": "native-data-output.v1",
            "operation": operation,
            "synthetic": True,
            "source": snapshot(source),
            "sourceSnapshot": snapshot(reference),
            "sourceDigest": canonical_digest(source),
            "adapter": self.adapter.descriptor(),
            "businessConclusion": "UNDETERMINED",
            "externalWrites": False,
            "limitations": ["Bounded source evidence; not business acceptance."],
        }
        if operation in {"ANALYZE_DATA", "RENDER_REPORT"}:
            prior = [
                v["nativeLoop"]
                for v in dependencies.values()
                if isinstance(v, dict) and "nativeLoop" in v
            ]
            if prior:
                if any(v != prior[0] for v in prior):
                    fail("NATIVE_DATA_LOOP_DEPENDENCIES_CONFLICT")
                loop = prior[0]
            else:
                if self.runner is None:
                    fail("NATIVE_DATA_MODEL_NOT_CONFIGURED")
                loop = self.runner(invocation_id, output, timeout_ms)
            if loop.get("status") != "SUCCEEDED":
                raise SkillExecutorFailure(
                    "NATIVE_DATA_LOOP_NOT_VERIFIED",
                    outcome_unknown=loop.get("status") == "OUTCOME_UNKNOWN",
                )
            # The runner and journal remain the original governed Native owner.
            trace = loop.get("trace")
            if not isinstance(trace, list) or not trace:
                fail("NATIVE_DATA_REPORT_NOT_VERIFIED")
            observations = [
                s["observation"]
                for s in trace
                if isinstance(s, dict) and isinstance(s.get("observation"), dict)
            ]
            library = self.adapter.tools(source, reference)
            expected_report = library.invoke("build_report", {})
            reports = [
                o.get("output")
                for o in observations
                if o.get("kind") == "TOOL_RESULT" and o.get("tool") == "build_report"
            ]
            if (
                not reports
                or reports[-1] != expected_report
                or not library.verify(
                    {"observations": observations}, loop.get("answer")
                )["passed"]
                or trace[-1].get("decision", {}).get("action") != "FINISH"
                or trace[-1].get("verification", {}).get("passed") is not True
            ):
                fail("NATIVE_DATA_REPORT_NOT_VERIFIED")
            output["nativeLoop"] = snapshot(loop)
            output["nativeReport"] = snapshot(expected_report)
            verification = {
                "schemaVersion": "native-data-report-verification.v1",
                "adapterDigest": self.adapter.configuration_digest,
                "sourceSnapshot": snapshot(reference),
                "sourceDigest": canonical_digest(source),
                "reportDigest": expected_report["reportDigest"],
                "businessAcceptance": False,
            }
            output["nativeReportVerification"] = {
                **verification,
                "digest": digest(verification),
            }
        return SkillExecutorResult(True, output, "native-data:" + invocation_id)


def executors(runner=None):
    return tuple(NativeDataSkillExecutor(adapter, runner) for adapter in ADAPTERS)


def exact_executor(revision):
    matches = [e for e in executors() if e.revision == revision]
    if len(matches) != 1:
        raise ValueError("NATIVE_DATA_EXECUTOR_NOT_REGISTERED")
    resolve(matches[0].adapter.descriptor())
    return matches[0]


EXECUTOR_IDS = frozenset(adapter.adapter_id for adapter in ADAPTERS)

SYNTHETIC_BOUNDARY = (
    "仅使用精确已授权的合成快照及注册只读工具核对证据；"  # noqa: RUF001
    "保留限制，不代表业务接受或外部操作授权。"  # noqa: RUF001
)
