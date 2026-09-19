"""Spawn targets only: do not import pytest, test modules or database bootstrap.

The production supervisor still starts its deadlines before spawn. Keeping fault
injection separate avoids importing the whole test harness inside that budget.
"""

import ssl
import time


# Fault injection below runs inside a fresh real spawned process. It does not
# claim actual stalled DNS/TCP/TLS integration evidence.
def _stalled_deadline_worker(channel, configuration, phase):
    import http.client
    import socket

    from agent_console.kimi_deadline import _worker

    def stall(*args, **kwargs):
        time.sleep(30)
        raise TimeoutError

    if phase == "dns":
        socket.getaddrinfo = stall
    elif phase == "tcp":
        socket.socket.connect = stall
    elif phase == "tls":
        ssl.SSLContext.wrap_socket = stall
    elif phase == "send":
        http.client.HTTPSConnection.request = stall
    elif phase == "headers":
        http.client.HTTPSConnection.getresponse = stall
    else:
        http.client.HTTPResponse.read = stall
    _worker(channel, configuration, phase)


def _stalled_receiver_worker(channel, configuration, phase):
    time.sleep(30)


def _partial_result_worker(channel, configuration, phase):
    from agent_console.kimi_deadline import _send

    _send(channel, {"connected": True})
    channel.sendall(b'{"result":')
    time.sleep(30)


def _noisy_request_worker(channel, configuration, invocation_id):
    import os

    from agent_console.kimi_deadline import _worker

    def noisy_once(self, **kwargs):
        import resource

        assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
        os.write(1, b"synthetic-secret-must-not-log")
        os.write(2, b"synthetic-body-must-not-log")
        raise RuntimeError("synthetic-secret-must-not-log")

    from agent_console.kimi_responses_draft_adapter import KimiResponsesDraftTransport

    KimiResponsesDraftTransport._dispatch_once = noisy_once
    _worker(channel, configuration, invocation_id)
