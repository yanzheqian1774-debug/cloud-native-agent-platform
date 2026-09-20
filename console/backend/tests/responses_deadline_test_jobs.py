"""Spawn-safe phase substitutes. Never open network or read credentials."""

import time
from dataclasses import dataclass


@dataclass
class StalledJob:
    stage: str

    def run(self, progress):
        progress(self.stage)
        time.sleep(20)
        return {"late": True}


@dataclass
class ResultJob:
    delay: float = 0

    def run(self, progress):
        progress("VALIDATE_RESPONSE")
        time.sleep(self.delay)
        return {"accepted": True}


def stalled_startup(channel):
    time.sleep(20)


class UnreapableProcess:
    pid = 999999999  # simulated OS failure; never a real process

    def start(self):
        pass

    def join(self, timeout):
        pass

    def is_alive(self):
        return True

    def kill(self):
        pass


@dataclass
class NetworkPhaseJob:
    """Patch one phase inside a real spawned worker, never in the parent."""

    job: object
    phase: str
    reached_path: str

    def run(self, progress):
        import http.client
        import socket
        import ssl
        from pathlib import Path

        from agent_console.plan_suggestion_invocation import PlanningProviderResult

        owner, name = {
            "DNS": (socket, "getaddrinfo"),
            "TCP": (socket.socket, "connect"),
            "TLS": (ssl.SSLContext, "wrap_socket"),
            "SEND_REQUEST": (http.client.HTTPSConnection, "request"),
            "VALIDATE_RESPONSE": (PlanningProviderResult, "model_validate_json"),
            "CLOSE": (http.client.HTTPSConnection, "close"),
        }[self.phase]

        def stalled(*args, **kwargs):
            Path(self.reached_path).touch(exist_ok=False)
            progress(self.phase)
            time.sleep(20)

        setattr(owner, name, stalled)
        return self.job.run(progress)
