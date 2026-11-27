# ruff: noqa: F401,F811 -- Shared original isolated owner fixtures.
"""Real Human owner routed with controlled empty Service peer, no actual model."""

from types import SimpleNamespace

import pytest
from agent_operator.native_host_policy_set import LeafKind
from agent_operator.native_host_service_discovery import Discovery
from native_policy_set_owner_support import routed as route_discovery
from owned_business_consumer_support import configure_scope, prepare_source
from test_conversation_experience_admission import pytestmark as pgmark
from test_owned_business_consumer_chain import (
    adopted,
    cleanup_consumer_resources,
    env,
    ordinary,
    owned_created,
    owned_ready,
    routed,
    setup,
)
from test_owned_business_consumer_chain import (
    test_same_owned_problem_confirms_prepares_and_worker_reads as exercise,
)

pytestmark = [
    pgmark,
    pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True),
    pytest.mark.parametrize(
        "owned_ready",
        [
            dict(
                mode="SOURCE_SUCCESSOR",
                prepare_source=prepare_source,
                configure_scope=configure_scope,
            )
        ],
        indirect=True,
    ),
]


def test_human_original_owner_passes_policy_set_router(
    owned_created, tmp_path, request
):
    e = owned_created
    observed = []

    def inspect(work, native, receipt, ready):
        assembly = SimpleNamespace(
            worker=SimpleNamespace(
                repository=SimpleNamespace(work=work),
                transport=SimpleNamespace(caller=None),
            ),
            execution_repository=native,
        )
        scope = (
            e.context.scope.tenant_id,
            e.context.scope.security_domain,
            e.context.principal_id,
        )
        discovery = route_discovery(
            Discovery(assembly, scope, "isolated-human"), LeafKind.HUMAN_OWNED
        )
        page = discovery.page()
        assert len(page) == 1
        assert page[0]["preparationDigest"] == receipt["preparationDigest"]
        assert discovery.current(page[0]) == page[0]
        observed.append(page[0])

    e.consumer_execution_observer = inspect
    exercise(e, tmp_path, request)
    assert len(observed) == 1
