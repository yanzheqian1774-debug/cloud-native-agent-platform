from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/acceptance"))
SUCCESSOR = "51fa5fcb266f1e58083c917dd4c99a02d9165c65"
TREE = "ddab80db6d82680d139bc97edac12f521d50a30f"
SOURCES = {
    "console/frontend/tests/e2e/knowledge-workbench.spec.ts": (
        "8225d3005727c230ff3a7fe1977095cab1186f6c"
    ),
    "console/frontend/tests/harness/structuredKnowledgeReporter.ts": (
        "d8ecee758fb2fafece69c6550d5802493377c11e"
    ),
    "console/frontend/playwright.config.ts": "c1f076d67e96f0628b1c3ff349e3f06f0382b6fd",
}
SPEC = importlib.util.spec_from_file_location(
    "isolated_browser_harness",
    ROOT / "scripts/acceptance/isolated_browser_harness.py",
)
assert SPEC and SPEC.loader
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)


def git(*args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, check=True
    ).stdout


def browser_failure_report() -> bytes:
    return json.dumps(
        {
            "stats": {"expected": 0, "unexpected": 1},
            "suites": [
                {
                    "file": "knowledge-workbench.spec.ts",
                    "specs": [
                        {
                            "title": (
                                "completes the real Knowledge lifecycle, retrieval, "
                                "recovery and purge journey"
                            ),
                            "tests": [
                                {
                                    "status": "unexpected",
                                    "results": [{"status": "failed", "errors": []}],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    ).encode()


def test_frozen_real_producer_reporter_to_current_parser(tmp_path: Path) -> None:
    assert git("rev-parse", f"{SUCCESSOR}^{{tree}}").decode().strip() == TREE
    for path, blob in SOURCES.items():
        assert git("rev-parse", f"{SUCCESSOR}:{path}").decode().strip() == blob
    reporter = tmp_path / "structuredKnowledgeReporter.ts"
    reporter.write_bytes(
        git(
            "show",
            f"{SUCCESSOR}:console/frontend/tests/harness/structuredKnowledgeReporter.ts",
        )
    )
    output = tmp_path / "real-reporter-output.json"
    driver = tmp_path / "driver.mjs"
    driver.write_text(
        """
import Reporter, {
  KNOWLEDGE_OPERATION_IDS,
  runKnowledgeOperation,
} from './structuredKnowledgeReporter.ts';
const attachments = [];
const testInfo = {
  attach: async (name, options) => attachments.push({name, ...options}),
};
for (const operationId of KNOWLEDGE_OPERATION_IDS.toReversed()) {
  try {
    await runKnowledgeOperation(testInfo, operationId, async () => {
      if (operationId === 'KNOWLEDGE_INDEX_RETRIEVE'
          || operationId === 'KNOWLEDGE_PURGE_RECOVERY') {
        const error = new Error(
          'selector URL says HTTP 503; exitCode=503 assertionCount=503',
        );
        throw error;
      }
      return { status: 202 };
    }, (result) => result.status);
  } catch {}
}
const reporter = new Reporter();
await reporter.onTestEnd({}, { attachments });
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["node", "--experimental-strip-types", driver],
        cwd=tmp_path,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "KNOWLEDGE_STRUCTURED_REPORT_PATH": str(output),
        },
        capture_output=True,
        check=False,
        text=True,
    )
    if "unknown option" in result.stderr.lower():
        pytest.skip("Node runtime lacks native TypeScript stripping")
    assert result.returncode == 0, result.stderr
    serialized = output.read_bytes()
    operations = harness.parse_knowledge_reporter_output(serialized)
    assert [item["operationId"] for item in operations] == list(
        harness.KNOWLEDGE_WORKBENCH_OPERATION_ORDER
    )
    record = harness.sanitized_first_failure_record(
        browser_failure_report(), "s5-impl-092-compatibility", 0, serialized
    )
    assert record["firstFailureOperationId"] == "KNOWLEDGE_INDEX_RETRIEVE"
    assert record["httpStatusSourceClass"] == "NO_STRUCTURED_HTTP_STATUS"
    assert record["httpStatusCategory"] in {"NONE", "UNKNOWN"}
    assert set(record) == harness.FIRST_FAILURE_FIELDS
    encoded = json.dumps(record)
    for prohibited in (
        "503",
        "selector",
        "http://",
        "https://",
        "payload",
        "credential",
        "trace",
        "screenshot",
        "video",
        "error-context",
    ):
        assert prohibited not in encoded.lower()


@pytest.mark.parametrize(
    "status,category",
    [
        (100, "HTTP_1XX"),
        (202, "HTTP_2XX"),
        (399, "HTTP_3XX"),
        (404, "HTTP_4XX"),
        (599, "HTTP_5XX"),
    ],
)
def test_real_reporter_shape_structured_http_categories(
    status: int, category: str
) -> None:
    serialized = json.dumps(
        [
            {
                "operationId": "KNOWLEDGE_UPDATE",
                "resultState": "UNEXPECTED",
                "structuredHttpStatus": status,
            }
        ]
    ).encode()
    record = harness.sanitized_first_failure_record(
        browser_failure_report(), "s5-impl-092-compatibility", 0, serialized
    )
    assert record["httpStatusCategory"] == category
    assert record["httpStatusSourceClass"] == "STRUCTURED_RESPONSE_STATUS"
    assert str(status) not in json.dumps(record)
