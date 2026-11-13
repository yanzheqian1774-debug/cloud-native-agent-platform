"""Offline SSE and actual subprocess cleanup, never a provider invocation."""

import asyncio
import json
import threading
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.model_stream_api import model_response
from agent_console.response_stream import emit
from agent_console.responses_deadline import (
    ResponsesBoundaryError,
    supervise,
)
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from responses_deadline_test_jobs import StalledJob
from test_responses_deadline import assert_reaped, config


@pytest.mark.parametrize(
    "error,code",
    [
        (AuthorityError("PRIVATE_GRANT_ID"), "STREAM_PROGRESS_VALIDATION_UNAVAILABLE"),
        (
            WorkbenchOwnerError("PRIVATE_OBJECT", 404),
            "STREAM_PROGRESS_VALIDATION_UNAVAILABLE",
        ),
        (
            AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE"),
            "STREAM_PROGRESS_READ_UNAVAILABLE",
        ),
        (OSError("private-host-and-token"), "STREAM_PROGRESS_READ_UNAVAILABLE"),
    ],
)
def test_read_failure_has_safe_code_and_existing_deadline_diagnostic(error, code):
    async def run():
        receipts, calls = [], []

        def action():
            calls.append(1)
            emit({"invocationId": "private-invocation", "preview": "PRIVATE_CONTENT"})
            try:
                job = StalledJob("CONNECT")
                job.invocation_id = "private-invocation"
                supervise(job, config(5))
            except ResponsesBoundaryError as exc:
                # This diagnostic is the existing provider receipt deadline payload.
                receipts.append(json.loads(json.dumps(exc.diagnostic)))
            return {"result": {"state": "OUTCOME_UNKNOWN"}}

        def authorize(identity):
            if identity is not None:
                raise error

        response = await model_response(
            NS(headers={"accept": "text/event-stream"}), action, authorize
        )
        data = "".join([frame async for frame in response.body_iterator])
        assert calls == [1]
        assert code in data and "event: error" in data
        assert "event: result" not in data
        for private in (str(error), "private-invocation", "PRIVATE_CONTENT"):
            assert private not in data
        assert len(receipts) == 1
        assert receipts[0]["reason"] == "CANCELLED"
        assert receipts[0]["cancellation_source"] == code
        assert_reaped(receipts[0])

    asyncio.run(run())


@pytest.mark.parametrize(
    "source", [None, "private-untrusted-value", "STREAM_DELIVERY_CANCELLED"]
)
def test_cancellation_source_is_optional_and_whitelisted(source):
    signal = threading.Event()
    signal.cancellation_source = source
    signal.set()
    with pytest.raises(ResponsesBoundaryError) as caught:
        supervise(StalledJob("CONNECT"), config(), cancel=signal)
    diagnostic = caught.value.diagnostic
    assert diagnostic["reason"] == "CANCELLED"
    if source == "STREAM_DELIVERY_CANCELLED":
        assert diagnostic["cancellation_source"] == source
    else:
        assert "cancellation_source" not in diagnostic
    assert_reaped(diagnostic)


def test_deadline_without_cancellation_does_not_claim_validation_failure():
    signal = threading.Event()
    signal.cancellation_source = "STREAM_PROGRESS_VALIDATION_UNAVAILABLE"
    with pytest.raises(ResponsesBoundaryError) as caught:
        supervise(StalledJob("CONNECT"), config(0.5), cancel=signal)
    assert caught.value.diagnostic["reason"] == "TOTAL_DEADLINE"
    assert "cancellation_source" not in caught.value.diagnostic
