"""Actual registered computation; injected authorization ports, no model/transport."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.skill_mcp_repository import InMemorySkillMcpRepository
from agent_console.skill_mcp_service import SkillMcpService
from agent_console.tool_contract_testing import ToolContractTesting
from agent_console.tool_lifecycle import ToolCommand
from test_skill_mcp_service import publish
from test_skill_resource_testing import fixture_content


@pytest.fixture
def configured(tmp_path):
    content, inputs = fixture_content()
    service = SkillMcpService(InMemorySkillMcpRepository())
    scope = service.scope("tool-tests", "synthetic")
    row = publish(service, scope, "skill", "registered computation", content)
    revision = next(
        x for x in row["revisions"] if x["revisionId"] == row["publishedRevisionId"]
    )
    now = datetime.now(UTC)
    current = {
        "toolId": "tool:test",
        "revisionId": "tool-revision:test",
        "digest": "a" * 64,
        "record": {
            "operation": {
                "source": {"kind": "PLUGIN", "id": "registered-fixture"},
                "inputSchema": {"type": "object"},
                "outputSchema": {"type": "object"},
            }
        },
    }
    binding = {
        "namespace": scope.namespace,
        "securityDomain": scope.security_domain,
        "subject": "human:tool-tester",
        "toolId": current["toolId"],
        "revisionId": current["revisionId"],
        "digest": current["digest"],
        "skillId": row["resourceId"],
        "skillRevisionId": revision["revisionId"],
        "skillDigest": revision["digest"],
        "operation": "READ_DATA",
        "expiresAt": (now + timedelta(minutes=5)).isoformat(),
    }
    path = tmp_path / "exact-mapping.json"
    path.write_text(
        json.dumps(
            {
                "schemaVersion": "tool-contract-test-policy.v1",
                "enabled": True,
                "bindings": [binding],
            }
        )
    )
    path.chmod(0o600)
    checked = []

    class Authority:
        denied = None

        def require(self, p, owner, action, target):
            checked.append((owner, action, target))
            if self.denied == action:
                raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    manager = NS(
        scope=lambda *_: None,
        owned=lambda *_: True,
        grants=NS(clock=lambda: now),
        services={"skill": service},
    )
    call = NS(
        context=NS(
            principal_id="human:tool-tester",
            scope=NS(tenant_id=scope.namespace, security_domain=scope.security_domain),
        ),
        authority=Authority(),
        connection=None,
    )
    return ToolContractTesting(path, manager), call, current, inputs, checked, path


def case(inputs, expected):
    return ToolCommand(
        action="test",
        commandId="test:registered",
        expectedVersion=1,
        revisionId="tool-revision:test",
        digest="a" * 64,
        testName="independent expected",
        input=inputs,
        expectedOutput=expected,
        comparison="subset",
    )


def test_registered_real_output_differs_from_expected_and_can_pass_independent_check(
    configured,
):
    runner, call, current, inputs, checked, _path = configured
    failed = runner.run(call, current, case(inputs, {"impossible": "not actual"}))
    assert failed["actualExecution"] and failed["status"] == "FAILED"
    assert "impossible" not in failed["actual"]
    # Independent constant from the fixture contract, never copied actual->expected.
    passed = runner.run(
        call,
        current,
        case(
            inputs, {"schemaVersion": "sales-diagnostic-output.v1", "synthetic": True}
        ),
    )
    assert passed["status"] == "PASSED" and passed["actualExecution"]
    assert passed["toolSourceInvoked"] is False
    assert passed["actual"]["schemaVersion"] == "sales-diagnostic-output.v1"
    assert (
        passed["observationId"].startswith("sales-diagnostic:")
        and passed["modelCalls"] == 0
    )
    assert {x[1] for x in checked} == {"MANAGE_RESOURCE", "READ_RESOURCE"}
    assert passed["verificationLevel"] == "ISOLATED_REGISTERED_SKILL_COMPUTATION"


def test_exact_mapping_expiry_change_source_and_current_authority(configured):
    runner, call, current, inputs, _checked, path = configured
    current["digest"] = "b" * 64
    assert runner.run(call, current, case(inputs, {}))["status"] == "NOT_EXECUTED"
    current["digest"] = "a" * 64
    current["record"]["operation"]["source"]["kind"] = "API"
    result = runner.run(call, current, case(inputs, {}))
    assert result["actual"] is None and not result["actualExecution"]
    current["record"]["operation"]["source"]["kind"] = "PLUGIN"
    call.authority.denied = "MANAGE_RESOURCE"
    with pytest.raises(AuthorityError):
        runner.run(call, current, case(inputs, {}))
    call.authority.denied = None
    path.write_text("{}")
    assert (
        runner.run(call, current, case(inputs, {}))["reasonCode"]
        == "TOOL_TEST_POLICY_CHANGED_OR_DISABLED"
    )


@pytest.mark.parametrize(
    "failure", ["expired", "subject", "scope", "skill_digest", "read_revoked"]
)
def test_exact_expiry_scope_and_read_revocation_fail_closed(configured, failure):
    runner, call, current, inputs, _checked, path = configured
    if failure == "read_revoked":
        call.authority.denied = "READ_RESOURCE"
        with pytest.raises(AuthorityError):
            runner.run(call, current, case(inputs, {"synthetic": True}))
        return
    value = json.loads(path.read_bytes())
    binding = value["bindings"][0]
    if failure == "expired":
        binding["expiresAt"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    elif failure == "subject":
        binding["subject"] = "human:other"
    elif failure == "scope":
        binding["namespace"] = "other"
    elif failure == "skill_digest":
        binding["skillDigest"] = "0" * 64
    path.write_text(json.dumps(value))
    runner = ToolContractTesting(path, runner.manager)
    result = runner.run(call, current, case(inputs, {"synthetic": True}))
    assert result["status"] == "NOT_EXECUTED" and result["actual"] is None


def test_empty_expectation_is_definite_not_executed_not_unknown(configured):
    runner, call, current, inputs, _checked, _path = configured
    result = runner.run(call, current, case(inputs, {}))
    assert result["status"] == "NOT_EXECUTED"
    assert result["reasonCode"] == "TOOL_TEST_EXPECTATION_REQUIRED"
    assert result["actual"] is None and not result["actualExecution"]


def test_missing_tool_candidate_is_definite_bound_resource_failure(monkeypatch):
    from agent_console.digital_employee_definition import (
        CompositionMember,
        EmployeeDefinitionError,
        MemberKind,
    )
    from agent_console.digital_employee_definition_postgres import (
        PostgresEmployeeDefinitionRepository as Employee,
    )
    from agent_console.execution_domain import ScopeIdentity
    from agent_console.tool_definition_postgres import (
        PostgresToolDefinitionRepository as Tool,
    )
    from agent_console.tool_definition_postgres import ToolStorageError

    def missing(*_args, **_kw):
        raise ToolStorageError("TOOL_NOT_FOUND")

    monkeypatch.setattr(Tool, "read", missing)
    revision = NS(
        scope=ScopeIdentity("tool-tests", "synthetic"),
        members=[
            CompositionMember(MemberKind.TOOL, "tool:missing", "rev:missing", "0" * 64)
        ],
    )
    with pytest.raises(EmployeeDefinitionError, match="BOUND_RESOURCE_NOT_FOUND"):
        Employee.validate_members(NS(execute=lambda *_args: None), revision)
