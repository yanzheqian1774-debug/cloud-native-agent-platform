"""Actual same-case planning owner; generated model content is controlled."""

# ruff: noqa: F401,F811 -- Shared disposable PostgreSQL fixtures.
import pytest
from owned_business_consumer_support import configure_scope, prepare_source
from owned_business_planning_support import (
    activate_created,
    document_semantics,
    governed_planning_service,
    planning_application,
)
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark as pgmark
from test_conversation_relation_bff import routed
from test_owned_business_admission import owned_created, owned_ready
from test_owned_business_consumer_chain import cleanup_consumer_resources
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted

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


def test_current_real_resources_and_mixed_lineage_generate_one_proposal(owned_created):
    e = activate_created(owned_created)
    _, _, current = planning_application(e)
    semantics = document_semantics(e, current["target"])
    with governed_planning_service(e, semantics) as (
        service,
        principal,
        request,
        provider,
    ):
        result = service.begin(principal, request)
        assert result["result"]["technical_status"] == "SUCCEEDED", result
        assert result["result"]["kind"] == "VALID_SUGGESTION", result
        assert result["result"]["proposal"]["semantics"]["target"] == current["target"]
        repeat = service.begin(principal, request)
        assert repeat["result"] == result["result"]
        assert provider.calls == 1
    assert len(e.calls) == e.business_model_call_count
