from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityScope
from agent_console.execution_preparation import initial_progress
from agent_console.workbench_current_work_projection import project_runs
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from test_execution_preparation import preparation


def setup(monkeypatch, *, state="RUNNING", cancelled=False):
    from agent_console import workbench_current_work_projection as module

    p = preparation()
    now = datetime.now(UTC)
    progress = initial_progress(p).model_copy(
        update={
            "state": state,
            "cancellation_request_id": "cancel:one" if cancelled else None,
        }
    )
    call = SimpleNamespace(
        context=SimpleNamespace(
            principal_id="human:alice",
            scope=AuthorityScope(p.namespace, p.security_domain),
        ),
        connection=None,
        authority=None,
    )
    row = dict(
        preparation=p.model_dump(mode="json"),
        digest=p.digest,
        workflow_run_id=p.run_id,
        progress=progress.model_dump(mode="json"),
        progress_version=progress.version,
        outcome_version=None,
        business_resolution=None,
        read_at=now,
        questions=[
            dict(
                questionKey="q",
                questionDigest="a" * 64,
                answerDigest=None,
                answered=False,
                expiresAt=(now + timedelta(minutes=1)).isoformat(),
            )
        ],
        origins=[
            dict(
                conversationId="private-bob",
                ownerId="human:bob",
                schemaVersion=1,
                journeyMatches=True,
            ),
            dict(
                conversationId="own-alice",
                ownerId="human:alice",
                schemaVersion=1,
                journeyMatches=False,
            ),
        ],
        title="测试交接",
        created_at=now,
        initiators=["human:alice"],
        artifact_count=0,
        business_problem_id=p.semantics.target.problem.resource_id,
        problem_revision_id=p.semantics.target.problem.revision_id,
        problem_digest=p.semantics.target.problem.digest,
    )
    monkeypatch.setattr(
        module, "readable_grants", lambda call, grants: tuple(True for _ in grants)
    )
    return call, row


def test_ordinary_user_does_not_inherit_native_or_foreign_conversation_access(
    monkeypatch,
):
    call, row = setup(monkeypatch)
    item = project_runs(call, [row], verified_administrator=False)[0]
    assert item.pendingQuestionCount is None and item.questionsDigest is None
    assert item.originConversationId == "own-alice" and not item.originVerified
    assert item.businessResolution is None


@pytest.mark.parametrize(
    "state,cancelled,expected",
    [
        ("RUNNING", False, 1),
        ("RUNNING", True, 0),
        ("CANCEL_REQUESTED", True, 0),
        ("SUCCEEDED", False, 0),
    ],
)
def test_question_counts_respect_current_run_and_cancel_state(
    monkeypatch, state, cancelled, expected
):
    call, row = setup(monkeypatch, state=state, cancelled=cancelled)
    item = project_runs(call, [row], verified_administrator=True)[0]
    assert item.pendingQuestionCount == expected
    assert item.originConversationId == "private-bob" and item.originVerified
    assert (item.displayState == "waiting") == bool(expected)


def test_denied_native_resource_hides_question_metadata(monkeypatch):
    from agent_console import workbench_current_work_projection as module

    call, row = setup(monkeypatch)
    monkeypatch.setattr(
        module, "readable_grants", lambda call, grants: tuple(False for _ in grants)
    )
    item = project_runs(call, [row], verified_administrator=True)[0]
    assert item.pendingQuestionCount is None and item.questionsDigest is None


def test_mismatched_answer_is_not_accepted_as_resolved_question(monkeypatch):
    call, row = setup(monkeypatch)
    row["questions"][0].update(answered=True, answerDigest="b" * 64)
    with pytest.raises(
        WorkbenchOwnerError, match="CURRENT_WORK_QUESTION_IDENTITY_MISMATCH"
    ):
        project_runs(call, [row], verified_administrator=True)


def test_evaluation_denial_hides_resolution_without_reading_evidence(monkeypatch):
    from agent_console import workbench_current_work_projection as module

    call, row = setup(monkeypatch, state="SUCCEEDED")
    row.update(outcome_version=1, business_resolution="CONFIRMED_SOLVED")
    monkeypatch.setattr(
        module, "readable_grants", lambda call, grants: tuple(False for _ in grants)
    )

    def must_not_read(*args):
        raise AssertionError("Denied evaluation must not read evidence")

    monkeypatch.setattr(module, "PreparedResultReview", must_not_read)
    value = project_runs(call, [row], verified_administrator=False)[0]
    assert value.businessResolution is None and value.outcomeVersion is None
    assert value.executionState == "SUCCEEDED"


def test_changed_progress_during_evidence_check_rejects_mixed_snapshot(monkeypatch):
    from agent_console import workbench_current_work_projection as module

    call, row = setup(monkeypatch, state="SUCCEEDED")
    row.update(outcome_version=1, business_resolution="UNDETERMINED")
    monkeypatch.setattr(
        module,
        "PreparedResultReview",
        lambda *args: SimpleNamespace(
            snapshot=lambda p: {"runVersion": row["progress_version"] + 1}
        ),
    )
    with pytest.raises(WorkbenchOwnerError, match="CURRENT_WORK_SNAPSHOT_CHANGED"):
        project_runs(call, [row], verified_administrator=True)


def test_count_projection_does_not_read_or_disclose_outcome_evidence(monkeypatch):
    from agent_console import workbench_current_work_projection as module

    call, row = setup(monkeypatch, state="SUCCEEDED")
    row.update(outcome_version=1, business_resolution="CONFIRMED_SOLVED")
    checked = []

    def permissions(call, grants):
        checked.extend(grants)
        return tuple(True for _ in grants)

    def must_not_read(*args):
        raise AssertionError("Off-page outcome evidence was read")

    monkeypatch.setattr(module, "readable_grants", permissions)
    monkeypatch.setattr(module, "PreparedResultReview", must_not_read)
    value = project_runs(
        call, [row], verified_administrator=True, include_outcomes=False
    )[0]
    assert value.executionState == "SUCCEEDED"
    assert value.businessResolution is None and value.outcomeVersion is None
    assert value.pendingQuestionCount == 0
    assert all(grant.owner != "EVALUATION" for grant in checked)


@pytest.mark.parametrize(
    "state,expected",
    [
        ("PENDING", "running"),
        ("RUNNING", "unknown"),
        ("CANCEL_REQUESTED", "unknown"),
        ("RECOVERY_REQUIRED", "unknown"),
    ],
)
def test_unreadable_questions_do_not_imply_confirmed_running(
    monkeypatch, state, expected
):
    call, row = setup(monkeypatch, state=state)
    result = project_runs(call, [row], verified_administrator=False)[0]
    assert result.displayState == expected
    assert result.pendingQuestionCount is None
