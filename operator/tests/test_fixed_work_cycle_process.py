"""Physical process/OS lock checks with a controlled, effect-free cycle host."""

import os
import selectors
import subprocess
import sys
from pathlib import Path

SCRIPT = """
import signal,sys
from datetime import UTC,datetime,timedelta
from contextlib import contextmanager
from threading import Event
from types import SimpleNamespace as N
from pathlib import Path
import agent_operator.fixed_work_cycle_service as module
from agent_operator.native_host_service_state import private_directory
@contextmanager
def value(v): yield v
now=datetime.now(UTC)
p=N(tenantId='test',securityDomain='isolated',work=N(resource_id='work'),digest='fixed',allowedEventIds=('saved-event',),eventWindows={'saved-event':(now-timedelta(hours=2),now-timedelta(hours=1))})
c=N(transaction=lambda:value(None),
    execute=lambda *a:N(fetchall=lambda:[{'event_id':'saved-event'}]))
registry=N(_policy=lambda:p,_check=lambda *a:now,
           repository=N(pool=N(connection=lambda:value(c))))
host=N(runtime=N(registry=registry),step=lambda *a:{'stage':'START_COMMITTED'})
module.machine_lock_directory=lambda:private_directory(Path(sys.argv[1]))
service=module.FixedWorkCycleService(host,lambda:N(principal_id='service:test'),'isolated-db',enabled=True,poll_seconds=5)
stop=Event()
signal.signal(signal.SIGTERM,lambda *_:stop.set())
service.run(stop,lambda rows:print(rows[0]['eventId'],flush=True))
"""


def test_real_process_lock_stop_and_restart_same_event(tmp_path):
    root = Path(__file__).parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(root / "operator/src"),
            str(root / "console/backend/src"),
            env.get("PYTHONPATH", ""),
        ]
    )
    command = [sys.executable, "-c", SCRIPT, str((tmp_path / "locks").resolve())]
    children = []

    def start():
        child = subprocess.Popen(
            command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        children.append(child)
        return child

    def ready(child):
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            assert selector.select(10), "controlled host readiness timeout"
            line = child.stdout.readline().strip()
            assert line == "saved-event", (
                child.stderr.read() if child.poll() is not None else line
            )

    try:
        first = start()
        ready(first)
        second = start()
        _, error = second.communicate(timeout=10)
        assert second.returncode != 0 and "BlockingIOError" in error
        first.terminate()
        assert first.wait(timeout=10) == 0
        restarted = start()
        ready(restarted)
        restarted.terminate()
        assert restarted.wait(timeout=10) == 0
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=10)
