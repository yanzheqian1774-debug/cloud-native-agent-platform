# ruff: noqa: F401,F811 -- Shared original isolated owner fixtures.
"""Real Service owner routed with controlled empty Human peer, no actual model."""

import pytest
import test_bound_service_execution as original
from agent_operator.native_host_policy_set import LeafKind
from agent_operator.native_host_service_discovery import Discovery
from native_policy_set_owner_support import routed
from test_bound_service_execution import automation, case, repository, services


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
def test_service_original_owner_passes_policy_set_router(
    automation, monkeypatch, tmp_path
):
    def discovery(assembly, scope, fingerprint):
        return routed(Discovery(assembly, scope, fingerprint), LeafKind.BOUND_SERVICE)

    monkeypatch.setattr(original, "Discovery", discovery)
    original.test_bound_service_discovery_runs_original_tasks_and_returns_to_original_chat(
        automation, monkeypatch, tmp_path, False
    )
