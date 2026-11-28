"""Isolated ordinary owner lifecycle; policy prerequisites are explicit fixtures.

No synthetic publication/test rows are inserted. Grant prerequisites use the
original policy issuer and GrantAdministrationService, never an admin selection
identity or a forged HUMAN_REVIEWED result.
"""

import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace as NS

from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import ExactGrant
from agent_console.business_capability import FixedReference
from agent_console.digital_employee_definition import EmployeeRevision
from agent_console.execution_domain import ScopeIdentity
from agent_console.grant_administration_application import (
    GrantDecisionCommand,
    GrantRequestCommand,
)
from agent_console.ontology_domain import OntologyError
from agent_console.ontology_management import OntologyManagement
from agent_console.ontology_management_policy import MaintenancePolicy, MaintenanceScope
from agent_console.ontology_postgres import PostgresOntologyRepository
from agent_console.ontology_service import resource
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.resource_management import (
    ManagementPolicy,
    ManagementScope,
    ManagementTargets,
    ResourceManagement,
)
from agent_console.resource_upgrade_batch_postgres import UpgradeBatchRepository
from agent_console.resource_upgrade_coordinator import SelectedUpgradeCoordinator
from agent_console.resource_upgrade_owners import SelectedUpgradeOwners
from agent_console.resource_upgrade_preview import (
    ConsumerSelection,
    SelectedUpgradePreview,
    UpgradeSelection,
)
from agent_console.resource_use_domain import canonical_digest
from agent_console.test_resource_read_access import prepare
from agent_console.test_resource_read_policy import TestReadPolicy
from agent_console.workbench_employee import EmployeeDefinitionCommandOwnerAdapter
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from agent_console.workbench_prepared_resources import reference
from test_local_accounts_postgres import login


def publish(e, c, automation, adapter, directory):
    g = automation.grants
    original = e.consumer_refs["skill"]
    old_employee = e.consumer_employee
    scope = ScopeIdentity(e.context.scope.tenant_id, e.context.scope.security_domain)
    policy_scope = e.business_owner.policy.scopes[0]
    ontology = policy_scope.documentRules.ontology
    calls_before = len(e.calls)
    generation = g.generation
    purposes = [
        RequestabilityRule("SKILL", action, "skill-invocation:", "RESOURCE_MANAGEMENT")
        for action in (
            "CREATE_RESOURCE",
            "MANAGE_RESOURCE",
            "READ_RESOURCE",
            "REVIEW_PUBLISH_RESOURCE",
            "CONNECT_MCP",
        )
    ]
    purposes += [
        RequestabilityRule(
            "BUSINESS_ONTOLOGY",
            action,
            "business-ontology:" + ontology.resource_id + ":",
            "ONTOLOGY_MAINTENANCE",
        )
        for action in ("REVISE", "VALIDATE", "TEST", "REVIEW", "PUBLISH", "READ")
    ]
    generation = replace(
        generation, requestability=(*generation.requestability, *purposes)
    )
    g._generation_provider = lambda: generation
    g.authorization._generation_provider = lambda: generation
    g.target_validator.additional += (ManagementTargets(),)
    issuer = automation.authenticate(e.context)
    from owned_business_consumer_support import prepare_current_resource_reads

    prepare_current_resource_reads(e, automation)
    index = 0

    def call(connection, payload=None, *, subject=None, kind="skill"):
        subject = subject or e.context
        return AuthorizedOwnerCall(
            "RESOURCE_MANAGEMENT",
            subject,
            connection,
            payload or {},
            {"kind": kind},
            {},
            (),
            AuthorizedOwnerAuthority(
                adapter, subject, connection, generation.generation, ()
            ),
            generation.generation,
            1,
        )

    def policy_grants(subject, members, label):
        # Explicit isolated, exact prerequisites. This does not claim that a
        # current deployment already has these permissions or auto-grants USE.
        nonlocal index
        index += 1
        request = g.submit_request(
            subject,
            GrantRequestCommand(
                "RESOURCE_PREPARATION",
                tuple(members),
                "a2-prerequisite-" + label + str(index),
            ),
        )
        g.decide_request(
            issuer,
            GrantDecisionCommand(
                request.request_id,
                True,
                "ASSIGNED_BUSINESS_DUTY",
                "POLICY",
                "isolated-a2-explicit-prerequisites:"
                + canonical_digest(
                    [
                        subject.principal_id,
                        [(x.owner, x.action, x.exact_resource) for x in members],
                    ]
                ),
                None,
                g.clock() + timedelta(minutes=10),
                "a2-prerequisite-decision-" + label + str(index),
                expected_version=1,
            ),
        )

    management = ResourceManagement(
        {**e.consumer_services, "mcp": e.consumer_services["skill"]},
        ManagementPolicy(
            enabled=True,
            policyId="isolated-a2-skill-author",
            policyVersion="1",
            issuer=automation.policy.issuer,
            credentialPath=automation.policy.credentialPath,
            workScopes=(
                ManagementScope(
                    namespace=scope.namespace,
                    securityDomain=scope.security_domain,
                    subject=e.context.principal_id,
                    kinds=("skill",),
                    expiresAt=g.clock() + timedelta(minutes=15),
                ),
            ),
        ),
        g,
    )
    service = e.consumer_services["skill"]
    rs = service.scope(scope.namespace, scope.security_domain)
    value = service.get(rs, "skill", original.resource_id)["resource"]
    sequence = 0

    def skill(action, **extra):
        nonlocal sequence, value
        sequence += 1
        with e.repo.connection_scope() as connection:
            result = management.handle(
                call(
                    connection,
                    {
                        "action": action,
                        "identity": original.resource_id,
                        "commandKey": "a2-skill-" + str(sequence),
                        "expectedVersion": value["aggregateVersion"],
                        **extra,
                    },
                )
            )
        value = result["resource"]
        return result

    skill("successor")
    source = json.loads(
        e.published_source["content"]["documents"][0]["chunks"][0]["content"]
    )
    old_content = PostgresOntologyRepository(c).read(
        (scope.namespace, scope.security_domain),
        ontology.resource_id,
        ontology.revision_id,
    )["content"]
    read_output = None
    draft = next(
        r
        for r in value["revisions"]
        if r["revisionId"] == value["currentDraftRevisionId"]
    )
    for operation in draft["content"]["operations"]:
        result = skill(
            "test",
            operation=operation["name"],
            testName="a2-" + operation["name"],
            testInput={
                "schemaVersion": "document-review-input.v1",
                "synthetic": True,
                "sourceSnapshot": e.consumer_refs["knowledge"].model_dump(mode="json"),
                "source": source,
                "dependencies": {} if read_output is None else {"read": read_output},
                "ontologyContent": old_content,
                "businessSemantics": policy_scope.documentRules.model_dump(mode="json"),
            },
            expectedOutput={"operation": operation["name"]},
            comparison="subset",
        )
        assert result["resource"]["testResults"][-1]["status"] == "PASSED"
        if operation["name"] == "READ_DATA":
            read_output = result["resource"]["testResults"][-1]["actual"]
    new_skill = ExactReference(
        resource_id=original.resource_id,
        revision_id=draft["revisionId"],
        digest=draft["digest"],
    )
    policy_grants(
        e.context,
        [
            ExactGrant(
                "AGENT",
                "READ",
                f"agent:{e.consumer_refs['agent'].resource_id}:{e.consumer_refs['agent'].revision_id}",
            ),
            ExactGrant("EMPLOYEE", "CREATE", "employee:collection"),
            *[
                ExactGrant(
                    "EMPLOYEE", action, f"employee:{old_employee.resource_id}:aggregate"
                )
                for action in ("VALIDATE", "APPROVE", "PUBLISH")
            ],
        ],
        "employee-publication",
    )
    with e.repo.connection_scope() as connection:
        UpgradeBatchRepository(e.repo.pool).migrate(
            Path(__file__).parents[1] / "migrations/0060_resource_upgrade_batch.sql"
        )
    owners = SelectedUpgradeOwners(
        management,
        EmployeeDefinitionCommandOwnerAdapter(
            automation.employees, prepared_resource_reads=True
        ),
        None,
    )
    coordinator = SelectedUpgradeCoordinator(
        SelectedUpgradePreview(service, automation.employees, None, None), owners
    )
    selected = UpgradeSelection(
        FixedReference(original.resource_id, original.revision_id, original.digest),
        FixedReference(new_skill.resource_id, new_skill.revision_id, new_skill.digest),
        (
            ConsumerSelection(
                FixedReference(
                    old_employee.resource_id,
                    old_employee.revision_id,
                    old_employee.digest,
                ),
                "employee-revision:a2-skill-successor",
            ),
        ),
        (),
    )
    with e.repo.connection_scope() as connection:
        preview = coordinator.preview(call(connection), selected)
    with e.repo.connection_scope() as connection:
        upgraded = coordinator.submit(
            call(connection),
            selected,
            command="a2-reviewed-skill-and-employee",
            reviewed_digest=preview["reviewDigest"],
            reason=(
                "Explicit same-contract Skill and exact employee successor selection"
            ),
        )
    last = upgraded["receipt"]["result"]["employees"][0][-1]
    new_employee = ExactReference(
        resource_id=last["employeeDefinitionId"],
        revision_id=last["employeeDefinitionRevisionId"],
        digest=last["employeeDefinitionDigest"],
    )
    secret = login(e.routing_sessions, "demo324")
    _, reviewer = e.routing_sessions.authenticate_session(secret.value)
    assert reviewer.principal_id != e.context.principal_id
    ontology_policy = MaintenancePolicy(
        enabled=True,
        policyId="isolated-a2-ontology-maintenance",
        policyVersion="1",
        issuer=automation.policy.issuer,
        credentialPath=automation.policy.credentialPath,
        workScopes=(
            MaintenanceScope(
                namespace=scope.namespace,
                securityDomain=scope.security_domain,
                subject=e.context.principal_id,
                ontologyIds=(ontology.resource_id,),
                actions=("REVISE", "VALIDATE", "TEST", "PUBLISH"),
                expiresAt=g.clock() + timedelta(minutes=15),
            ),
            MaintenanceScope(
                namespace=scope.namespace,
                securityDomain=scope.security_domain,
                subject=reviewer.principal_id,
                ontologyIds=(ontology.resource_id,),
                actions=("REVIEW",),
                expiresAt=g.clock() + timedelta(minutes=15),
            ),
        ),
    )
    manager = OntologyManagement(ontology_policy, g)
    reads_index = 0

    def reads(ref, actor, *, kind="ontology"):
        nonlocal reads_index
        reads_index += 1
        owner = {
            "ontology": "BUSINESS_ONTOLOGY",
            "employee": "EMPLOYEE",
            "skill": "SKILL",
            "knowledge": "KNOWLEDGE",
        }[kind]
        exact = (
            resource(ref.resource_id, ref.revision_id)
            if kind == "ontology"
            else (
                f"employee:{ref.resource_id}:{ref.revision_id}"
                if kind == "employee"
                else reference(kind, ref.resource_id, ref.revision_id)
            )
        )
        policy = TestReadPolicy(
            schemaVersion="test-resource-read-policy.v1",
            policyId="isolated-a2-precise-read",
            policyVersion="1",
            enabled=True,
            tenant=scope.namespace,
            securityDomain=scope.security_domain,
            subjects=(actor.principal_id,),
            issuer=automation.policy.issuer,
            credentialPath=automation.policy.credentialPath,
            expiresAt=g.clock() + timedelta(minutes=10),
            grantTTLSeconds=600,
            targets=(
                {
                    "owner": owner,
                    "action": "READ"
                    if kind in {"ontology", "employee"}
                    else "READ_RESOURCE",
                    "resource": exact,
                    "digest": ref.digest,
                    "purpose": "RESOURCE_PREPARATION",
                },
            ),
        )
        with e.repo.connection_scope() as connection:
            assert prepare(
                policy, g, actor, connection, "a2-precise-read-" + str(reads_index)
            )["items"]

    reads(ontology, e.context)
    changed = json.loads(json.dumps(old_content))
    for action in changed["actions"]:
        assert action["skill"] == original.model_dump(mode="json")
        action["skill"] = new_skill.model_dump(mode="json")
    old_row = PostgresOntologyRepository(c).read(
        (scope.namespace, scope.security_domain),
        ontology.resource_id,
        ontology.revision_id,
    )

    def maintain(payload, subject=None):
        with e.repo.connection_scope() as connection:
            return manager.handle(
                replace(
                    call(connection, payload, subject=subject),
                    operation="ONTOLOGY_MAINTENANCE",
                    path={},
                )
            )

    result = maintain(
        dict(
            action="REVISE",
            commandKey="a2-ontology-real-revise",
            ontologyId=ontology.resource_id,
            expectedVersion=old_row["version"],
            baseRevision=ontology.revision_id,
            baseDigest=ontology.digest,
            content=changed,
            reason=(
                "Keep all business rules and source unchanged; "
                "bind reviewed exact Skill successor"
            ),
        )
    )
    for action in ("VALIDATE", "TEST"):
        outcome = result["outcome"]
        result = maintain(
            dict(
                action=action,
                commandKey="a2-ontology-" + action,
                ontologyId=ontology.resource_id,
                expectedVersion=outcome["version"],
                revision=outcome["revision_id"],
                digest=outcome["digest"],
                reason="Normal exact lifecycle",
            )
        )
    outcome = result["outcome"]
    new_ontology = ExactReference(
        resource_id=ontology.resource_id,
        revision_id=outcome["revision_id"],
        digest=outcome["digest"],
    )
    for ref, kind in (
        (e.consumer_refs["knowledge"], "knowledge"),
        (new_skill, "skill"),
        (new_ontology, "ontology"),
    ):
        reads(ref, reviewer, kind=kind)
    try:
        maintain(
            dict(
                action="REVIEW",
                commandKey="a2-self-review-denied",
                ontologyId=ontology.resource_id,
                expectedVersion=outcome["version"],
                revision=outcome["revision_id"],
                digest=outcome["digest"],
                reason="Must not invent independent review",
            )
        )
    except (OntologyError, ValueError):
        pass
    else:
        raise AssertionError("author cannot review its own ontology")
    result = maintain(
        dict(
            action="REVIEW",
            commandKey="a2-real-other-ordinary-review",
            ontologyId=ontology.resource_id,
            expectedVersion=outcome["version"],
            revision=outcome["revision_id"],
            digest=outcome["digest"],
            reason=(
                "Separate ordinary actor reviews unchanged source/rules "
                "and exact reviewed successor"
            ),
        ),
        reviewer,
    )
    outcome = result["outcome"]
    result = maintain(
        dict(
            action="PUBLISH",
            commandKey="a2-real-owner-publish",
            ontologyId=ontology.resource_id,
            expectedVersion=outcome["version"],
            revision=outcome["revision_id"],
            digest=outcome["digest"],
            reason="Publish the real reviewed revision",
        )
    )
    assert result["outcome"]["state"] == "PUBLISH"
    # Existing exact GrantAdmin policy prerequisite, explicitly configured here.
    # Ontology maintenance publication itself never creates execution USE.
    policy_grants(
        e.context,
        [
            ExactGrant(
                "BUSINESS_ONTOLOGY",
                "USE",
                resource(new_ontology.resource_id, new_ontology.revision_id),
            )
        ],
        "new-ontology-use",
    )
    assert len(e.calls) == calls_before
    e.a2_published = dict(
        skill=new_skill,
        ontology=new_ontology,
        employee=new_employee,
        batch=upgraded["receipt"],
        ontologyPublication=result,
        author=e.context.principal_id,
        reviewer=reviewer.principal_id,
    )

    def publish_next_role():
        from agent_console.resource_upgrade_owners import EmployeePublication

        with e.repo.connection_scope() as connection:
            current = automation.employees.read_revision_for_workbench(
                connection,
                scope,
                new_employee.resource_id,
                new_employee.revision_id,
                authorized=True,
            )
            old_revision = EmployeeRevision.from_record(current["revision"])
            next_revision = replace(
                old_revision,
                revision_id="employee-revision:a2-new-role-after-adoption",
                predecessor_revision_id=old_revision.revision_id,
                role=old_revision.role + " successor role",
            )
            heads = automation.employees.authoring_heads_for_workbench(
                connection, scope, new_employee.resource_id, authorized=True
            )
            receipts = owners.publish_employee(
                call(connection),
                "a2-role-only-after-adoption",
                EmployeePublication(next_revision, heads["aggregateVersion"]),
            )
        final = receipts[-1]
        ref = ExactReference(
            resource_id=final["employeeDefinitionId"],
            revision_id=final["employeeDefinitionRevisionId"],
            digest=final["employeeDefinitionDigest"],
        )
        reads(ref, e.context, kind="employee")
        return ref

    e.a2_publish_next_role = publish_next_role
    return e.consumer_refs["agent"], new_employee


def prepare_owned_source(e):
    """Normal creator provenance exists before the first Goal/admission.

    Bootstrap supplies only isolated source/runtime/agent dependencies. The Skill
    actually used by the Goal is created/tested/published by its ordinary owner.
    We do not manufacture a handoff receipt for an older bootstrap Skill.
    """
    from tempfile import TemporaryDirectory

    import owned_business_consumer_support as support
    from test_document_rule_owner import rules
    from test_owned_resource_assembly_chain import prepare_source

    result = prepare_source(e)
    directory = TemporaryDirectory(prefix="a2-normal-skill-author-")
    previous_cleanup = e.consumer_cleanup

    def clean():
        previous_cleanup()
        directory.cleanup()

    e.consumer_cleanup = clean
    e.business_owner = None
    automation, adapter = support.resource_automation(
        e, NS(problems=None), Path(directory.name)
    )
    g = automation.grants
    generation = replace(
        g.generation,
        requestability=(
            *g.generation.requestability,
            *(
                RequestabilityRule(
                    "SKILL", action, "skill-invocation:", "RESOURCE_MANAGEMENT"
                )
                for action in (
                    "CREATE_RESOURCE",
                    "MANAGE_RESOURCE",
                    "READ_RESOURCE",
                    "REVIEW_PUBLISH_RESOURCE",
                    "CONNECT_MCP",
                )
            ),
        ),
    )
    g._generation_provider = lambda: generation
    g.authorization._generation_provider = lambda: generation
    g.target_validator.additional += (ManagementTargets(),)
    scope = e.context.scope
    management = ResourceManagement(
        {**e.consumer_services, "mcp": e.consumer_services["skill"]},
        ManagementPolicy(
            enabled=True,
            policyId="isolated-a2-original-owner",
            policyVersion="1",
            issuer=automation.policy.issuer,
            credentialPath=automation.policy.credentialPath,
            workScopes=(
                ManagementScope(
                    namespace=scope.tenant_id,
                    securityDomain=scope.security_domain,
                    subject=e.context.principal_id,
                    kinds=("skill",),
                    expiresAt=g.clock() + timedelta(minutes=15),
                ),
            ),
        ),
        g,
    )
    old = e.consumer_records["skill"]
    content = next(
        r["content"]
        for r in old["revisions"]
        if r["revisionId"] == old["publishedRevisionId"]
    )
    number = 0
    value = None

    def command(action, **extra):
        nonlocal number, value
        number += 1
        args = {
            "action": action,
            "commandKey": "a2-original-skill-" + str(number),
            **extra,
        }
        if value is not None:
            args.update(
                identity=value["resourceId"], expectedVersion=value["aggregateVersion"]
            )
        with e.repo.connection_scope() as c:
            call = AuthorizedOwnerCall(
                "RESOURCE_MANAGEMENT",
                e.context,
                c,
                args,
                {"kind": "skill"},
                {},
                (),
                AuthorizedOwnerAuthority(
                    adapter, e.context, c, generation.generation, ()
                ),
                generation.generation,
                1,
            )
            value = management.handle(call)["resource"]
        return value

    command(
        "create", name="Normally owned same-contract synthetic Skill", content=content
    )
    draft = value["revisions"][-1]
    ref = ExactReference(
        resource_id=value["resourceId"],
        revision_id=draft["revisionId"],
        digest=draft["digest"],
    )
    source = json.loads(
        e.published_source["content"]["documents"][0]["chunks"][0]["content"]
    )
    ontology = rules(
        source=source,
        reference=e.consumer_refs["knowledge"].model_dump(mode="json"),
        skill=ref.model_dump(mode="json"),
    )
    read_output = None
    for operation in content["operations"]:
        command(
            "test",
            operation=operation["name"],
            testName="initial-" + operation["name"],
            testInput={
                "schemaVersion": "document-review-input.v1",
                "synthetic": True,
                "sourceSnapshot": e.consumer_refs["knowledge"].model_dump(mode="json"),
                "source": source,
                "dependencies": {} if read_output is None else {"read": read_output},
                "ontologyContent": ontology.model_dump(mode="json"),
                "businessSemantics": {
                    "schema_version": "document-semantics-binding.v1",
                    "ontology": {
                        "resource_id": "unpublished-computation-fixture",
                        "revision_id": "not-execution",
                        "digest": "0" * 64,
                    },
                    "mapping_code": "interview",
                    "source": e.consumer_refs["knowledge"].model_dump(mode="json"),
                    "scope": "interview",
                },
            },
            expectedOutput={"operation": operation["name"]},
            comparison="subset",
        )
        assert value["testResults"][-1]["status"] == "PASSED"
        if operation["name"] == "READ_DATA":
            read_output = value["testResults"][-1]["actual"]
    command("publish-tested")
    e.consumer_refs["skill"] = ref
    service = e.consumer_services["skill"]
    e.consumer_records["skill"] = service.repository.get(
        service.scope(scope.tenant_id, scope.security_domain), "skill", ref.resource_id
    )
    e.a2_original_skill_owner_receipt = value
    return result
