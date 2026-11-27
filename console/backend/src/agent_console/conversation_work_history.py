"""Derive historical READ targets from original owned work; never execution rights."""

from .authority_contracts import AuthorityError, ExactGrant
from .business_problem_authorization import problem_resource
from .context_call_admission import lock, request_row


def targets(service, records, c, context, conversation):
    if getattr(service, "conversation_relation", None) is None:
        return set()
    if not c.execute(
        "SELECT to_regclass('private_conversation.journeys') present"
    ).fetchone()["present"]:
        return set()
    scope = records.scope(context)
    from .conversation_goal_selection import journal_relation

    journals = c.execute(
        f"SELECT state FROM {journal_relation(c)} j WHERE tenant_id=%s "
        "AND security_domain=%s AND conversation_id=%s",
        (*scope, conversation),
    ).fetchall()
    result = set()
    for journal in journals:
        result.update(
            _targets_for_state(
                service, records, c, context, conversation, journal.get("state") or {}
            )
        )
    return result


def _targets_for_state(service, records, c, context, conversation, state):
    scope = records.scope(context)
    problem = state.get("problem")
    if not problem:
        return set()
    if not isinstance(problem, dict):
        raise AuthorityError("CONVERSATION_HISTORY_WORK_SOURCE_MISMATCH")
    policy = service.experience
    ref = tuple(
        problem.get(k) for k in ("business_problem_id", "revision_id", "digest")
    )
    identity, revision, commitment = ref
    if not all(isinstance(v, str) and v for v in ref):
        raise AuthorityError("CONVERSATION_HISTORY_WORK_SOURCE_MISMATCH")
    links = c.execute(
        "SELECT target FROM private_conversation.links WHERE tenant_id=%s "
        "AND security_domain=%s AND conversation_id=%s "
        "AND target->>'problemId'=%s",
        (*scope, conversation, identity),
    ).fetchall()
    if not any(
        tuple(r["target"].get(k) for k in ("problemId", "revisionId", "problemDigest"))
        == ref
        for r in links
    ):
        raise AuthorityError("CONVERSATION_HISTORY_WORK_SOURCE_MISMATCH")
    binding = c.execute(
        "SELECT context_id,invocation_id FROM authorization_admin.context_call_objects "
        "WHERE tenant_id=%s AND security_domain=%s AND owner='BUSINESS_PROBLEM' "
        "AND resource_id=%s",
        (*scope, identity),
    ).fetchone()
    row = request_row(c, binding["context_id"]) if binding else None
    record = (row or {}).get("record") or {}
    adopted = False
    owned = getattr(service, "owned_business", None)
    owned_record = None
    owned_binding = None
    if owned is not None and binding:
        from .owned_business_postgres import saved

        owned_record = saved(c, context, binding["invocation_id"])
    if owned_record is not None:
        from .plan_suggestion_domain import ExactReference

        owned_binding = owned.work(
            c,
            context,
            ExactReference(
                resource_id=identity, revision_id=revision, digest=commitment
            ),
            history=True,
        )
        adopted = True
    elif row and record.get("configuration") != service.configuration:
        from .draft_assistance import DraftAssistanceError
        from .understanding_adoption_history import source

        try:
            row = source(
                getattr(service, "understanding_adoption", None),
                c,
                context,
                binding["invocation_id"],
                conversation,
            )
        except DraftAssistanceError as exc:
            raise AuthorityError("CONVERSATION_HISTORY_WORK_SOURCE_MISMATCH") from exc
        if row["context_id"] != binding["context_id"]:
            raise AuthorityError("CONVERSATION_HISTORY_WORK_SOURCE_MISMATCH")
        record = row["record"]
        adopted = True
    elif binding:
        lock(c, binding["context_id"])
    if (
        not row
        or (row["tenant_id"], row["security_domain"]) != tuple(scope)
        or row["subject_id"] != context.principal_id
        or record.get("conversation_id") != conversation
        or record.get("experience_policy_digest") != policy.policy_digest
        or (not adopted and record.get("configuration") != service.configuration)
    ):
        raise AuthorityError("CONVERSATION_HISTORY_WORK_SOURCE_MISMATCH")
    if adopted:
        pass  # The historical resolver validated every exact context in the chain.
    elif record.get("owned_understanding_policy_digest"):
        policy.require_record(c, context, row)
    elif conversation not in policy.document.conversations:
        raise AuthorityError("CONVERSATION_HISTORY_WORK_SCOPE_DENIED")
    # Expiration of the old call lease is allowed for READ, explicit revocation is not.
    if c.execute(
        "SELECT 1 FROM authorization_admin.context_call_decisions d "
        "JOIN authorization_admin.context_call_revocations r USING(admission_id) "
        "WHERE d.context_id=%s LIMIT 1",
        (row["context_id"],),
    ).fetchone():
        raise AuthorityError("CONVERSATION_HISTORY_WORK_REVOKED")
    original = c.execute(
        "SELECT record FROM draft_assistance.invocation_versions WHERE namespace=%s "
        "AND security_domain=%s AND invocation_id=%s "
        "ORDER BY aggregate_version DESC LIMIT 1",
        (*scope, binding["invocation_id"]),
    ).fetchone()
    invocation = (original or {}).get("record") or {}
    if (
        invocation.get("contextId") != row["context_id"]
        or invocation.get("initiatingPrincipalId") != context.principal_id
        or invocation.get("state") != "SUCCEEDED"
        or invocation.get("resultKind") != "DRAFT_READY"
    ):
        raise AuthorityError("CONVERSATION_HISTORY_WORK_SOURCE_MISMATCH")
    actual = c.execute(
        "SELECT p.owner_id,p.current_revision_id,r.digest FROM "
        "business_problem_authority.problems p JOIN "
        "business_problem_authority.problem_revisions r ON r.namespace=p.namespace "
        "AND r.security_domain=p.security_domain "
        "AND r.revision_id=p.current_revision_id "
        "WHERE p.namespace=%s AND p.security_domain=%s AND p.business_problem_id=%s "
        "FOR SHARE OF p,r",
        (*scope, identity),
    ).fetchone()
    if actual != {
        "owner_id": context.principal_id,
        "current_revision_id": revision,
        "digest": commitment,
    }:
        raise AuthorityError("CONVERSATION_HISTORY_WORK_SOURCE_MISMATCH")
    grants = {ExactGrant("BUSINESS_PROBLEM", "READ", problem_resource(identity))}
    if owned_binding is not None:
        from .workbench_prepared_resources import reference

        source_ref = owned_binding.scope.source
        grants.update(
            (
                ExactGrant("PLAN", "READ", "plan:prepared:" + identity),
                ExactGrant(
                    "KNOWLEDGE",
                    "READ_RESOURCE",
                    reference(
                        "knowledge", source_ref.resource_id, source_ref.revision_id
                    ),
                ),
            )
        )
        # The history-access owner still requires a prior exact READ grant and
        # refuses revoked/denied rights. These targets do not issue first READs.
    execution = state.get("execution")
    if not execution:
        return grants
    prepared = c.execute(
        "SELECT prepared_by FROM execution_authority.prepared_candidates "
        "WHERE namespace=%s AND security_domain=%s AND digest=%s",
        (*scope, execution),
    ).fetchone()
    if not prepared or prepared["prepared_by"] != context.principal_id:
        raise AuthorityError("CONVERSATION_HISTORY_WORK_SOURCE_MISMATCH")
    from .execution_domain import ScopeIdentity
    from .native_progress_projection import projection_read_grants
    from .workbench_prepared_execution import candidate

    p = candidate(c, ScopeIdentity(*scope), execution)
    target = p.semantics.target.problem
    if (target.resource_id, target.revision_id, target.digest) != ref:
        raise AuthorityError("CONVERSATION_HISTORY_WORK_SOURCE_MISMATCH")
    source = (invocation.get("inputSource") or {}).get("source") or {}
    if tuple(source.get(k) for k in ("resource_id", "revision_id", "digest")) != (
        p.source_snapshot.resource_id,
        p.source_snapshot.revision_id,
        p.source_snapshot.digest,
    ):
        raise AuthorityError("CONVERSATION_HISTORY_WORK_SOURCE_MISMATCH")
    grants.add(
        ExactGrant("EXECUTION", "READ", "governed-execution:prepared:" + execution)
    )
    for participant in p.participants:
        grants.update(
            g
            for g in projection_read_grants(p, participant)
            if (g.owner, g.action)
            in {
                ("KNOWLEDGE", "READ_RESOURCE"),
                ("RUNTIME_PROFILE", "READ_RESOURCE"),
                ("BUSINESS_ONTOLOGY", "READ"),
            }
        )
    grants.update(result_read_targets(c, p))
    # BUSINESS_ONTOLOGY/USE is an existing separate gate; never renew it here.
    return grants


def result_read_targets(c, p):
    """Saved run only; prospective future attempt targets are never renewed."""
    from .business_problem_authorization import (
        criteria_resource,
        criterion_revision_resource,
    )
    from .execution_preparation_postgres import PreparedExecutionStore
    from .prepared_skill_invocation import planned_outputs

    key = (p.namespace, p.security_domain, p.run_id)
    if not c.execute(
        "SELECT 1 FROM execution_authority.run_preparations WHERE namespace=%s "
        "AND security_domain=%s AND workflow_run_id=%s",
        key,
    ).fetchone():
        return set()
    stored, progress = PreparedExecutionStore(c).read(*key)
    if stored != p:
        raise AuthorityError("CONVERSATION_HISTORY_WORK_SOURCE_MISMATCH")
    target = p.semantics.target
    grants = {
        ExactGrant("EVALUATION", "READ", "evaluation:prepared:" + p.digest),
        ExactGrant(
            "SUCCESS_CRITERIA_SET",
            "READ",
            criteria_resource(target.problem.resource_id),
        ),
        *(
            ExactGrant("SUCCESS_CRITERION", "READ", criterion_revision_resource(r))
            for r in target.criterion_revision_ids
        ),
    }
    for output in planned_outputs(p, progress):
        grants.add(ExactGrant("EVIDENCE", "READ_REFERENCE", output["evidenceGrant"]))
        grants.add(ExactGrant("RESOURCE_USE", "READ", output["resourceGrant"]))
    return grants
