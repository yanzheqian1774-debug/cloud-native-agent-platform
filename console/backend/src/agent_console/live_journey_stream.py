"""Replaceable journey-event ports and a bounded process-local broker."""

from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

from agent_console.live_journey_stream_schemas import (
    JourneyEventEnvelope,
    serialize_envelope,
)


class JourneyStreamFailure(ValueError):
    reason_code = "JOURNEY_STREAM_ERROR"


class JourneyResumeUnavailable(JourneyStreamFailure):
    reason_code = "RESUME_UNAVAILABLE"


class JourneySubscriptionLimit(JourneyStreamFailure):
    reason_code = "JOURNEY_SUBSCRIBER_LIMIT"


class JourneyEventPublisher(Protocol):
    def publish(self, envelope: JourneyEventEnvelope) -> None: ...


class JourneyEventSource(Protocol):
    def replay_and_subscribe(
        self, scope: JourneyStreamScope, last_event_id: str | None
    ) -> JourneySubscription: ...

    def next_sequence(self, scope: JourneyStreamScope) -> int: ...

    def clear_scope(self, scope: JourneyStreamScope) -> bool: ...


@dataclass(frozen=True, slots=True)
class JourneyStreamScope:
    tenant_id: str
    security_domain: str
    journey_id: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.tenant_id, self.security_domain, self.journey_id)


@dataclass(slots=True)
class _Buffer:
    events: deque[JourneyEventEnvelope] = field(default_factory=deque)
    serialized: dict[str, str] = field(default_factory=dict)
    next_sequence: int = 1
    terminal: bool = False
    subscribers: set[asyncio.Queue[JourneyEventEnvelope]] = field(default_factory=set)


class JourneySubscription:
    def __init__(
        self,
        broker: InMemoryJourneyEventBroker,
        scope: JourneyStreamScope,
        replay: tuple[JourneyEventEnvelope, ...],
        queue: asyncio.Queue[JourneyEventEnvelope],
    ) -> None:
        self._broker = broker
        self._scope = scope
        self._replay = replay
        self._queue = queue
        self._closed = False

    async def events(self) -> AsyncIterator[JourneyEventEnvelope]:
        try:
            for event in self._replay:
                yield event
            while not self._closed:
                yield await self._queue.get()
        finally:
            self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._broker.unsubscribe(self._scope, self._queue)


class InMemoryJourneyEventBroker(JourneyEventPublisher, JourneyEventSource):
    """Ordered best-effort replay with strict process-local resource bounds."""

    def __init__(
        self,
        *,
        max_journeys: int = 64,
        max_events: int = 256,
        retention: timedelta = timedelta(minutes=15),
        max_subscribers: int = 8,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._max_journeys = max_journeys
        self._max_events = max_events
        self._retention = retention
        self._max_subscribers = max_subscribers
        self._clock = clock or (lambda: datetime.now(UTC))
        self._buffers: OrderedDict[tuple[str, str, str], _Buffer] = OrderedDict()

    def _prune(self, buffer: _Buffer, now: datetime) -> None:
        cutoff = now - self._retention
        while buffer.events and buffer.events[0].occurredAt <= cutoff:
            removed = buffer.events.popleft()
            buffer.serialized.pop(removed.eventId, None)
        while len(buffer.events) > self._max_events:
            removed = buffer.events.popleft()
            buffer.serialized.pop(removed.eventId, None)

    def publish(self, envelope: JourneyEventEnvelope) -> None:
        identity = envelope.identity
        key = (identity.tenantId, identity.securityDomain, envelope.journeyId)
        buffer = self._buffers.get(key)
        if buffer is None:
            if len(self._buffers) >= self._max_journeys:
                for existing_key, existing in tuple(self._buffers.items()):
                    self._prune(existing, self._clock())
                    if not existing.events and not existing.subscribers:
                        del self._buffers[existing_key]
                if len(self._buffers) >= self._max_journeys:
                    raise JourneyStreamFailure("JOURNEY_BUFFER_LIMIT")
            buffer = _Buffer()
            self._buffers[key] = buffer
        canonical = serialize_envelope(envelope)
        duplicate = buffer.serialized.get(envelope.eventId)
        if duplicate is not None:
            if duplicate == canonical:
                return
            raise JourneyStreamFailure("CONFLICTING_EVENT_ID")
        if buffer.terminal:
            raise JourneyStreamFailure("EVENT_AFTER_TERMINAL")
        if envelope.sequence != buffer.next_sequence:
            raise JourneyStreamFailure("EVENT_SEQUENCE_INVALID")
        if any(queue.full() for queue in buffer.subscribers):
            raise JourneyStreamFailure("SUBSCRIBER_BACKPRESSURE")
        buffer.events.append(envelope)
        buffer.serialized[envelope.eventId] = canonical
        buffer.next_sequence += 1
        buffer.terminal = envelope.terminal
        self._prune(buffer, self._clock())
        self._buffers.move_to_end(key)
        for queue in tuple(buffer.subscribers):
            queue.put_nowait(envelope)

    def replay_and_subscribe(
        self, scope: JourneyStreamScope, last_event_id: str | None
    ) -> JourneySubscription:
        buffer = self._buffers.get(scope.key)
        if buffer is None:
            raise JourneyResumeUnavailable()
        self._prune(buffer, self._clock())
        if len(buffer.subscribers) >= self._max_subscribers:
            raise JourneySubscriptionLimit()
        events = tuple(buffer.events)
        if last_event_id is not None:
            indexes = [
                i for i, item in enumerate(events) if item.eventId == last_event_id
            ]
            if not indexes:
                raise JourneyResumeUnavailable()
            events = events[indexes[0] + 1 :]
        queue: asyncio.Queue[JourneyEventEnvelope] = asyncio.Queue(maxsize=256)
        buffer.subscribers.add(queue)
        self._buffers.move_to_end(scope.key)
        return JourneySubscription(self, scope, events, queue)

    def unsubscribe(
        self, scope: JourneyStreamScope, queue: asyncio.Queue[JourneyEventEnvelope]
    ) -> None:
        buffer = self._buffers.get(scope.key)
        if buffer is not None:
            buffer.subscribers.discard(queue)

    def next_sequence(self, scope: JourneyStreamScope) -> int:
        buffer = self._buffers.get(scope.key)
        return 1 if buffer is None else buffer.next_sequence

    def clear_scope(self, scope: JourneyStreamScope) -> bool:
        """Forget one exact process-local replay/subscriber scope."""
        buffer = self._buffers.pop(scope.key, None)
        if buffer is None:
            return False
        buffer.subscribers.clear()
        buffer.events.clear()
        buffer.serialized.clear()
        return True

    def scope_counts(self, scope: JourneyStreamScope) -> tuple[int, int]:
        """Expose bounded diagnostics without disclosing event content."""
        buffer = self._buffers.get(scope.key)
        if buffer is None:
            return (0, 0)
        return (len(buffer.events), len(buffer.subscribers))


def format_sse(envelope: JourneyEventEnvelope) -> bytes:
    """Frame one already-authoritative event without changing its content."""
    return (
        f"id: {envelope.eventId}\n"
        f"event: {envelope.eventType}\n"
        f"data: {serialize_envelope(envelope)}\n\n"
    ).encode()
