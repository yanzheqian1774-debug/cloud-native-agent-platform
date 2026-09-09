from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTER = ROOT / "console/frontend/tests/harness/structuredKnowledgeReporter.ts"


def run_node(tmp_path: Path, source: str, **environment: str) -> None:
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


def test_reporter_retains_all_safe_failures_and_counts(tmp_path: Path) -> None:
    reporter = tmp_path / REPORTER.name
    reporter.write_bytes(REPORTER.read_bytes())
    output = tmp_path / "browser-diagnostics.v1.json"
    legacy = tmp_path / "knowledge-operation-result.json"
    run_node(
        tmp_path,
        """
import Reporter from './structuredKnowledgeReporter.ts';

const path = '/private/checkout/console/frontend/tests/e2e/knowledge-workbench.spec.ts';
const lifecycle = {
  id: 'known-lifecycle',
  title: 'completes the real Knowledge lifecycle, retrieval, recovery' +
    ' and purge journey',
  location: {file: path},
};
const mobile = {
  id: 'known-mobile',
  title: 'validates real form inputs and keeps denied and service failures' +
    ' distinct at mobile width',
  location: {file: path},
};
const passing = {
  id: 'known-context',
  title: 'isolates late retrieval responses and preserves filter and exact' +
    ' revision context',
  location: {file: path},
};
const attachment = (operationId, resultState) => ({
  name: 'knowledge-operation-result.v1',
  contentType: 'application/vnd.agent-platform.knowledge-operation-result.v1+json',
  body: Buffer.from(JSON.stringify({operationId, resultState}), 'utf8'),
});
const reporter = new Reporter();
reporter.onBegin({}, {allTests: () => [lifecycle, mobile, passing]});
await reporter.onTestEnd(lifecycle, {
  status: 'failed',
  errors: [{message: 'expect(locator).toBeVisible PRIVATE_DOCUMENT_TEXT'}],
  attachments: [
    attachment('KNOWLEDGE_GOVERNED_CREATE_PUBLISH', 'EXPECTED'),
    attachment('KNOWLEDGE_INDEX_RETRIEVE', 'UNEXPECTED'),
  ],
});
await reporter.onTestEnd(mobile, {
  status: 'failed',
  errors: [{message: 'navigation to https://private.invalid failed'}],
  attachments: [],
});
await reporter.onTestEnd(passing, {
  status: 'passed', errors: [], attachments: [],
});
await reporter.onEnd({status: 'failed'});
""",
        KNOWLEDGE_DIAGNOSTIC_REPORT_PATH=str(output),
        KNOWLEDGE_STRUCTURED_REPORT_PATH=str(legacy),
    )
    diagnostic = json.loads(output.read_text(encoding="utf-8"))
    assert diagnostic == {
        "schemaVersion": 1,
        "completionState": "FAILED",
        "counts": {
            "selected": 3,
            "executed": 3,
            "passed": 1,
            "failed": 2,
            "skipped": 0,
            "flaky": 0,
        },
        "failures": [
            {
                "testPath": ("console/frontend/tests/e2e/knowledge-workbench.spec.ts"),
                "scenarioId": "KNOWLEDGE_WORKBENCH_LIFECYCLE",
                "testStatus": "FAILED",
                "errorClass": "ASSERTION",
                "firstFailureOperationId": "KNOWLEDGE_INDEX_RETRIEVE",
            },
            {
                "testPath": ("console/frontend/tests/e2e/knowledge-workbench.spec.ts"),
                "scenarioId": "KNOWLEDGE_WORKBENCH_INPUT_DENIAL_MOBILE",
                "testStatus": "FAILED",
                "errorClass": "NAVIGATION",
                "firstFailureOperationId": "UNKNOWN",
            },
        ],
    }
    encoded = output.read_text(encoding="utf-8")
    for prohibited in (
        "PRIVATE_DOCUMENT_TEXT",
        "private.invalid",
        "https://",
        "/private/checkout",
    ):
        assert prohibited not in encoded
    assert json.loads(legacy.read_text(encoding="utf-8")) == [
        {
            "operationId": "KNOWLEDGE_GOVERNED_CREATE_PUBLISH",
            "resultState": "EXPECTED",
        },
        {
            "operationId": "KNOWLEDGE_INDEX_RETRIEVE",
            "resultState": "UNEXPECTED",
        },
    ]


def test_reporter_success_and_diagnostic_failures_preserve_results(
    tmp_path: Path,
) -> None:
    reporter = tmp_path / REPORTER.name
    reporter.write_bytes(REPORTER.read_bytes())
    blocked_parent = tmp_path / "blocked-parent"
    blocked_parent.write_text("not a directory", encoding="utf-8")
    success = tmp_path / "success.json"
    run_node(
        tmp_path,
        """
import Reporter, {runKnowledgeOperation} from './structuredKnowledgeReporter.ts';

const primary = new Error('PRIMARY_PRIVATE_FAILURE');
let caught;
try {
  await runKnowledgeOperation(
    {attach: async () => { throw new Error('ATTACH_PRIVATE_FAILURE'); }},
    'KNOWLEDGE_UPDATE',
    async () => { throw primary; },
  );
} catch (error) {
  caught = error;
}
if (caught !== primary) throw new Error('primary failure was replaced');
const value = await runKnowledgeOperation(
  {attach: async () => { throw new Error('ATTACH_PRIVATE_FAILURE'); }},
  'KNOWLEDGE_UPDATE',
  async () => 42,
);
if (value !== 42) throw new Error('successful result was replaced');

process.env.KNOWLEDGE_DIAGNOSTIC_REPORT_PATH = process.env.BLOCKED_OUTPUT;
const blocked = new Reporter();
const test = {
  id: 'passing',
  title: 'isolates late retrieval responses and preserves filter and exact' +
    ' revision context',
  location: {file: '/repo/console/frontend/tests/e2e/knowledge-workbench.spec.ts'},
};
blocked.onBegin({}, {allTests: () => [test]});
await blocked.onTestEnd(test, {status: 'passed', errors: [], attachments: []});
await blocked.onEnd({status: 'passed'});

process.env.KNOWLEDGE_DIAGNOSTIC_REPORT_PATH = process.env.SUCCESS_OUTPUT;
const successful = new Reporter();
successful.onBegin({}, {allTests: () => [test]});
await successful.onTestEnd(test, {status: 'passed', errors: [], attachments: []});
await successful.onEnd({status: 'passed'});
""",
        BLOCKED_OUTPUT=str(blocked_parent / "diagnostic.json"),
        SUCCESS_OUTPUT=str(success),
    )
    assert json.loads(success.read_text(encoding="utf-8")) == {
        "schemaVersion": 1,
        "completionState": "PASSED",
        "counts": {
            "selected": 1,
            "executed": 1,
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "flaky": 0,
        },
        "failures": [],
    }


def test_reporter_redacts_unlisted_title_but_keeps_safe_test_path(
    tmp_path: Path,
) -> None:
    reporter = tmp_path / REPORTER.name
    reporter.write_bytes(REPORTER.read_bytes())
    output = tmp_path / "unknown-title.json"
    run_node(
        tmp_path,
        """
import Reporter from './structuredKnowledgeReporter.ts';

const test = {
  id: 'private-test-id',
  title: 'PRIVATE_DYNAMIC_CUSTOMER_TITLE',
  location: {file: '/private/root/console/frontend/tests/e2e/other.spec.ts'},
};
const reporter = new Reporter();
reporter.onBegin({}, {allTests: () => [test]});
await reporter.onTestEnd(test, {
  status: 'failed',
  errors: [{message: 'PRIVATE_DYNAMIC_ERROR'}],
  attachments: [],
});
await reporter.onEnd({status: 'failed'});
""",
        KNOWLEDGE_DIAGNOSTIC_REPORT_PATH=str(output),
    )
    diagnostic = json.loads(output.read_text(encoding="utf-8"))
    assert diagnostic["failures"] == [
        {
            "testPath": "console/frontend/tests/e2e/other.spec.ts",
            "scenarioId": "UNKNOWN",
            "testStatus": "FAILED",
            "errorClass": "UNKNOWN",
            "firstFailureOperationId": "UNKNOWN",
        }
    ]
    encoded = output.read_text(encoding="utf-8")
    assert "PRIVATE_DYNAMIC_CUSTOMER_TITLE" not in encoded
    assert "PRIVATE_DYNAMIC_ERROR" not in encoded
    assert "/private/root" not in encoded
