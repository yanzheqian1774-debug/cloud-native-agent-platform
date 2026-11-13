"""Existing receipt storage roundtrip, isolated PostgreSQL and offline workers."""

# ruff: noqa: F401, F811 -- Existing isolated database fixtures.
import threading
from pathlib import Path

import pytest
from agent_console.execution_domain import ScopeIdentity
from agent_console.plan_invocation_postgres import PostgresPlanningInvocations
from agent_console.responses_deadline import ResponsesBoundaryError, supervise
from responses_deadline_test_jobs import StalledJob
from test_plan_suggestion_v2 import repository
from test_responses_deadline import config


@pytest.mark.parametrize(
    "source",
    ["STREAM_PROGRESS_VALIDATION_UNAVAILABLE", "STREAM_PROGRESS_READ_UNAVAILABLE"],
)
def test_cancellation_source_survives_existing_receipt_restart(repository, source):
    with repository.pool.connection() as c:
        c.execute(
            (
                Path(__file__).parents[1] / "migrations/0023_draft_assistance.sql"
            ).read_text()
        )
    owner = PostgresPlanningInvocations(repository)
    owner.migrate()
    signal = threading.Event()
    signal.cancellation_source = source
    signal.set()
    with pytest.raises(ResponsesBoundaryError) as caught:
        supervise(StalledJob("CONNECT"), config(), cancel=signal)
    scope = ScopeIdentity("tenant-a", "quality")
    identity = "offline-stream-cancellation"
    owner.claim(
        scope, "test-actor", identity, "a" * 64, {"target": {"invocation_id": identity}}
    )
    receipt = {"deadline": caught.value.diagnostic, "measurement": {}}
    owner.save_receipt(scope, identity, receipt)
    restarted = PostgresPlanningInvocations(repository)
    saved = restarted.receipt(scope, identity)
    assert saved == receipt
    assert saved["deadline"]["cancellation_source"] == source
    assert saved["deadline"]["reason"] == "CANCELLED"
    assert saved["measurement"] == {}
