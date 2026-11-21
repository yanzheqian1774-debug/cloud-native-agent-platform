"""Read-port tampering and current static tombstone boundaries, no audit writes."""

from copy import deepcopy
from types import SimpleNamespace as N

import pytest
from agent_console.authority_contracts import AuthorityError, ExactGrant
from agent_console.digital_employee_definition import digest
from agent_console.fixed_chat_facts import source_fact
from agent_console.fixed_chat_grants import static_read_revoked
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.workbench_owner_authorization import WorkbenchOwnerError


def fact():
    work = ExactReference(resource_id="w", revision_id="r", digest="a" * 64)
    record = dict(
        subjectId="human:a",
        conversationId="chat",
        commandId="command",
        work=work.model_dump(mode="json"),
        executionEnabled=False,
    )
    row = dict(
        namespace="t",
        security_domain="d",
        subject_id="human:a",
        conversation_id="chat",
        command_id="command",
        work_id="w",
        revision_id="r",
        record=record,
        digest=digest(record),
    )
    return work, row


@pytest.mark.parametrize(
    "column",
    [
        "namespace",
        "security_domain",
        "subject_id",
        "conversation_id",
        "command_id",
        "work_id",
        "revision_id",
        "digest",
    ],
)
def test_source_fact_rejects_every_mismatched_persisted_identity(column):
    work, row = fact()
    assert source_fact(row, ("t", "d"), "human:a", "chat", work) == row["record"]
    broken = deepcopy(row)
    broken[column] = "other"
    with pytest.raises(WorkbenchOwnerError):
        source_fact(broken, ("t", "d"), "human:a", "chat", work)


@pytest.mark.parametrize(
    "field", ["subjectId", "conversationId", "commandId", "work", "executionEnabled"]
)
def test_self_rehashed_json_cannot_override_persisted_source_scope(field):
    work, row = fact()
    broken = deepcopy(row)
    broken["record"][field] = True if field == "executionEnabled" else "other"
    broken["digest"] = digest(broken["record"])
    with pytest.raises(WorkbenchOwnerError):
        source_fact(broken, ("t", "d"), "human:a", "chat", work)


@pytest.mark.parametrize(
    "identity,blocked",
    [("local", True), ("source", True), ("other", False), ("orphan", None)],
)
def test_static_tombstone_all_identity_sources_and_unknown_mapping(identity, blocked):
    scope = N(tenant_id="t", security_domain="d")
    context = N(scope=scope, principal_id="human:a")
    grant = ExactGrant("EXECUTION", "READ", "governed-execution:prepared:" + "a" * 64)
    own = N(
        scope=scope,
        principal_id="human:a",
        credential_id="local",
        grant_source_id="source",
    )
    other = N(scope=scope, principal_id="human:other", credential_id="other")
    generation = N(
        credentials=(other,),
        local_accounts=(own,),
        static_grant_revocation_tombstones=frozenset({(identity, grant)}),
    )
    if blocked is None:
        with pytest.raises(AuthorityError, match="FIXED_CHAT_READ_IDENTITY_UNVERIFIED"):
            static_read_revoked(generation, context, (grant,))
    else:
        assert static_read_revoked(generation, context, (grant,)) is blocked
