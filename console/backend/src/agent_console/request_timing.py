"""Opt-in request-local timings; never retain request bodies or SQL parameters."""

import json
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from threading import Lock
from time import perf_counter

_current = ContextVar("workbench_timing", default=None)


class Observation:
    def __init__(self):
        self.values = {}
        self.lock = Lock()

    def add(self, name, elapsed=0):
        with self.lock:
            item = self.values.setdefault(name, {"count": 0, "ms": 0.0})
            item["count"] += 1
            item["ms"] += elapsed * 1000


def count(name):
    observation = _current.get()
    if observation is not None:
        observation.add(name)


@contextmanager
def span(name):
    observation = _current.get()
    if observation is None:
        yield
        return
    started = perf_counter()
    try:
        yield
    finally:
        observation.add(name, perf_counter() - started)


def measured(name):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with span(name):
                return function(*args, **kwargs)

        return wrapped

    return decorate


@contextmanager
def measured_context(manager, name):
    """Separate acquisition and release without changing exception suppression."""

    class TimedContext:
        def __enter__(self):
            with span(name + ".enter"):
                return manager.__enter__()

        def __exit__(self, *exc):
            with span(name + ".exit"):
                return manager.__exit__(*exc)

    with TimedContext() as value:
        yield value


def observe_request(function):
    @wraps(function)
    async def wrapped(request, call_next):
        path = request.scope.get("path", "") if request is not None else ""
        selected = path == "/api/workbench/v1/session" or path.startswith(
            "/api/workbench/v1/resource-directory"
        )
        if os.environ.get("WORKBENCH_REQUEST_TIMING") != "1" or not selected:
            return await function(request, call_next)
        observation = Observation()
        token = _current.set(observation)
        started = perf_counter()
        status = None
        try:
            response = await function(request, call_next)
            status = response.status_code
            return response
        finally:
            _current.reset(token)
            # Route template only: no path identities, query, body or credentials.
            record = {
                "requestId": getattr(request.state, "diagnostic_id", None),
                "route": getattr(request.scope.get("route"), "path", "UNREGISTERED"),
                "status": status,
                "responseReadyMs": (perf_counter() - started) * 1000,
                "spans": observation.values,
            }
            logging.getLogger("uvicorn.error").info(
                "workbench_timing %s", json.dumps(record, sort_keys=True)
            )

    return wrapped
