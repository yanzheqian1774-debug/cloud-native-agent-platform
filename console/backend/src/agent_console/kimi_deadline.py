"""Private POSIX supervision for one Kimi request; no owner or credential IO."""

from __future__ import annotations

import base64
import json
import multiprocessing
import os
import resource
import selectors
import socket
import ssl
import threading
import time
from contextlib import suppress
from dataclasses import asdict, dataclass

from agent_console.draft_assistance import (
    DraftAssistanceError,
    DraftResultKind,
    ObservationState,
    PreparedProviderRequest,
    ProviderBudgetQuote,
    ProviderObservation,
)

CLEANUP_SECONDS = 1.0


@dataclass(frozen=True)
class DeadlineMetrics:
    decision_seconds: float
    cleanup_seconds: float
    reason: str
    worker_pid: int | None
    reaped: bool


def _send(channel, value):
    channel.sendall(json.dumps(value, ensure_ascii=True).encode() + b"\n")


def _parent_watch(channel):
    # After the one request is read, parent sends no more data. EOF means exit
    # or completed supervision, including while DNS/SSL/read is blocked.
    try:
        channel.recv(1)
    finally:
        os._exit(0)


def _worker(channel, configuration, invocation_id):
    # Spawn, not fork: no inherited database connections or threaded SSL state.
    # Only anonymous spawn IPC carries the already-resolved credential/content.
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        with open(os.devnull, "wb") as sink:
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
        from agent_console.kimi_responses_draft_adapter import (
            KimiResponsesDraftTransport,
            ResolvedKimiCredential,
        )

        incoming = bytearray()
        limit = configuration.maximum_input_tokens * 2 + 32768
        while b"\n" not in incoming:
            chunk = channel.recv(65536)
            if not chunk or len(incoming) + len(chunk) > limit:
                raise OSError
            incoming.extend(chunk)
        document = json.loads(incoming)
        request = PreparedProviderRequest(
            base64.b64decode(document["payload"], validate=True),
            ProviderBudgetQuote(**document["quote"]),
        )
        credential = ResolvedKimiCredential(
            document["credential"],
            configuration.credential_reference,
            configuration.credential_version,
        )
        del document, incoming
        threading.Thread(target=_parent_watch, args=(channel,), daemon=True).start()
        result = KimiResponsesDraftTransport(configuration)._dispatch_once(
            invocation_id=invocation_id,
            request=request,
            credential=credential,
            profile=None,
            connected=lambda: _send(channel, {"connected": True}),
        )
        _send(channel, {"result": asdict(result)})
    except BaseException as exc:
        # No exception text/traceback, request, credential or body diagnostics.
        code = (
            "KIMI_RESPONSES_TLS_CONFIGURATION_INVALID"
            if isinstance(exc, DraftAssistanceError)
            and str(exc) == "KIMI_RESPONSES_TLS_CONFIGURATION_INVALID"
            else "TRANSPORT_AMBIGUOUS"
        )
        cause = (
            "TLS" if isinstance(exc.__cause__, ssl.SSLCertVerificationError) else "IO"
        )
        with suppress(OSError):
            _send(channel, {"error": code, "cause": cause})
    finally:
        channel.close()


def _check_deadline(now, total_at, connect_at, connected):
    # Deadline wins equality and any result concurrently becoming readable.
    if now >= total_at:
        return "TOTAL_DEADLINE"
    if not connected and now >= connect_at:
        return "CONNECT_DEADLINE"
    return None


def _request_message(request, credential):
    return (
        json.dumps(
            {
                "payload": base64.b64encode(request.payload).decode("ascii"),
                "quote": asdict(request.quote),
                "credential": credential.authorization_value()[len("Bearer ") :],
            }
        ).encode()
        + b"\n"
    )


def supervise(configuration, invocation_id, request, credential, metrics):
    return _supervise(
        configuration, invocation_id, request, credential, metrics, worker=_worker
    )


def _supervise(configuration, invocation_id, request, credential, metrics, *, worker):
    started = time.monotonic()
    total_at = started + configuration.total_timeout_seconds
    connect_at = started + configuration.connect_timeout_seconds
    parent, child = socket.socketpair()
    process = multiprocessing.get_context("spawn").Process(
        target=worker,
        args=(child, configuration, invocation_id),
        name="kimi-one-request",
    )
    connected = False
    reason = "WORKER_FAILURE"
    decision = None
    pid = None
    buffer = bytearray()
    # JSON escapes can multiply body bytes; fixed overhead covers safe metadata.
    max_message = configuration.maximum_response_bytes * 6 + 65536
    try:
        # Payload/secret never enter spawn arguments. Nonblocking IPC prevents
        # startup/import stalls from blocking a large launch-pipe write.
        outgoing = memoryview(
            _request_message(request, credential) if request is not None else b"\n"
        )
        process.start()
        pid = process.pid
        child.close()
        parent.setblocking(False)
        with selectors.DefaultSelector() as selector:
            selector.register(parent, selectors.EVENT_READ | selectors.EVENT_WRITE)
            while True:
                now = time.monotonic()
                expired = _check_deadline(now, total_at, connect_at, connected)
                if expired:
                    reason = expired
                    raise TimeoutError
                wait_until = total_at if connected else min(total_at, connect_at)
                events = selector.select(wait_until - now)
                if not events:
                    continue
                # Recheck after waking, before sending or accepting any bytes.
                expired = _check_deadline(
                    time.monotonic(), total_at, connect_at, connected
                )
                if expired:
                    reason = expired
                    raise TimeoutError
                mask = events[0][1]
                if mask & selectors.EVENT_WRITE:
                    try:
                        sent = parent.send(outgoing[:65536])
                        outgoing = outgoing[sent:]
                    except BlockingIOError:
                        pass
                    if not outgoing:
                        selector.modify(parent, selectors.EVENT_READ)
                if not mask & selectors.EVENT_READ:
                    continue
                chunk = parent.recv(65536)
                if not chunk:
                    raise OSError
                buffer.extend(chunk)
                if len(buffer) > max_message:
                    raise OSError
                while b"\n" in buffer:
                    line, _, rest = buffer.partition(b"\n")
                    buffer = bytearray(rest)
                    expired = _check_deadline(
                        time.monotonic(), total_at, connect_at, connected
                    )
                    if expired:
                        reason = expired
                        raise TimeoutError
                    message = json.loads(line)
                    if message == {"connected": True} and not connected:
                        connected = True
                        continue
                    if "error" in message:
                        reason = "WORKER_ERROR"
                        cause = (
                            ssl.SSLCertVerificationError("Kimi TLS verification failed")
                            if message.get("cause") == "TLS"
                            else OSError("Kimi worker failed")
                        )
                        code = message["error"]
                        if code not in {
                            "KIMI_RESPONSES_TLS_CONFIGURATION_INVALID",
                            "TRANSPORT_AMBIGUOUS",
                        }:
                            code = "TRANSPORT_AMBIGUOUS"
                        raise DraftAssistanceError(code) from cause
                    if not connected or set(message) != {"result"}:
                        raise OSError
                    value = message["result"]
                    value["state"] = ObservationState(value["state"])
                    if value.get("result_kind") is not None:
                        value["result_kind"] = DraftResultKind(value["result_kind"])
                    result = ProviderObservation(**value)
                    # Deserialization/validation time is inside the deadline too.
                    decision = time.monotonic()
                    if decision >= total_at:
                        reason = "TOTAL_DEADLINE"
                        raise TimeoutError
                    reason = "RESULT_ACCEPTED"
                    return result
    except DraftAssistanceError:
        raise
    except Exception as exc:
        raise DraftAssistanceError("TRANSPORT_AMBIGUOUS") from exc
    finally:
        decision = time.monotonic() if decision is None else decision
        cleanup_started = time.monotonic()
        parent.close()
        child.close()
        reaped = pid is None
        try:
            if pid is not None:
                if process.is_alive():
                    process.kill()
                process.join(
                    max(0.0, CLEANUP_SECONDS - (time.monotonic() - cleanup_started))
                )
                reaped = not process.is_alive()
            if reaped:
                process.close()
        finally:
            cleanup = time.monotonic() - cleanup_started
            if not reaped or cleanup > CLEANUP_SECONDS:
                reason = "CLEANUP_FAILURE"
            metrics(DeadlineMetrics(decision - started, cleanup, reason, pid, reaped))
        if not reaped or cleanup > CLEANUP_SECONDS:
            # No late success, hidden background reaper, or automatic restart.
            raise DraftAssistanceError("TRANSPORT_AMBIGUOUS")
