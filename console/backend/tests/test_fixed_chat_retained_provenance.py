"""Read-port mutations; never UPDATE an immutable context/admission audit row."""

from copy import deepcopy
from types import SimpleNamespace as N

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.digital_employee_definition import digest
from agent_console.fixed_chat_provenance import require_retained
from agent_console.workbench_owner_authorization import WorkbenchOwnerError


def facts():
    context = N(principal_id="human:a", scope=N(tenant_id="t", security_domain="d"))
    original = dict(
        context_id="ctx",
        subject_id="human:a",
        tenant_id="t",
        security_domain="d",
        record=dict(configuration={"exact": "profile"}, conversation_id="chat"),
    )
    binding = dict(
        contextId="ctx",
        configuration={"exact": "profile"},
        understandingPolicyDigest=None,
        questionOnly=False,
    )
    record = dict(
        schemaVersion="owned-business-admission.v1",
        subject="human:a",
        tenantId="t",
        securityDomain="d",
        conversationId="chat",
        contextId="ctx",
        invocationId="inv",
        policyDigest="a" * 64,
        inputSource={"saved": "source"},
        understandingBindings=[binding],
    )
    row = dict(
        admission_id="admission",
        subject_id="human:a",
        tenant_id="t",
        security_domain="d",
        conversation_id="chat",
        invocation_id="inv",
        context_id="ctx",
        policy_digest="a" * 64,
        record=record,
        record_digest=digest(record),
    )
    bound = dict(
        admission=dict(id="admission", digest=row["record_digest"]),
        subjectId="human:a",
        conversationId="chat",
        understanding=dict(invocationId="inv", contextId="ctx"),
        inputSource=record["inputSource"],
        originalContextId="ctx",
    )
    return context, original, row, bound


class Port:
    def __init__(self, original, row, revoked=False, context_revoked=False):
        self.original, self.row, self.revoked, self.context_revoked = (
            original,
            row,
            revoked,
            context_revoked,
        )

    def execute(self, query, params):
        assert not query.startswith(("INSERT", "UPDATE", "DELETE"))
        if "owned_business_revocations" in query:
            value = {"present": 1} if self.revoked else None
        elif "owned_business_admissions" in query:
            value = self.row
        elif "context_call_requests" in query:
            value = self.original
        elif "context_call_revocations" in query:
            value = {"present": 1} if self.context_revoked else None
        else:
            value = None
        return N(fetchone=lambda: value)


@pytest.mark.parametrize(
    "column",
    [
        "subject_id",
        "tenant_id",
        "security_domain",
        "conversation_id",
        "invocation_id",
        "context_id",
        "policy_digest",
        "record_digest",
    ],
)
def test_retained_admission_column_mismatch_rejected(column):
    context, original, row, bound = facts()
    require_retained(Port(original, row), context, bound)
    broken = deepcopy(row)
    broken[column] = "other"
    with pytest.raises(WorkbenchOwnerError):
        require_retained(Port(original, broken), context, bound)


@pytest.mark.parametrize("column", ["subject_id", "tenant_id", "security_domain"])
def test_context_column_scope_mismatch_rejected(column):
    context, original, row, bound = facts()
    original[column] = "other"
    with pytest.raises(WorkbenchOwnerError):
        require_retained(Port(original, row), context, bound)


def test_revocations_do_not_become_expired_lease_renewal():
    context, original, row, bound = facts()
    with pytest.raises(AuthorityError, match="OWNED_BUSINESS_ADMISSION_REVOKED"):
        require_retained(Port(original, row, revoked=True), context, bound)
    with pytest.raises(WorkbenchOwnerError):
        require_retained(Port(original, row, context_revoked=True), context, bound)
