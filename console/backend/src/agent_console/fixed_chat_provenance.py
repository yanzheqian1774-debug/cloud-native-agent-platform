# ruff: noqa: E501 -- Exact retained identity queries.
"""Retained BOUND provenance and revocation; never reactivate a model lease."""

from .context_call_admission import lock, request_row
from .digital_employee_definition import digest
from .fixed_chat_facts import require
from .owned_business_postgres import context_binding, require_not_revoked


def require_retained(c, context, bound):
    proof = bound["admission"]
    require_not_revoked(c, proof["id"])
    row = c.execute(
        "SELECT * FROM authorization_admin.owned_business_admissions WHERE admission_id=%s",
        (proof["id"],),
    ).fetchone()
    require(row is not None)
    record = row["record"]
    require(
        row["record_digest"] == proof["digest"] == digest(record)
        and record["schemaVersion"] == "owned-business-admission.v1"
        and row["subject_id"]
        == record["subject"]
        == context.principal_id
        == bound["subjectId"]
        and row["tenant_id"] == record["tenantId"] == context.scope.tenant_id
        and row["security_domain"]
        == record["securityDomain"]
        == context.scope.security_domain
        and row["conversation_id"]
        == record["conversationId"]
        == bound["conversationId"]
        and row["invocation_id"]
        == record["invocationId"]
        == bound["understanding"]["invocationId"]
        and row["context_id"]
        == record["contextId"]
        == bound["understanding"]["contextId"]
        and row["policy_digest"] == record["policyDigest"]
        and record["inputSource"] == bound["inputSource"]
    )
    bindings = record["understandingBindings"]
    identities = {b["contextId"] for b in bindings}
    require(
        len(bindings) == len(identities)
        and {bound["originalContextId"], row["context_id"]} <= identities
    )
    for binding in sorted(bindings, key=lambda value: value["contextId"]):
        lock(c, binding["contextId"])
        original = request_row(c, binding["contextId"])
        require(original is not None)
        require(
            original["subject_id"] == context.principal_id
            and original["tenant_id"] == context.scope.tenant_id
            and original["security_domain"] == context.scope.security_domain
            and original["record"].get("conversation_id") == bound["conversationId"]
            and context_binding(original) == binding
        )
        require(
            not c.execute(
                "SELECT 1 FROM authorization_admin.context_call_decisions d "
                "JOIN authorization_admin.context_call_revocations r USING(admission_id) WHERE d.context_id=%s",
                (binding["contextId"],),
            ).fetchone()
        )
