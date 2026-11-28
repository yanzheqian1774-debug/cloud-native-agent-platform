"""Explicit same-goal re-admission, stored as an immutable owner command fact.

A fact is not a lease, a rewritten 0066 admission, or a Problem-wide override.
Only its exact approved resource-selection successor Plan may consume it.
"""

from datetime import UTC, datetime

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError
from .owned_business_postgres import require_not_revoked, saved
from .owned_resource_assembly import MODE, plan_reference
from .resource_use_domain import canonical_digest

SCHEMA = "owned-business-admission-successor.v1"
PREFIX = "owned-business-successor:"


def require(condition, reason):
    if not condition:
        raise AuthorityError("OWNED_BUSINESS_SUCCESSOR_" + reason)


def read_exact(c, identity, tenant, domain, subject, *, expected_digest=None, seen=()):
    from .task_identity_continuity import lock_owner_generation

    lock_owner_generation(c)
    try:
        return _read_exact(
            c,
            identity,
            tenant,
            domain,
            subject,
            expected_digest=expected_digest,
            seen=seen,
        )
    except AuthorityError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthorityError("OWNED_BUSINESS_SUCCESSOR_FACT_CORRUPT") from exc


def _read_exact(c, identity, tenant, domain, subject, *, expected_digest=None, seen=()):
    """Parse one typed identity under the original subject, never a latest row."""
    require(
        isinstance(identity, str) and identity not in seen and len(seen) < 8,
        "CHAIN_INVALID",
    )
    if not identity.startswith(PREFIX):
        row = c.execute(
            "SELECT admission_id,record,record_digest FROM "
            "authorization_admin.owned_business_admissions WHERE admission_id=%s "
            "AND tenant_id=%s AND security_domain=%s AND subject_id=%s",
            (identity, tenant, domain, subject),
        ).fetchone()
        require(row is not None, "ANCESTOR_REQUIRED")
        require_not_revoked(c, identity)
    else:
        row = c.execute(
            "SELECT payload_digest,record FROM "
            "execution_authority.resource_policy_plan_commands WHERE namespace=%s "
            "AND security_domain=%s AND subject_id=%s AND request_key=%s",
            (tenant, domain, subject, identity),
        ).fetchone()
        require(row is not None, "FACT_REQUIRED")
        fact = row["record"]
        require(
            fact.get("schemaVersion") == SCHEMA
            and fact.get("revocationMode") == "ORIGINAL_CONTEXT_LINEAGE"
            and fact.get("identity") == identity
            and row["payload_digest"] == canonical_digest(fact)
            and identity == PREFIX + canonical_digest(fact["identityBasis"]),
            "FACT_CORRUPT",
        )
        record = fact["admission"]
        require(
            (record["tenantId"], record["securityDomain"], record["subject"])
            == (tenant, domain, subject)
            and record["schemaVersion"] == "owned-business-admission.v1"
            and fact["recordDigest"] == canonical_digest(record),
            "IDENTITY_CHANGED",
        )
        ancestor = read_exact(
            c,
            fact["previous"]["admissionId"],
            tenant,
            domain,
            subject,
            expected_digest=fact["previous"]["recordDigest"],
            seen=(*seen, identity),
        )
        old = ancestor["record"]
        immutable = set(old) - {"policyDigest", "scope", "expiresAt"}
        require(
            set(record) == set(old)
            and all(record[key] == old[key] for key in immutable),
            "ORIGIN_CHANGED",
        )
        # There is no pretend revocation row for this new id. The supported
        # owner revokes the whole original context lineage, checked below.
        row = {
            "admission_id": identity,
            "record": record,
            "record_digest": fact["recordDigest"],
            "successor": fact,
        }
    require(canonical_digest(row["record"]) == row["record_digest"], "RECORD_CORRUPT")
    require(
        expected_digest is None or row["record_digest"] == expected_digest,
        "DIGEST_CHANGED",
    )
    record = row["record"]
    from .context_call_admission import lock

    for binding in sorted(
        record.get("understandingBindings", ()), key=lambda item: item["contextId"]
    ):
        lock(c, binding["contextId"])
        if c.execute(
            "SELECT 1 FROM authorization_admin.context_call_decisions d JOIN "
            "authorization_admin.context_call_revocations r USING(admission_id) "
            "WHERE d.context_id=%s",
            (binding["contextId"],),
        ).fetchone():
            require(False, "CONTEXT_REVOKED")
    return row


def for_plan(c, context, plan, *, _seen=()):
    """Find only a receipt naming this exact Plan, or its real prepared source."""
    if plan is None:
        return None
    tables = c.execute(
        "SELECT to_regclass('execution_authority.resource_policy_plan_commands') "
        "AS selections, "
        "to_regclass('execution_authority.prepared_resource_commands') AS prepared"
    ).fetchone()
    if not tables["selections"]:
        return None
    requested = plan_reference(plan).model_dump(mode="json")
    requested_digest = canonical_digest(requested)
    require(requested_digest not in _seen and len(_seen) < 16, "PLAN_LINEAGE_INVALID")
    args = (
        context.scope.tenant_id,
        context.scope.security_domain,
        context.principal_id,
    )
    rows = c.execute(
        "SELECT request_key,record FROM "
        "execution_authority.resource_policy_plan_commands "
        "WHERE namespace=%s AND security_domain=%s AND subject_id=%s "
        "AND record->'assemblyAdoption'->'body'->'plan'=%s",
        (*args, Jsonb(requested)),
    ).fetchall()
    if not rows:
        if not tables["prepared"]:
            return None
        # This is only identity discovery. execution_projection subsequently
        # verifies the real approved preparation and full execution semantics.
        prepared = c.execute(
            "SELECT result FROM execution_authority.prepared_resource_commands "
            "WHERE namespace=%s AND security_domain=%s AND actor_id=%s "
            "AND result->'executionPlan'->'plan'->>'plan_id'=%s "
            "AND result->'executionPlan'->'plan'->>'version'=%s",
            (*args, requested["resource_id"], requested["revision_id"]),
        ).fetchall()
        require(len(prepared) <= 1, "AMBIGUOUS_PLAN")
        if not prepared:
            return None
        result = prepared[0]["result"]
        source = {
            "resource_id": result["sourcePlanId"],
            "revision_id": str(result["sourcePlanVersion"]),
            "digest": result["sourcePlanDigest"],
        }
        rows = c.execute(
            "SELECT request_key,record FROM "
            "execution_authority.resource_policy_plan_commands "
            "WHERE namespace=%s AND security_domain=%s AND subject_id=%s "
            "AND record->'assemblyAdoption'->'body'->'plan'=%s",
            (*args, Jsonb(source)),
        ).fetchall()
    require(len(rows) <= 1, "AMBIGUOUS_PLAN")
    if not rows:
        return None
    proof = rows[0]["record"]["assemblyAdoption"]
    require(proof.get("digest") == canonical_digest(proof["body"]), "PROOF_CORRUPT")
    basis = proof["body"]["admission"]
    if not basis["admissionId"].startswith(PREFIX):
        return None
    fact_row = read_exact(
        c, basis["admissionId"], *args, expected_digest=basis["recordDigest"]
    )
    identity = fact_row["successor"]["identityBasis"]
    if identity["predecessorPlan"] == proof["body"]["previousPlan"]:
        require(identity["selectionKey"] == rows[0]["request_key"], "SELECTION_CHANGED")
    else:
        from .plan_suggestion_domain import ExactReference

        previous = for_plan(
            c,
            context,
            ExactReference.model_validate(proof["body"]["previousPlan"]),
            _seen=(*_seen, requested_digest),
        )
        require(
            previous is not None
            and previous["admission_id"] == fact_row["admission_id"]
            and previous["record_digest"] == fact_row["record_digest"],
            "SELECTION_CHANGED",
        )
    return fact_row


def fresh(owner, c, context, plan, *, key=None):
    """Normal owner admission from confirmed Goal, without another invocation.

    key=None is a read-only eligibility preview. It cannot become execution work.
    The write case belongs to the original selection transaction and rolls back
    together with any failed permission, resource or confirmation gate.
    """
    from .task_identity_continuity import lock_owner_generation

    lock_owner_generation(c)
    p = owner.policy
    source, account, _, expires, value, selected, ancestry = owner._source(
        c, context, _invocation(c, context, plan.semantics.target.problem.resource_id)
    )
    require(getattr(selected, "trustedAssemblyAdoption", None) == MODE, "DISABLED")
    previous = saved(c, context, value.invocation_id)
    require(previous is not None, "ANCESTOR_REQUIRED")
    old = read_exact(
        c, previous["admission_id"], p.tenantId, p.securityDomain, p.subjectId
    )
    # Only explicitly pinned old policy is trusted for the perimeter transition.
    retained = owner.work_reader.retained_history.get(old["record"]["policyDigest"])
    require(retained is not None, "PRIOR_POLICY_NOT_PINNED")
    before = retained.work(c, context, plan.semantics.target.problem, history=True)
    require(before.ontology_correction is None, "ONTOLOGY_SUCCESSOR_REQUIRED")
    original_scope = dict(old["record"]["scope"])
    current_scope = selected.model_dump(mode="json")
    require(
        original_scope.get("trustedAssemblyAdoption") is None,
        "PRIOR_MODE_ALREADY_ENABLED",
    )
    original_scope.pop("trustedAssemblyAdoption", None)
    current_scope.pop("trustedAssemblyAdoption", None)
    require(original_scope == current_scope, "SCOPE_CHANGED")
    require(plan.semantics.target.problem == before.problem, "PROBLEM_CHANGED")
    record = owner._record(
        c, context, source, account, expires, value, selected, ancestry
    )
    # The original formal Problem link is an allowed append after understanding.
    record["aggregateVersion"] = old["record"]["aggregateVersion"]
    immutable = set(old["record"]) - {"policyDigest", "scope", "expiresAt"}
    require(
        set(record) == set(old["record"])
        and all(record[k] == old["record"][k] for k in immutable),
        "ORIGIN_CHANGED",
    )
    require(datetime.now(UTC) < min(p.expiresAt, expires), "EXPIRED")
    ensure_business_idle(c, context, before.problem.resource_id)
    identity_basis = {
        "tenant": p.tenantId,
        "domain": p.securityDomain,
        "subject": p.subjectId,
        "previousAdmissionId": old["admission_id"],
        "previousRecordDigest": old["record_digest"],
        "policyDigest": p.digest,
        "problem": before.problem.model_dump(mode="json"),
        "predecessorPlan": plan_reference(plan).model_dump(mode="json"),
        "selectionKey": key,
    }
    fact = {
        "schemaVersion": SCHEMA,
        "identityBasis": identity_basis,
        "identity": PREFIX + canonical_digest(identity_basis),
        "previous": {
            "admissionId": old["admission_id"],
            "recordDigest": old["record_digest"],
        },
        "admission": record,
        "recordDigest": canonical_digest(record),
        "revocationMode": "ORIGINAL_CONTEXT_LINEAGE",
    }
    if key is not None:
        c.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,3240066))",
            (fact["identity"],),
        )
        prior = c.execute(
            "SELECT payload_digest,record FROM "
            "execution_authority.resource_policy_plan_commands "
            "WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND "
            "request_key=%s",
            (p.tenantId, p.securityDomain, p.subjectId, fact["identity"]),
        ).fetchone()
        require(
            prior is None
            or prior == {"payload_digest": canonical_digest(fact), "record": fact},
            "KEY_CONFLICT",
        )
        if prior is None:
            c.execute(
                "INSERT INTO execution_authority.resource_policy_plan_commands "
                "(namespace,security_domain,subject_id,request_key,payload_digest"
                ",record) VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    p.tenantId,
                    p.securityDomain,
                    p.subjectId,
                    fact["identity"],
                    canonical_digest(fact),
                    Jsonb(fact),
                ),
            )
    return {
        "admission_id": fact["identity"],
        "record_digest": fact["recordDigest"],
        "record": record,
        "successor": fact,
    }


def _invocation(c, context, problem):
    row = c.execute(
        "SELECT invocation_id FROM authorization_admin.context_call_objects "
        "WHERE tenant_id=%s AND security_domain=%s AND owner='BUSINESS_PROBLEM' "
        "AND resource_id=%s",
        (context.scope.tenant_id, context.scope.security_domain, problem),
    ).fetchone()
    require(row is not None, "PROBLEM_REQUIRED")
    return row["invocation_id"]


def ensure_business_idle(c, context, problem):
    """One formal Problem lineage, across any Plan or admission identity."""
    c.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,3240066))",
        (
            "business-lineage:"
            + canonical_digest(
                [
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    context.principal_id,
                    problem,
                ]
            ),
        ),
    )
    tables = c.execute(
        "SELECT to_regclass('execution_authority.prepared_resource_commands') AS "
        "prepared, "
        "to_regclass('execution_authority.native_dispatch_commands') AS commands, "
        "to_regclass('execution_authority.prepared_run_progress') AS progress"
    ).fetchone()
    if not tables["prepared"] or not tables["commands"]:
        return
    rows = c.execute(
        "SELECT result FROM execution_authority.prepared_resource_commands "
        "WHERE namespace=%s AND security_domain=%s AND actor_id=%s "
        "AND result->'executionPlan'->'plan'->'semantics'->'target'->'problem'->>"
        "'resource_id'=%s",
        (
            context.scope.tenant_id,
            context.scope.security_domain,
            context.principal_id,
            problem,
        ),
    ).fetchall()
    for row in rows:
        result = row["result"]
        pending = c.execute(
            "SELECT 1 FROM execution_authority.native_dispatch_commands "
            "WHERE namespace=%s AND security_domain=%s AND principal_id=%s "
            "AND authorization_resource=%s AND state NOT IN "
            "('SUCCEEDED','FAILED','CANCELLED','REJECTED') LIMIT 1",
            (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
                "governed-execution:prepared:" + result["preparationDigest"],
            ),
        ).fetchone()
        progress = (
            tables["progress"]
            and c.execute(
                "SELECT 1 FROM execution_authority.prepared_run_progress WHERE "
                "namespace=%s "
                "AND security_domain=%s AND workflow_run_id=%s "
                "AND record->>'state' IN ('PENDING','RUNNING') LIMIT 1",
                (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    result["runId"],
                ),
            ).fetchone()
        )
        require(not pending and not progress, "PRIOR_EXECUTION_UNRESOLVED")
