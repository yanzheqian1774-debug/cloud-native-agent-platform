# ruff: noqa: E501, RUF001 -- Explicit fixture SQL and approved boundary text.
"""Explicit synthetic owner fixtures, never imported by runtime or acceptance setup."""

from datetime import UTC, datetime
from types import SimpleNamespace

from agent_console.cost_execution_revision import (
    EXECUTION_ONLY,
    SYNTHETIC_ONLY,
)
from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeRevision,
    MemberKind,
)
from agent_console.execution_domain import ScopeIdentity
from agent_console.plan_suggestion_domain import ExactReference, ProposalRevision
from agent_console.resource_use_domain import canonical_digest
from psycopg.types.json import Jsonb
from test_execution_preparation import preparation
from test_plan_suggestion_v2 import confirm
from test_prepared_execution_binding import upgrade


class ExactTestAuthority:
    def __init__(self, p):
        from agent_console.prepared_execution_resources import resource_read_grants

        self.resources = {
            (g.owner, g.action, g.exact_resource)
            for t in p.participants
            for g in resource_read_grants(p, t)
        }
        self.allowed = {"governed-execution:prepared:" + p.digest} | {
            f"governed-execution:participant:{p.digest}:{t.task_id}"
            for t in p.participants
        }

    def require(self, principal, owner, action, resource):
        if (owner, action, resource) in self.resources:
            return SimpleNamespace(decision_id="test-resource-read-authority")
        if owner == "SKILL" and action == "INVOKE_SKILL" and resource in self.allowed:
            return SimpleNamespace(decision_id="test-only-skill-authority")
        if owner != "EXECUTION" or action != "START" or resource not in self.allowed:
            raise PermissionError("TEST_EXACT_GRANT_DENIED")
        return SimpleNamespace(decision_id="test-only-authority")


def seed(repo, *, target=None, synthetic_skill=False, evidence_ready=True):
    upgrade(repo)
    p = preparation()
    if target is not None:
        p = p.model_copy(
            update={"semantics": p.semantics.model_copy(update={"target": target})}
        )
    scope = ScopeIdentity(p.namespace, p.security_domain)
    key = (p.namespace, p.security_domain)
    ops = [
        {
            "name": t.operation,
            "inputSchema": {"type": "object"},
            "outputSchema": {"type": "object"},
            "sideEffectClass": "READ_ONLY",
            "executorId": "cost-readonly",
            "executorRevision": "1",
            "executorConfigurationDigest": "e" * 64,
            "sideEffectPolicy": {
                "policyId": "readonly",
                "policyRevision": "1",
                "policyDigest": "f" * 64,
            },
            "ioLimits": {
                "policyId": "bounded",
                "policyRevision": "1",
                "maxInputBytes": 4096,
                "maxOutputBytes": 4096,
                "maxObjectDepth": 8,
                "maxProperties": 64,
                "timeoutMs": 1000,
            },
        }
        for t in p.semantics.tasks
    ]
    knowledge_content = {}
    if synthetic_skill:
        from agent_console.knowledge_ingestion import ingest_text
        from agent_console.prepared_resource_bundle import resource_content

        bundle = resource_content()
        ops = bundle["skill"]["operations"]
        chunks, source_digest = ingest_text(
            "fixture-source", bundle["knowledge"]["content"]
        )
        knowledge_content = {
            "documents": [{"contentDigest": source_digest, "chunks": chunks}]
        }
    digest = canonical_digest({"operations": ops})
    skill = ExactReference(resource_id="skill", revision_id="1", digest=digest)
    employee = EmployeeRevision(
        scope,
        "employee",
        "1",
        "Synthetic cost analyst",
        ("Read synthetic inputs",),
        (
            CompositionMember(MemberKind.AGENT, "agent-definition", "1", "a" * 64),
            CompositionMember(MemberKind.SKILL, "skill", "1", digest),
        ),
    )
    participants = tuple(
        t.model_copy(
            update={
                "definition": ExactReference(
                    resource_id="employee", revision_id="1", digest=employee.digest
                ),
                "executor_id": ops[0]["executorId"],
                "executor_revision": ops[0]["executorRevision"],
                "executor_digest": ops[0]["executorConfigurationDigest"],
                "skill": t.skill.model_copy(
                    update={
                        "reference": skill,
                        "input_schema_digest": canonical_digest(
                            next(
                                o["inputSchema"]
                                for o in ops
                                if o["name"] == t.skill.operation
                            )
                        ),
                        "output_schema_digest": canonical_digest(
                            next(
                                o["outputSchema"]
                                for o in ops
                                if o["name"] == t.skill.operation
                            )
                        ),
                    }
                ),
            }
        )
        for t in p.participants
    )
    p = p.model_copy(update={"participants": participants})
    with repo.pool.connection() as c:
        if evidence_ready:
            c.execute(
                "UPDATE execution_authority.evidence_cutover SET state='POSTGRES_ACTIVE',authoritative_writer='POSTGRES'"
            )  # explicit fixture only
        for kind, table, col, rid, rdigest, content in (
            (
                "agent",
                "agent_definition.definitions",
                "definition_id",
                "agent-definition",
                "a" * 64,
                {},
            ),
            (
                "skill",
                "skill_mcp_resource.resources",
                "resource_id",
                "skill",
                digest,
                {"operations": ops},
            ),
            (
                "knowledge",
                "knowledge_operation.knowledge",
                "knowledge_id",
                "controlled",
                "a" * 64,
                knowledge_content,
            ),
            (
                "runtime",
                "runtime_profile.profiles",
                "runtime_profile_id",
                "controlled",
                "a" * 64,
                {"provider": "NATIVE_KUBERNETES"},
            ),
        ):
            record = {
                "enabled": True,
                "publishedRevisionId": "1",
                "revisions": [
                    {
                        "revisionId": "1",
                        "state": "PUBLISHED",
                        "digest": rdigest,
                        "content": content,
                    }
                ],
            }
            cols = f"namespace,security_domain,{col},aggregate_version,record"
            if kind == "skill":
                c.execute(
                    f"INSERT INTO {table} ({cols},kind) VALUES (%s,%s,%s,1,%s,'skill')",
                    (*key, rid, Jsonb(record)),
                )
            else:
                c.execute(
                    f"INSERT INTO {table} ({cols}) VALUES (%s,%s,%s,1,%s)",
                    (*key, rid, Jsonb(record)),
                )
        c.execute(
            "INSERT INTO digital_employee_definition.definitions VALUES (%s,%s,'employee',1)",
            key,
        )
        c.execute(
            "INSERT INTO digital_employee_definition.revisions VALUES (%s,%s,'employee','1',NULL,%s,%s)",
            (*key, employee.digest, Jsonb(employee.record)),
        )
        for ordinal, action in enumerate(
            ("CREATE", "VALIDATE", "APPROVE", "PUBLISH"), 1
        ):
            c.execute(
                "INSERT INTO digital_employee_definition.facts "
                "(namespace,security_domain,definition_id,ordinal,revision_id,action,revision_digest,decision_id,command_id,payload_digest) "
                "VALUES (%s,%s,'employee',%s,'1',%s,%s,'test-decision',%s,%s)",
                (
                    *key,
                    ordinal,
                    action,
                    employee.digest,
                    "test-" + action,
                    employee.digest,
                ),
            )
        for identity in (p.root_instance_id, "analyst"):
            record = {
                "definition_authority": "DIGITAL_EMPLOYEE_DEFINITION_V1",
                "definition_id": "employee",
                "definition_revision_id": "1",
                "definition_digest": employee.digest,
                "lifecycle": "ENABLED",
            }
            c.execute(
                "INSERT INTO execution_authority.digital_employee_instances "
                "(namespace,security_domain,digital_employee_instance_id,definition_revision_id,aggregate_version,record) "
                "VALUES (%s,%s,%s,'1',1,%s)",
                (*key, identity, Jsonb(record)),
            )
            c.execute(
                "INSERT INTO digital_employee_definition.instance_bindings VALUES (%s,%s,%s,'employee','1',%s)",
                (*key, identity, employee.digest),
            )
        for assignment, instance in [
            (p.root_assignment_id, p.root_instance_id),
            *[(t.assignment_id, t.instance_id) for t in p.participants],
        ]:
            c.execute(
                "INSERT INTO execution_authority.assignments VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    *key,
                    assignment,
                    instance,
                    "a" * 64,
                    Jsonb(
                        {
                            "lifecycle": "ACTIVE",
                            "effective_from": datetime.now(UTC).isoformat(),
                            "effective_until": None,
                        }
                    ),
                ),
            )
    semantics = p.semantics.model_copy(
        update={
            "business_rules": (EXECUTION_ONLY,),
            "requirements": tuple(
                r.model_copy(
                    update={
                        "selected": participants[0].definition
                        if r.kind == "EMPLOYEE"
                        else p.source_snapshot
                    }
                )
                for r in p.semantics.requirements
            ),
            "boundaries": (
                SYNTHETIC_ONLY,
                f"执行准备映射SHA256：{p.mapping_digest}；fixture",
            ),
        }
    )
    proposal = ProposalRevision(
        proposal_id="prepared-plan",
        revision=1,
        predecessor_digest=None,
        invocation_id="fixture",
        semantics=semantics,
    )
    with repo.transaction(scope, proposal.proposal_id, authorized=True) as c:
        repo.add_proposal(c, scope, proposal)
    confirmed = confirm(repo, scope, proposal, "fixture")
    return p.model_copy(
        update={
            "plan_id": confirmed["plan"]["plan_id"],
            "plan_version": 1,
            "plan_digest": confirmed["digest"],
            "approval_id": confirmed["approval"]["approval_decision_id"],
            "semantics": semantics,
        }
    )
