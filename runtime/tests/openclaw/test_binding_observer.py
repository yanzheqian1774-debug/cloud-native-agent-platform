from dataclasses import replace
from datetime import UTC, datetime

import pytest
from agent_core.execution_contract import (
    CommandId,
    Generation,
    PlacementId,
    RuntimeInstanceId,
    ScopeIdentity,
)
from agent_core.openclaw_binding import (
    AssociationStatus,
    OpenClawGenerationBinding,
    OpenClawRuntimeBinding,
)
from agent_runtime.providers.openclaw.binding_observer import OpenClawBindingObserver
from agent_runtime.providers.openclaw.models import OpenClawError, ReasonCode


def records(tmp_path):
    now = datetime(2026, 9, 12, tzinfo=UTC)
    scope = ScopeIdentity("tenant-a", "restricted")
    binding = OpenClawRuntimeBinding(
        scope,
        RuntimeInstanceId("runtime-1"),
        PlacementId("placement-1"),
        "a" * 64,
        "agent-1",
        str(tmp_path.resolve()),
        "gateway-host-1",
        "storage-domain-1",
        "2026.7.1-2",
        "authorization-1",
        now,
    )
    generation = OpenClawGenerationBinding(
        scope,
        binding.runtime_instance_id,
        Generation(1),
        "agent:agent-1:runtime-1-g1",
        "session-1",
        CommandId("command-1"),
        "idempotency-1",
        "b" * 64,
        AssociationStatus.UNVERIFIED,
        0,
        now,
    )
    return binding, generation, now


class ReadClient:
    def __init__(self, binding, generation):
        self.binding = binding
        self.calls = []
        self.responses = {
            "health": {"eventLoop": {"degraded": False}},
            "status": {"runtimeVersion": "2026.7.1-2"},
            "agents.list": {
                "agents": [
                    {
                        "id": binding.agent_id,
                        "workspace": binding.canonical_workspace,
                    }
                ]
            },
            "agents.files.list": {"files": []},
            "sessions.list": {
                "sessions": [
                    {
                        "key": generation.session_key,
                        "sessionId": generation.session_id,
                    }
                ]
            },
            "sessions.describe": {
                "key": generation.session_key,
                "sessionId": generation.session_id,
            },
            "sessions.get": {"messages": []},
        }

    def binding_observation_domain(self):
        return (
            self.binding.gateway_digest,
            self.binding.workspace_host,
            self.binding.workspace_storage_domain,
        )

    def read_only_rpc(self, method, params, *, timeout_seconds=None):
        self.calls.append((method, params))
        response = self.responses[method]
        if isinstance(response, Exception):
            raise response
        return response


def test_composite_match_uses_every_surface_and_never_resolve_or_write(tmp_path):
    binding, generation, now = records(tmp_path)
    client = ReadClient(binding, generation)

    result = OpenClawBindingObserver(client).observe(
        binding, generation, high_water=1, at=now
    )

    assert result.association_status is AssociationStatus.MATCHED
    assert result.freshness_deadline.timestamp() - result.observed_at.timestamp() == 30
    assert [method for method, _ in client.calls] == [
        "health",
        "status",
        "agents.list",
        "agents.files.list",
        "sessions.list",
        "sessions.describe",
        "sessions.get",
    ]
    assert all("resolve" not in method for method, _ in client.calls)
    assert all(
        not any(
            token in method
            for token in ("create", "update", "patch", "delete", "abort")
        )
        for method, _ in client.calls
    )


@pytest.mark.parametrize("failure", ["missing", "duplicate", "partial"])
def test_missing_duplicate_and_partial_session_require_recovery(tmp_path, failure):
    binding, generation, now = records(tmp_path)
    client = ReadClient(binding, generation)
    session = {
        "key": generation.session_key,
        "sessionId": generation.session_id,
    }
    client.responses["sessions.list"] = {
        "sessions": [] if failure in {"missing", "partial"} else [session, session]
    }

    result = OpenClawBindingObserver(client).observe(
        binding, generation, high_water=1, at=now
    )

    assert result.association_status is AssociationStatus.RECOVERY_REQUIRED
    assert not result.session_matched
    assert [method for method, _ in client.calls][-1] == "sessions.list"


def test_workspace_or_session_mismatch_is_not_reported_as_match(tmp_path):
    binding, generation, now = records(tmp_path)
    client = ReadClient(binding, generation)
    client.responses["agents.list"]["agents"][0]["workspace"] = str(tmp_path / "other")
    workspace = OpenClawBindingObserver(client).observe(
        binding, generation, high_water=1, at=now
    )
    assert workspace.association_status is AssociationStatus.MISMATCHED

    client = ReadClient(binding, generation)
    client.responses["sessions.describe"]["sessionId"] = "other-session"
    session = OpenClawBindingObserver(client).observe(
        binding, generation, high_water=1, at=now
    )
    assert session.association_status is AssociationStatus.MISMATCHED


def test_timeout_is_recovery_required_and_does_not_issue_later_calls(tmp_path):
    binding, generation, now = records(tmp_path)
    client = ReadClient(binding, generation)
    client.responses["sessions.list"] = OpenClawError(
        ReasonCode.GATEWAY_UNAVAILABLE.value
    )

    result = OpenClawBindingObserver(client).observe(
        binding, generation, high_water=1, at=now
    )

    assert result.association_status is AssociationStatus.RECOVERY_REQUIRED
    assert result.reason_code == ReasonCode.GATEWAY_UNAVAILABLE.value
    assert [method for method, _ in client.calls][-1] == "sessions.list"


def test_fixed_source_version_mismatch_is_rejected_before_session_reads(tmp_path):
    binding, generation, now = records(tmp_path)
    binding = replace(binding, source_version="2026.7.2")
    client = ReadClient(binding, generation)

    result = OpenClawBindingObserver(client).observe(
        binding, generation, high_water=1, at=now
    )

    assert result.association_status is AssociationStatus.MISMATCHED
    assert [method for method, _ in client.calls] == ["health", "status"]


def test_total_reconciliation_budget_fails_closed_before_another_rpc(tmp_path):
    binding, generation, now = records(tmp_path)
    client = ReadClient(binding, generation)
    ticks = iter((0.0, 1.0, 2.0, 3.0, 4.0, 31.0))

    result = OpenClawBindingObserver(
        client, monotonic_clock=lambda: next(ticks)
    ).observe(binding, generation, high_water=1, at=now)

    assert result.association_status is AssociationStatus.RECOVERY_REQUIRED
    assert result.reason_code == ReasonCode.GATEWAY_UNAVAILABLE.value
    assert [method for method, _ in client.calls] == [
        "health",
        "status",
        "agents.list",
        "agents.files.list",
    ]
