"""Business process definitions, distinct from executable Workflow definitions.

Drafts can record unknown business facts. Diagnostics are definition checks,
never evidence that resources are authorized or that execution succeeded.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1, max_length=2000, strict=True)]
Name = Annotated[str, Field(min_length=1, max_length=160, strict=True)]
Identity = Annotated[str, Field(min_length=1, max_length=200, strict=True)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$", strict=True)]


class BusinessDefinition(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    @model_validator(mode="after")
    def meaningful_text(self):
        for value in self.__dict__.values():
            values = value if isinstance(value, tuple) else (value,)
            if any(isinstance(item, str) and not item.strip() for item in values):
                raise ValueError("BUSINESS_PROCESS_BLANK_TEXT")
        return self


class BusinessDomain(BusinessDefinition):
    domain_id: Identity
    name: Name
    band: Literal["MANAGEMENT", "CORE", "SUPPORT"]


class BusinessProcessGroup(BusinessDefinition):
    group_id: Identity
    domain_id: Identity
    name: Name


class BusinessArchitecture(BusinessDefinition):
    domains: tuple[BusinessDomain, ...] = Field(default=(), max_length=200)
    groups: tuple[BusinessProcessGroup, ...] = Field(default=(), max_length=1000)

    @model_validator(mode="after")
    def unique_hierarchy(self):
        domains = [item.domain_id for item in self.domains]
        groups = [item.group_id for item in self.groups]
        if len(domains) != len(set(domains)) or len(groups) != len(set(groups)):
            raise ValueError("BUSINESS_ARCHITECTURE_DUPLICATE_ID")
        if any(item.domain_id not in domains for item in self.groups):
            raise ValueError("BUSINESS_GROUP_DOMAIN_NOT_FOUND")
        return self


class FixedBusinessReference(BusinessDefinition):
    resource_id: Identity
    revision_id: Identity
    digest: Digest


class BusinessActivity(BusinessDefinition):
    activity_id: Identity
    name: Name
    responsible_role: Name | None = None
    inputs: tuple[Name, ...] = Field(default=(), max_length=128)
    outputs: tuple[Name, ...] = Field(default=(), max_length=128)
    completion_conditions: tuple[Text, ...] = Field(default=(), max_length=32)
    human_boundary: Text | None = None
    # A fixed digital employee reference does not replace business responsibility.
    employee: FixedBusinessReference | None = None


class BusinessHandoff(BusinessDefinition):
    # Optional only for historical drafts; new editor-created handoffs retain this ID.
    handoff_id: Identity | None = None
    from_activity_id: Identity
    to_activity_id: Identity
    event: Literal["COMPLETED", "RETURNED", "NEEDS_INFORMATION"]
    explanation: Text
    responsible_role: Name | None = None


class BusinessProcessContent(BusinessDefinition):
    name: Name
    business_code: Name | None = None
    domain_id: Identity
    group_id: Identity
    owner_description: Name | None = None
    purpose: Text | None = None
    source_materials: tuple[FixedBusinessReference, ...] = Field(
        default=(), max_length=64
    )
    improvement_notes: Text | None = None
    # Array order is business reading order, not a scheduler dependency graph.
    activities: tuple[BusinessActivity, ...] = Field(default=(), max_length=200)
    handoffs: tuple[BusinessHandoff, ...] = Field(default=(), max_length=600)

    @model_validator(mode="after")
    def stable_activity_references(self):
        identities = [activity.activity_id for activity in self.activities]
        if len(identities) != len(set(identities)):
            raise ValueError("BUSINESS_ACTIVITY_DUPLICATE_ID")
        handoff_ids = [item.handoff_id for item in self.handoffs if item.handoff_id]
        if len(handoff_ids) != len(set(handoff_ids)):
            raise ValueError("BUSINESS_HANDOFF_DUPLICATE_ID")
        edges = []
        for handoff in self.handoffs:
            if (
                handoff.from_activity_id not in identities
                or handoff.to_activity_id not in identities
            ):
                raise ValueError("BUSINESS_HANDOFF_ACTIVITY_NOT_FOUND")
            edges.append(
                (handoff.from_activity_id, handoff.to_activity_id, handoff.event)
            )
        if len(edges) != len(set(edges)):
            raise ValueError("BUSINESS_HANDOFF_DUPLICATE")
        # Return and missing-information paths may point back to earlier activities.
        # These are documented business handoffs, not executable DAG edges.
        return self


class BusinessCapabilityRelation(BusinessDefinition):
    relation_id: Identity
    relation_revision_id: Identity
    relation_type: Literal["SUPPORTS_ACTIVITY", "DERIVED_FROM_PROCESS"]
    process: FixedBusinessReference
    activity_ids: tuple[Identity, ...] = Field(min_length=1, max_length=200)
    capability: FixedBusinessReference
    coverage_description: Text

    @model_validator(mode="after")
    def unique_coverage(self):
        if len(self.activity_ids) != len(set(self.activity_ids)):
            raise ValueError("BUSINESS_CAPABILITY_COVERAGE_DUPLICATE")
        return self


class BusinessDefinitionIssue(BusinessDefinition):
    code: Identity
    path: Identity
    message: Text


def definition_issues(
    content: BusinessProcessContent, architecture: BusinessArchitecture
) -> tuple[BusinessDefinitionIssue, ...]:
    """Return only known definition gaps. Never invent missing business facts."""
    issues = []

    def missing(code, path, message):
        issues.append(BusinessDefinitionIssue(code=code, path=path, message=message))

    if not any(
        domain.domain_id == content.domain_id for domain in architecture.domains
    ):
        missing("DOMAIN_NOT_FOUND", "domain_id", "所属业务领域尚未登记。")
    group = next(
        (group for group in architecture.groups if group.group_id == content.group_id),
        None,
    )
    if group is None or group.domain_id != content.domain_id:
        missing("GROUP_DOMAIN_MISMATCH", "group_id", "流程组与所属领域尚未核对一致。")
    for field, label in (("owner_description", "业务负责人"), ("purpose", "流程目的")):
        if getattr(content, field) is None:
            missing("BUSINESS_FACT_MISSING", field, f"请补齐{label}。")
    if not content.activities:
        missing("ACTIVITIES_MISSING", "activities", "尚未登记业务活动。")
    for index, activity in enumerate(content.activities):
        for field, label in (
            ("responsible_role", "业务责任角色"),
            ("inputs", "活动输入"),
            ("outputs", "活动输出"),
            ("completion_conditions", "完成条件"),
            ("human_boundary", "人工参与边界"),
        ):
            if not getattr(activity, field):
                missing(
                    "ACTIVITY_FACT_MISSING",
                    f"activities.{index}.{field}",
                    f"“{activity.name}”尚未填写{label}。",
                )
    for index, handoff in enumerate(content.handoffs):
        if handoff.event != "COMPLETED" and handoff.responsible_role is None:
            missing(
                "HANDOFF_ROLE_MISSING",
                f"handoffs.{index}.responsible_role",
                "退回或补资料交接尚未说明负责角色。",
            )
    return tuple(issues)


def relation_issues(
    relation: BusinessCapabilityRelation,
    process_reference: FixedBusinessReference,
    content: BusinessProcessContent,
) -> tuple[BusinessDefinitionIssue, ...]:
    """Caller must separately authorize both exact references before read/return."""
    if relation.process != process_reference:
        return (
            BusinessDefinitionIssue(
                code="PROCESS_REVISION_MISMATCH",
                path="process",
                message="关联指定的流程固定版本与读取版本不一致。",
            ),
        )
    activity_ids = {item.activity_id for item in content.activities}
    if any(identity not in activity_ids for identity in relation.activity_ids):
        return (
            BusinessDefinitionIssue(
                code="ACTIVITY_COVERAGE_NOT_FOUND",
                path="activity_ids",
                message="关联范围包含此流程版本中不存在的活动。",
            ),
        )
    return ()
