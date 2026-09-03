from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from agent_console.execution_domain import ScopeIdentity
from agent_console.workflow_control_application import (
    EffectState,
    TrustedPrincipal,
    WorkflowControlApplicationError,
    WorkflowControlApplicationService,
    minimum_disclosure_evidence,
    terminal_outcome,
)
from agent_console.workflow_control_domain import (
    AtomicCommandType,
    InterventionTarget,
    PlanCorrection,
    WorkflowControlOperation,
    WorkflowControlOperationResult,
)


class Store:
    def __init__(self) -> None:
        self.calls = 0
        self.results = {}

    def persist_operation(self, operation, *, authorized):
        assert authorized
        self.calls += 1
        old = self.results.get(operation.idempotency_key)
        if old is not None:
            digest, result = old
            if digest != operation.payload_digest:
                raise RuntimeError("IDEMPOTENCY_PAYLOAD_MISMATCH")
            return replace(result, replayed=True)
        target = next(x for x in operation.target.values() if x)
        result = WorkflowControlOperationResult(
            False,
            operation.command_type,
            operation.control_command_id,
            target,
            operation.target_expected_version + 1,
            operation.intervention_id,
            evidence_ids=tuple(
                x["evidence_record_id"] for x in operation.evidence_records
            ),
            outcome_ids=tuple(x["outcome_id"] for x in operation.outcome_records),
        )
        self.results[operation.idempotency_key] = (operation.payload_digest, result)
        return result

    def lookup_idempotency(self, scope, actor_id, command_type, key):
        return self.results.get(key)

    def read_linked_evidence(self, scope, intervention_id):
        return next(iter(self.results.values()))[1].evidence_ids

    def read_linked_outcomes(self, scope, intervention_id):
        return next(iter(self.results.values()))[1].outcome_ids


def operation(kind=AtomicCommandType.REQUEST_INTERVENTION, **changes):
    now = datetime.now(UTC)
    evidence = minimum_disclosure_evidence(
        evidence_id="evidence-1",
        workflow_id="run-1",
        task_id="task-1",
        execution_id="attempt-1",
        attempt_ordinal=1,
        event_ordinal=1,
        event_type="HUMAN_INTERVENTION",
        category="CONTROL",
        reason_code="AUTHORIZED",
        occurred_at=now,
    )
    values = dict(
        scope=ScopeIdentity("tenant", "domain"),
        command_type=kind,
        actor_id="actor",
        idempotency_key="key-1",
        payload={"action": kind.value},
        control_command_id="command-1",
        requested_at=now,
        retain_until=now + timedelta(days=30),
        target=InterventionTarget(workflow_run_id="run-1"),
        target_expected_version=1,
        intervention_id="intervention-1",
        evidence_records=(evidence,),
    )
    values.update(changes)
    return WorkflowControlOperation(**values)


def principal(*permissions):
    return TrustedPrincipal(
        "actor", ScopeIdentity("tenant", "domain"), frozenset(permissions)
    )


def test_authorization_precedes_persistence_and_effect() -> None:
    store = Store()
    with pytest.raises(WorkflowControlApplicationError, match="NOT_AUTHORIZED"):
        WorkflowControlApplicationService(store).execute(principal(), operation())
    assert store.calls == 0


def test_all_closed_commands_map_to_the_durable_uow_and_replay() -> None:
    for kind in AtomicCommandType:
        store = Store()
        current = operation(
            kind,
            idempotency_key=f"key-{kind.value}",
            control_command_id=f"command-{kind.value}",
        )
        if kind is AtomicCommandType.CORRECT_PLAN:
            current = replace(
                current,
                correction=PlanCorrection(
                    "correction",
                    "plan",
                    1,
                    "plan",
                    2,
                    "actor",
                    "HUMAN",
                    "BUSINESS_CORRECTION",
                    {"objective": "corrected"},
                    datetime.now(UTC),
                ),
            )
        if kind is AtomicCommandType.COMPLETE_EXECUTION_WITH_OUTCOME:
            current = replace(
                current,
                terminal_state="SUCCEEDED",
                outcome_records=(
                    terminal_outcome(
                        outcome_id="outcome-1",
                        target_id="run-1",
                        terminal_state="SUCCEEDED",
                        classification="SUCCESS",
                    ),
                ),
            )
        first = WorkflowControlApplicationService(store).execute(
            principal(kind), current
        )
        replay = WorkflowControlApplicationService(store).execute(
            principal(kind), current
        )
        assert first.effect_state is EffectState.NOT_APPLICABLE
        assert replay.durable.replayed is True


def test_conflicting_replay_is_rejected() -> None:
    store = Store()
    service = WorkflowControlApplicationService(store)
    current = operation()
    service.execute(principal(current.command_type), current)
    with pytest.raises(RuntimeError, match="IDEMPOTENCY_PAYLOAD_MISMATCH"):
        service.execute(
            principal(current.command_type),
            replace(current, payload={"action": "different"}),
        )


def test_business_correction_is_bounded_and_history_is_supplied_to_uow() -> None:
    current = operation(
        AtomicCommandType.CORRECT_PLAN,
        correction=PlanCorrection(
            "correction",
            "plan",
            1,
            "plan",
            2,
            "actor",
            "HUMAN",
            "BUSINESS_CORRECTION",
            {"objective": "corrected"},
            datetime.now(UTC),
        ),
    )
    WorkflowControlApplicationService(Store()).execute(
        principal(current.command_type), current
    )
    bad = replace(
        current,
        idempotency_key="key-2",
        correction=replace(
            current.correction, normalized_correction={"database_record": "edit"}
        ),
    )
    with pytest.raises(
        WorkflowControlApplicationError, match="CORRECTION_FIELD_NOT_ALLOWED"
    ):
        WorkflowControlApplicationService(Store()).execute(
            principal(current.command_type), bad
        )


def test_outcome_is_only_allowed_for_real_terminal_completion() -> None:
    current = operation(
        outcome_records=(
            terminal_outcome(
                outcome_id="outcome",
                target_id="run-1",
                terminal_state="SUCCEEDED",
                classification="SUCCESS",
            ),
        )
    )
    with pytest.raises(WorkflowControlApplicationError, match="PREMATURE_OUTCOME"):
        WorkflowControlApplicationService(Store()).execute(
            principal(current.command_type), current
        )


def test_protected_and_unbounded_business_input_is_rejected() -> None:
    for payload in ({"raw_prompt": "hidden"}, {"objective": "x" * 2001}):
        current = operation(payload=payload)
        with pytest.raises(WorkflowControlApplicationError):
            WorkflowControlApplicationService(Store()).execute(
                principal(current.command_type), current
            )


def test_effect_runs_only_after_durable_readback_and_failure_is_truthful() -> None:
    events = []

    class OrderedStore(Store):
        def lookup_idempotency(self, *args):
            events.append("readback")
            return super().lookup_idempotency(*args)

    class Effect:
        def apply(self, request):
            events.append("effect")
            return "observation-1"

    current = operation(runtime_command_id="runtime-command")
    ordered_store = OrderedStore()
    ordered_service = WorkflowControlApplicationService(ordered_store)
    result = ordered_service.execute(
        principal(current.command_type), current, effect=Effect()
    )
    assert events == ["readback", "effect"]
    assert result.effect_state is EffectState.OBSERVED

    replay = ordered_service.execute(
        principal(current.command_type),
        current,
        effect=Effect(),
    )
    assert replay.effect_state is EffectState.AUTHORIZED_PENDING
    assert events == ["readback", "effect", "readback"]

    class BrokenEffect:
        def apply(self, request):
            raise RuntimeError("private provider detail")

    with pytest.raises(WorkflowControlApplicationError, match="RECOVERY_REQUIRED"):
        WorkflowControlApplicationService(Store()).execute(
            principal(current.command_type),
            replace(current, idempotency_key="key-failure"),
            effect=BrokenEffect(),
        )


def test_persistence_or_readback_failure_never_calls_effect() -> None:
    calls = []

    class BrokenStore(Store):
        def persist_operation(self, operation, *, authorized):
            raise RuntimeError("PERSISTENCE_FAILED")

    class Effect:
        def apply(self, request):
            calls.append(request)
            return "observation"

    current = operation()
    with pytest.raises(RuntimeError, match="PERSISTENCE_FAILED"):
        WorkflowControlApplicationService(BrokenStore()).execute(
            principal(current.command_type), current, effect=Effect()
        )
    assert calls == []
