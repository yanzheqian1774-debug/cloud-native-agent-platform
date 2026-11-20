"""Controlled host orchestration checks; not a real service/owner acceptance."""

from contextlib import contextmanager
from types import SimpleNamespace as N
from unittest.mock import Mock

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.fixed_work_cycle_host import FixedWorkCycleHost
from agent_console.fixed_work_service_continuation import ServiceCycleContinuation
from agent_console.fixed_work_service_runtime import ServicePlanningRuntime


class Cursor:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value

    def fetchall(self):
        return self.value


@contextmanager
def value(v):
    yield v


def setup_host(*, prepared=True, result=None):
    policy = N(
        allowedEventIds=("slot",),
        tenantId="t",
        securityDomain="d",
        work=N(resource_id="w"),
        digest="p",
    )
    row = (
        dict(
            subject_id="service:s",
            credential_id="cred",
            policy_digest="p",
            invocation_id="original",
        )
        if prepared
        else None
    )
    c = N(transaction=lambda: value(None))
    c.execute = Mock(side_effect=[Cursor(row), Cursor([])])
    registry = N(
        _policy=lambda: policy,
        _check=Mock(),
        repository=N(pool=N(connection=lambda: value(c))),
    )
    runtime = object.__new__(ServicePlanningRuntime)
    runtime.registry = registry
    runtime.begin = Mock(return_value={"result": result})
    runtime.service = N(
        read=Mock(return_value={"result": result}), application=N(confirm=Mock())
    )
    continuation = object.__new__(ServiceCycleContinuation)
    continuation.registry = registry
    continuation.continue_once = Mock()
    call_scope = Mock()
    host = FixedWorkCycleHost(runtime, continuation, call_scope, enabled=True)
    context = N(
        principal_id="service:s",
        scope=N(tenant_id="t", security_domain="d"),
        session_id_or_service_credential_id="cred",
    )
    return host, context


def test_disabled_does_not_read_or_begin():
    host, context = setup_host()
    host.enabled = False
    with pytest.raises(AuthorityError, match="FIXED_WORK_CYCLE_HOST_DISABLED"):
        host.step(context, "slot")
    host.runtime.registry._check.assert_not_called()
    host.runtime.begin.assert_not_called()


@pytest.mark.parametrize("status", ["OUTCOME_UNKNOWN", "FAILED", "RUNNING"])
def test_saved_non_success_never_begins_or_confirms(status):
    host, context = setup_host(result={"technical_status": status, "kind": None})
    assert host.step(context, "slot")["stage"] == "PLANNING_OBSERVATION"
    host.runtime.begin.assert_not_called()
    assert host.runtime.service.read.call_args.kwargs == {"settle_receipt": False}
    assert host.runtime.service.read.call_args.args[1] == "original"
    host.runtime.service.application.confirm.assert_not_called()
    host.continuation.continue_once.assert_not_called()


def test_saved_preparation_missing_invocation_never_rebegins():
    host, context = setup_host()
    host.runtime.service.read.side_effect = RuntimeError("PLANNING_NOT_FOUND")
    with pytest.raises(RuntimeError, match="PLANNING_NOT_FOUND"):
        host.step(context, "slot")
    host.runtime.begin.assert_not_called()
    host.runtime.service.application.confirm.assert_not_called()


def test_new_event_uses_one_normal_owner_begin_then_stops_on_unknown():
    host, context = setup_host(
        prepared=False,
        result={
            "technical_status": "OUTCOME_UNKNOWN",
            "kind": None,
        },
    )
    assert host.step(context, "slot")["stage"] == "PLANNING_OBSERVATION"
    host.runtime.begin.assert_called_once_with(context, "slot")
    host.runtime.service.application.confirm.assert_not_called()
    host.continuation.continue_once.assert_not_called()


def test_disabled_composition_does_not_load_policy_or_operator_services():
    from agent_console.fixed_work_cycle_composition import compose_cycle_service

    assert (
        compose_cycle_service(
            planning_service=None,
            authorization=None,
            policy_path="/not-read",
            readonly_owner=None,
            current_context=None,
            authorized_call_scope=None,
            database_fingerprint="not-read",
        )
        is None
    )


def test_policy_change_after_model_return_blocks_confirmation():
    host, context = setup_host(
        result={
            "technical_status": "SUCCEEDED",
            "kind": "VALID_SUGGESTION",
            "proposal": {"proposal_id": "plan", "revision": 1},
            "proposal_digest": "digest",
        }
    )
    original = host.runtime.registry._policy()
    original.work.model_dump = lambda **_: {"resource_id": "w"}
    host.runtime.registry._policy = Mock(side_effect=[original, N(digest="changed")])
    host.call_scope.return_value = value(N(context=context, connection=None))
    with pytest.raises(AuthorityError, match="FIXED_WORK_CYCLE_CONFIGURATION_CHANGED"):
        host.step(context, "slot")
    host.runtime.begin.assert_not_called()
    host.runtime.service.application.confirm.assert_not_called()
    host.continuation.continue_once.assert_not_called()
