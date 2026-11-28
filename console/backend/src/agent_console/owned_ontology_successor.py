"""Same-business ontology successor adoption; never ontology publication.

The resource selection owner may consume one real selected-upgrade receipt and a
real independently reviewed/published ontology revision. It cannot create either.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import UTC, datetime

from .authority_contracts import AuthorityError, ExactGrant
from .digital_employee_definition import EmployeeRevision
from .digital_employee_definition_postgres import PostgresEmployeeDefinitionRepository
from .execution_domain import ScopeIdentity
from .ontology_execution import published_content
from .ontology_postgres import PostgresOntologyRepository
from .ontology_service import resource
from .owned_resource_assembly import MODE
from .plan_suggestion_domain import ExactReference
from .planning_candidates import read_published
from .resource_upgrade_batch_postgres import UpgradeBatchRepository
from .resource_use_domain import canonical_digest
from .skill_mcp_service import SkillMcpService
from .workbench_prepared_resources import reference

SCHEMA = "same-scope-ontology-skill-successor.v1"
MARKER = "ONTOLOGY_FIXED_REFERENCE:"


def require(condition, reason):
    if not condition:
        raise AuthorityError("OWNED_ONTOLOGY_SUCCESSOR_" + reason)


LINEAGE_READ = ContextVar("owned_ontology_lineage_read", default=())


@contextmanager
def lineage_guard(plan):
    identity = (plan.resource_id, plan.revision_id, plan.digest)
    current = LINEAGE_READ.get()
    require(identity not in current and len(current) < 32, "LINEAGE_LIMIT")
    token = LINEAGE_READ.set((*current, identity))
    try:
        yield
    finally:
        LINEAGE_READ.reset(token)


def marker(ontology):
    import json

    return MARKER + json.dumps(
        ontology.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )


def equal_business_content(before, after, old_skill, new_skill):
    """The one permitted semantic edit is an exact action Skill reference."""
    require(
        old_skill.resource_id == new_skill.resource_id and old_skill != new_skill,
        "SKILL_IDENTITY_CHANGED",
    )
    normalized = deepcopy(after)
    changes = 0
    for action in normalized["actions"]:
        if action["skill"] == new_skill.model_dump(mode="json"):
            action["skill"] = old_skill.model_dump(mode="json")
            changes += 1
    require(
        changes > 0 and canonical_digest(normalized) == canonical_digest(before),
        "BUSINESS_SEMANTICS_CHANGED",
    )


def equal_skill_contract(before, after):
    # Description is display metadata. Instructions, capabilities and the entire
    # registered operation/IO/executor/effect/limits contract remain exact.
    before, after = dict(before), dict(after)
    before.pop("description", None)
    after.pop("description", None)
    require(
        canonical_digest(before) == canonical_digest(after),
        "EXECUTION_CONTRACT_CHANGED",
    )


def skill_lineage(c, scope, before, after):
    row = c.execute(
        "SELECT record FROM skill_mcp_resource.resources WHERE namespace=%s "
        "AND security_domain=%s AND kind='skill' AND resource_id=%s FOR SHARE",
        (scope.namespace, scope.security_domain, after.resource_id),
    ).fetchone()
    require(
        row is not None and before.resource_id == after.resource_id,
        "SKILL_IDENTITY_CHANGED",
    )
    record = row["record"]
    revisions = {r["revisionId"]: r for r in record["revisions"]}
    current, seen = after.revision_id, set()
    while current != before.revision_id:
        require(current not in seen and len(seen) < 32, "SKILL_LINEAGE_INVALID")
        seen.add(current)
        revision = revisions.get(current)
        require(
            revision is not None
            and SkillMcpService._digest(record, revision) == revision["digest"],
            "SKILL_LINEAGE_CORRUPT",
        )
        current = revision.get("predecessorRevisionId")
        require(current is not None, "SKILL_SUCCESSOR_REQUIRED")
    require(
        revisions[current]["digest"] == before.digest
        and revisions[after.revision_id]["digest"] == after.digest,
        "SKILL_LINEAGE_CORRUPT",
    )


def upgrade_receipt(reader, c, context, employee, old_skill, new_skill, *, history):
    """Read the real immutable reviewed batch, not a fabricated publication hint."""
    table = c.execute(
        "SELECT to_regclass('resource_upgrade.receipts') AS name"
    ).fetchone()
    require(table["name"] is not None, "REVIEWED_UPGRADE_REQUIRED")
    rows = c.execute(
        "SELECT actor_id,command_id,request_digest,preview_digest,record_digest,record "
        "FROM resource_upgrade.receipts WHERE namespace=%s AND security_domain=%s "
        "AND record->'result'->'resource'->>'identity'=%s "
        "AND record->'result'->'resource'->>'revisionId'=%s "
        "AND record->'result'->'resource'->>'digest'=%s",
        (
            context.scope.tenant_id,
            context.scope.security_domain,
            new_skill.resource_id,
            new_skill.revision_id,
            new_skill.digest,
        ),
    ).fetchall()
    matched = []
    for row in rows:
        key = (
            context.scope.tenant_id,
            context.scope.security_domain,
            row["actor_id"],
            row["command_id"],
        )
        record = UpgradeBatchRepository._record(row, key)
        require(
            record.get("schemaVersion") == "selected-resource-upgrade-receipt.v1"
            and record.get("actorId") == row["actor_id"]
            and record.get("decisionIds"),
            "UPGRADE_FACT_CORRUPT",
        )
        for chain in record["result"].get("employees", []):
            if not chain:
                continue
            final = chain[-1]
            if (
                final.get("employeeDefinitionId"),
                final.get("employeeDefinitionRevisionId"),
                final.get("employeeDefinitionDigest"),
                final.get("lifecycleState"),
            ) != (
                employee.resource_id,
                employee.revision_id,
                employee.digest,
                "PUBLISHED",
            ):
                continue
            scope = ScopeIdentity(
                context.scope.tenant_id, context.scope.security_domain
            )
            current, _ = read_published(c, scope, "EMPLOYEE", employee)
            current = EmployeeRevision.from_record(current)
            require(
                current.predecessor_revision_id is not None,
                "EMPLOYEE_SUCCESSOR_REQUIRED",
            )
            old = PostgresEmployeeDefinitionRepository._read(
                c, scope, employee.resource_id, current.predecessor_revision_id
            )
            old_ref = ExactReference(
                resource_id=employee.resource_id,
                revision_id=current.predecessor_revision_id,
                digest=old["digest"],
            )
            reader._reads(
                c,
                context,
                (
                    ExactGrant(
                        "EMPLOYEE",
                        "READ",
                        f"employee:{old_ref.resource_id}:{old_ref.revision_id}",
                    ),
                ),
                datetime.now(UTC),
                history=history,
            )
            old_value, _ = read_published(c, scope, "EMPLOYEE", old_ref)
            old_revision = EmployeeRevision.from_record(old_value)
            replacements = [
                (m, n)
                for m, n in zip(old_revision.members, current.members, strict=True)
                if m != n
            ]
            require(len(replacements) == 1, "EMPLOYEE_BATCH_SCOPE_CHANGED")
            before, after = replacements[0]
            require(
                str(before.kind) == "SKILL"
                and str(after.kind) == "SKILL"
                and (before.resource_id, before.revision_id, before.digest)
                == (old_skill.resource_id, old_skill.revision_id, old_skill.digest)
                and (after.resource_id, after.revision_id, after.digest)
                == (new_skill.resource_id, new_skill.revision_id, new_skill.digest),
                "EMPLOYEE_BATCH_SCOPE_CHANGED",
            )
            matched.append(
                {
                    "actor": row["actor_id"],
                    "command": row["command_id"],
                    "digest": row["record_digest"],
                }
            )
    require(len(matched) == 1, "EXACT_REVIEWED_UPGRADE_REQUIRED")
    return matched[0]


def adopted_evidence(reader, c, context, work, previous_plan, skills):
    """Only a real already-adopted exact Plan can carry an A2 basis forward."""
    if work is None or work.assemblyAdoption is None or previous_plan is None:
        return None
    require(
        (work.namespace, work.securityDomain, work.subject)
        == (
            context.scope.tenant_id,
            context.scope.security_domain,
            context.principal_id,
        ),
        "PREDECESSOR_SUBJECT_CHANGED",
    )
    metadata = work.assemblyAdoption
    if work.businessScope.documentRules is None or tuple(skills) != tuple(
        work.businessScope.skills
    ):
        return None
    from .owned_resource_assembly import admission_basis, plan_reference

    require(
        metadata["plan"] == plan_reference(previous_plan).model_dump(mode="json"),
        "PREDECESSOR_PLAN_CHANGED",
    )
    row = c.execute(
        "SELECT record FROM execution_authority.resource_policy_plan_commands "
        "WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND "
        "request_key=%s",
        (
            context.scope.tenant_id,
            context.scope.security_domain,
            context.principal_id,
            metadata["requestKey"],
        ),
    ).fetchone()
    require(row is not None, "ADOPTED_LINEAGE_REQUIRED")
    proof = row["record"].get("assemblyAdoption") or {}
    body = proof.get("body") or {}
    require(
        proof.get("digest") == metadata["digest"] == canonical_digest(body)
        and body.get("plan") == metadata.get("sourcePlan", metadata["plan"])
        and body.get("admission") == admission_basis(work)
        and body.get("scope") == work.businessScope.model_dump(mode="json")
        and body.get("subject") == context.principal_id
        and body.get("authorityGeneration") == reader.generation
        and body.get("recoveryEpoch") == reader.recovery_epoch,
        "ADOPTED_LINEAGE_CHANGED",
    )
    prior = body.get("ontologySuccessor")
    if prior is not None:
        require(
            prior["ontology"]
            == work.businessScope.documentRules.ontology.model_dump(mode="json")
            and ExactReference.model_validate(prior["newSkill"])
            in work.businessScope.skills,
            "ADOPTED_LINEAGE_CHANGED",
        )
    elif not body.get("ontologyPredecessor"):
        return None
    return {
        "plan": plan_reference(previous_plan).model_dump(mode="json"),
        "digest": canonical_digest(metadata),
    }


def resolve(
    reader,
    c,
    context,
    original,
    employee,
    skills,
    *,
    requested=None,
    history=False,
    selecting=True,
):
    if original.documentRules is None:
        require(requested is None, "UNEXPECTED_ONTOLOGY_SELECTION")
        return None, None
    changed = [r for r in skills if r not in original.skills]
    if not changed:
        require(requested is None, "UNEXPECTED_ONTOLOGY_SELECTION")
        return original.documentRules, None
    require(
        getattr(original, "trustedAssemblyAdoption", None) == MODE
        and original.documentRules is not None,
        "DISABLED",
    )
    require(
        len(changed) == 1 and len(skills) == len(original.skills),
        "ONE_SKILL_UPGRADE_REQUIRED",
    )
    new_skill = changed[0]
    old = [r for r in original.skills if r.resource_id == new_skill.resource_id]
    require(len(old) == 1, "SKILL_IDENTITY_CHANGED")
    old_skill = old[0]
    scope = ScopeIdentity(context.scope.tenant_id, context.scope.security_domain)
    reader._reads(
        c,
        context,
        tuple(
            ExactGrant(
                "SKILL",
                "READ_RESOURCE",
                reference("skill", r.resource_id, r.revision_id),
            )
            for r in (old_skill, new_skill)
        ),
        datetime.now(UTC),
        history=history,
    )
    old_content, _ = read_published(
        c, scope, "SKILL", old_skill, _published_binding=True
    )
    new_content, _ = read_published(
        c, scope, "SKILL", new_skill, _published_binding=not selecting
    )
    equal_skill_contract(old_content, new_content)
    skill_lineage(c, scope, old_skill, new_skill)
    batch = upgrade_receipt(
        reader, c, context, employee, old_skill, new_skill, history=history
    )
    previous = original.documentRules
    old_ontology = published_content(c, scope, previous).model_dump(mode="json")
    repo = PostgresOntologyRepository(c)
    if requested is not None:
        candidates = [ExactReference.model_validate(requested)]
    else:
        candidates = [
            ExactReference(
                resource_id=previous.ontology.resource_id,
                revision_id=r["revision_id"],
                digest=r["digest"],
            )
            for r in c.execute(
                "SELECT revision_id,digest FROM business_ontology.revisions "
                "WHERE namespace=%s AND security_domain=%s AND ontology_id=%s "
                "AND predecessor=%s",
                (
                    scope.namespace,
                    scope.security_domain,
                    previous.ontology.resource_id,
                    previous.ontology.revision_id,
                ),
            ).fetchall()
        ]
    valid = []
    for candidate in candidates:
        try:
            require(
                candidate.resource_id == previous.ontology.resource_id
                and candidate != previous.ontology,
                "ONTOLOGY_IDENTITY_CHANGED",
            )
            reader._reads(
                c,
                context,
                tuple(
                    ExactGrant(
                        "BUSINESS_ONTOLOGY",
                        a,
                        resource(candidate.resource_id, candidate.revision_id),
                    )
                    for a in ("READ", "USE")
                ),
                datetime.now(UTC),
                history=history,
            )
            record = repo.read(
                (scope.namespace, scope.security_domain),
                candidate.resource_id,
                candidate.revision_id,
            )
            require(
                record["predecessor"] == previous.ontology.revision_id,
                "ONTOLOGY_SUCCESSOR_REQUIRED",
            )
            binding = previous.model_copy(update={"ontology": candidate})
            content = published_content(c, scope, binding).model_dump(mode="json")
            equal_business_content(old_ontology, content, old_skill, new_skill)
            facts = record["facts"]
            require(
                any(
                    f["action"] == "REVIEW" and f["actor"] != record["author"]
                    for f in facts
                ),
                "INDEPENDENT_REVIEW_REQUIRED",
            )
            valid.append(
                (
                    binding,
                    {
                        "schemaVersion": SCHEMA,
                        "previousOntology": previous.ontology.model_dump(mode="json"),
                        "ontology": candidate.model_dump(mode="json"),
                        "oldSkill": old_skill.model_dump(mode="json"),
                        "newSkill": new_skill.model_dump(mode="json"),
                        "upgradeReceipt": batch,
                        "employee": employee.model_dump(mode="json"),
                    },
                )
            )
        except (AuthorityError, ValueError):
            if requested is not None:
                raise
            continue  # No hidden tuple, name or count enters a public preview.
    require(len(valid) == 1, "EXACT_PUBLISHED_ONTOLOGY_REQUIRED")
    return valid[0]
