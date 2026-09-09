"""Bounded Console persistence preparation and migration activation."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any


class ConsoleBootstrapError(RuntimeError):
    """Fail the process before health when required persistence is unavailable."""


@dataclass(frozen=True, slots=True)
class BootstrapStep:
    name: str
    prepare: Callable[[], Any]
    activate: Callable[[Any], None]


def _close(value: Any) -> None:
    if isinstance(value, Mapping):
        for item in value.values():
            _close(item)
        return
    if isinstance(value, (tuple, list)):
        for item in value:
            _close(item)
        return
    pool = getattr(value, "pool", None)
    close = getattr(pool, "close", None)
    if callable(close):
        close()


def migration_recorded(value: Any, schema: str, version: int) -> bool:
    """Detect an existing ledger version without treating mismatch as fresh."""
    with value.pool.connection() as connection:
        relation = connection.execute(
            "SELECT to_regclass(%s) AS relation", (f"{schema}.schema_migrations",)
        ).fetchone()["relation"]
        if relation is None:
            return False
        return (
            connection.execute(
                f"SELECT 1 FROM {schema}.schema_migrations WHERE version=%s",
                (version,),
            ).fetchone()
            is not None
        )


def prepare_in_parallel(steps: Iterable[BootstrapStep]) -> dict[str, Any]:
    """Open independent pools concurrently without executing a migration."""
    ordered = tuple(steps)
    if not ordered:
        return {}
    prepared: dict[str, Any] = {}
    failures: list[Exception] = []
    with ThreadPoolExecutor(
        max_workers=len(ordered), thread_name_prefix="console-persistence-prepare"
    ) as executor:
        futures = {executor.submit(step.prepare): step for step in ordered}
        for future in as_completed(futures):
            step = futures[future]
            try:
                prepared[step.name] = future.result()
            except Exception as exc:
                failures.append(exc)
    if failures:
        for value in prepared.values():
            _close(value)
        raise ConsoleBootstrapError(
            "CONSOLE_PERSISTENCE_PREPARATION_FAILED"
        ) from failures[0]
    return prepared


def activate_in_order(
    steps: Iterable[BootstrapStep], prepared: Mapping[str, Any]
) -> None:
    """Run every migration on the caller thread in the declared writer order."""
    ordered = tuple(steps)
    try:
        for step in ordered:
            step.activate(prepared[step.name])
    except Exception as exc:
        for value in prepared.values():
            _close(value)
        raise ConsoleBootstrapError("CONSOLE_PERSISTENCE_ACTIVATION_FAILED") from exc
