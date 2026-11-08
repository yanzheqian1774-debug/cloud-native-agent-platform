"""Browsing planning references never reconciles original provider receipts."""

from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from agent_console.plan_suggestion_api import install_planning_invocations
from fastapi import FastAPI


@pytest.mark.parametrize("by_key", [False, True])
def test_conversation_planning_projection_disables_settlement(by_key):
    service = NS(
        read=Mock(return_value={"original": True}),
        invocations=NS(find_request=Mock(return_value="original-invocation")),
        application=NS(scope=lambda p: p),
    )
    app = FastAPI()
    install_planning_invocations(lambda _: service)(app, Mock(), Mock(), Mock())
    context = NS(
        principal_id="human:owner",
        scope=NS(tenant_id="tenant", security_domain="domain"),
    )
    result = app.state.conversation_planning_reader(
        context, "original-key" if by_key else "original-invocation", by_key=by_key
    )
    assert result == {"original": True}
    args, kwargs = service.read.call_args
    assert args[0].principal_id == context.principal_id
    assert args[1] == "original-invocation"
    assert kwargs == {"settle_receipt": False}
    assert service.invocations.find_request.call_count == int(by_key)
