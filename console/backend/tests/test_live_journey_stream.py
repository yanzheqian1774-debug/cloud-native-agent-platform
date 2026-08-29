"""Contract, ordering, replay, bounds, and coordinator-authority tests."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest
from agent_console.live_journey import LiveJourneyCoordinator
from agent_console.live_journey_stream import (
    InMemoryJourneyEventBroker,
    JourneyResumeUnavailable,
    JourneyStreamFailure,
    JourneyStreamScope,
    JourneySubscriptionLimit,
    format_sse,
)
from agent_console.live_journey_stream_schemas import (
    JourneyEventEnvelope,
    JourneyEventPayload,
    serialize_envelope,
)
from test_live_journey import ExecutionAuthority, seed


def envelope(
    sequence: int,
    *,
    event_id: str | None = None,
    terminal: bool = False,
    journey_id: str = "journey:supplier-quality-1",
    occurred_at: datetime | None = None,
) -> JourneyEventEnvelope:
    identity = (
        LiveJourneyCoordinator()
        .register_live(seed(journey_id=journey_id))
        .successor.identity
    )
    return JourneyEventEnvelope(
        journeyId=journey_id,
        eventId=event_id or f"event:{sequence}",
        sequence=sequence,
        occurredAt=occurred_at or datetime.now(UTC),
        eventType="EXECUTION_SUCCEEDED" if terminal else "EXECUTION_STARTED",
        stage="EXECUTION",
        status="SUCCEEDED" if terminal else "STARTED",
        terminal=terminal,
        reasonCode="OBSERVED_TRANSITION",
        localizationKey="liveJourney.event.executionSucceeded"
        if terminal
        else "liveJourney.event.executionStarted",
        identity=identity,
        payload=JourneyEventPayload(revision=1),
    )


def scope(journey_id: str = "journey:supplier-quality-1") -> JourneyStreamScope:
    return JourneyStreamScope("tenant-a", "quality", journey_id)


def test_replay_is_exact_ordered_and_subsequent_to_cursor() -> None:
    broker = InMemoryJourneyEventBroker()
    events = (envelope(1), envelope(2), envelope(3, terminal=True))
    for event in events:
        broker.publish(event)
    subscription = broker.replay_and_subscribe(scope(), events[0].eventId)

    async def collect():
        received = []
        async for event in subscription.events():
            received.append(event)
            if event.terminal:
                break
        return received

    received = asyncio.run(collect())
    assert [item.sequence for item in received] == [2, 3]
    assert serialize_envelope(received[0]) == serialize_envelope(events[1])


def test_duplicate_gap_and_post_terminal_fail_closed() -> None:
    broker = InMemoryJourneyEventBroker()
    first = envelope(1)
    broker.publish(first)
    broker.publish(first)
    with pytest.raises(JourneyStreamFailure, match="CONFLICTING_EVENT_ID"):
        broker.publish(envelope(2, event_id=first.eventId))
    with pytest.raises(JourneyStreamFailure, match="EVENT_SEQUENCE_INVALID"):
        broker.publish(envelope(3))
    terminal = envelope(2, terminal=True)
    broker.publish(terminal)
    with pytest.raises(JourneyStreamFailure, match="EVENT_AFTER_TERMINAL"):
        broker.publish(envelope(3))


def test_expired_unknown_and_restart_lost_cursor_are_unavailable() -> None:
    expired = InMemoryJourneyEventBroker(retention=timedelta(seconds=1))
    expired.publish(envelope(1, occurred_at=datetime.now(UTC) - timedelta(minutes=2)))
    with pytest.raises(JourneyResumeUnavailable):
        expired.replay_and_subscribe(scope(), "event:1")
    with pytest.raises(JourneyResumeUnavailable):
        InMemoryJourneyEventBroker().replay_and_subscribe(scope(), "event:1")


def test_exact_journey_buffer_limit_fails_closed_without_scope_eviction() -> None:
    broker = InMemoryJourneyEventBroker()
    subscriptions = []
    for index in range(64):
        journey_id = f"journey:limit-{index}"
        broker.publish(envelope(1, journey_id=journey_id))
        subscriptions.append(broker.replay_and_subscribe(scope(journey_id), None))
    with pytest.raises(JourneyStreamFailure, match="JOURNEY_BUFFER_LIMIT"):
        broker.publish(envelope(1, journey_id="journey:limit-64"))
    assert len(broker._buffers) == 64
    assert all(len(item._replay) == 1 for item in subscriptions)
    for subscription in subscriptions:
        subscription.close()


def test_exact_event_retention_limit_evicts_oldest_without_partial_publish() -> None:
    now = datetime(2026, 8, 29, 1, 0, tzinfo=UTC)
    broker = InMemoryJourneyEventBroker(clock=lambda: now)
    broker.publish(envelope(1, occurred_at=now))
    subscription = broker.replay_and_subscribe(scope(), None)
    for sequence in range(2, 258):
        broker.publish(envelope(sequence, occurred_at=now))
    retained = tuple(broker._buffers[scope().key].events)
    assert len(retained) == 256
    assert (retained[0].sequence, retained[-1].sequence) == (2, 257)
    assert subscription._queue.qsize() == 256
    with pytest.raises(JourneyStreamFailure, match="SUBSCRIBER_BACKPRESSURE"):
        broker.publish(envelope(258, occurred_at=now))
    assert tuple(broker._buffers[scope().key].events) == retained
    subscription.close()


def test_exact_fifteen_minute_retention_boundary() -> None:
    now = datetime(2026, 8, 29, 1, 0, tzinfo=UTC)
    broker = InMemoryJourneyEventBroker(clock=lambda: now)
    retained_id = "journey:retained"
    expired_id = "journey:expired"
    broker.publish(
        envelope(
            1,
            journey_id=retained_id,
            occurred_at=now - timedelta(minutes=15) + timedelta(microseconds=1),
        )
    )
    broker.publish(
        envelope(
            1,
            journey_id=expired_id,
            occurred_at=now - timedelta(minutes=15),
        )
    )
    retained = broker.replay_and_subscribe(scope(retained_id), "event:1")
    retained.close()
    with pytest.raises(JourneyResumeUnavailable):
        broker.replay_and_subscribe(scope(expired_id), "event:1")


def test_exact_subscriber_limit_preserves_existing_subscribers() -> None:
    broker = InMemoryJourneyEventBroker()
    broker.publish(envelope(1))
    subscriptions = [broker.replay_and_subscribe(scope(), None) for _ in range(8)]
    with pytest.raises(JourneySubscriptionLimit):
        broker.replay_and_subscribe(scope(), None)
    assert len(broker._buffers[scope().key].subscribers) == 8
    for subscription in subscriptions:
        subscription.close()


def _payload_with_exact_size(target: int) -> JourneyEventPayload:
    for full_count in range(128):
        for tail_length in range(1, 200):
            values = ["x" * 200] * full_count + ["y" * tail_length]
            raw = {
                "revision": 1,
                "approvalId": None,
                "platformExecutionIdentity": None,
                "sharedSnapshotId": None,
                "graphSnapshotId": None,
                "evidenceIds": values[:64],
                "citationIds": values[64:128],
                "limitationCodes": [],
            }
            size = len(
                json.dumps(
                    raw,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            )
            if size == target:
                return JourneyEventPayload.model_validate(raw)
    raise AssertionError(f"unable to construct payload of {target} bytes")


def _envelope_with_exact_size(target: int) -> JourneyEventEnvelope:
    raw = envelope(1).model_dump(mode="json")
    for full_count in range(256):
        for tail_length in range(1, 200):
            raw["identity"]["evidenceIds"] = ["x" * 200] * full_count + [
                "y" * tail_length
            ]
            size = len(
                json.dumps(
                    raw,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            )
            if size == target:
                return JourneyEventEnvelope.model_validate(raw)
    raise AssertionError(f"unable to construct envelope of {target} bytes")


def test_exact_payload_envelope_and_text_boundaries() -> None:
    payload = _payload_with_exact_size(16 * 1024)
    assert (
        len(
            json.dumps(
                payload.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        )
        == 16 * 1024
    )
    oversized_payload = payload.model_dump(mode="json")
    target_list = oversized_payload["citationIds"] or oversized_payload["evidenceIds"]
    target_list[-1] += "z"
    with pytest.raises(ValueError, match="STREAM_PAYLOAD_TOO_LARGE"):
        JourneyEventPayload.model_validate(oversized_payload)

    exact_envelope = _envelope_with_exact_size(32 * 1024)
    assert len(serialize_envelope(exact_envelope).encode()) == 32 * 1024
    oversized_envelope = exact_envelope.model_dump(mode="json")
    oversized_envelope["identity"]["evidenceIds"][-1] += "z"
    with pytest.raises(ValueError, match="STREAM_ENVELOPE_TOO_LARGE"):
        JourneyEventEnvelope.model_validate(oversized_envelope)

    bounded = envelope(1).model_dump(mode="json")
    bounded.update(
        journeyId="j" * 200,
        eventId="e" * 200,
        reasonCode="r" * 200,
        localizationKey="k" * 200,
    )
    JourneyEventEnvelope.model_validate(bounded)
    JourneyEventPayload(limitationCodes=["c" * 200])
    for field in ("journeyId", "eventId", "reasonCode", "localizationKey"):
        with pytest.raises(ValueError):
            JourneyEventEnvelope.model_validate({**bounded, field: "x" * 201})
    with pytest.raises(ValueError):
        JourneyEventPayload(limitationCodes=["c" * 201])


def test_schema_bounds_utc_and_sse_frame_are_exact() -> None:
    event = envelope(1)
    frame = format_sse(event).decode()
    expected = (
        f"id: {event.eventId}\n"
        f"event: {event.eventType}\n"
        f"data: {serialize_envelope(event)}\n\n"
    )
    assert frame == expected
    with pytest.raises(ValueError):
        JourneyEventEnvelope.model_validate(
            {**event.model_dump(), "reasonCode": "x" * 201}
        )
    with pytest.raises(ValueError):
        JourneyEventEnvelope.model_validate(
            {**event.model_dump(), "occurredAt": "2026-08-29T01:00:00"}
        )
    with pytest.raises(ValueError):
        JourneyEventPayload(limitationCodes=["x" * 201])


def test_coordinator_publishes_only_observed_progress_before_execution_returns() -> (
    None
):
    broker = InMemoryJourneyEventBroker()

    class ObservingAuthority(ExecutionAuthority):
        def rerun(self, **request: str):
            subscription = broker.replay_and_subscribe(scope(), None)
            assert [event.eventType for event in subscription._replay][-2:] == [
                "EXECUTION_AUTHORIZED",
                "EXECUTION_STARTED",
            ]
            subscription.close()
            return super().rerun(**request)

    coordinator = LiveJourneyCoordinator(ObservingAuthority(), broker)
    coordinator.register_live(seed())
    principal = coordinator._system_principal(seed())
    current = coordinator.get(seed().journey_id, principal).successor
    pending = coordinator.correct(
        seed().journey_id,
        principal,
        predecessor_revision_id=current.identity.canonicalWorkflowRevisionId,
        predecessor_digest=current.identity.canonicalDigest,
        objective="Prioritize severe issues first",
        reason_code="CONSTRAINT_CHANGED",
    ).successor
    approved = coordinator.approve(
        seed().journey_id,
        principal,
        candidate_digest=pending.identity.canonicalDigest,
        decision="APPROVE",
        reason_code="HUMAN_APPROVED",
        replay_identity="replay:stream",
    ).successor
    coordinator.rerun(
        seed().journey_id,
        principal,
        revision_id=approved.identity.canonicalWorkflowRevisionId,
        digest=approved.identity.canonicalDigest,
    )
    replay = broker.replay_and_subscribe(scope(), None)
    assert [item.eventType for item in replay._replay] == [
        "JOURNEY_REGISTERED",
        "CORRECTION_ACCEPTED",
        "APPROVAL_RECORDED",
        "EXECUTION_AUTHORIZED",
        "EXECUTION_STARTED",
        "EXECUTION_SUCCEEDED",
    ]
    assert replay._replay[-1].terminal is True
    replay.close()
