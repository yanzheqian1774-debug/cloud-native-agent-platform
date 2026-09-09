import threading
import time

import pytest
from agent_console.persistence_bootstrap import (
    BootstrapStep,
    ConsoleBootstrapError,
    activate_in_order,
    prepare_in_parallel,
)


class Pool:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class Prepared:
    def __init__(self):
        self.pool = Pool()


def test_independent_pool_preparation_overlaps():
    barrier = threading.Barrier(3)
    callers = []

    def prepare(name):
        callers.append((name, threading.get_ident()))
        barrier.wait(timeout=1)
        return Prepared()

    steps = tuple(
        BootstrapStep(name, lambda name=name: prepare(name), lambda _value: None)
        for name in ("knowledge", "skill", "execution")
    )

    prepared = prepare_in_parallel(steps)

    assert set(prepared) == {"knowledge", "skill", "execution"}
    assert len({thread for _, thread in callers}) == 3


def test_migration_activation_is_ordered_on_one_writer_thread():
    order = []
    writers = []
    caller = threading.get_ident()
    steps = tuple(
        BootstrapStep(
            name,
            Prepared,
            lambda _value, name=name: (
                order.append(name),
                writers.append(threading.get_ident()),
                time.sleep(0.001),
            ),
        )
        for name in ("knowledge", "runtime", "skill", "workflow", "agent", "execution")
    )
    prepared = {step.name: Prepared() for step in steps}

    activate_in_order(steps, prepared)

    assert order == [step.name for step in steps]
    assert writers == [caller] * len(steps)


def test_preparation_failure_closes_completed_pools():
    first = Prepared()
    release = threading.Event()

    def successful():
        release.wait(timeout=1)
        return first

    def failed():
        release.set()
        raise ValueError("unavailable")

    steps = (
        BootstrapStep("first", successful, lambda _value: None),
        BootstrapStep("failed", failed, lambda _value: None),
    )

    with pytest.raises(
        ConsoleBootstrapError, match="CONSOLE_PERSISTENCE_PREPARATION_FAILED"
    ):
        prepare_in_parallel(steps)

    assert first.pool.closed


def test_activation_failure_closes_all_pools_and_never_runs_later_step():
    values = {name: Prepared() for name in ("first", "failed", "later")}
    activated = []

    def fail(_value):
        activated.append("failed")
        raise ValueError("migration failed")

    steps = (
        BootstrapStep("first", Prepared, lambda _value: activated.append("first")),
        BootstrapStep("failed", Prepared, fail),
        BootstrapStep("later", Prepared, lambda _value: activated.append("later")),
    )

    with pytest.raises(
        ConsoleBootstrapError, match="CONSOLE_PERSISTENCE_ACTIVATION_FAILED"
    ):
        activate_in_order(steps, values)

    assert activated == ["first", "failed"]
    assert all(value.pool.closed for value in values.values())
