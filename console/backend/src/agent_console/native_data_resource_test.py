"""Resource-test computation only; never a Native execution or model decision."""

from agent_runtime.native_loop import snapshot

from .native_data_skill import NativeDataSkillExecutor
from .resource_use_domain import canonical_digest
from .skill_executor import SkillExecutorResult
from .skill_invocation_domain import ExecutorRevision


class NativeDataResourceTest:
    def __init__(self, adapter):
        self.adapter = adapter
        self.revision = ExecutorRevision(
            adapter.adapter_id + "-resource-computation",
            "1",
            canonical_digest(
                {
                    "adapter": adapter.descriptor(),
                    "mode": "RESOURCE_TEST_NO_MODEL_NO_NATIVE_DECISION",
                }
            ),
        )

    def invoke(self, identity, operation, inputs, timeout):
        # Reuse exact source/dependency checks without invoking ANALYZE or a model.
        value = (
            NativeDataSkillExecutor(self.adapter)
            .invoke(
                identity,
                "READ_DATA" if operation == "READ_DATA" else "VALIDATE_DATA",
                inputs,
                timeout,
            )
            .output
        )
        value["operation"] = operation
        if operation == "RENDER_REPORT":
            library = self.adapter.tools(value["source"], value["sourceSnapshot"])
            value["resourceTestReport"] = snapshot(library.invoke("build_report", {}))
        return SkillExecutorResult(True, value, "resource-computation:" + identity)
