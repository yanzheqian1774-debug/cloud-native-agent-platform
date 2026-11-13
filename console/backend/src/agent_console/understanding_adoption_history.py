"""Historical renewal eligibility from actual C2 ancestry, never execution admission."""

from .context_call_admission import lock, request_row
from .draft_assistance import DraftInvocationState, DraftResultKind, DraftScope
from .draft_assistance_authorization import read_grant
from .draft_assistance_postgres import PostgresDraftAssistanceRepository
from .read_access_recovery import current
from .resource_automation import bound_grants
from .test_resource_read_access import was_denied
from .understanding_adoption_postgres import read_chain
from .understanding_result_adoption import require


def source(resolver, c, context, invocation_id, conversation):
    require(
        resolver is not None
        and resolver.enabled is True
        and resolver.profile.adapter_revision
        in {
            "v3-relation-adoption",
            "v3-relation-adoption-source",
            "v3-relation-adoption-source-answers",
        }
        and resolver.routing.experience.root is resolver.root
        and resolver.routing.experience.routing_document.scopeMode
        == "EXISTING_WORK_AND_INITIAL_UNDERSTANDING",
        "BRIDGE_DISABLED",
    )
    root, routing = resolver.root, resolver.routing
    account, _, _ = root.experience._require(root, c, context)
    routing.experience._require(routing, c, context)
    bound = bound_grants(root.delegation.grants, c)
    scope = (context.scope.tenant_id, context.scope.security_domain)
    contexts = set()

    def eligible(connection, ctx, original, actual):
        for invocation in (original, actual):
            contexts.add(invocation.context_id)
            grant = read_grant(invocation)
            state = current(bound, ctx, (grant,))
            require(
                state in {"EFFECTIVE", "NOT_EFFECTIVE"}
                and not was_denied(connection, ctx, grant),
                "READ_DENIED",
            )
            prior = connection.execute(
                "SELECT 1 FROM authorization_admin.grants WHERE tenant_id=%s "
                "AND security_domain=%s AND subject_principal_id=%s AND owner=%s "
                "AND action=%s AND exact_resource=%s LIMIT 1",
                (
                    *scope,
                    ctx.principal_id,
                    grant.owner,
                    grant.action,
                    grant.exact_resource,
                ),
            ).fetchone()
            require(prior is not None, "READ_DENIED")

    # This callback authorizes renewal inspection of previously granted exact READ,
    # not business consumption. The chain itself still validates every saved version.
    chain = read_chain(c, context, invocation_id, eligible)
    require(bool(chain), "REFERENCE_REQUIRED")
    locked_contexts = frozenset(contexts)
    for identity in sorted(locked_contexts):
        lock(c, identity)
    # Explicit revocation and current immutable lineage are rechecked under the locks.
    checked = read_chain(c, context, invocation_id, eligible)
    require(checked == chain and contexts == locked_contexts, "REFERENCE_CHANGED")
    result = PostgresDraftAssistanceRepository._latest(
        c, DraftScope.from_context(context), invocation_id
    )
    require(
        result is not None
        and result.state is DraftInvocationState.SUCCEEDED
        and result.result_kind is DraftResultKind.DRAFT_READY
        and result.snapshot is not None,
        "RESULT_NOT_ADOPTABLE",
    )
    resolver.for_result(result)
    origin_id = chain[-1]["target"]["original_context_id"]
    require(
        all(item["target"]["conversation_id"] == conversation for item in chain),
        "BUSINESS_SCOPE_DENIED",
    )
    rows = {}
    for identity in sorted(contexts):
        row = request_row(c, identity)
        require(row is not None, "CONTEXT_NOT_FOUND")
        rows[identity] = row
        record = row["record"]
        original = identity == origin_id
        selected = None if original else resolver.for_record(record)
        if selected is not None:
            selected.routing.experience._require(selected.routing, c, context)
        require(
            (row["tenant_id"], row["security_domain"]) == scope
            and row["subject_id"] == context.principal_id
            and record.get("conversation_id") == conversation
            and record.get("experience_policy_digest") == root.experience.policy_digest
            and record.get("configuration")
            == (root.configuration if original else selected.routing.configuration)
            and record.get("account_id") == account["account_id"]
            and record.get("budget_allowance_id")
            == root.experience.document.allowanceId,
            "BUSINESS_SCOPE_DENIED",
        )
        require(
            (
                not record.get("owned_understanding_policy_digest")
                and conversation in root.experience.document.conversations
            )
            if original
            else (
                record.get("question_only") is True
                and record.get("owned_understanding_policy_digest")
                == selected.routing.experience.understanding_policy_digest
            ),
            "BUSINESS_SCOPE_DENIED",
        )
        revoked = c.execute(
            "SELECT 1 FROM authorization_admin.context_call_decisions d "
            "JOIN authorization_admin.context_call_revocations r USING(admission_id) "
            "WHERE d.context_id=%s LIMIT 1",
            (identity,),
        ).fetchone()
        require(revoked is None, "READ_DENIED")
    return rows[result.context_id]
