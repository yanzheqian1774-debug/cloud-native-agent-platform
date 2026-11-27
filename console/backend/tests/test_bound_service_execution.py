# ruff: noqa: F401,F811,E501 -- Actual random owner fixtures.
"""Formal service Plan/START -> real Discovery and runner -> original chat result.

Provider/Kubernetes and historical Human BOUND creation are controlled fixtures.
No prewritten WAIT and no 0078 schema/delegation. Native Skill execution is real.
"""

from types import SimpleNamespace

import pytest
from agent_console.bound_service_execution import BoundServiceExecutionBridge
from agent_console.fixed_work_service_continuation import ServiceCycleContinuation
from agent_operator.native_host_service_discovery import Discovery
from test_fixed_chat_delivery_postgres import automation, case, repository, services
from test_fixed_chat_delivery_postgres import (
    test_bound_committed_event_is_read_in_original_chat_without_human_model_lease as original_chain,
)


@pytest.mark.parametrize("withdraw", [False, True, "UNKNOWN"])
@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
def test_bound_service_discovery_runs_original_tasks_and_returns_to_original_chat(
    automation, monkeypatch, tmp_path, withdraw
):
    import pending_pipeline_support
    from agent_console.authority_contracts import AuthorityError

    original_continue = ServiceCycleContinuation.continue_once
    original_drive = pending_pipeline_support.drive
    holder, observed = {}, []

    class WithdrawObserved(BaseException):
        pass

    def continued(owner, call, event):
        result = original_continue(owner, call, event)
        holder["bridge"] = BoundServiceExecutionBridge(owner.registry)
        return result

    def inspect(work, native, caller):
        assembly = SimpleNamespace(
            worker=SimpleNamespace(
                repository=SimpleNamespace(work=work),
                transport=SimpleNamespace(caller=caller),
            ),
            execution_repository=native,
        )
        context = automation.subject
        scope = (
            context.scope.tenant_id,
            context.scope.security_domain,
            context.principal_id,
        )
        assert work.owned_business is None
        with native.pool.connection() as c:
            before = c.execute(
                "SELECT count(*) n FROM execution_authority.native_dispatch_facts"
            ).fetchone()["n"]
        discovery = Discovery(assembly, scope, "isolated")
        page = discovery.page()
        assert len(page) == 1
        assert discovery.current(page[0]) == page[0]
        with pytest.raises(AuthorityError, match="BOUND_SERVICE_EXECUTION"):
            Discovery(assembly, (*scope[:2], "service:another"), "isolated")
        with native.pool.connection() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM execution_authority.native_dispatch_facts"
                ).fetchone()["n"]
                == before
            )
            assert (
                c.execute("SELECT to_regclass('fixed_question.answers') t").fetchone()[
                    "t"
                ]
                is None
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM draft_provider_budget.reservations"
                ).fetchone()["n"]
                == 1
            )
        observed.append(page[0])
        if withdraw == "UNKNOWN":
            from contextlib import contextmanager

            # Observation corruption port only; never rewrite immutable command facts.
            class Connection:
                def __init__(self, c):
                    self.c = c

                def execute(self, query, params=()):
                    cursor = self.c.execute(query, params)
                    if "SELECT state,worker_id FROM" in query:
                        rows = [
                            {**row, "state": "UNKNOWN"} for row in cursor.fetchall()
                        ]
                        return SimpleNamespace(fetchall=lambda: rows)
                    return cursor

            class Pool:
                @contextmanager
                def connection(self):
                    with native.pool.connection() as c:
                        yield Connection(c)

            discovery.repository = SimpleNamespace(pool=Pool())
            assert discovery.current(page[0]) is None
            assert discovery.page() == []
            with native.pool.connection() as c:
                assert (
                    c.execute(
                        "SELECT count(*) n FROM execution_authority.native_dispatch_facts"
                    ).fetchone()["n"]
                    == before
                )
            raise WithdrawObserved()
        if withdraw:
            from agent_console.grant_administration_application import (
                GrantRevocationCommand,
            )

            with native.pool.connection() as c:
                grant = c.execute(
                    "SELECT grant_id FROM authorization_admin.grants WHERE subject_principal_id=%s AND owner='EXECUTION' AND action='START' AND exact_resource=%s",
                    (context.principal_id, page[0]["resource"]),
                ).fetchone()
                assert grant is not None
                before_requests = c.execute(
                    "SELECT count(*) n FROM authorization_admin.grant_requests"
                ).fetchone()["n"]
            automation.automation.grants.revoke_grant(
                context,
                GrantRevocationCommand(
                    grant["grant_id"],
                    "TEST_WITHDRAWAL",
                    "withdraw-service-start",
                    surrender=True,
                ),
            )
            assert discovery.current(page[0]) is None
            assert discovery.page() == []
            assert work.dispatches() == ()
            with native.pool.connection() as c:
                assert (
                    c.execute(
                        "SELECT count(*) n FROM authorization_admin.grant_requests"
                    ).fetchone()["n"]
                    == before_requests
                )
                assert (
                    c.execute(
                        "SELECT count(*) n FROM execution_authority.native_dispatch_facts"
                    ).fetchone()["n"]
                    == before
                )
            raise WithdrawObserved()

    def drive(*args, **kwargs):
        return original_drive(
            *args,
            **kwargs,
            bound_service_execution=holder["bridge"],
            discovery_observer=inspect,
        )

    monkeypatch.setattr(ServiceCycleContinuation, "continue_once", continued)
    monkeypatch.setattr(pending_pipeline_support, "drive", drive)
    if withdraw:
        with pytest.raises(WithdrawObserved):
            original_chain(automation, monkeypatch, tmp_path)
    else:
        original_chain(automation, monkeypatch, tmp_path)
    assert len(observed) >= 1
