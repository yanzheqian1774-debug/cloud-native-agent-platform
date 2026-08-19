#!/usr/bin/env python3

import json
import sys
from datetime import datetime
from pathlib import Path

tmp = Path(sys.argv[1])

passed = 0
failed = 0


def load(name):
    with open(tmp / name, encoding="utf-8") as file:
        return json.load(file)


def check(label, actual, expected):
    global passed, failed

    if actual == expected:
        print(f"PASS  {label}")
        passed += 1
        return

    print(f"FAIL  {label}")
    print(f"      expected: {expected!r}")
    print(f"      actual:   {actual!r}")
    failed += 1


def check_true(label, condition, detail=None):
    global passed, failed

    if condition:
        print(f"PASS  {label}")
        passed += 1
        return

    print(f"FAIL  {label}")

    if detail is not None:
        print(f"      detail: {detail!r}")

    failed += 1


def input_sources(spec):
    raw_sources = spec.get("input", {}).get("from", [])
    sources = []

    for source in raw_sources:
        if isinstance(source, str):
            sources.append(source)
        elif isinstance(source, dict):
            task_name = source.get("task")
            if task_name:
                sources.append(task_name)
        else:
            raise TypeError(f"Unsupported input.from entry: {source!r}")

    return sources


def task_index(task_list):
    result = {}

    for task in task_list.get("items", []):
        logical_name = (
            task.get("metadata", {}).get("labels", {}).get("agentos.io/workflow-task")
        )

        if logical_name:
            result[logical_name] = task

    return result


def node_index(detail):
    return {node["name"]: node for node in detail.get("nodes", [])}


def stable_workflow(resource):
    return {
        "resourceVersion": (resource.get("metadata", {}).get("resourceVersion")),
        "spec": resource.get("spec"),
        "status": resource.get("status"),
    }


def stable_tasks(resource):
    normalized = []

    for item in resource.get("items", []):
        normalized.append(
            {
                "name": item["metadata"]["name"],
                "resourceVersion": (item["metadata"].get("resourceVersion")),
                "spec": item.get("spec"),
                "status": item.get("status"),
            }
        )

    return sorted(
        normalized,
        key=lambda item: item["name"],
    )


def parse_time(value):
    if not value:
        return None

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


success_workflow_before = load("success-workflow-before.json")
success_workflow_after = load("success-workflow-after.json")

failed_workflow_before = load("failed-workflow-before.json")
failed_workflow_after = load("failed-workflow-after.json")

success_tasks_before = load("success-tasks-before.json")
success_tasks_after = load("success-tasks-after.json")

failed_tasks_before = load("failed-tasks-before.json")
failed_tasks_after = load("failed-tasks-after.json")

workflow_list = load("workflow-list.json")
success_api = load("success-api.json")
failed_api = load("failed-api.json")

success_nodes = node_index(success_api)
failed_nodes = node_index(failed_api)

success_tasks = task_index(success_tasks_before)
failed_tasks = task_index(failed_tasks_before)

success_spec = {task["name"]: task for task in success_workflow_before["spec"]["tasks"]}

failed_spec = {task["name"]: task for task in failed_workflow_before["spec"]["tasks"]}

failed_workflow_states = failed_workflow_before.get("status", {}).get("tasks", {})


print()
print("=== A. Workflow Projection ===")

items = workflow_list.get("items", [])

for workflow, api in (
    (success_workflow_before, success_api),
    (failed_workflow_before, failed_api),
):
    name = workflow["metadata"]["name"]
    namespace = workflow["metadata"]["namespace"]

    summary = next(
        (
            item
            for item in items
            if item.get("name") == name and item.get("namespace") == namespace
        ),
        None,
    )

    check_true(
        f"{name} exists in workflow list",
        summary is not None,
    )

    check(
        f"{name} detail phase",
        api.get("phase"),
        workflow.get("status", {}).get("phase"),
    )

    check(
        f"{name} detail taskCount",
        api.get("taskCount"),
        workflow.get("status", {}).get("taskCount"),
    )

    if summary:
        check(
            f"{name} list phase",
            summary.get("phase"),
            workflow.get("status", {}).get("phase"),
        )

        check(
            f"{name} list taskCount",
            summary.get("taskCount"),
            workflow.get("status", {}).get("taskCount"),
        )


print()
print("=== B. Success DAG Semantics ===")

check(
    "success DAG nodes",
    sorted(success_nodes),
    sorted(success_spec),
)

expected_edges = []

for node_name, spec in success_spec.items():
    for source in spec.get("dependsOn", []):
        expected_edges.append((source, node_name, "control"))

    for source in input_sources(spec):
        expected_edges.append((source, node_name, "data"))

actual_edges = [
    (
        edge["source"],
        edge["target"],
        edge["type"],
    )
    for edge in success_api.get("edges", [])
]

check(
    "control/data edge semantics",
    actual_edges,
    expected_edges,
)

for node_name, spec in success_spec.items():
    node = success_nodes[node_name]

    check(
        f"{node_name} dependsOn",
        node.get("dependsOn", []),
        spec.get("dependsOn", []),
    )

    check(
        f"{node_name} inputFrom",
        node.get("inputFrom", []),
        input_sources(spec),
    )


print()
print("=== C. Success Execution Evidence ===")

for node_name, spec in success_spec.items():
    node = success_nodes[node_name]
    execution = node["execution"]
    task = success_tasks.get(node_name)

    check_true(
        f"{node_name} Task CR exists",
        task is not None,
    )

    if task is None:
        continue

    status = task.get("status", {})

    check(
        f"{node_name} agent",
        node.get("agent", {}).get("name"),
        spec.get("agentRef", {}).get("name"),
    )

    check(
        f"{node_name} taskRef",
        execution.get("taskRef"),
        task["metadata"]["name"],
    )

    check(
        f"{node_name} declaredInput",
        execution.get("declaredInput"),
        spec.get("input", {}).get("prompt", ""),
    )

    check(
        f"{node_name} resolvedInput",
        execution.get("resolvedInput"),
        task.get("spec", {}).get("input", {}).get("prompt"),
    )

    for field in (
        "phase",
        "result",
        "attempts",
        "startedAt",
        "completedAt",
    ):
        check(
            f"{node_name} {field}",
            execution.get(field),
            status.get(field),
        )


print()
print("=== D. Upstream Results / Fan-In ===")

for node_name in ("builder", "tester", "reviewer"):
    sources = input_sources(success_spec[node_name])

    projected = {
        item["task"]: item["result"]
        for item in (success_nodes[node_name]["execution"].get("upstreamResults", []))
    }

    check(
        f"{node_name} upstream source set",
        sorted(projected),
        sorted(sources),
    )

    for source in sources:
        source_result = success_tasks[source].get("status", {}).get("result")

        check(
            f"{node_name} upstream result from {source}",
            projected.get(source),
            source_result,
        )


reviewer_runtime_input = (
    success_tasks["reviewer"].get("spec", {}).get("input", {}).get("prompt", "")
)

for source in ("builder", "tester"):
    source_result = success_tasks[source].get("status", {}).get("result", "")

    check_true(
        f"reviewer runtime input contains {source} result",
        bool(source_result) and source_result in reviewer_runtime_input,
    )


print()
print("=== E. Parallel / Fan-In Timing ===")

builder_status = success_tasks["builder"]["status"]
tester_status = success_tasks["tester"]["status"]
reviewer_status = success_tasks["reviewer"]["status"]

builder_started = parse_time(builder_status.get("startedAt"))
builder_completed = parse_time(builder_status.get("completedAt"))

tester_started = parse_time(tester_status.get("startedAt"))
tester_completed = parse_time(tester_status.get("completedAt"))

reviewer_started = parse_time(reviewer_status.get("startedAt"))

check_true(
    "builder and tester timing exists",
    all(
        (
            builder_started,
            builder_completed,
            tester_started,
            tester_completed,
        )
    ),
)

if all(
    (
        builder_started,
        builder_completed,
        tester_started,
        tester_completed,
    )
):
    check_true(
        "builder and tester execution overlaps",
        (builder_started < tester_completed and tester_started < builder_completed),
    )

if reviewer_started and builder_completed:
    check_true(
        "reviewer starts after builder",
        reviewer_started >= builder_completed,
    )

if reviewer_started and tester_completed:
    check_true(
        "reviewer starts after tester",
        reviewer_started >= tester_completed,
    )


print()
print("=== F. Failure / Skip Semantics ===")

check(
    "failed DAG contains declared nodes",
    sorted(failed_nodes),
    sorted(failed_spec),
)

builder_task = failed_tasks["builder"]
builder_status = builder_task.get("status", {})
builder_execution = failed_nodes["builder"]["execution"]

for field in (
    "phase",
    "result",
    "reason",
    "message",
    "retryable",
    "attempts",
    "startedAt",
    "completedAt",
):
    check(
        f"failed builder {field}",
        builder_execution.get(field),
        builder_status.get(field),
    )

reviewer_state = failed_workflow_states["reviewer"]
reviewer_execution = failed_nodes["reviewer"]["execution"]

check(
    "reviewer has no Task CR",
    "reviewer" in failed_tasks,
    False,
)

for field in ("phase", "reason", "message"):
    check(
        f"skipped reviewer {field}",
        reviewer_execution.get(field),
        reviewer_state.get(field),
    )

for field in (
    "taskRef",
    "resolvedInput",
    "result",
    "attempts",
    "startedAt",
    "completedAt",
    "retryable",
):
    check(
        f"skipped reviewer {field} is null",
        reviewer_execution.get(field),
        None,
    )


print()
print("=== G. Read-Only Source of Truth ===")

check(
    "success Workflow unchanged",
    stable_workflow(success_workflow_after),
    stable_workflow(success_workflow_before),
)

check(
    "success Tasks unchanged",
    stable_tasks(success_tasks_after),
    stable_tasks(success_tasks_before),
)

check(
    "failed Workflow unchanged",
    stable_workflow(failed_workflow_after),
    stable_workflow(failed_workflow_before),
)

check(
    "failed Tasks unchanged",
    stable_tasks(failed_tasks_after),
    stable_tasks(failed_tasks_before),
)


print()
print("============================================================")
print(f"PASS: {passed}")
print(f"FAIL: {failed}")
print("============================================================")

if failed:
    print("CONSOLE REAL WORKFLOW E2E: FAIL")
    sys.exit(1)

print("CONSOLE REAL WORKFLOW E2E: PASS")
