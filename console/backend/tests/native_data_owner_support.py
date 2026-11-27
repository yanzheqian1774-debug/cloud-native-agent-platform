"""Same-database owner fixtures; publication authority/provider are controlled."""

from agent_console.delivery_resource_bundle import source_document
from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeRevision,
    MemberKind,
)
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.execution_domain import ScopeIdentity
from agent_console.native_data_adapters import capabilities
from agent_console.native_data_resource_bundle import resource_content
from agent_console.plan_suggestion_domain import ExactReference

DESCRIPTOR = capabilities("synthetic-delivery-source.v1")[0]


def prepare_source(e):
    import owned_business_consumer_support as support

    original = support.resource_content
    try:
        support.resource_content = lambda *_args, **_kwargs: resource_content(
            source_document(), DESCRIPTOR
        )
        support.prepare_source(e)
    finally:
        support.resource_content = original


def configure_scope(e, result, policy):
    refs = e.consumer_refs
    scope = e.context.scope
    employee = EmployeeRevision(
        ScopeIdentity(scope.tenant_id, scope.security_domain),
        "employee-definition:native-data-test",
        "employee-revision:native-data-test",
        "Native data test employee",
        ("Isolated test only",),
        tuple(
            CompositionMember(
                MemberKind("RUNTIME_PROFILE" if k == "runtime" else k.upper()),
                ref.resource_id,
                ref.revision_id,
                ref.digest,
            )
            for k, ref in refs.items()
        ),
    )
    repo = PostgresEmployeeDefinitionRepository(e.repo)
    with e.repo.connection_scope() as c:
        value = repo.create_for_workbench(
            c,
            employee,
            expected_version=0,
            decision_id="isolated-publication-port",
            command_id="native-data-employee-create",
            authorized=True,
        )
        for action in ("VALIDATE", "APPROVE", "PUBLISH"):
            value = repo.decide_for_workbench(
                c,
                employee.scope,
                employee.definition_id,
                employee.revision_id,
                employee.digest,
                action,
                expected_version=value["aggregateVersion"],
                decision_id="isolated-publication-port",
                command_id="native-data-employee-" + action,
                authorized=True,
            )
    e.consumer_employee = ExactReference(
        resource_id=employee.definition_id,
        revision_id=employee.revision_id,
        digest=employee.digest,
    )
    policy.update(
        schemaVersion="owned-business-admission.v4",
        retainedReadPolicyDigests=[],
        independentGoalProfile={
            "profileRevisionId": "unused-root-path",
            "profileDigest": "a" * 64,
            "adapterRevision": "v4-structured-conversation",
        },
    )
    policy["scopes"][0].update(
        case="native_readonly",
        sourceSchema=DESCRIPTOR["sourceSchema"],
        adapter=DESCRIPTOR,
        documentRules=None,
        employees=[e.consumer_employee.model_dump()],
        agents=[refs["agent"].model_dump()],
        skills=[refs["skill"].model_dump()],
        runtimes=[refs["runtime"].model_dump()],
        operations=DESCRIPTOR["operations"],
        nativeAgentName="isolated-native-data",
    )


def semantics(e, target):
    from agent_console.plan_suggestion_domain import FlexiblePlanSemantics
    from test_conversation_planning_source import boundary
    from test_planning_contracts import modern

    v = modern(DESCRIPTOR["operations"])
    v.update(
        scenario="GENERAL_READ_ONLY",
        target=target,
        title="检查所选交付资料",
        business_rules=["按资料声明的评估日期核对原始行,区分异常与原因。"],
        boundaries=[
            boundary(e.consumer_refs["knowledge"].model_dump()),
            "仅分析合成资料,不写外部系统。",
        ],
        requirements=[
            dict(
                requirement_id="employee",
                kind="EMPLOYEE",
                name="已发布的数据分析员工",
                purpose="读取并核对资料依据",
                required=True,
                preparation="使用精确已发布的职责绑定",
                selected=e.consumer_employee.model_dump(),
            ),
            dict(
                requirement_id="snapshot",
                kind="KNOWLEDGE",
                name="所选资料",
                purpose="提供分析依据",
                required=True,
                preparation="核对原始资料摘要",
                selected=e.consumer_refs["knowledge"].model_dump(),
            ),
        ],
    )
    for i, task in enumerate(v["tasks"]):
        task.update(
            title=("读取资料", "核验资料", "分析资料", "生成报告")[i],
            responsibility="读取并核对资料依据",
            criterion_revision_ids=target["criterion_revision_ids"],
            inputs=["精确资料快照" if i == 0 else f"output-{i - 1}"],
            outputs=[f"output-{i}"],
        )
    return FlexiblePlanSemantics.model_validate(v)
