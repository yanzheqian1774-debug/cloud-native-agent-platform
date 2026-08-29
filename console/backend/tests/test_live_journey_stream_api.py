"""Authorization-first and nondisclosing SSE endpoint tests."""

from agent_console.app import app, get_live_journey_principal, get_live_journey_service
from agent_console.live_journey import LiveJourneyCoordinator, TrustedJourneyPrincipal
from agent_console.live_journey_stream import InMemoryJourneyEventBroker
from fastapi.testclient import TestClient
from test_live_journey import ExecutionAuthority, seed


class CountingBroker(InMemoryJourneyEventBroker):
    def __init__(self) -> None:
        super().__init__()
        self.source_calls = 0

    def replay_and_subscribe(self, scope, last_event_id):
        self.source_calls += 1
        return super().replay_and_subscribe(scope, last_event_id)


def configured(principal: TrustedJourneyPrincipal):
    broker = CountingBroker()
    service = LiveJourneyCoordinator(ExecutionAuthority(), broker)
    service.register_live(seed())
    app.dependency_overrides[get_live_journey_service] = lambda: service
    app.dependency_overrides[get_live_journey_principal] = lambda: principal
    return TestClient(app), broker


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_denied_absent_and_foreign_are_identical_before_source_call() -> None:
    path = "/api/internal/preview/v1/live-planning-journeys/{}/events"
    principals = (
        TrustedJourneyPrincipal("", "", "", False),
        TrustedJourneyPrincipal("human:x", "tenant-a", "quality", True),
        TrustedJourneyPrincipal("human:x", "tenant-b", "quality", True),
    )
    journey_ids = (
        "journey:supplier-quality-1",
        "journey:absent",
        "journey:supplier-quality-1",
    )
    responses = []
    for principal, journey_id in zip(principals, journey_ids, strict=True):
        client, broker = configured(principal)
        response = client.get(path.format(journey_id))
        responses.append((response.status_code, response.json()))
        assert broker.source_calls == 0
    assert responses[0] == responses[1] == responses[2]
    assert "supplier" not in str(responses[0]) and "tenant" not in str(responses[0])


def test_unknown_last_event_id_returns_explicit_terminal_resume_unavailable() -> None:
    client, broker = configured(
        TrustedJourneyPrincipal("human:x", "tenant-a", "quality", True)
    )
    response = client.get(
        "/api/internal/preview/v1/live-planning-journeys/journey:supplier-quality-1/events",
        headers={"Last-Event-ID": "event:lost-after-restart"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: RESUME_UNAVAILABLE" in response.text
    assert '"reasonCode":"RESUME_UNAVAILABLE"' in response.text
    assert '"terminal":true' in response.text
    assert broker.source_calls == 1
