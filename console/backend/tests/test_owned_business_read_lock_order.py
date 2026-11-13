"""Actual independent owner transactions: governance precedes admission locks."""

# ruff: noqa: F401,F811 -- Explicit disposable fixture registration.
from concurrent.futures import ThreadPoolExecutor
from threading import Event, current_thread

import pytest
from agent_console import task_identity_continuity as identity
from agent_console.authority_contracts import AuthorityError
from agent_console.owned_business_postgres import require_not_revoked
from agent_console.plan_suggestion_domain import ExactReference
from test_owned_business_admission import (
    adopted,
    env,
    ordinary,
    owned_created,
    owned_ready,
    pytestmark,
    routed,
    setup,
)


def test_governance_first_concurrent_read_reentrant_and_revoked(
    owned_created, monkeypatch
):
    e = owned_created
    revision = e.created["revision"]
    problem = ExactReference(
        resource_id=revision["business_problem_id"],
        revision_id=revision["revision_id"],
        digest=revision["digest"],
    )
    with e.repo.connection_scope() as c:
        admission = e.business_owner.work(c, e.context, problem).admission_id
    before_calls = len(e.calls)
    entering = Event()
    original = identity.lock_owner_generation

    def observed(c):
        if current_thread().name.startswith("owned-reader"):
            entering.set()
        return original(c)

    monkeypatch.setattr(identity, "lock_owner_generation", observed)

    def read():
        with e.repo.connection_scope() as c:
            return e.business_owner.work(c, e.context, problem)

    with ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="owned-reader"
    ) as executor:
        # Effect caller's existing order: governance, then business admission.
        with e.repo.connection_scope() as c:
            c.execute("SET LOCAL lock_timeout='3s'")
            original(c)
            future = executor.submit(read)
            assert entering.wait(5)
            # With the old reader, the other transaction holds this admission
            # while awaiting our governance lock, deterministically timing out.
            require_not_revoked(c, admission)
            assert (
                e.business_owner.work(c, e.context, problem).admission_id == admission
            )
        assert future.result(timeout=10).admission_id == admission

    with e.repo.connection_scope() as c:
        original(c)
        require_not_revoked(c, admission)
        c.execute(
            "INSERT INTO authorization_admin.owned_business_revocations "
            "(admission_id,actor_id,reason_code) VALUES(%s,%s,%s)",
            (admission, e.context.principal_id, "USER_REQUESTED"),
        )
    with (
        e.repo.connection_scope() as c,
        pytest.raises(AuthorityError, match="ADMISSION_REVOKED"),
    ):
        e.business_owner.work(c, e.context, problem)
    assert len(e.calls) == before_calls
