# ruff: noqa: E501 -- Exact same-transaction grant receipt SQL.
"""Exact QUESTION_ANSWER authority through the original independent grant owner."""

from datetime import UTC, timedelta

from .authority_contracts import AuthorityError, ExactGrant
from .fixed_chat_grants import grants_on_connection, static_read_revoked
from .fixed_question_facts import require
from .fixed_question_store import FixedQuestionStore
from .grant_administration_application import GrantDecisionCommand, GrantRequestCommand
from .read_access_recovery import current
from .resource_use_domain import canonical_digest
from .test_resource_read_access import was_denied


def member(identity):
    return ExactGrant("EXECUTION", "QUESTION_ANSWER", identity.exact_resource)


class QuestionGrantTargets:
    """Only a server-verified, persisted exact anchor is requestable."""

    def is_known_exact_target(self, context, grant, *, connection=None):
        prefix = "governed-execution:question:"
        if (
            connection is None
            or grant.owner != "EXECUTION"
            or grant.action != "QUESTION_ANSWER"
            or not grant.exact_resource.startswith(prefix)
        ):
            return False
        present = connection.execute(
            "SELECT to_regclass('fixed_question.questions') AS relation"
        ).fetchone()
        if not present["relation"]:
            return False
        i = FixedQuestionStore(
            connection, (context.scope.tenant_id, context.scope.security_domain)
        ).question(grant.exact_resource[len(prefix) :])
        if i is None or i.exact_resource != grant.exact_resource:
            return False
        owned = connection.execute(
            "SELECT owner_id,archived_at FROM private_conversation.conversations "
            "WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s",
            (i.tenantId, i.securityDomain, i.conversationId),
        ).fetchone()
        return (
            owned is not None
            and owned["owner_id"] == context.principal_id
            and owned["archived_at"] is None
        )


def issue(call, automation, policy, identity, checkpoint):
    """Called only after exact facts, account, conversation CAS and anchor locks.

    The grant request key is identity-scoped, independent of client command key;
    a second tab cannot manufacture a second lease for the same question.
    """
    c, context = call.connection, call.context
    bound = grants_on_connection(automation.grants, c)
    grant = member(identity)
    if static_read_revoked(bound.generation, context, (grant,)):
        raise AuthorityError("FIXED_QUESTION_ANSWER_REVOKED")
    if current(bound, context, (grant,)) in {"REVOKED", "UNAVAILABLE"} or was_denied(
        c, context, grant
    ):
        raise AuthorityError("FIXED_QUESTION_ANSWER_DENIED")
    issuer = automation.authenticate(context)
    require(
        issuer.principal_id == policy.issuerId
        and issuer.session_id_or_service_credential_id == policy.issuerCredentialId
        and issuer.principal_id not in {context.principal_id, identity.executionSubject}
    )
    credential = bound.generation.credential_by_id(policy.issuerCredentialId)
    require(credential is not None)
    key = "fixed-question:" + canonical_digest([context.principal_id, identity.digest])
    request = bound.submit_request(
        context, GrantRequestCommand("FIXED_QUESTION_ANSWER", (grant,), key)
    )
    expires = min(
        policy.expiresAt,
        checkpoint.human_expires_at,
        checkpoint.authority_expires_at,
        credential.expires_at,
        request.created_at + timedelta(seconds=policy.grantTTLSeconds),
    )
    require(expires > bound.clock())
    basis = "fixed-question-policy:" + policy.digest
    bound.decide_request(
        issuer,
        GrantDecisionCommand(
            request.request_id,
            True,
            "ASSIGNED_BUSINESS_DUTY",
            "POLICY",
            basis,
            None,
            expires.astimezone(UTC),
            "fixed-question-decision:" + canonical_digest([key, request.request_id]),
            expected_version=1,
        ),
    )
    automation.proof_grants(call, (grant,))
    rows = c.execute(
        "SELECT g.grant_id,g.decision_id,g.expires_at,d.basis_type,"
        "d.basis_reference_digest,d.issuer_principal_id FROM authorization_admin.grants g "
        "JOIN authorization_admin.grant_decisions d USING(decision_id) "
        "WHERE g.request_id=%s AND g.tenant_id=%s AND g.security_domain=%s "
        "AND g.subject_principal_id=%s AND g.owner=%s AND g.action=%s AND g.exact_resource=%s",
        (
            request.request_id,
            context.scope.tenant_id,
            context.scope.security_domain,
            context.principal_id,
            grant.owner,
            grant.action,
            grant.exact_resource,
        ),
    ).fetchall()
    require(len(rows) == 1)
    row = rows[0]
    require(
        row["expires_at"] == expires and row["issuer_principal_id"] == policy.issuerId
    )
    require(
        row["basis_type"] == "POLICY"
        and row["basis_reference_digest"]
        == canonical_digest(dict(type="POLICY", reference=basis))
    )
    return request.request_id, row["decision_id"], row["grant_id"], expires
