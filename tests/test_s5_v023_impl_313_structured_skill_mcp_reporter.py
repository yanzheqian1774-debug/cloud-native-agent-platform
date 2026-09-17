from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTER = ROOT / "console/frontend/tests/harness/structuredSkillMcpReporter.ts"


def run_node(tmp_path: Path, source: str, **environment: str) -> None:
    reporter = tmp_path / REPORTER.name
    reporter.write_bytes(REPORTER.read_bytes())
    driver = tmp_path / "driver.mjs"
    driver.write_text(source, encoding="utf-8")
    result = subprocess.run(
        ["node", "--experimental-strip-types", driver],
        cwd=tmp_path,
        env={**os.environ, **environment},
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_reporter_records_closed_progress_http_and_redacts(tmp_path: Path) -> None:
    output = tmp_path / "skill-mcp-diagnostic.v1.json"
    run_node(
        tmp_path,
        """
import Reporter from './structuredSkillMcpReporter.ts';

const test = {
  id: 'main',
  title: 'publishes, binds and authorizes one bounded real capability test',
  location: {
    file: '/private/checkout/console/frontend/tests/e2e/' +
      'skill-mcp-workbench.spec.ts',
  },
};
const attachment = (operationId, resultState, structuredHttpStatus) => ({
  name: 'skill-mcp-operation-result.v1',
  contentType: 'application/vnd.agent-platform.skill-mcp-operation-result.v1+json',
  body: Buffer.from(JSON.stringify({operationId, resultState, structuredHttpStatus})),
});
const reporter = new Reporter();
reporter.onBegin({}, {allTests: () => [test]});
await reporter.onTestEnd(test, {
  status: 'failed',
  errors: [{message: 'expect(locator) PRIVATE_RESPONSE_BODY'}],
  attachments: [
    attachment('SKILL_MCP_DISCOVERY_HTTP_COMPLETION', 'EXPECTED', 200),
    attachment('SKILL_MCP_TOOL_SELECTION_READBACK', 'UNEXPECTED', 409),
  ],
  steps: [
    {title: 'SKILL_MCP_BACKEND_READY'},
    {title: 'SKILL_MCP_MCP_PUBLISHED'},
    {title: 'SKILL_MCP_HEALTH_SUBMIT'},
    {title: 'SKILL_MCP_HEALTH_HTTP_COMPLETION'},
    {title: 'SKILL_MCP_HEALTH_UI_RENDERED'},
    {title: 'SKILL_MCP_DISCOVERY_SUBMIT'},
    {title: 'SKILL_MCP_DISCOVERY_HTTP_COMPLETION'},
    {title: 'SKILL_MCP_DISCOVERY_SNAPSHOT_READBACK'},
    {title: 'SKILL_MCP_DISCOVERY_UI_RENDERED'},
    {title: 'SKILL_MCP_TOOL_SELECTION_SUBMIT'},
    {title: 'SKILL_MCP_TOOL_SELECTION_READBACK', error: {}},
  ],
});
await reporter.onEnd({status: 'failed'});
""",
        SKILL_MCP_DIAGNOSTIC_REPORT_PATH=str(output),
    )
    diagnostic = json.loads(output.read_text(encoding="utf-8"))
    assert diagnostic == {
        "schemaVersion": 1,
        "completionState": "FAILED",
        "counts": {
            "selected": 1,
            "executed": 1,
            "passed": 0,
            "failed": 1,
            "skipped": 0,
            "flaky": 0,
        },
        "failures": [
            {
                "testPath": ("console/frontend/tests/e2e/skill-mcp-workbench.spec.ts"),
                "scenarioId": "SKILL_MCP_WORKBENCH_PUBLISH_BIND_AUTHORIZE",
                "testStatus": "FAILED",
                "errorClass": "ASSERTION",
                "lastCompletedOperationId": "SKILL_MCP_TOOL_SELECTION_SUBMIT",
                "firstFailureOperationId": "SKILL_MCP_TOOL_SELECTION_READBACK",
                "http": [
                    {
                        "operationId": "SKILL_MCP_DISCOVERY_HTTP_COMPLETION",
                        "resultState": "EXPECTED",
                        "structuredHttpStatus": 200,
                    },
                    {
                        "operationId": "SKILL_MCP_TOOL_SELECTION_READBACK",
                        "resultState": "UNEXPECTED",
                        "structuredHttpStatus": 409,
                    },
                ],
            }
        ],
    }
    encoded = output.read_text(encoding="utf-8")
    for prohibited in ("PRIVATE_RESPONSE_BODY", "/private/checkout"):
        assert prohibited not in encoded


def test_reporter_uses_first_incomplete_and_keeps_unknown_identity(
    tmp_path: Path,
) -> None:
    output = tmp_path / "interrupted.json"
    run_node(
        tmp_path,
        """
import Reporter from './structuredSkillMcpReporter.ts';

const known = {
  id: 'known',
  title: 'publishes, binds and authorizes one bounded real capability test',
  location: {file: '/repo/console/frontend/tests/e2e/skill-mcp-workbench.spec.ts'},
};
const unknown = {
  id: 'unknown',
  title: 'PRIVATE_DYNAMIC_TITLE',
  location: {file: '/repo/console/frontend/tests/e2e/other.spec.ts'},
};
const reporter = new Reporter();
reporter.onBegin({}, {allTests: () => [known, unknown]});
await reporter.onTestEnd(known, {
  status: 'interrupted', errors: [], attachments: [],
  steps: [{title: 'SKILL_MCP_BACKEND_READY'}],
});
await reporter.onTestEnd(unknown, {
  status: 'failed', errors: [{message: 'PRIVATE_FAILURE'}], attachments: [], steps: [],
});
await reporter.onEnd({status: 'interrupted'});
""",
        SKILL_MCP_DIAGNOSTIC_REPORT_PATH=str(output),
    )
    failures = json.loads(output.read_text(encoding="utf-8"))["failures"]
    known = next(item for item in failures if item["scenarioId"] != "UNKNOWN")
    unknown = next(item for item in failures if item["scenarioId"] == "UNKNOWN")
    assert known["lastCompletedOperationId"] == "SKILL_MCP_BACKEND_READY"
    assert known["firstFailureOperationId"] == "SKILL_MCP_MCP_PUBLISHED"
    assert unknown["firstFailureOperationId"] == "UNKNOWN"
    assert "PRIVATE_DYNAMIC_TITLE" not in output.read_text(encoding="utf-8")
    assert "PRIVATE_FAILURE" not in output.read_text(encoding="utf-8")


def test_attachment_and_output_failures_do_not_replace_test_result(
    tmp_path: Path,
) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    run_node(
        tmp_path,
        """
import Reporter, {recordSkillMcpOperationResult} from './structuredSkillMcpReporter.ts';

await recordSkillMcpOperationResult(
  {attach: async () => { throw new Error('PRIVATE_ATTACH_FAILURE'); }},
  {operationId: 'SKILL_MCP_BACKEND_READY', resultState: 'EXPECTED'},
);
const reporter = new Reporter();
const test = {
  id: 'passing',
  title: 'publishes, binds and authorizes one bounded real capability test',
  location: {file: '/repo/console/frontend/tests/e2e/skill-mcp-workbench.spec.ts'},
};
reporter.onBegin({}, {allTests: () => [test]});
await reporter.onTestEnd(test, {status: 'passed', errors: [], attachments: []});
await reporter.onEnd({status: 'passed'});
""",
        SKILL_MCP_DIAGNOSTIC_REPORT_PATH=str(blocked / "diagnostic.json"),
    )
