"""Computation test receipts never claim a Native model decision."""

import pytest
from agent_console.automatic_skill_testing import independent
from agent_console.delivery_resource_bundle import source_document
from agent_console.native_data_adapters import ADAPTERS
from agent_console.native_data_resource_bundle import resource_content
from agent_console.native_data_resource_test import NativeDataResourceTest
from agent_console.native_data_skill import NativeDataSkillExecutor
from agent_console.skill_executor import SkillExecutorFailure
from agent_console.skill_resource_testing import schema_check
from test_native_diagnostic_tools import REFERENCE


def test_exact_resource_computation_contract_and_independent_report():
    adapter = ADAPTERS[1]
    source = source_document()
    bundle = resource_content(source, adapter.descriptor())
    executor = NativeDataResourceTest(adapter)
    assert executor.revision != NativeDataSkillExecutor(adapter).revision
    read = None
    for operation in bundle["skill"]["operations"]:
        inputs = dict(
            schemaVersion="native-data-input.v1",
            synthetic=True,
            sourceSnapshot=REFERENCE,
            source=source,
            dependencies={"read": read} if read else {},
        )
        schema_check(inputs, operation["inputSchema"], "INPUT")
        output = executor.invoke("test", operation["name"], inputs, 1000).output
        schema_check(output, operation["outputSchema"], "OUTPUT")
        assert "nativeLoop" not in output
        if operation["name"] == "READ_DATA":
            read = output
        if operation["name"] == "RENDER_REPORT":
            assert all(
                v["result"] == "SATISFIED"
                for v in independent(source, output["resourceTestReport"], REFERENCE)
            )
    with pytest.raises(SkillExecutorFailure, match="MODEL_NOT_CONFIGURED"):
        NativeDataSkillExecutor(adapter).invoke("real", "ANALYZE_DATA", inputs, 1000)


def test_native_report_requires_independent_original_rows_not_success_label():
    from copy import deepcopy

    from agent_runtime.native_loop import NativeLoop
    from test_native_delivery_tools import Decisions
    from test_native_diagnostic_tools import Journal

    adapter = ADAPTERS[1]
    source = source_document()
    ports = Decisions(source)
    loop = NativeLoop(ports.library.tools, ports, Journal()).run(
        "controlled-executor", "Check source", ["Original evidence"], {}
    )
    executor = NativeDataSkillExecutor(adapter, lambda *_: loop)
    inputs = dict(
        schemaVersion="native-data-input.v1",
        synthetic=True,
        sourceSnapshot=REFERENCE,
        source=source,
        dependencies={},
    )
    read = executor.invoke("read", "READ_DATA", inputs, 1000).output
    inputs["dependencies"] = {"read": read}
    result = executor.invoke("analysis", "ANALYZE_DATA", inputs, 1000).output
    assert result["nativeReportVerification"]["sourceSnapshot"] == REFERENCE
    assert result["nativeReportVerification"]["businessAcceptance"] is False
    for forged in [dict(status="SUCCEEDED", trace=[], answer={}), deepcopy(loop)]:
        if forged["trace"]:
            forged["trace"] = [
                s
                for s in forged["trace"]
                if s.get("observation", {}).get("tool") != "inspect_rows"
            ]
        invalid = NativeDataSkillExecutor(adapter, lambda *_, saved=forged: saved)
        with pytest.raises(SkillExecutorFailure, match="REPORT_NOT_VERIFIED"):
            invalid.invoke("forged", "ANALYZE_DATA", inputs, 1000)
