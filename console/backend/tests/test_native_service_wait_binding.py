# ruff: noqa: F401,F811,E501 -- Original random owner fixture chain.
"""Real service planning/START/BOUND rows; controlled provider/Kubernetes only."""

from dataclasses import replace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.bound_service_execution import BoundServiceExecutionBridge
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.execution_preparation_postgres import PreparedExecutionStore
from agent_console.fixed_work_service_continuation import ServiceCycleContinuation
from test_fixed_chat_delivery_postgres import automation, case, repository, services
from test_fixed_chat_delivery_postgres import (
    test_bound_committed_event_is_read_in_original_chat_without_human_model_lease as original_chain,
)


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
def test_service_wait_source_uses_original_committed_owners_not_human_admission(
    automation, monkeypatch, tmp_path
):
    original = ServiceCycleContinuation.continue_once
    seen = []

    def observe(owner, call, event):
        result = original(owner, call, event)
        c = call.connection
        prepared, _ = PreparedExecutionStore(c).read(
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
            result["runId"],
        )
        row = c.execute(
            "SELECT payload FROM execution_authority.native_dispatch_commands WHERE namespace=%s AND security_domain=%s AND authorization_resource=%s ORDER BY command_id LIMIT 1",
            (
                prepared.namespace,
                prepared.security_domain,
                "governed-execution:prepared:" + prepared.digest,
            ),
        ).fetchone()
        assert row is not None
        command = PostgresExecutionAuthorityRepository._dispatch_command(row["payload"])
        reader = BoundServiceExecutionBridge(owner.registry)
        value = reader.read(c, call.context, command, prepared)
        source = c.execute(
            "SELECT record,digest FROM fixed_work_sources.bindings"
        ).fetchone()
        assert value.conversation_id == source["record"]["conversationId"]
        assert value.execution_subject == call.context.principal_id
        assert value.execution_subject.startswith("service:")
        assert value.binding_digest == source["digest"]
        assert value.source == prepared.source_snapshot
        with pytest.raises(
            AuthorityError, match=r"^BOUND_SERVICE_EXECUTION_BINDING_INVALID$"
        ):
            reader.read(
                c,
                call.context,
                replace(command, principal_id=source["record"]["subjectId"]),
                prepared,
            )
        with pytest.raises(
            AuthorityError, match=r"^BOUND_SERVICE_EXECUTION_BINDING_INVALID$"
        ):
            reader.read(
                c,
                call.context,
                replace(command, credential_id="different-service-credential"),
                prepared,
            )
        seen.append(value)
        return result

    monkeypatch.setattr(ServiceCycleContinuation, "continue_once", observe)
    original_chain(automation, monkeypatch, tmp_path)
    assert seen
