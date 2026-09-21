"""Accepted D324 retry, cancellation and static dependency behavior."""

import hashlib
import json
from pathlib import Path

import pytest
from agent_console.execution_preparation import (
    ArtifactDocument,
    ExecutionPreparation,
    ExecutionPreparationError,
    ProgressEvent,
    initial_progress,
    transition,
)
from pydantic import ValidationError


def preparation():
    raw = json.loads(
        (
            Path(__file__).parents[2] / "frontend/tests/e2e/fixtures/cost323.json"
        ).read_text()
    )
    semantics = raw["semantics"]
    ref = {"resource_id": "controlled", "revision_id": "1", "digest": "a" * 64}
    return ExecutionPreparation.model_validate(
        {
            "namespace": "controlled-324",
            "security_domain": "isolated",
            "plan_id": "cost",
            "plan_version": 3,
            "plan_digest": "b" * 64,
            "approval_id": "approval",
            "root_assignment_id": "root",
            "root_instance_id": "root-instance",
            "semantics": semantics,
            "source_snapshot": ref,
            "synthetic": True,
            "execution_boundary": "ISOLATED_SYNTHETIC_READ_ONLY",
            "participants": [
                {
                    "task_id": t["task_id"],
                    "assignment_id": "assignment:" + t["task_id"],
                    "instance_id": "analyst",
                    "definition": ref,
                    "skill": {
                        "kind": "SKILL",
                        "reference": ref,
                        "owner_observation": "published",
                        "input_schema_digest": "c" * 64,
                        "output_schema_digest": "d" * 64,
                        "operation": t["operation"],
                    },
                    "executor_id": "cost-readonly",
                    "executor_revision": "1",
                    "executor_digest": "e" * 64,
                    "agent_instance_id": "agent",
                    "runtime_instance_id": "native",
                    "runtime_generation": 1,
                    "profile": ref,
                }
                for t in semantics["tasks"]
            ],
        }
    )


def emit(p, s, action, task="t1-read", attempt="attempt:1", artifacts=()):
    return transition(
        p,
        s,
        ProgressEvent(
            action=action,
            task_id=task,
            attempt_id=attempt,
            evidence_id=f"evidence:{s.version}",
            artifact_ids=artifacts,
        ),
    )


def states(s):
    return {t.task_id: t.state for t in s.tasks}


def succeed(p, s, task):
    s = emit(p, s, "QUEUE", task, task + ":1")
    s = emit(p, s, "STARTED", task, task + ":1")
    return emit(p, s, "SUCCEEDED", task, task + ":1", ("artifact:" + task,))


def test_six_tasks_follow_exact_dependencies_and_one_preparation_identity():
    p = preparation()
    s = initial_progress(p)
    assert [k for k, v in states(s).items() if v == "READY"] == ["t1-read"]
    for task in [
        "t1-read",
        "t2-validate",
        "t3-summarize",
        "t4-analyze",
        "t5-recommend",
        "t6-report",
    ]:
        assert states(s)[task] == "READY"
        s = succeed(p, s, task)
    assert s.state == "SUCCEEDED"
    with pytest.raises(ExecutionPreparationError, match="TERMINAL_IMMUTABLE"):
        emit(p, s, "RETRY")


def test_retry_wait_blocks_descendants_until_final_failure_without_resurrection():
    p = preparation()
    s = emit(p, initial_progress(p), "QUEUE")
    s = emit(p, s, "FAILED")
    assert s.state == "RUNNING"
    assert states(s)["t1-read"] == "RETRY_WAIT"
    assert states(s)["t2-validate"] == "WAITING"
    s = emit(p, s, "RETRY", attempt="attempt:2")
    s = emit(p, s, "FAILED", attempt="attempt:2")
    assert s.state == "FAILED"
    assert states(s)["t1-read"] == "FINAL_FAILED"
    assert all(v == "SKIPPED" for k, v in states(s).items() if k != "t1-read")
    with pytest.raises(ExecutionPreparationError, match="TERMINAL_IMMUTABLE"):
        emit(p, s, "RETRY", attempt="attempt:3")


def test_declining_retry_finalizes_before_skipping_descendants():
    p = preparation()
    s = emit(p, emit(p, initial_progress(p), "QUEUE"), "FAILED")
    assert "SKIPPED" not in states(s).values()
    assert emit(p, s, "FINALIZE_FAILURE").state == "FAILED"


def test_unknown_never_redispatches_and_cancel_needs_request_and_ack():
    p = preparation()
    s = emit(p, emit(p, initial_progress(p), "QUEUE"), "STARTED")
    with pytest.raises(ExecutionPreparationError, match="TRANSITION_REJECTED"):
        emit(p, s, "STOP_CONFIRMED")
    s = emit(p, s, "UNKNOWN")
    assert s.state == "RECOVERY_REQUIRED"
    with pytest.raises(ExecutionPreparationError, match="NOT_READY"):
        emit(p, s, "RETRY", attempt="attempt:2")
    s = emit(p, s, "REQUEST_CANCEL")
    assert s.state == "CANCEL_REQUESTED"
    assert states(s)["t1-read"] == "UNKNOWN"
    s = emit(p, s, "STOP_CONFIRMED")
    assert s.state == "CANCELLED"
    assert s.cancellation_request_id and all(t.stop_evidence for t in s.tasks)


def test_cancel_queued_task_is_not_assumed_stopped():
    p = preparation()
    s = emit(p, emit(p, initial_progress(p), "QUEUE"), "REQUEST_CANCEL")
    assert s.state == "CANCEL_REQUESTED"
    assert states(s)["t1-read"] == "QUEUED"


def test_success_requires_output_and_exact_attempt():
    p = preparation()
    s = emit(p, emit(p, initial_progress(p), "QUEUE"), "STARTED")
    with pytest.raises(ExecutionPreparationError, match="TRANSITION_REJECTED"):
        emit(p, s, "SUCCEEDED")
    with pytest.raises(ExecutionPreparationError, match="ATTEMPT_MISMATCH"):
        emit(p, s, "FAILED", attempt="foreign")


@pytest.mark.parametrize("change", ["cycle", "missing", "wrong-operation", "too-many"])
def test_invalid_graph_or_mapping_rejected_before_run(change):
    raw = preparation().model_dump(mode="json")
    if change == "cycle":
        raw["semantics"]["tasks"][0]["depends_on"] = ["t6-report"]
    elif change == "missing":
        raw["participants"].pop()
    elif change == "wrong-operation":
        raw["participants"][0]["skill"]["operation"] = "DELETE"
    else:
        raw["participants"] *= 6
    with pytest.raises(ValidationError):
        ExecutionPreparation.model_validate(raw)


def test_artifact_digest_and_utf8_bytes_are_checked():
    content = "中文" * 50000
    with pytest.raises(ValidationError, match="ARTIFACT_SIZE_OR_DIGEST_INVALID"):
        ArtifactDocument(
            artifact_id="a",
            task_id="t",
            attempt_id="attempt",
            kind="REPORT",
            schema_version="report.v1",
            content=content,
            digest=hashlib.sha256(content.encode()).hexdigest(),
        )
    with pytest.raises(ValidationError, match="ARTIFACT_SIZE_OR_DIGEST_INVALID"):
        ArtifactDocument(
            artifact_id="a",
            task_id="t",
            attempt_id="attempt",
            kind="REPORT",
            schema_version="report.v1",
            content="tampered",
            digest="a" * 64,
        )
