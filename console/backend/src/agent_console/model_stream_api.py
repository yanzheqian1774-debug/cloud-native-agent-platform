"""Request-local SSE delivery. No replay, owner, durable store, or new call."""

import asyncio
import json
import threading
from contextlib import suppress
from datetime import UTC, datetime

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse

from .authority_contracts import AuthorityError
from .response_stream import SINK
from .responses_deadline import CANCEL, cancellable_request
from .workbench_owner_authorization import WorkbenchOwnerError


def stream_authorization(request, authenticate, require_csrf, read):
    """Reuse request identity, never authorization; each READ rechecks live grants.

    Re-authentication touches the session using an exclusive lock, which waits
    behind the dispatch guard's shared session lock until the model finishes.
    The original owner READ checks current session/account/grants without that
    idle-timer write. The request's cookie and CSRF headers are immutable.
    """
    context = None

    def authorize(identity):
        nonlocal context
        if identity is None or context is None:
            session, context = authenticate(request)
            require_csrf(request, session)
        if identity is not None:
            read(context, identity)

    return authorize


def frame(event, value):
    return (
        "event: "
        + event
        + "\ndata: "
        + json.dumps(
            jsonable_encoder({"at": datetime.now(UTC).isoformat(), **value}),
            ensure_ascii=False,
        )
        + "\n\n"
    )


def wants_stream(request):
    return "text/event-stream" in request.headers.get("accept", "")


async def model_response(request, action, authorize):
    if not wants_stream(request):
        return await cancellable_request(request, action)
    # No header is sent until the caller's session and CSRF are validated.
    await asyncio.to_thread(authorize, None)

    async def events():
        signal, lock, latest = threading.Event(), threading.Lock(), {}

        def receive(value):
            with lock:
                latest.clear()
                latest.update(value)

        def execute():
            cancel_token, sink_token = CANCEL.set(signal), SINK.set(receive)
            try:
                return action()
            finally:
                SINK.reset(sink_token)
                CANCEL.reset(cancel_token)

        task = asyncio.create_task(asyncio.to_thread(execute))
        identity = None
        failure = "STREAM_SERVICE_UNAVAILABLE"

        async def check_read():
            nonlocal failure
            try:
                await asyncio.to_thread(authorize, identity)
            except Exception as exc:
                validation = (
                    isinstance(exc, PermissionError)
                    or (
                        isinstance(exc, AuthorityError)
                        and exc.reason_code != "AUTHORITY_STORAGE_UNAVAILABLE"
                    )
                    or (
                        isinstance(exc, WorkbenchOwnerError)
                        and exc.status_code in {401, 403, 404}
                    )
                )
                failure = (
                    "STREAM_PROGRESS_VALIDATION_UNAVAILABLE"
                    if validation
                    else "STREAM_PROGRESS_READ_UNAVAILABLE"
                )
                raise

        def cancel(source):
            signal.cancellation_source = source
            signal.set()

        try:
            yield frame("progress", {"kind": "accepted"})
            while not task.done():
                await asyncio.sleep(0.25)
                with lock:
                    value = dict(latest)
                    latest.clear()
                if value:
                    identity = value.get("invocationId") or identity
                    await check_read()
                    yield frame("progress", value)
                else:
                    # Keepalive means only that the connection is still open.
                    yield ": keepalive\n\n"
            result = await task
            await check_read()
            if isinstance(result, JSONResponse):
                status, body = result.status_code, json.loads(result.body)
            else:
                status, body = 201, result
            yield frame("result", {"status": status, "body": body})
        except asyncio.CancelledError:
            cancel("STREAM_DELIVERY_CANCELLED")
            await asyncio.shield(task)
            raise
        except Exception:
            cancel(failure)
            with suppress(Exception):
                await asyncio.shield(task)
            yield frame("error", {"reasonCode": failure})
        finally:
            signal.set()
            if not task.done():
                await asyncio.shield(task)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def snapshot_response(read):
    async def events():
        previous = None
        try:
            # Reconnect is a read only; each snapshot rechecks existing authority.
            for _ in range(60):
                value = await asyncio.to_thread(read)
                encoded = json.dumps(value, sort_keys=True, default=str)
                if encoded != previous:
                    yield frame("snapshot", value)
                    previous = encoded
                else:
                    yield ": keepalive\n\n"
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception:
            yield frame("error", {"reasonCode": "PROGRESS_READ_UNAVAILABLE"})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
