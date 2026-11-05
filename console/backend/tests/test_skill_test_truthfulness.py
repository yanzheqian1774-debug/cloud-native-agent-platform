"""An expected value is not independent execution evidence."""

from agent_console.skill_mcp_repository import InMemorySkillMcpRepository, ResourceScope
from agent_console.skill_mcp_service import SkillMcpService


def test_saved_test_never_copies_expected_into_actual_or_reports_execution_pass():
    service = SkillMcpService(InMemorySkillMcpRepository())
    scope = ResourceScope("test", "isolated")
    resource = service.create(
        scope,
        "skill",
        "human:test",
        "真实判定边界",
        {
            "description": "声明检查",
            "capabilities": ["lookup"],
            "instructions": "read only",
            "inputSchema": {"required": ["id"]},
        },
    )
    identity = resource["resourceId"]
    saved = service.save_test(
        scope,
        identity,
        "human:test",
        1,
        "任意伪造预期",
        {"id": "1"},
        {"impossible": "expected is not actual"},
    )["resource"]
    result = service.run_test(
        scope,
        identity,
        "human:test",
        saved["aggregateVersion"],
        saved["savedTests"][-1]["testId"],
    )["testResult"]
    assert (
        result["status"] == "NOT_EXECUTED"
        and result["actual"] is None
        and result["actualExecution"] is False
    )
    assert result["reasonCode"] == "SKILL_TEST_EXECUTOR_NOT_CONFIGURED"
    saved = service.save_test(
        scope, identity, "human:test", 3, "缺少输入", {}, {"value": "fake"}
    )["resource"]
    failed = service.run_test(
        scope,
        identity,
        "human:test",
        saved["aggregateVersion"],
        saved["savedTests"][-1]["testId"],
    )["testResult"]
    assert failed["status"] == "FAILED" and failed["actual"] is None
    assert (
        failed["errors"] == ["required:id"]
        and failed["verificationLevel"] == "INPUT_CONTRACT_ONLY"
    )
