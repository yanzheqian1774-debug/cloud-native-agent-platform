"""Private Responses spawn supervision. IPC carries no database handles.

Only this process creates jobs; pickle is confined to its anonymous socketpair.
Worker results are bounded JSON. No provider text, secret or exception is logged.
"""

import asyncio
import contextvars
import json
import multiprocessing
import os
import pickle
import resource
import selectors
import socket
import threading
import time
from contextlib import suppress

from .draft_assistance import DraftAssistanceError

CLEANUP_SECONDS = 2.0
CANCEL = contextvars.ContextVar("responses_cancel", default=None)
STAGES = {
    "STARTUP",
    "PREPARE",
    "CREDENTIAL",
    "CONNECT",
    "DNS",
    "TCP",
    "TLS",
    "SEND_REQUEST",
    "WAIT_HEADERS",
    "READ_BODY",
    "VALIDATE_RESPONSE",
    "CLOSE",
    "IPC",
}


class ResponsesBoundaryError(DraftAssistanceError):
    def __init__(self, diagnostic):
        super().__init__("TRANSPORT_AMBIGUOUS")
        self.diagnostic = diagnostic


def _send(channel, value):
    channel.sendall(json.dumps(value).encode() + b"\n")


def _watch_parent(channel):
    try:
        channel.recv(1)
    finally:
        os._exit(0)


def _worker(channel):
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        with open(os.devnull, "wb") as sink:
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
        data = bytearray()
        header = channel.recv(8)
        while len(header) < 8:
            part = channel.recv(8 - len(header))
            if not part:
                raise OSError
            header += part
        size = int.from_bytes(header, "big")
        if not 0 < size <= 2_000_000:
            raise ValueError
        while len(data) < size:
            part = channel.recv(min(65536, size - len(data)))
            if not part:
                raise OSError
            data.extend(part)
        job = pickle.loads(data)  # trusted parent-only anonymous IPC
        del data
        threading.Thread(target=_watch_parent, args=(channel,), daemon=True).start()
        result = job.run(lambda stage: _send(channel, {"stage": stage}))
        _send(channel, {"result": result})
    except BaseException:
        with suppress(OSError):
            _send(channel, {"error": "WORKER_FAILURE"})
    finally:
        channel.close()


def supervise(job, configuration, *, cancel=None, worker=_worker):
    """Return only after worker reaping; deadlines/cancellation win late results."""
    started = time.monotonic()
    total_at = started + configuration.total_timeout_seconds
    cancel = cancel if cancel is not None else CANCEL.get()
    parent, child = socket.socketpair()
    process = multiprocessing.get_context("spawn").Process(
        target=worker, args=(child,), name="responses-one-request"
    )
    stage, reason = "STARTUP", "WORKER_FAILURE"
    connect_at = None
    result = None
    pid = None
    reaped = False
    stages = {}
    try:
        payload = pickle.dumps(job)
        if len(payload) > 2_000_000:
            raise ValueError
        outgoing = memoryview(len(payload).to_bytes(8, "big") + payload)
        process.start()
        pid = process.pid
        child.close()
        parent.setblocking(False)
        incoming = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(parent, selectors.EVENT_READ | selectors.EVENT_WRITE)
            while result is None:
                now = time.monotonic()
                if now >= total_at:
                    reason = "TOTAL_DEADLINE"
                    break
                if cancel is not None and cancel.is_set():
                    reason = "CANCELLED"
                    break
                if connect_at is not None and now >= connect_at:
                    reason = "CONNECT_DEADLINE"
                    break
                deadline = min(total_at, connect_at or total_at)
                events = selector.select(min(0.025, max(0, deadline - now)))
                for _, mask in events:
                    if mask & selectors.EVENT_WRITE:
                        with suppress(BlockingIOError):
                            count = parent.send(outgoing[:65536])
                            outgoing = outgoing[count:]
                        if not outgoing:
                            selector.modify(parent, selectors.EVENT_READ)
                    if not mask & selectors.EVENT_READ:
                        continue
                    chunk = parent.recv(65536)
                    if not chunk:
                        raise OSError
                    incoming.extend(chunk)
                    if len(incoming) > configuration.maximum_response_bytes * 8 + 65536:
                        raise ValueError
                    while b"\n" in incoming:
                        line, _, incoming = incoming.partition(b"\n")
                        message = json.loads(line)
                        now = time.monotonic()
                        if now >= total_at or (cancel is not None and cancel.is_set()):
                            reason = (
                                "TOTAL_DEADLINE" if now >= total_at else "CANCELLED"
                            )
                            raise TimeoutError
                        if connect_at is not None and now >= connect_at:
                            reason = "CONNECT_DEADLINE"
                            raise TimeoutError
                        if set(message) == {"stage"} and message["stage"] in STAGES:
                            stage = message["stage"]
                            stages[stage] = now - started
                            if stage == "CONNECT":
                                connect_at = now + configuration.connect_timeout_seconds
                            elif stage == "SEND_REQUEST":
                                connect_at = None
                        elif set(message) == {"result"}:
                            result = message["result"]
                            reason = "RESULT_ACCEPTED"
                        else:
                            raise OSError
        # JSON decode and result acceptance are also inside the parent deadline.
        if time.monotonic() >= total_at:
            reason, result = "TOTAL_DEADLINE", None
        if cancel is not None and cancel.is_set():
            reason, result = "CANCELLED", None
    except Exception:
        result = None
    finally:
        decision = time.monotonic()
        cleanup_started = decision
        parent.close()
        child.close()
        killed = False
        try:
            if pid is not None:
                process.join(max(0, 1.0 - (time.monotonic() - cleanup_started)))
                if process.is_alive():
                    killed = True
                    process.kill()
                    process.join(
                        max(0, CLEANUP_SECONDS - (time.monotonic() - cleanup_started))
                    )
                reaped = not process.is_alive()
            else:
                reaped = True
            if reaped:
                process.close()
        except Exception:
            reaped = False
        cleanup = time.monotonic() - cleanup_started
        if not reaped or cleanup > CLEANUP_SECONDS:
            reason, result = "CLEANUP_FAILURE", None
    diagnostic = {
        "reason": reason,
        "stage": stage,
        "stage_seconds": stages,
        "decision_seconds": decision - started,
        "cleanup_seconds": cleanup,
        "worker_pid": pid,
        "reaped": reaped,
        "kill_requested": killed,
    }
    if cancel is not None and cancel.is_set() and reason != "CLEANUP_FAILURE":
        diagnostic["reason"] = "CANCELLED"
        result = None
    if result is None:
        raise ResponsesBoundaryError(diagnostic)
    return result, diagnostic


async def cancellable_request(request, action):
    """ASGI disconnect signals local supervision; finish UNKNOWN persistence."""
    signal = threading.Event()
    token = CANCEL.set(signal)
    task = asyncio.create_task(asyncio.to_thread(action))
    try:
        while not task.done():
            await asyncio.sleep(0.025)
            if await request.is_disconnected():
                signal.set()
        return await task
    except asyncio.CancelledError:
        signal.set()
        # Do not abandon the owner thread before it persists the unknown result.
        await asyncio.shield(task)
        raise
    finally:
        CANCEL.reset(token)
