#!/usr/bin/env python3
"""Own an isolated real backend while a serialized browser command runs."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import threading
import time
import urllib.request
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, NoReturn
from urllib.parse import urlparse

import psycopg
from browser_build_preflight import verify_build_identity
from minimum_disclosure import (
    EVIDENCE_FIELDS,
    extract_allowlisted,
    scan_generated_artifacts,
)
from psycopg import sql

FIRST_FAILURE_SCHEMA_VERSION = 2
MAX_DIAGNOSTIC_COUNT = 100_000
FIRST_FAILURE_FIELDS = frozenset(
    {
        "schemaVersion",
        "journeyId",
        "runnerPhase",
        "harnessPhase",
        "firstFailureAssertionId",
        "firstFailureOperationId",
        "expectedResultClass",
        "observedResultClass",
        "failureCategory",
        "failureSubtype",
        "exceptionClass",
        "httpStatusCategory",
        "httpStatusSourceClass",
        "correlationDigest",
        "completedJourneyCount",
        "completedAssertionCount",
        "unexpectedAssertionCount",
        "backendStateClass",
        "frontendStateClass",
        "listenerStateClass",
        "restartCountClass",
        "completionState",
    }
)
FIRST_FAILURE_V1_FIELDS = FIRST_FAILURE_FIELDS - {
    "firstFailureOperationId",
    "httpStatusSourceClass",
}
FIRST_FAILURE_ASSERTION_IDS = {
    (
        "agent-workbench.spec.ts",
        "publishes an exact reviewed revision through the real Workbench",
    ): "AGENT_WORKBENCH_PUBLISH_REVIEWED_REVISION",
    (
        "agent-workbench.spec.ts",
        "creates a governed draft through the guided Builder",
    ): "AGENT_WORKBENCH_CREATE_GOVERNED_DRAFT",
    (
        "knowledge-workbench.spec.ts",
        "completes the real Knowledge lifecycle, retrieval, recovery and purge journey",
    ): "KNOWLEDGE_WORKBENCH_LIFECYCLE",
    (
        "skill-mcp-workbench.spec.ts",
        "publishes, binds and authorizes one bounded real capability test",
    ): "SKILL_MCP_WORKBENCH_PUBLISH_BIND_AUTHORIZE",
    (
        "unified-product-assembly.spec.ts",
        "proves the complete durable unified-product browser journey",
    ): "UNIFIED_PRODUCT_ASSEMBLY_DURABLE_JOURNEY",
    (
        "unified-product-assembly.spec.ts",
        "keeps denial disclosure-safe and responsive navigation accessible",
    ): "UNIFIED_PRODUCT_ASSEMBLY_DISCLOSURE_DENIAL",
    (
        "wave-3b-product-technical-evidence.spec.ts",
        "canonical URL context is deterministic and round-trip stable",
    ): "WAVE_3B_CANONICAL_CONTEXT_ROUND_TRIP",
    (
        "wave-3b-product-technical-evidence.spec.ts",
        "invalid URL context fails closed",
    ): "WAVE_3B_INVALID_CONTEXT_FAIL_CLOSED",
    (
        "wave-3b-product-technical-evidence.spec.ts",
        "proves all twelve Wave 3B real-service browser journeys",
    ): "WAVE_3B_REAL_SERVICE_JOURNEYS",
    (
        "workflow-runtime-workbench.spec.ts",
        "publishes a Runtime Profile then a governed Workflow through real Workbenches",
    ): "WORKFLOW_RUNTIME_PUBLISH_GOVERNED_WORKFLOW",
    (
        "workflow-runtime-workbench.spec.ts",
        "shows controlled empty and validation failure states",
    ): "WORKFLOW_RUNTIME_CONTROLLED_FAILURE_STATES",
    (
        "workflow-runtime-workbench.spec.ts",
        "renders a disclosure-safe denied state",
    ): "WORKFLOW_RUNTIME_DISCLOSURE_DENIAL",
}
FIRST_FAILURE_ASSERTION_IDS.update(
    {
        ("platform-support-surfaces.spec.ts", title): scenario
        for title, scenario in (
            (
                "exposes nine truthful Chinese-first platform support surfaces",
                "PLATFORM_SUPPORT_TRUTHFUL_SURFACES",
            ),
            (
                "keeps unsupported actions disabled and preserves real navigation",
                "PLATFORM_SUPPORT_DISABLED_ACTIONS",
            ),
            (
                "keeps all support pages reachable from the mobile navigation",
                "PLATFORM_SUPPORT_MOBILE_NAVIGATION",
            ),
            (
                "keeps all nineteen primary surfaces responsive "
                "and restores heading focus",
                "PLATFORM_PRIMARY_RESPONSIVE_FOCUS",
            ),
            (
                "navigates the repeatable 业务闭环 journey with browser history",
                "PLATFORM_BUSINESS_JOURNEY",
            ),
            (
                "navigates the repeatable 数字员工装配 journey with browser history",
                "PLATFORM_ASSEMBLY_JOURNEY",
            ),
            (
                "navigates the repeatable 平台治理 journey with browser history",
                "PLATFORM_GOVERNANCE_JOURNEY",
            ),
        )
    }
)
FAILURE_CATEGORIES = frozenset(
    {
        "BROWSER_ASSERTION",
        "BROWSER_TIMEOUT",
        "BROWSER_HTTP_ERROR",
        "BROWSER_NAVIGATION_ERROR",
        "BROWSER_PROCESS_ERROR",
        "BROWSER_DIAGNOSTIC_GAP",
    }
)
FAILURE_SUBTYPES = frozenset(
    {
        "ASSERTION_MISMATCH",
        "TIMEOUT",
        "HTTP_ERROR",
        "NAVIGATION_ERROR",
        "SELECTOR_STATE_MISMATCH",
        "APPLICATION_STATE_MISMATCH",
        "PROCESS_EXIT",
        "UNKNOWN",
    }
)
HTTP_STATUS_CATEGORIES = frozenset(
    {
        "NONE",
        "HTTP_1XX",
        "HTTP_2XX",
        "HTTP_3XX",
        "HTTP_4XX",
        "HTTP_5XX",
        "CONNECTION_FAILURE",
        "TIMEOUT",
        "UNKNOWN",
    }
)
HTTP_STATUS_SOURCE_CLASSES = frozenset(
    {
        "STRUCTURED_RESPONSE_STATUS",
        "NO_STRUCTURED_HTTP_STATUS",
        "NOT_RETAINED",
    }
)
KNOWLEDGE_WORKBENCH_OPERATION_IDS = frozenset(
    {
        "KNOWLEDGE_GOVERNED_CREATE_PUBLISH",
        "KNOWLEDGE_INDEX_RETRIEVE",
        "KNOWLEDGE_UPDATE",
        "KNOWLEDGE_RESTART_READBACK",
        "KNOWLEDGE_PURGE_RECOVERY",
    }
)
KNOWLEDGE_WORKBENCH_OPERATION_ORDER = (
    "KNOWLEDGE_GOVERNED_CREATE_PUBLISH",
    "KNOWLEDGE_INDEX_RETRIEVE",
    "KNOWLEDGE_UPDATE",
    "KNOWLEDGE_RESTART_READBACK",
    "KNOWLEDGE_PURGE_RECOVERY",
)
KNOWLEDGE_REPORTER_FIELDS = frozenset({"operationId", "resultState"})
KNOWLEDGE_REPORTER_HTTP_FIELDS = KNOWLEDGE_REPORTER_FIELDS | {"structuredHttpStatus"}
FIRST_FAILURE_OPERATION_IDS = {
    "KNOWLEDGE_WORKBENCH_LIFECYCLE": KNOWLEDGE_WORKBENCH_OPERATION_IDS,
    **{
        assertion_id: frozenset({assertion_id})
        for assertion_id in FIRST_FAILURE_ASSERTION_IDS.values()
        if assertion_id != "KNOWLEDGE_WORKBENCH_LIFECYCLE"
    },
}
EXCEPTION_CLASSES = frozenset(
    {
        "NONE",
        "ASSERTION_ERROR",
        "TIMEOUT_ERROR",
        "HTTP_ERROR",
        "NAVIGATION_ERROR",
        "PROCESS_ERROR",
        "UNKNOWN",
    }
)
_ASSERTION_ID = re.compile(r"[A-Z][A-Z0-9_]{2,95}\Z")


def _browser_json(stdout: bytes) -> dict[str, object] | None:
    try:
        start = stdout.find(b"{")
        end = stdout.rfind(b"}")
        value = json.loads(stdout[start : end + 1])
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _ordered_specs(suites: object):
    if not isinstance(suites, list):
        return
    for suite in suites:
        if not isinstance(suite, dict):
            continue
        yield from _ordered_specs(suite.get("suites"))
        specs = suite.get("specs")
        if isinstance(specs, list):
            for spec in specs:
                if isinstance(spec, dict):
                    yield suite, spec


_FAILURE_CONTEXT_UNSET = object()


def first_failure_context(
    report: dict[str, object],
) -> (
    tuple[
        dict[str, object],
        dict[str, object],
        dict[str, object],
        dict[str, object],
    ]
    | None
):
    """Return one unambiguous failed result from the first failing spec."""
    ordered = list(_ordered_specs(report.get("suites")))
    for suite, spec in ordered:
        tests = spec.get("tests")
        if not isinstance(tests, list):
            continue
        candidates = []
        for test in tests:
            if not isinstance(test, dict):
                return None
            results = test.get("results")
            if not isinstance(results, list):
                if test.get("status") == "unexpected":
                    return None
                continue
            if any(not isinstance(result, dict) for result in results):
                return None
            failed = [
                result
                for result in results
                if result.get("status") in {"failed", "timedOut", "interrupted"}
            ]
            if test.get("status") == "unexpected" or failed:
                if len(results) != 1 or len(failed) != 1:
                    return None
                candidates.append((suite, spec, test, failed[0]))
        if not candidates:
            continue
        if len(candidates) != 1:
            return None
        key = (Path(str(suite.get("file", ""))).name, spec.get("title"))
        occurrences = sum(
            (Path(str(item_suite.get("file", ""))).name, item_spec.get("title")) == key
            for item_suite, item_spec in ordered
        )
        return candidates[0] if occurrences == 1 else None
    return None


def _bounded_count(value: object) -> int:
    return value if type(value) is int and 0 <= value <= MAX_DIAGNOSTIC_COUNT else 0


def _structured_http_classification(status: object) -> tuple[str, str]:
    if status is None:
        return "NO_STRUCTURED_HTTP_STATUS", "NONE"
    if type(status) is not int or not 100 <= status <= 599:
        raise ValueError("browser structured HTTP status violation")
    return "STRUCTURED_RESPONSE_STATUS", f"HTTP_{status // 100}XX"


def parse_knowledge_reporter_output(data: bytes) -> list[dict[str, object]]:
    """Parse the frozen reporter's closed, minimum-disclosure output."""
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Knowledge reporter output is malformed") from exc
    if not isinstance(value, list) or len(value) > len(
        KNOWLEDGE_WORKBENCH_OPERATION_ORDER
    ):
        raise ValueError("Knowledge reporter output is not a bounded list")
    order = {
        operation_id: index
        for index, operation_id in enumerate(KNOWLEDGE_WORKBENCH_OPERATION_ORDER)
    }
    seen: set[str] = set()
    normalized: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict) or frozenset(item) not in {
            KNOWLEDGE_REPORTER_FIELDS,
            KNOWLEDGE_REPORTER_HTTP_FIELDS,
        }:
            raise ValueError("Knowledge reporter operation field violation")
        operation_id = item.get("operationId")
        if operation_id not in KNOWLEDGE_WORKBENCH_OPERATION_IDS:
            raise ValueError("Knowledge reporter operation identity violation")
        if operation_id in seen:
            raise ValueError("Knowledge reporter operation is duplicated")
        seen.add(str(operation_id))
        if item.get("resultState") not in {"EXPECTED", "UNEXPECTED"}:
            raise ValueError("Knowledge reporter result state violation")
        _structured_http_classification(item.get("structuredHttpStatus"))
        normalized.append(item)
    return sorted(normalized, key=lambda item: order[str(item["operationId"])])


def _failure_details(
    text: str, status: str, structured_http_status: object = None
) -> tuple[str, str, str, str, str]:
    http_source, http_category = _structured_http_classification(structured_http_status)
    if http_source == "STRUCTURED_RESPONSE_STATUS":
        return (
            "BROWSER_HTTP_ERROR",
            "HTTP_ERROR",
            "HTTP_ERROR",
            http_category,
            http_source,
        )
    lowered = text.lower()
    if status == "interrupted":
        return (
            "BROWSER_PROCESS_ERROR",
            "PROCESS_EXIT",
            "PROCESS_ERROR",
            "NONE",
            http_source,
        )
    if status == "timedOut" or "timeout" in lowered or "timed out" in lowered:
        return "BROWSER_TIMEOUT", "TIMEOUT", "TIMEOUT_ERROR", "NONE", http_source
    if "net::err_" in lowered or "connection" in lowered:
        return (
            "BROWSER_NAVIGATION_ERROR",
            "NAVIGATION_ERROR",
            "NAVIGATION_ERROR",
            "NONE",
            http_source,
        )
    if "goto" in lowered or "navigation" in lowered:
        return (
            "BROWSER_NAVIGATION_ERROR",
            "NAVIGATION_ERROR",
            "NAVIGATION_ERROR",
            "NONE",
            http_source,
        )
    if (
        "locator" in lowered
        or "selector" in lowered
        or "tobevisible" in lowered
        or "tohave" in lowered
    ):
        return (
            "BROWSER_ASSERTION",
            "SELECTOR_STATE_MISMATCH",
            "ASSERTION_ERROR",
            "NONE",
            http_source,
        )
    if "expect(" in lowered or "assert" in lowered:
        return (
            "BROWSER_ASSERTION",
            "ASSERTION_MISMATCH",
            "ASSERTION_ERROR",
            "NONE",
            http_source,
        )
    return (
        "BROWSER_ASSERTION",
        "APPLICATION_STATE_MISMATCH",
        "UNKNOWN",
        "UNKNOWN",
        http_source,
    )


def sanitized_first_failure_record(
    stdout: bytes,
    journey_id: str,
    restart_count: int,
    knowledge_reporter_output: bytes | None = None,
    failure_context: object = _FAILURE_CONTEXT_UNSET,
) -> dict[str, object] | None:
    report = _browser_json(stdout)
    if report is None:
        return None
    stats = report.get("stats") if isinstance(report.get("stats"), dict) else {}
    unexpected = _bounded_count(stats.get("unexpected"))
    first = (
        first_failure_context(report)
        if failure_context is _FAILURE_CONTEXT_UNSET
        else failure_context
    )
    if first is None and unexpected == 0:
        return None
    assertion_id = "NOT_RETAINED"
    operation_id = "NOT_RETAINED"
    category, subtype, exception_class, http_category, http_source = (
        "BROWSER_DIAGNOSTIC_GAP",
        "UNKNOWN",
        "UNKNOWN",
        "UNKNOWN",
        "NOT_RETAINED",
    )
    if first is not None:
        suite, spec, _test, result = first
        title = spec.get("title")
        mapped = (
            FIRST_FAILURE_ASSERTION_IDS.get(
                (Path(str(suite.get("file", ""))).name, title)
            )
            if isinstance(title, str)
            else None
        )
        if mapped:
            assertion_id = mapped
        operation = result
        if (
            assertion_id == "KNOWLEDGE_WORKBENCH_LIFECYCLE"
            and knowledge_reporter_output
        ):
            reporter_operations = parse_knowledge_reporter_output(
                knowledge_reporter_output
            )
            operation = next(
                (
                    {
                        "operationId": item["operationId"],
                        "status": "failed",
                        **(
                            {"structuredHttpStatus": item["structuredHttpStatus"]}
                            if "structuredHttpStatus" in item
                            else {}
                        ),
                    }
                    for item in reporter_operations
                    if item["resultState"] == "UNEXPECTED"
                ),
                {},
            )
        operations = result.get("operations") if isinstance(result, dict) else None
        if operations is not None and knowledge_reporter_output is None:
            if not isinstance(operations, list):
                raise ValueError("browser operation result source violation")
            operation = next(
                (
                    item
                    for item in operations
                    if isinstance(item, dict)
                    and item.get("status") in {"failed", "timedOut", "interrupted"}
                ),
                {},
            )
        supplied_operation_id = (
            operation.get("operationId") if isinstance(operation, dict) else None
        )
        allowed_operations = FIRST_FAILURE_OPERATION_IDS.get(assertion_id, frozenset())
        if supplied_operation_id in allowed_operations:
            operation_id = supplied_operation_id
        elif len(allowed_operations) == 1:
            operation_id = next(iter(allowed_operations))
        errors = result.get("errors") if isinstance(result, dict) else []
        transient = " ".join(
            str(item.get("message", "")) for item in errors if isinstance(item, dict)
        )[:65_536]
        structured_http_status = (
            operation.get("structuredHttpStatus")
            if isinstance(operation, dict)
            else None
        )
        category, subtype, exception_class, http_category, http_source = (
            _failure_details(
                transient,
                str(operation.get("status", result.get("status", "")))
                if isinstance(operation, dict)
                else str(result.get("status", "")),
                structured_http_status,
            )
        )
        if assertion_id == "NOT_RETAINED" or operation_id == "NOT_RETAINED":
            category, subtype, exception_class, http_category, http_source = (
                "BROWSER_DIAGNOSTIC_GAP",
                "UNKNOWN",
                "UNKNOWN",
                "UNKNOWN",
                "NOT_RETAINED",
            )
    completed = _bounded_count(stats.get("expected")) + unexpected
    record: dict[str, object] = {
        "schemaVersion": FIRST_FAILURE_SCHEMA_VERSION,
        "journeyId": journey_id,
        "runnerPhase": "browser-harness",
        "harnessPhase": "BROWSER_COMMAND",
        "firstFailureAssertionId": assertion_id,
        "firstFailureOperationId": operation_id,
        "expectedResultClass": "EXPECTED",
        "observedResultClass": "UNEXPECTED",
        "failureCategory": category,
        "failureSubtype": subtype,
        "exceptionClass": exception_class,
        "httpStatusCategory": http_category,
        "httpStatusSourceClass": http_source,
        "completedJourneyCount": 0,
        "completedAssertionCount": min(completed, MAX_DIAGNOSTIC_COUNT),
        "unexpectedAssertionCount": unexpected,
        "backendStateClass": "RUNNING",
        "frontendStateClass": "UNKNOWN",
        "listenerStateClass": "ACTIVE",
        "restartCountClass": "NONE" if restart_count == 0 else "ONE_OR_MORE",
        "completionState": "FAILED",
    }
    normalized = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    record["correlationDigest"] = hashlib.sha256(normalized).hexdigest()
    return validate_first_failure_record(record)


def validate_first_failure_record(record: object) -> dict[str, object]:
    if not isinstance(record, dict):
        raise ValueError("browser first-failure schema violation")
    schema_version = record.get("schemaVersion")
    expected_fields = {
        1: FIRST_FAILURE_V1_FIELDS,
        FIRST_FAILURE_SCHEMA_VERSION: FIRST_FAILURE_FIELDS,
    }.get(schema_version)
    if expected_fields is None:
        raise ValueError("browser first-failure schema version violation")
    if set(record) != expected_fields:
        raise ValueError("browser first-failure schema violation")
    if not isinstance(record["journeyId"], str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{2,95}", record["journeyId"]
    ):
        raise ValueError("browser first-failure journey identity violation")
    assertion_id = record["firstFailureAssertionId"]
    if assertion_id != "NOT_RETAINED" and (
        not isinstance(assertion_id, str) or not _ASSERTION_ID.fullmatch(assertion_id)
    ):
        raise ValueError("browser first-failure assertion identity violation")
    if (
        assertion_id != "NOT_RETAINED"
        and assertion_id not in FIRST_FAILURE_ASSERTION_IDS.values()
    ):
        raise ValueError("browser first-failure assertion identity is not versioned")
    if schema_version == FIRST_FAILURE_SCHEMA_VERSION:
        operation_id = record["firstFailureOperationId"]
        if operation_id != "NOT_RETAINED" and operation_id not in (
            FIRST_FAILURE_OPERATION_IDS.get(assertion_id, frozenset())
        ):
            raise ValueError(
                "browser first-failure operation identity is not versioned"
            )
    enum_fields = {
        "runnerPhase": {"browser-harness"},
        "harnessPhase": {"BROWSER_COMMAND"},
        "expectedResultClass": {"EXPECTED"},
        "observedResultClass": {"UNEXPECTED"},
        "failureCategory": FAILURE_CATEGORIES,
        "failureSubtype": FAILURE_SUBTYPES,
        "exceptionClass": EXCEPTION_CLASSES,
        "httpStatusCategory": HTTP_STATUS_CATEGORIES,
        "backendStateClass": {"RUNNING", "STOPPED", "UNKNOWN"},
        "frontendStateClass": {"RUNNING", "STOPPED", "UNKNOWN"},
        "listenerStateClass": {"ACTIVE", "INACTIVE", "UNKNOWN"},
        "restartCountClass": {"NONE", "ONE_OR_MORE", "UNKNOWN"},
        "completionState": {"FAILED"},
    }
    if any(record[name] not in allowed for name, allowed in enum_fields.items()):
        raise ValueError("browser first-failure enum violation")
    if schema_version == FIRST_FAILURE_SCHEMA_VERSION:
        http_source = record["httpStatusSourceClass"]
        http_category = record["httpStatusCategory"]
        if http_source not in HTTP_STATUS_SOURCE_CLASSES:
            raise ValueError("browser HTTP status source violation")
        if (
            (
                http_category.startswith("HTTP_")
                and http_source != "STRUCTURED_RESPONSE_STATUS"
            )
            or (
                http_source == "STRUCTURED_RESPONSE_STATUS"
                and http_category not in {f"HTTP_{value}XX" for value in range(1, 6)}
            )
            or (
                http_source in {"NO_STRUCTURED_HTTP_STATUS", "NOT_RETAINED"}
                and http_category not in {"NONE", "UNKNOWN"}
            )
        ):
            raise ValueError("browser HTTP source/category contradiction")
        if (
            operation_id == "NOT_RETAINED"
            and record["failureCategory"] != "BROWSER_DIAGNOSTIC_GAP"
        ):
            raise ValueError("browser operation diagnostic-gap contradiction")
    for name in (
        "completedJourneyCount",
        "completedAssertionCount",
        "unexpectedAssertionCount",
    ):
        if (
            type(record[name]) is not int
            or not 0 <= record[name] <= MAX_DIAGNOSTIC_COUNT
        ):
            raise ValueError("browser first-failure count violation")
    if not isinstance(record["correlationDigest"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", record["correlationDigest"]
    ):
        raise ValueError("browser first-failure digest violation")
    digest_source = {
        key: value for key, value in record.items() if key != "correlationDigest"
    }
    expected_digest = hashlib.sha256(
        json.dumps(digest_source, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if record["correlationDigest"] != expected_digest:
        raise ValueError("browser first-failure digest mismatch")
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":"))
    if len(encoded) > 4096 or re.search(
        r"(?i)(https?://|[?&][a-z]+=|/Users/|/home/|/tmp/|password|token|secret|trace|screenshot|video|error-context)",
        encoded,
    ):
        raise ValueError("browser first-failure disclosure violation")
    return record


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        if "required" in message:
            category = "REQUIRED"
        elif "unrecognized" in message:
            category = "UNKNOWN"
        elif "credential file mode" in message:
            category = "CREDENTIAL_MODE"
        else:
            category = "VALUE"
        print(f"harness argument failure: {category}", file=sys.stderr)
        super().error("invalid Harness arguments")


def sanitized_browser_failure_class(stdout: bytes, stderr: bytes) -> str:
    try:
        start = stdout.find(b"{")
        end = stdout.rfind(b"}")
        report = json.loads(stdout[start : end + 1])
    except (UnicodeDecodeError, json.JSONDecodeError):
        report = None
    if isinstance(report, dict):
        stats = report.get("stats")
        if isinstance(stats, dict) and stats.get("unexpected", 0) > 0:
            return "ASSERTION"
        if report.get("errors"):
            return "INVOCATION"
    combined = stdout + stderr
    if not combined:
        return "EMPTY"
    if (
        b"npm error" in combined
        or b"Unknown option" in combined
        or b"not found" in combined
        or b"ENOENT" in combined
    ):
        return "INVOCATION"
    if b"EACCES" in combined or b"Permission denied" in combined:
        return "PERMISSION"
    if re.search(rb'"unexpected"\s*:\s*[1-9]', combined) or re.search(
        rb'"status"\s*:\s*"(?:failed|timedOut)"', combined
    ):
        return "ASSERTION"
    patterns = (
        (b"browserType.launch", "LAUNCH"),
        (b"Timed out", "TIMEOUT"),
        (b"TimeoutError", "TIMEOUT"),
        (b"expect(", "ASSERTION"),
        (b"ERR_CONNECTION", "CONNECTION"),
        (b"webServer", "SERVER"),
        (b"Process from config.webServer", "SERVER"),
    )
    return next(
        (category for marker, category in patterns if marker in combined), "COMMAND"
    )


def verify_browser_report(stdout: bytes) -> bool:
    try:
        start = stdout.find(b"{")
        end = stdout.rfind(b"}")
        report = json.loads(stdout[start : end + 1])
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    stats = report.get("stats") if isinstance(report, dict) else None
    return bool(
        isinstance(stats, dict)
        and type(stats.get("expected")) is int
        and stats["expected"] > 0
        and stats.get("unexpected") == 0
        and stats.get("skipped") == 0
        and stats.get("flaky") == 0
    )


SUMMARY_PREFIX = "BROWSER_FAILURE_SUMMARY_V1 "
SUMMARY_FIELDS = frozenset(
    {
        "schemaVersion",
        "scenarioId",
        "spec",
        "sourceLine",
        "locationKind",
        "failureCategory",
        "failureSubtype",
        "actionClass",
        "restartCountClass",
        "restartCountScope",
        "counts",
        "buildModeIdentity",
        "frontendManifestDigest",
    }
)
SUMMARY_COUNT_FIELDS = frozenset(
    {"selected", "executed", "passed", "failed", "skipped", "flaky"}
)
PRIMARY_ROUTE_KEYS = (
    "HOME",
    "WORK",
    "EMPLOYEES",
    "AGENTS",
    "SKILLS",
    "MCP",
    "KNOWLEDGE",
    "WORKFLOWS",
    "RUNTIMES",
    "EVIDENCE",
    "OUTCOMES",
    "APPLICATIONS",
    "PERMISSIONS",
    "SECURITY",
    "OPERATIONS",
    "MODELS",
    "USAGE",
    "SETTINGS",
    "HELP",
)
PRIMARY_STEP_IDS = {
    f"PRIMARY_{route}_{viewport}_{action}": (route, viewport)
    for viewport in ("DESKTOP", "MOBILE")
    for route in PRIMARY_ROUTE_KEYS
    for action in ("NAVIGATE", "HEADING_VISIBLE", "HEADING_FOCUSED", "NO_OVERFLOW")
}
PRIMARY_ACTION_CLASSES = (
    "NAVIGATE",
    "HEADING_VISIBLE",
    "HEADING_FOCUSED",
    "NO_OVERFLOW",
)


def _primary_action_class(step_id: str) -> str:
    return next(
        action for action in PRIMARY_ACTION_CLASSES if step_id.endswith(f"_{action}")
    )


WAVE_3B_STEP_IDS = {
    "1 context-preserving catalog round trip": (
        "WAVE3B_01_CATALOG_ROUND_TRIP",
        "CATALOG",
        "DESKTOP",
        "NAVIGATION",
    ),
    "2 claim Evidence fact business-step chain": (
        "WAVE3B_02_EVIDENCE_CHAIN",
        "EVIDENCE",
        "DESKTOP",
        "EVIDENCE_CHAIN",
    ),
    "3 fact reverses to exact claim": (
        "WAVE3B_03_FACT_TO_CLAIM",
        "EVIDENCE",
        "DESKTOP",
        "IDENTITY_CHECK",
    ),
    "4 Agent retains five exact bindings": (
        "WAVE3B_04_AGENT_BINDINGS",
        "AGENTS",
        "DESKTOP",
        "IDENTITY_CHECK",
    ),
    "5 Workflow task edge and lifecycle Evidence survive": (
        "WAVE3B_05_WORKFLOW_EVIDENCE",
        "WORKFLOWS",
        "DESKTOP",
        "EVIDENCE_CHAIN",
    ),
    "6 Runtime remains declaration-only": (
        "WAVE3B_06_RUNTIME_DECLARATION",
        "RUNTIMES",
        "DESKTOP",
        "IDENTITY_CHECK",
    ),
    "7 Knowledge routine precedes advanced": (
        "WAVE3B_07_KNOWLEDGE_HIERARCHY",
        "KNOWLEDGE",
        "DESKTOP",
        "HIERARCHY_CHECK",
    ),
    "WAVE3B_08_NAVIGATION": (
        "WAVE3B_08_NAVIGATION",
        "WORKFLOWS",
        "DESKTOP",
        "NAVIGATION",
    ),
    "WAVE3B_08_MAKE_STALE": (
        "WAVE3B_08_MAKE_STALE",
        "WORKFLOWS",
        "DESKTOP",
        "STALE_PREPARATION",
    ),
    "WAVE3B_08_CONFLICT_WRITE": (
        "WAVE3B_08_CONFLICT_WRITE",
        "WORKFLOWS",
        "DESKTOP",
        "CONFLICT_WRITE",
    ),
    "WAVE3B_08_ERROR_UI": (
        "WAVE3B_08_ERROR_UI",
        "WORKFLOWS",
        "DESKTOP",
        "ERROR_STATE",
    ),
    "WAVE3B_08_AUTHORITATIVE_READBACK": (
        "WAVE3B_08_AUTHORITATIVE_READBACK",
        "WORKFLOWS",
        "DESKTOP",
        "AUTHORITATIVE_READBACK",
    ),
    "WAVE3B_08_EXPLICIT_RECOVERY": (
        "WAVE3B_08_EXPLICIT_RECOVERY",
        "WORKFLOWS",
        "DESKTOP",
        "EXPLICIT_RECOVERY",
    ),
    "WAVE3B_08_FINAL_ASSERTION": (
        "WAVE3B_08_FINAL_ASSERTION",
        "WORKFLOWS",
        "DESKTOP",
        "STATE_CHECK",
    ),
    "9 denied and absent are nondisclosing": (
        "WAVE3B_09_BOUNDED_DISCLOSURE",
        "EVIDENCE",
        "DESKTOP",
        "DISCLOSURE_CHECK",
    ),
    "10 unavailable backend shows no false success": (
        "WAVE3B_10_BACKEND_UNAVAILABLE",
        "EVIDENCE",
        "DESKTOP",
        "SERVICE_AVAILABILITY",
    ),
    "WAVE3B_11_ENTER_TECHNICAL_PAGE": (
        "WAVE3B_11_ENTER_TECHNICAL_PAGE",
        "EVIDENCE",
        "DESKTOP",
        "NAVIGATION",
    ),
    "WAVE3B_11_RESTART_READINESS": (
        "WAVE3B_11_RESTART_READINESS",
        "EVIDENCE",
        "DESKTOP",
        "RESTART_READINESS",
    ),
    "WAVE3B_11_RELOAD": (
        "WAVE3B_11_RELOAD",
        "EVIDENCE",
        "DESKTOP",
        "RELOAD",
    ),
    "WAVE3B_11_REVISION_IDENTITY_CHECK": (
        "WAVE3B_11_REVISION_IDENTITY_CHECK",
        "EVIDENCE",
        "DESKTOP",
        "IDENTITY_CHECK",
    ),
    "WAVE3B_12_MOBILE_NAVIGATION": (
        "WAVE3B_12_MOBILE_NAVIGATION",
        "EVIDENCE",
        "MOBILE",
        "NAVIGATION",
    ),
    "WAVE3B_12_OPEN_EVIDENCE": (
        "WAVE3B_12_OPEN_EVIDENCE",
        "EVIDENCE",
        "MOBILE",
        "OPEN_EVIDENCE",
    ),
    "WAVE3B_12_CLOSE_FOCUS_CHECK": (
        "WAVE3B_12_CLOSE_FOCUS_CHECK",
        "EVIDENCE",
        "MOBILE",
        "FOCUS_CHECK",
    ),
    "WAVE3B_12_CLOSE_ACTION": (
        "WAVE3B_12_CLOSE_ACTION",
        "EVIDENCE",
        "MOBILE",
        "CLOSE_ACTION",
    ),
    "WAVE3B_12_CLAIM_FOCUS_RESTORED": (
        "WAVE3B_12_CLAIM_FOCUS_RESTORED",
        "EVIDENCE",
        "MOBILE",
        "FOCUS_CHECK",
    ),
    "WAVE3B_12_USER_FOCUS_TRANSFER_SETUP": (
        "WAVE3B_12_USER_FOCUS_TRANSFER_SETUP",
        "EVIDENCE",
        "MOBILE",
        "FOCUS_TRANSFER_SETUP",
    ),
    "WAVE3B_12_USER_FOCUS_TRANSFER": (
        "WAVE3B_12_USER_FOCUS_TRANSFER",
        "EVIDENCE",
        "MOBILE",
        "FOCUS_TRANSFER",
    ),
    "WAVE3B_12_USER_FOCUS_PRESERVED": (
        "WAVE3B_12_USER_FOCUS_PRESERVED",
        "EVIDENCE",
        "MOBILE",
        "FOCUS_CHECK",
    ),
}
UNIFIED_PRODUCT_STEP_IDS = {
    "UNIFIED_01_PROBLEM_GAP": ("WORK", "DESKTOP", "STATE_CHECK"),
    "UNIFIED_02_AGENT_PUBLISH": ("AGENTS", "DESKTOP", "LIFECYCLE_CHECK"),
    "UNIFIED_03_EMPLOYEE_INPUT_CONTRACT": (
        "EMPLOYEES",
        "DESKTOP",
        "INPUT_CHECK",
    ),
    "UNIFIED_03_EMPLOYEE_CREATE": ("EMPLOYEES", "DESKTOP", "CREATE"),
    "UNIFIED_03_EMPLOYEE_VALIDATE": ("EMPLOYEES", "DESKTOP", "VALIDATE"),
    "UNIFIED_03_EMPLOYEE_APPROVE": ("EMPLOYEES", "DESKTOP", "APPROVE"),
    "UNIFIED_03_EMPLOYEE_PUBLISH": ("EMPLOYEES", "DESKTOP", "PUBLISH"),
    "UNIFIED_03_AGENT_AUTHORITY_ASSERTIONS": (
        "AGENTS",
        "DESKTOP",
        "IDENTITY_CHECK",
    ),
    "UNIFIED_04_AGENT_MATCHING": ("WORK", "DESKTOP", "MATCHING_CHECK"),
    "UNIFIED_05_CATALOG": ("CATALOG", "DESKTOP", "IDENTITY_CHECK"),
    "UNIFIED_06_RELATIONSHIPS": ("CATALOG", "DESKTOP", "RELATIONSHIP_CHECK"),
    "UNIFIED_07_EMPLOYEE_MANAGEMENT": ("EMPLOYEES", "DESKTOP", "IDENTITY_CHECK"),
    "UNIFIED_08_RESTART_READBACK": ("EMPLOYEES", "DESKTOP", "RESTART_READINESS"),
}
DIAGNOSTIC_STEP_IDS = {
    **{
        step_id: (route, viewport, _primary_action_class(step_id))
        for step_id, (route, viewport) in PRIMARY_STEP_IDS.items()
    },
    **{
        step_id: (route, viewport, action)
        for step_id, route, viewport, action in WAVE_3B_STEP_IDS.values()
    },
    **UNIFIED_PRODUCT_STEP_IDS,
}
ACTION_CLASSES = frozenset(
    {"UNKNOWN", *(identity[2] for identity in DIAGNOSTIC_STEP_IDS.values())}
)


def _step_identity(scenario: str, title: object):
    if not isinstance(title, str):
        return None
    if scenario == "PLATFORM_PRIMARY_RESPONSIVE_FOCUS":
        identity = PRIMARY_STEP_IDS.get(title)
        if identity is None:
            return None
        route, viewport = identity
        return title, route, viewport, _primary_action_class(title)
    if scenario == "WAVE_3B_REAL_SERVICE_JOURNEYS":
        return WAVE_3B_STEP_IDS.get(title)
    if scenario == "UNIFIED_PRODUCT_ASSEMBLY_DURABLE_JOURNEY":
        identity = UNIFIED_PRODUCT_STEP_IDS.get(title)
        return (title, *identity) if identity is not None else None
    return None


def step_diagnostic(failure_context: object, scenario: str) -> dict[str, object] | None:
    if not isinstance(failure_context, tuple) or len(failure_context) != 4:
        return None
    suite, spec, _test, result = failure_context
    if not all(isinstance(value, dict) for value in failure_context):
        return None
    mapped = FIRST_FAILURE_ASSERTION_IDS.get(
        (Path(str(suite.get("file", ""))).name, spec.get("title"))
    )
    if mapped != scenario or scenario not in {
        "PLATFORM_PRIMARY_RESPONSIVE_FOCUS",
        "WAVE_3B_REAL_SERVICE_JOURNEYS",
        "UNIFIED_PRODUCT_ASSEMBLY_DURABLE_JOURNEY",
    }:
        return None
    steps = result.get("steps")
    if not isinstance(steps, list):
        return None
    completed = 0
    last = failed = None
    for step in steps:
        if not isinstance(step, dict):
            return None
        identity = _step_identity(scenario, step.get("title"))
        if identity is None:
            return None
        step_id, route, viewport, action = identity
        duration = step.get("duration")
        item = {
            "routeKey": route,
            "viewportKey": viewport,
            "stepId": step_id,
            "actionClass": action,
            "elapsedMs": duration
            if type(duration) is int and 0 <= duration <= 3600000
            else None,
        }
        if step.get("error"):
            failed = item
            break
        completed += 1
        last = item
    elapsed = result.get("duration")
    return {
        "failedStep": failed,
        "lastCompletedStep": last,
        "completedStepCount": completed,
        "elapsedMs": elapsed
        if type(elapsed) is int and 0 <= elapsed <= 3600000
        else None,
        "timeoutKind": "SCENARIO" if result.get("status") == "timedOut" else "UNKNOWN",
    }


def validate_step_diagnostic(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {
        "failedStep",
        "lastCompletedStep",
        "completedStepCount",
        "elapsedMs",
        "timeoutKind",
    }:
        raise ValueError("step diagnostic schema violation")
    if value["timeoutKind"] not in {"SCENARIO", "NAVIGATION", "ASSERTION", "UNKNOWN"}:
        raise ValueError("step timeout violation")
    if type(value["completedStepCount"]) is not int or not 0 <= value[
        "completedStepCount"
    ] <= len(DIAGNOSTIC_STEP_IDS):
        raise ValueError("step count violation")
    for item in (value, value["failedStep"], value["lastCompletedStep"]):
        if item is None:
            continue
        if not isinstance(item, dict):
            raise ValueError("step schema violation")
        duration = item.get("elapsedMs")
        if duration is not None and (
            type(duration) is not int or not 0 <= duration <= 3600000
        ):
            raise ValueError("step duration violation")
        if item is value:
            continue
        if set(item) != {
            "routeKey",
            "viewportKey",
            "stepId",
            "actionClass",
            "elapsedMs",
        } or DIAGNOSTIC_STEP_IDS.get(item["stepId"]) != (
            item["routeKey"],
            item["viewportKey"],
            item["actionClass"],
        ):
            raise ValueError("step identity violation")


def summary_counts(report: dict[str, object]) -> dict[str, int | None]:
    unknown = dict.fromkeys(SUMMARY_COUNT_FIELDS)
    counts = dict.fromkeys(SUMMARY_COUNT_FIELDS, 0)
    for _, spec in _ordered_specs(report.get("suites")):
        tests = spec.get("tests")
        if not isinstance(tests, list) or not tests:
            return unknown
        for test in tests:
            if not isinstance(test, dict) or not isinstance(test.get("results"), list):
                return unknown
            status = test.get("status")
            if status not in {"expected", "unexpected", "skipped", "flaky"}:
                return unknown
            results = test["results"]
            if any(
                not isinstance(r, dict)
                or r.get("status")
                not in {"passed", "failed", "timedOut", "interrupted", "skipped"}
                for r in results
            ):
                return unknown
            if not results and status != "skipped":
                return unknown
            if status != "skipped" and not any(
                r["status"] != "skipped" for r in results
            ):
                return unknown
            counts["selected"] += 1
            counts["executed"] += int(any(r["status"] != "skipped" for r in results))
            counts[
                {
                    "expected": "passed",
                    "unexpected": "failed",
                    "skipped": "skipped",
                    "flaky": "flaky",
                }[status]
            ] += 1
    stats = report.get("stats")
    if not counts["selected"] or not isinstance(stats, dict):
        return unknown
    for source, target in (
        ("expected", "passed"),
        ("unexpected", "failed"),
        ("skipped", "skipped"),
        ("flaky", "flaky"),
    ):
        if type(stats.get(source)) is not int or stats[source] != counts[target]:
            return unknown
    if any(value > MAX_DIAGNOSTIC_COUNT for value in counts.values()):
        return unknown
    return counts


def build_failure_summary(
    stdout: bytes,
    failure: dict[str, object],
    identity: dict[str, object],
    failure_context: object = _FAILURE_CONTEXT_UNSET,
) -> dict[str, object]:
    validate_first_failure_record(failure)
    scenario = failure["firstFailureAssertionId"]
    mapping = next(
        (
            key
            for key, value in FIRST_FAILURE_ASSERTION_IDS.items()
            if value == scenario
        ),
        None,
    )
    report = _browser_json(stdout) or {}
    context = (
        first_failure_context(report)
        if failure_context is _FAILURE_CONTEXT_UNSET
        else failure_context
    )
    line = None
    if mapping:
        for suite, spec in _ordered_specs(report.get("suites")):
            if (Path(str(suite.get("file", ""))).name, spec.get("title")) == mapping:
                candidate = spec.get("line")
                if type(candidate) is int and 1 <= candidate <= MAX_DIAGNOSTIC_COUNT:
                    line = candidate
                break
    summary = {
        "schemaVersion": 1,
        "scenarioId": scenario,
        "spec": f"console/frontend/tests/e2e/{mapping[0]}" if mapping else None,
        "sourceLine": line,
        "locationKind": "TEST_DECLARATION" if line is not None else "UNKNOWN",
        "failureCategory": failure["failureCategory"],
        "failureSubtype": failure["failureSubtype"],
        "actionClass": "UNKNOWN",
        "restartCountClass": failure["restartCountClass"],
        "restartCountScope": "SUITE_CUMULATIVE",
        "counts": summary_counts(report),
        "buildModeIdentity": identity["buildModeIdentity"],
        "frontendManifestDigest": identity["frontendManifestDigest"],
    }
    diagnostic = step_diagnostic(context, str(scenario))
    if diagnostic is not None:
        validate_step_diagnostic(diagnostic)
        summary["stepDiagnostic"] = diagnostic
        if diagnostic["failedStep"] is not None:
            summary["actionClass"] = diagnostic["failedStep"]["actionClass"]
    return summary


def encode_failure_summary(summary: dict[str, object]) -> str:
    if (
        set(summary) not in (SUMMARY_FIELDS, SUMMARY_FIELDS | {"stepDiagnostic"})
        or type(summary["schemaVersion"]) is not int
        or summary["schemaVersion"] != 1
    ):
        raise ValueError("summary schema violation")
    if "stepDiagnostic" in summary:
        validate_step_diagnostic(summary["stepDiagnostic"])
    scenario = summary["scenarioId"]
    mapping = next(
        (
            key
            for key, value in FIRST_FAILURE_ASSERTION_IDS.items()
            if value == scenario
        ),
        None,
    )
    if mapping is None and scenario != "NOT_RETAINED":
        raise ValueError("summary identity violation")
    if summary["spec"] != (
        f"console/frontend/tests/e2e/{mapping[0]}" if mapping else None
    ):
        raise ValueError("summary path violation")
    line = summary["sourceLine"]
    if line is not None and (
        mapping is None
        or type(line) is not int
        or not 1 <= line <= MAX_DIAGNOSTIC_COUNT
    ):
        raise ValueError("summary location violation")
    if summary["locationKind"] != (
        "TEST_DECLARATION" if line is not None else "UNKNOWN"
    ):
        raise ValueError("summary location violation")
    if (
        summary["failureCategory"] not in FAILURE_CATEGORIES
        or summary["failureSubtype"] not in FAILURE_SUBTYPES
        or summary["actionClass"] not in ACTION_CLASSES
    ):
        raise ValueError("summary category violation")
    diagnostic = summary.get("stepDiagnostic")
    expected_action = (
        diagnostic["failedStep"]["actionClass"]
        if isinstance(diagnostic, dict) and diagnostic.get("failedStep") is not None
        else "UNKNOWN"
    )
    if summary["actionClass"] != expected_action:
        raise ValueError("summary action identity violation")
    if summary["restartCountScope"] != "SUITE_CUMULATIVE" or summary[
        "restartCountClass"
    ] not in {"NONE", "ONE_OR_MORE", "UNKNOWN"}:
        raise ValueError("summary restart scope violation")
    counts = summary["counts"]
    if not isinstance(counts, dict) or set(counts) != SUMMARY_COUNT_FIELDS:
        raise ValueError("summary counts violation")
    if not all(v is None for v in counts.values()):
        if any(
            type(v) is not int or not 0 <= v <= MAX_DIAGNOSTIC_COUNT
            for v in counts.values()
        ):
            raise ValueError("summary counts violation")
        if (
            counts["selected"]
            != counts["passed"] + counts["failed"] + counts["skipped"] + counts["flaky"]
            or counts["executed"] > counts["selected"]
        ):
            raise ValueError("summary counts mismatch")
    if (
        summary["buildModeIdentity"] != "LIVE_DEMO"
        or not isinstance(summary["frontendManifestDigest"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", summary["frontendManifestDigest"])
    ):
        raise ValueError("summary build identity violation")
    encoded = json.dumps(
        summary, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    if len((SUMMARY_PREFIX + encoded).encode()) > 4096:
        raise ValueError("summary size violation")
    return encoded


def emit_failure_summary(
    stdout: bytes,
    failure: dict[str, object],
    identity: dict[str, object],
    failure_context: object = _FAILURE_CONTEXT_UNSET,
) -> None:
    # Only the new optional log channel is best-effort. Existing scanners and
    # cleanup remain outside this exception boundary and retain their gates.
    try:
        encoded = encode_failure_summary(
            build_failure_summary(stdout, failure, identity, failure_context)
        )
        print(SUMMARY_PREFIX + encoded, file=sys.stderr, flush=True)
    except Exception:
        with suppress(Exception):
            print(
                SUMMARY_PREFIX + '{"diagnosticState":"DIAGNOSTIC_GAP"}',
                file=sys.stderr,
                flush=True,
            )


def release_manifest(root: Path) -> dict[str, dict[str, str | int]]:
    result: dict[str, dict[str, str | int]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        entry: dict[str, str | int] = {"mode": stat.S_IMODE(path.lstat().st_mode)}
        if path.is_symlink():
            entry.update(type="symlink", target=os.readlink(path))
        elif path.is_dir():
            entry["type"] = "directory"
        elif path.is_file():
            entry.update(
                type="file", sha256=hashlib.sha256(path.read_bytes()).hexdigest()
            )
        else:
            entry["type"] = "other"
        result[relative] = entry
    return result


def assert_immutable(root: Path) -> None:
    writable = [
        str(path)
        for path in (root, *root.rglob("*"))
        if not path.is_symlink() and path.stat().st_mode & 0o222
    ]
    if writable:
        raise RuntimeError(f"release tree is writable by mode: {writable[0]}")


def endpoint(value: str, name: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https", "postgresql", "postgres"}
        or not parsed.hostname
        or not parsed.port
    ):
        raise ValueError(f"{name} must include an explicit scheme, host and port")
    return value


def verify_postgres_role_readiness(postgres_url: str, expected_role: str) -> None:
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", expected_role):
        raise RuntimeError("PostgreSQL validation role identity is invalid")
    schema_name = f"acceptance_preflight_{secrets.token_hex(8)}"
    try:
        with psycopg.connect(postgres_url) as connection:
            identity = connection.execute(
                "SELECT current_user, session_user"
            ).fetchone()
            if identity != (expected_role, expected_role):
                raise RuntimeError("PostgreSQL validation role identity mismatch")
            schema = sql.Identifier(schema_name)
            table = sql.Identifier(schema_name, "migration_read_write_probe")
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
            connection.execute(
                sql.SQL(
                    "CREATE TABLE {} (id INTEGER PRIMARY KEY, state TEXT NOT NULL)"
                ).format(table)
            )
            connection.execute(
                sql.SQL("INSERT INTO {} (id, state) VALUES (1, 'CREATED')").format(
                    table
                )
            )
            row = connection.execute(
                sql.SQL("SELECT state FROM {} WHERE id = 1").format(table)
            ).fetchone()
            if row != ("CREATED",):
                raise RuntimeError("PostgreSQL validation role read check failed")
            connection.execute(
                sql.SQL("UPDATE {} SET state = 'UPDATED' WHERE id = 1").format(table)
            )
            connection.execute(sql.SQL("DELETE FROM {} WHERE id = 1").format(table))
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(schema))
            connection.rollback()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("PostgreSQL validation role readiness failed") from exc


STARTUP_EXCEPTION_TYPES = frozenset(
    {
        "RuntimeError",
        "ValueError",
        "OSError",
        "PermissionError",
        "FileNotFoundError",
        "ModuleNotFoundError",
        "ImportError",
        "SyntaxError",
        "ConnectionRefusedError",
        "ConnectionResetError",
        "TimeoutError",
        "OperationalError",
        "InterfaceError",
        "URLError",
        "HTTPError",
        "CalledProcessError",
        "TimeoutExpired",
        "AssertionError",
    }
)


def startup_exception_type(exc: BaseException) -> str:
    name = type(exc).__name__
    return name if name in STARTUP_EXCEPTION_TYPES else "UNKNOWN"


class StartupStderr:
    """Discard raw stderr while retaining bounded static classifications."""

    LINE_LIMIT = 4096
    RECORD_LIMIT = 32

    def __init__(self, release: Path):
        self.release = release
        self.lock = threading.Lock()
        self.exceptions: list[str] = []
        self.locations: list[dict[str, str | int]] = []
        self.truncated = False
        self.eof = threading.Event()
        self.read_error = False

    def consume_line(self, line: bytes) -> None:
        text = line.decode("utf-8", errors="replace")
        exception = re.match(r"^(?:[a-zA-Z_][\w]*\.)*([A-Za-z_][\w]*):", text)
        if exception and exception[1] in STARTUP_EXCEPTION_TYPES:
            with self.lock:
                if len(self.exceptions) < self.RECORD_LIMIT:
                    self.exceptions.append(exception[1])
        frame = re.fullmatch(r'\s*File "([^"]+)", line (\d+), in ([\w<>]+)\s*', text)
        if frame:
            try:
                path = Path(frame[1]).resolve()
                relative = path.relative_to(self.release)
                if path.suffix != ".py" or "site-packages" in relative.parts:
                    return
                source = path.read_text(encoding="utf-8")
                functions = {"<module>"} | {
                    node.name
                    for node in ast.walk(ast.parse(source))
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                if frame[3] not in functions or not 1 <= int(frame[2]) <= len(
                    source.splitlines()
                ):
                    return
                location = {
                    "file": relative.as_posix(),
                    "function": frame[3],
                    "line": int(frame[2]),
                }
                with self.lock:
                    if len(self.locations) < self.RECORD_LIMIT:
                        self.locations.append(location)
            except (OSError, ValueError, SyntaxError):
                pass

    def drain(self, stream: BinaryIO) -> None:
        pending = bytearray()
        dropping = False
        try:
            while chunk := stream.read1(self.LINE_LIMIT):
                for byte in chunk:
                    if byte == 10:
                        if not dropping:
                            self.consume_line(bytes(pending))
                        pending.clear()
                        dropping = False
                    elif not dropping:
                        if len(pending) < self.LINE_LIMIT:
                            pending.append(byte)
                        else:
                            pending.clear()
                            dropping = True
                            self.truncated = True
            if pending and not dropping:
                self.consume_line(bytes(pending))
        except Exception:
            self.read_error = True
        finally:
            stream.close()
            self.eof.set()

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            return {
                "exceptionTypes": list(self.exceptions),
                "locations": list(self.locations),
                "classification": "CLASSIFIED" if self.exceptions else "UNKNOWN",
                "oversizedLineDiscarded": self.truncated,
                "eof": self.eof.is_set(),
                "readError": self.read_error,
            }


class Harness:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.release = args.release_root.resolve()
        self.runtime = args.runtime_dir.resolve()
        self.runtime.mkdir(parents=True, exist_ok=False)
        if self.runtime == self.release or self.release in self.runtime.parents:
            raise RuntimeError("runtime directory must be outside the release")
        self.token = secrets.token_urlsafe(32)
        self.child: subprocess.Popen[bytes] | None = None
        self.child_started_ns = 0
        self.startup_records: list[dict[str, object]] = []
        self.startup_stderr: StartupStderr | None = None
        self.stderr_thread: threading.Thread | None = None
        self.health_error_class = "NONE"
        self.socket_path = self.runtime / "control.sock"
        self.metadata_path = self.runtime / "backend.json"
        caches = [
            path
            for path in self.release.rglob("*")
            if path.name == "__pycache__" or path.suffix == ".pyc"
        ]
        if caches:
            raise RuntimeError(f"release already contains Python cache: {caches[0]}")
        self.before = release_manifest(self.release)
        self.before_digest = self.manifest_digest(self.before)
        self.restart_count = 0
        (self.runtime / "release-manifest-before.json").write_text(
            json.dumps(self.before, indent=2, sort_keys=True), encoding="utf-8"
        )
        assert_immutable(self.release)

    @property
    def url(self) -> str:
        return f"http://{self.args.backend_host}:{self.args.backend_port}"

    @staticmethod
    def manifest_digest(manifest: dict[str, dict[str, str | int]]) -> str:
        encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def assert_port_free(self) -> None:
        with socket.socket() as connection_probe:
            connection_probe.settimeout(0.2)
            if (
                connection_probe.connect_ex(
                    (self.args.backend_host, self.args.backend_port)
                )
                == 0
            ):
                raise RuntimeError(
                    "backend port is occupied by an unowned process: "
                    f"{self.args.backend_host}:{self.args.backend_port}"
                )
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((self.args.backend_host, self.args.backend_port))
            except OSError as exc:
                raise RuntimeError(
                    "backend port is occupied by an unowned process: "
                    f"{self.args.backend_host}:{self.args.backend_port}"
                ) from exc

    def write_metadata(self) -> None:
        assert self.child is not None
        payload = {
            "schemaVersion": 1,
            "ownershipToken": self.token,
            "supervisorPid": os.getpid(),
            "backendPid": self.child.pid,
            "backendStartTimeNs": self.child_started_ns,
            "backendHost": self.args.backend_host,
            "backendPort": self.args.backend_port,
            "backendUrl": self.url,
            "releaseRoot": str(self.release),
            "runtimeDir": str(self.runtime),
            "controlSocket": str(self.socket_path),
        }
        temporary = self.metadata_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        temporary.replace(self.metadata_path)

    def wait_health(self, expected: bool, timeout: float = 20) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            healthy = False
            try:
                with urllib.request.urlopen(
                    f"{self.url}/healthz", timeout=0.5
                ) as response:
                    healthy = response.status == 200
            except Exception as exc:
                reason = getattr(exc, "reason", exc)
                self.health_error_class = startup_exception_type(reason)
            if healthy is expected:
                return
            time.sleep(0.1)
        raise RuntimeError(f"backend health did not become {expected}")

    def start(self, overrides: dict[str, str] | None = None) -> None:
        self.health_error_class = "NONE"
        try:
            self._start(overrides)
        except BaseException as exc:
            self.record_startup("STARTUP_FAILED", exc)
            raise
        self.record_startup("STARTUP_READY")

    def _start(self, overrides: dict[str, str] | None = None) -> None:
        self.assert_port_free()
        env = os.environ.copy()
        python_paths = [
            str((self.release / entry).resolve())
            for entry in self.args.python_path.split(os.pathsep)
        ]
        env.update(
            {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPYCACHEPREFIX": str(self.runtime / "pycache"),
                "AGENT_DEFINITION_DATABASE_URL": self.args.postgres_url,
                "SKILL_MCP_DATABASE_URL": self.args.postgres_url,
                "KNOWLEDGE_DATABASE_URL": self.args.postgres_url,
                "WORKFLOW_RUNTIME_DATABASE_URL": self.args.postgres_url,
                "EXECUTION_DATABASE_URL": self.args.postgres_url,
                "KNOWLEDGE_QDRANT_URL": self.args.qdrant_url,
                "S5_IMPL_041_QDRANT_URL": self.args.qdrant_url,
                "S5_HARNESS_OWNERSHIP_TOKEN": self.token,
                "PYTHONPATH": os.pathsep.join(python_paths),
            }
        )
        allowed = {
            "S5_PLANNING_PROVIDER",
            "S5_PLANNING_BASE_URL",
            "S5_PLANNING_API_KEY",
            "S5_PLANNING_MODEL",
            "S5_EMBEDDING_PROVIDER",
            "S5_EMBEDDING_BASE_URL",
            "S5_EMBEDDING_API_KEY",
            "S5_EMBEDDING_MODEL",
        }
        for key, value in (overrides or {}).items():
            if key not in allowed or not isinstance(value, str):
                raise RuntimeError("unsupported backend environment override")
            if key.endswith("BASE_URL"):
                parsed = urlparse(value)
                if (
                    parsed.scheme != "http"
                    or parsed.hostname
                    not in {
                        "127.0.0.1",
                        "localhost",
                    }
                    or not parsed.port
                ):
                    raise RuntimeError("test provider URL must be explicit localhost")
            env[key] = value
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "agent_console.app:app",
            "--host",
            self.args.backend_host,
            "--port",
            str(self.args.backend_port),
            "--header",
            f"X-Harness-Ownership-Token:{self.token}",
        ]
        self.child = subprocess.Popen(
            command,
            cwd=self.release,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self.startup_stderr = StartupStderr(self.release)
        assert self.child.stderr is not None
        self.stderr_thread = threading.Thread(
            target=self.startup_stderr.drain, args=(self.child.stderr,), daemon=True
        )
        self.stderr_thread.start()
        self.child_started_ns = time.time_ns()
        self.write_metadata()
        self.wait_health(True)

    def verify_owned(self) -> None:
        if self.child is None or self.child.poll() is not None:
            raise RuntimeError("owned backend is not running")
        metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        expected = (
            self.token,
            self.child.pid,
            str(self.release),
            self.args.backend_port,
            os.getpid(),
            self.child_started_ns,
        )
        actual = (
            metadata.get("ownershipToken"),
            metadata.get("backendPid"),
            metadata.get("releaseRoot"),
            metadata.get("backendPort"),
            metadata.get("supervisorPid"),
            metadata.get("backendStartTimeNs"),
        )
        if actual != expected:
            raise RuntimeError("backend ownership metadata mismatch")
        if Path(f"/proc/{self.child.pid}").exists():
            cwd = Path(f"/proc/{self.child.pid}/cwd").resolve()
            command = (
                Path(f"/proc/{self.child.pid}/cmdline")
                .read_bytes()
                .rstrip(b"\0")
                .split(b"\0")
            )
            joined = b" ".join(command)
            parent = re.search(
                r"^PPid:\s+(\d+)$",
                Path(f"/proc/{self.child.pid}/status").read_text(),
                re.MULTILINE,
            )
            if (
                cwd != self.release
                or b"uvicorn" not in joined
                or str(self.args.backend_port).encode() not in command
                or self.token.encode() not in joined
                or command != [os.fsencode(arg) for arg in self.child.args]
                or parent is None
                or parent[1] != str(os.getpid())
            ):
                raise RuntimeError("backend process identity mismatch")
        else:
            command = subprocess.run(
                ["ps", "-p", str(self.child.pid), "-o", "command="],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            cwd = subprocess.run(
                ["lsof", "-a", "-p", str(self.child.pid), "-d", "cwd", "-Fn"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            parent = subprocess.run(
                ["ps", "-p", str(self.child.pid), "-o", "ppid="],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            if (
                "uvicorn" not in command
                or self.token not in command
                or str(self.args.backend_port) not in command
                or f"n{self.release}" not in cwd
                or parent.strip() != str(os.getpid())
                or shlex.split(command) != list(self.child.args)
            ):
                raise RuntimeError(
                    "backend executable, command, cwd, token, or parent mismatch"
                )

    def stop(self) -> None:
        self.record_startup("CLEANUP_ENTER")
        try:
            self._stop()
        except BaseException as exc:
            self.record_startup("CLEANUP_FAILED", exc)
            raise
        if (
            self.stderr_thread is not None
            and self.child is not None
            and self.child.poll() is not None
        ):
            self.stderr_thread.join(timeout=1)
        self.record_startup("CLEANUP_COMPLETE")

    def _stop(self) -> None:
        if self.child is None or self.child.poll() is not None:
            return
        self.verify_owned()
        self.child.terminate()
        try:
            self.child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.verify_owned()
            self.child.kill()
            self.child.wait(timeout=5)
        self.wait_health(False)

    def record_startup(self, phase: str, exc: BaseException | None = None) -> None:
        """Evidence failures cannot replace the failure being diagnosed."""
        try:
            code = self.child.poll() if self.child is not None else None
            record: dict[str, object] = {
                "phase": phase,
                "backendCreated": self.child is not None,
                "backendAlive": self.child is not None and code is None,
                "backendExitCode": code
                if code is not None
                else "NOT_EXITED"
                if self.child is not None
                else "NOT_CREATED",
                "exceptionType": startup_exception_type(exc) if exc else "NONE",
                "healthErrorClass": self.health_error_class,
                "stderr": self.startup_stderr.snapshot()
                if self.startup_stderr
                else {"classification": "UNKNOWN"},
                "locations": [],
            }
            tb = exc.__traceback__ if exc else None
            while tb and len(record["locations"]) < 16:
                if (
                    tb.tb_frame.f_code.co_filename == __file__
                    and tb.tb_frame.f_code.co_name
                    in {
                        "start",
                        "_start",
                        "stop",
                        "_stop",
                        "wait_health",
                        "verify_owned",
                        "write_metadata",
                        "assert_port_free",
                    }
                ):
                    record["locations"].append(
                        {
                            "file": "scripts/acceptance/isolated_browser_harness.py",
                            "function": tb.tb_frame.f_code.co_name,
                            "line": tb.tb_lineno,
                        }
                    )
                tb = tb.tb_next
            if len(self.startup_records) < 64:
                self.startup_records.append(record)
            self.write_startup_diagnostics()
        except Exception:
            pass

    def write_startup_diagnostics(
        self, primary: BaseException | None = None, cleanup: BaseException | None = None
    ) -> None:
        path = self.runtime / "startup-diagnostics.json"
        temporary = path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as output:
            json.dump(
                {
                    "schemaVersion": 1,
                    "events": self.startup_records,
                    "primaryExceptionType": startup_exception_type(primary)
                    if primary
                    else "NONE",
                    "cleanupExceptionType": startup_exception_type(cleanup)
                    if cleanup
                    else "NONE",
                },
                output,
            )
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)

    def restart(self, overrides: dict[str, str] | None = None) -> None:
        self.stop()
        self.start(overrides)
        self.restart_count += 1

    def serve(self, ready: threading.Event) -> None:
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(self.socket_path))
            os.chmod(self.socket_path, 0o600)
            server.listen()
            ready.set()
            while True:
                connection, _ = server.accept()
                with connection:
                    request = json.loads(connection.recv(65536))
                    if request.get("ownershipToken") != self.token:
                        response = {"ok": False, "error": "ownership token mismatch"}
                    elif request.get("action") == "restart":
                        try:
                            self.restart(request.get("environment"))
                            response = {
                                "ok": True,
                                "backendPid": self.child.pid,
                                "backendStartTimeNs": self.child_started_ns,
                            }
                        except Exception as exc:
                            response = {"ok": False, "error": str(exc)}
                    elif request.get("action") == "status":
                        try:
                            self.verify_owned()
                            response = {
                                "ok": True,
                                "backendPid": self.child.pid,
                                "backendStartTimeNs": self.child_started_ns,
                            }
                        except Exception as exc:
                            response = {"ok": False, "error": str(exc)}
                    elif request.get("action") == "stop":
                        try:
                            self.stop()
                            response = {"ok": True}
                        except Exception as exc:
                            response = {"ok": False, "error": str(exc)}
                    elif request.get("action") == "start":
                        try:
                            if self.child is not None and self.child.poll() is None:
                                raise RuntimeError("owned backend is already running")
                            self.start(request.get("environment"))
                            response = {
                                "ok": True,
                                "backendPid": self.child.pid,
                                "backendStartTimeNs": self.child_started_ns,
                            }
                        except Exception as exc:
                            response = {"ok": False, "error": str(exc)}
                    else:
                        response = {"ok": False, "error": "unsupported action"}
                    connection.sendall(json.dumps(response).encode())

    def verify_release(self) -> dict[str, dict[str, str | int]]:
        after = release_manifest(self.release)
        (self.runtime / "release-manifest-after.json").write_text(
            json.dumps(after, indent=2, sort_keys=True), encoding="utf-8"
        )
        if after != self.before:
            raise RuntimeError(
                "immutable release content, file modes, or directory modes changed"
            )
        caches = [
            path
            for path in self.release.rglob("*")
            if path.name == "__pycache__" or path.suffix == ".pyc"
        ]
        if caches:
            raise RuntimeError(f"Python cache appeared inside release: {caches[0]}")
        return after

    def write_minimum_disclosure_evidence(
        self, after: dict[str, dict[str, str | int]], command_result: int
    ) -> Path:
        assert self.child is not None
        record = {
            "schemaVersion": 1,
            "acceptanceState": "PASSED" if command_result == 0 else "FAILED",
            "backendPid": self.child.pid,
            "backendStartTimeNs": self.child_started_ns,
            "backendRestartCount": self.restart_count,
            "releaseEntryCount": len(after),
            "releaseManifestBeforeDigest": self.before_digest,
            "releaseManifestAfterDigest": self.manifest_digest(after),
            "journeyId": self.args.journey_id,
            "phase": "BROWSER_EXECUTION",
            "assertionCategory": "BROWSER_ACCEPTANCE",
            "statusCode": command_result,
            "exceptionClass": (
                "NONE" if command_result == 0 else "BROWSER_COMMAND_FAILED"
            ),
            "correlationDigest": hashlib.sha256(
                (
                    f"{self.args.journey_id}:{command_result}:{self.restart_count}:"
                    f"{self.before_digest}:{self.manifest_digest(after)}"
                ).encode()
            ).hexdigest(),
            "restartRelation": (
                "NO_RESTART"
                if self.restart_count == 0
                else f"OWNED_RESTART_COUNT_{self.restart_count}"
            ),
            "completedAt": datetime.now(UTC).isoformat(),
        }
        evidence = extract_allowlisted(record, set(EVIDENCE_FIELDS))
        path = self.runtime / "acceptance-evidence.json"
        path.write_text(json.dumps(evidence, sort_keys=True), encoding="utf-8")
        return path


def parse_args() -> argparse.Namespace:
    parser = SafeArgumentParser()
    parser.add_argument("--release-root", required=True, type=Path)
    parser.add_argument("--runtime-dir", required=True, type=Path)
    parser.add_argument("--backend-host", required=True)
    parser.add_argument("--backend-port", required=True, type=int)
    parser.add_argument("--frontend-port", required=True, type=int)
    postgres = parser.add_mutually_exclusive_group(required=True)
    postgres.add_argument("--postgres-url")
    postgres.add_argument("--postgres-url-file", type=Path)
    parser.add_argument("--postgres-validation-role", required=True)
    parser.add_argument("--qdrant-url", required=True)
    parser.add_argument("--build-mode-identity", required=True, type=Path)
    parser.add_argument("--journey-id", required=True)
    parser.add_argument("--python-path", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command[:1] == ["--"]:
        args.command = args.command[1:]
    if not args.command:
        parser.error("a browser command is required after --")
    if args.postgres_url_file is not None:
        if stat.S_IMODE(args.postgres_url_file.stat().st_mode) != 0o600:
            parser.error("PostgreSQL credential file mode must be 0600")
        args.postgres_url = args.postgres_url_file.read_text(encoding="utf-8")
    args.postgres_url = endpoint(args.postgres_url, "PostgreSQL endpoint")
    args.qdrant_url = endpoint(args.qdrant_url, "Qdrant endpoint")
    return args


def main() -> int:
    args = parse_args()
    print("harness phase: ARGUMENTS", file=sys.stderr)
    build_identity = verify_build_identity(
        args.release_root.resolve() / "console/frontend/dist",
        args.build_mode_identity.resolve(),
    )
    print("harness phase: BUILD_IDENTITY", file=sys.stderr)
    verify_postgres_role_readiness(args.postgres_url, args.postgres_validation_role)
    print("harness phase: POSTGRES_ROLE", file=sys.stderr)
    harness = Harness(args)
    print("harness phase: CANDIDATE", file=sys.stderr)
    command_result = 1
    primary_error: BaseException | None = None
    try:
        harness.start()
        print("harness phase: BACKEND", file=sys.stderr)
        ready = threading.Event()
        threading.Thread(target=harness.serve, args=(ready,), daemon=True).start()
        ready.wait(timeout=5)
        env = os.environ.copy()
        env.update(
            {
                "S5_HARNESS_METADATA": str(harness.metadata_path),
                "S5_HARNESS_OWNERSHIP_TOKEN": harness.token,
                "CONSOLE_BACKEND_URL": harness.url,
                "VITE_BACKEND_URL": harness.url,
                "CONSOLE_FRONTEND_PORT": str(args.frontend_port),
                "KNOWLEDGE_QDRANT_DIRECT_URL": args.qdrant_url,
                "S5_IMMUTABLE_ACCEPTANCE": "1",
                "PLAYWRIGHT_OUTPUT_DIR": str(harness.runtime / "playwright-output"),
                "S5_HARNESS_PYTHON": sys.executable,
                "KNOWLEDGE_STRUCTURED_REPORT_PATH": str(
                    harness.runtime / "knowledge-operation-result.json"
                ),
            }
        )
        browser_result = subprocess.run(
            args.command,
            cwd=harness.release,
            env=env,
            capture_output=True,
            check=False,
        )
        command_result = browser_result.returncode
        if command_result == 0 and not verify_browser_report(browser_result.stdout):
            command_result = 1
        print("harness phase: BROWSER_COMMAND", file=sys.stderr)
        if command_result:
            category = sanitized_browser_failure_class(
                browser_result.stdout, browser_result.stderr
            )
            print(f"browser acceptance failed: {category}", file=sys.stderr)
            report = _browser_json(browser_result.stdout)
            failure_context = (
                first_failure_context(report) if report is not None else None
            )
            failure = sanitized_first_failure_record(
                browser_result.stdout,
                args.journey_id,
                harness.restart_count,
                (
                    (harness.runtime / "knowledge-operation-result.json").read_bytes()
                    if (harness.runtime / "knowledge-operation-result.json").is_file()
                    else None
                ),
                failure_context,
            )
            if failure is None:
                failure = sanitized_first_failure_record(
                    json.dumps({"stats": {"unexpected": 1}}).encode(),
                    args.journey_id,
                    harness.restart_count,
                )
            failure_path = harness.runtime / "browser-first-failure.json"
            failure_path.write_text(
                json.dumps(failure, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            scan_generated_artifacts([failure_path])
            emit_failure_summary(
                browser_result.stdout,
                failure,
                build_identity,
                failure_context,
            )
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        cleanup_error: BaseException | None = None
        try:
            harness.stop()
        except BaseException as exc:
            cleanup_error = exc
        try:
            playwright_output = harness.runtime / "playwright-output"
            if playwright_output.exists():
                shutil.rmtree(playwright_output)
            structured_report = harness.runtime / "knowledge-operation-result.json"
            if structured_report.exists():
                structured_report.unlink()
            if playwright_output.exists():
                raise RuntimeError("raw browser artifacts were retained")
            after = harness.verify_release()
            evidence = harness.write_minimum_disclosure_evidence(after, command_result)
            scan_generated_artifacts([args.build_mode_identity, evidence])
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc
        try:
            harness.write_startup_diagnostics(primary_error, cleanup_error)
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc
        if primary_error is None and cleanup_error is not None:
            raise cleanup_error
    return command_result


if __name__ == "__main__":
    print("harness phase: MODULE", file=sys.stderr)
    try:
        raise SystemExit(main())
    except Exception as exc:
        safe_class = (
            "PREFLIGHT_FAILURE"
            if isinstance(exc, (RuntimeError, ValueError))
            else "INTERNAL_FAILURE"
        )
        print(f"isolated browser acceptance failed: {safe_class}", file=sys.stderr)
        raise SystemExit(2) from None
