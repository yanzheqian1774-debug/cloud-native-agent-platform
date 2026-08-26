"""Pure internal graph projection foundation for Product and Technical views.

This module deliberately owns no persistence, API, Kubernetes, controller, or
execution behavior.  It converts already-authorized evidence into one immutable
canonical graph and derives both visual projections from that same value.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from agent_console.shared_views import PlatformExecutionIdentity


class GraphProjectionError(ValueError):
    """Stable fail-closed error for invalid projection evidence."""


class GraphLayer(StrEnum):
    PLAN = "PLAN"
    EXECUTION_DEPENDENCY = "EXECUTION_DEPENDENCY"
    ASSIGNMENT = "ASSIGNMENT"
    DATA_EVIDENCE = "DATA_EVIDENCE"
    APPROVAL_DECISION = "APPROVAL_DECISION"


class NodeType(StrEnum):
    BUSINESS_PROBLEM = "BUSINESS_PROBLEM"
    PLAN = "PLAN"
    WORKFLOW = "WORKFLOW"
    TASK = "TASK"
    DEFINITION = "DEFINITION"
    INSTANCE = "INSTANCE"
    RUNTIME_REALIZATION = "RUNTIME_REALIZATION"
    CAPABILITY = "CAPABILITY"
    KNOWLEDGE = "KNOWLEDGE"
    APPROVAL = "APPROVAL"
    OUTCOME = "OUTCOME"


class Phase(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    DENIED = "DENIED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class RelationType(StrEnum):
    CONTAINS = "CONTAINS"
    DECOMPOSES_TO = "DECOMPOSES_TO"
    DEPENDS_ON = "DEPENDS_ON"
    DATA_FLOW = "DATA_FLOW"
    TRIGGERS = "TRIGGERS"
    ASSIGNED_TO = "ASSIGNED_TO"
    EXECUTED_BY = "EXECUTED_BY"
    REQUESTS = "REQUESTS"
    AUTHORIZED_BY = "AUTHORIZED_BY"
    PRODUCES = "PRODUCES"
    REFERENCES = "REFERENCES"
    APPROVED_BY = "APPROVED_BY"
    BLOCKS = "BLOCKS"
    COMPENSATES = "COMPENSATES"


class Cardinality(StrEnum):
    ONE_TO_ONE = "ONE_TO_ONE"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_ONE = "MANY_TO_ONE"
    MANY_TO_MANY = "MANY_TO_MANY"


class Direction(StrEnum):
    SOURCE_TO_TARGET = "SOURCE_TO_TARGET"


class ProjectionVisibility(StrEnum):
    PRODUCT = "PRODUCT"
    TECHNICAL = "TECHNICAL"
    BOTH = "BOTH"
    DETAIL_ONLY = "DETAIL_ONLY"


class ProjectionContext(StrEnum):
    PRODUCT = "PRODUCT"
    TECHNICAL = "TECHNICAL"


class PathClass(StrEnum):
    NORMAL = "NORMAL"
    FAILURE = "FAILURE"
    COMPENSATION = "COMPENSATION"
    HISTORICAL = "HISTORICAL"


class GroupKind(StrEnum):
    DEFINITION_INSTANCES = "DEFINITION_INSTANCES"
    REPEATED_TASKS = "REPEATED_TASKS"
    PARALLEL_BRANCHES = "PARALLEL_BRANCHES"
    EVIDENCE_COLLECTION = "EVIDENCE_COLLECTION"
    CAPABILITY_GROUP = "CAPABILITY_GROUP"
    RUNTIME_POOL = "RUNTIME_POOL"
    FAN = "FAN"


_TYPE_RANK = {item: index for index, item in enumerate(RelationType)}
_TYPE_RANK.update(
    {
        item: index
        for index, item in enumerate(
            (
                RelationType.BLOCKS,
                RelationType.DEPENDS_ON,
                RelationType.TRIGGERS,
                RelationType.DATA_FLOW,
                RelationType.ASSIGNED_TO,
                RelationType.EXECUTED_BY,
                RelationType.REQUESTS,
                RelationType.AUTHORIZED_BY,
                RelationType.APPROVED_BY,
                RelationType.PRODUCES,
                RelationType.COMPENSATES,
                RelationType.DECOMPOSES_TO,
                RelationType.CONTAINS,
                RelationType.REFERENCES,
            )
        )
    }
)
_NODE_RANK = {item: index for index, item in enumerate(NodeType)}
_CARDINALITY_RANK = {item: index for index, item in enumerate(Cardinality)}
_GROUP_RANK = {item: index for index, item in enumerate(GroupKind)}


def _required(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GraphProjectionError(code)
    return unicodedata.normalize("NFC", value)


def _stable_strings(values: Sequence[str], code: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise GraphProjectionError(code)
    normalized = tuple(sorted({_required(value, code) for value in values}))
    if len(normalized) != len(values):
        raise GraphProjectionError(code)
    return normalized


def _normalize(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, PlatformExecutionIdentity):
        return value.value
    if isinstance(value, Mapping):
        return {
            unicodedata.normalize("NFC", str(key)): _normalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_normalize(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [_normalize(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise GraphProjectionError("NON_CANONICAL_IDENTITY_INPUT")


def canonical_json(value: object) -> str:
    """Return the GP11 canonical JSON representation."""
    return json.dumps(
        _normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _identity(domain: str, value: object) -> str:
    digest = hashlib.sha256(canonical_json(value).encode()).hexdigest()
    return f"{domain}:{digest}"


@dataclass(frozen=True, slots=True)
class SnapshotContext:
    authoritative_input_id: str
    approved_plan_revision: str
    execution_snapshot_id: str
    policy_version: str = "v0.2-candidate"
    security_domain: str = "default"

    def __post_init__(self) -> None:
        for name in (
            "authoritative_input_id",
            "approved_plan_revision",
            "execution_snapshot_id",
            "policy_version",
            "security_domain",
        ):
            object.__setattr__(
                self, name, _required(getattr(self, name), "INVALID_CONTEXT")
            )

    @property
    def snapshot_id(self) -> str:
        return _identity("gps:v0.2-candidate", asdict(self))


@dataclass(frozen=True, slots=True)
class NodeSpec:
    node_type: NodeType
    entity_id: str
    label_key: str
    phase: Phase = Phase.UNKNOWN
    progress: float | None = None
    execution_identity: PlatformExecutionIdentity | None = None
    occurrence_context: str = "default"
    summary: str = ""
    evidence_ids: tuple[str, ...] = ()
    limitation_codes: tuple[str, ...] = ()
    visibility: ProjectionVisibility = ProjectionVisibility.BOTH
    group_kind: GroupKind | None = None
    group_parent_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.node_type, NodeType) or not isinstance(
            self.phase, Phase
        ):
            raise GraphProjectionError("INVALID_NODE_ENUM")
        for name in ("entity_id", "label_key", "occurrence_context"):
            object.__setattr__(
                self, name, _required(getattr(self, name), "INVALID_NODE")
            )
        if self.progress is not None and (
            isinstance(self.progress, bool)
            or not isinstance(self.progress, (int, float))
            or not 0 <= self.progress <= 1
        ):
            raise GraphProjectionError("INVALID_PROGRESS")
        if self.execution_identity is not None and not isinstance(
            self.execution_identity, PlatformExecutionIdentity
        ):
            raise GraphProjectionError("PLATFORM_EXECUTION_IDENTITY_REQUIRED")
        object.__setattr__(
            self, "evidence_ids", _stable_strings(self.evidence_ids, "INVALID_EVIDENCE")
        )
        object.__setattr__(
            self,
            "limitation_codes",
            _stable_strings(self.limitation_codes, "INVALID_LIMITATION"),
        )
        if not isinstance(self.visibility, ProjectionVisibility):
            raise GraphProjectionError("INVALID_VISIBILITY")
        if (self.group_kind is None) != (self.group_parent_id is None):
            raise GraphProjectionError("INCOMPLETE_GROUP_CLASSIFICATION")


@dataclass(frozen=True, slots=True)
class GraphNode:
    node_id: str
    node_type: NodeType
    entity_id: str
    label_key: str
    phase: Phase
    progress: float | None
    execution_identity: PlatformExecutionIdentity | None
    summary: str
    evidence_ids: tuple[str, ...]
    limitation_codes: tuple[str, ...]
    visibility: ProjectionVisibility
    group_kind: GroupKind | None
    group_parent_id: str | None


@dataclass(frozen=True, slots=True)
class RelationSpec:
    source_entity_id: str
    target_entity_id: str
    relation_types: tuple[RelationType, ...]
    layer: GraphLayer
    declared_cardinality: Cardinality
    state: Phase = Phase.UNKNOWN
    evidence_ids: tuple[str, ...] = ()
    display_priority: int = 100
    projection_visibility: ProjectionVisibility = ProjectionVisibility.BOTH
    semantic_discriminator: str = "default"
    path_class: PathClass = PathClass.NORMAL
    blocking_class: str = "INFORMATIONAL"
    authorization_class: str = "UNCLASSIFIED"
    evidence_authority_class: str = "UPSTREAM"
    execution_or_historical_context: str = "CURRENT"
    tenant_or_security_domain: str = "default"
    aggregation_key: str | None = None
    observed_source_count: int = 1
    observed_target_count: int = 1

    def __post_init__(self) -> None:
        for name in (
            "source_entity_id",
            "target_entity_id",
            "semantic_discriminator",
            "blocking_class",
            "authorization_class",
            "evidence_authority_class",
            "execution_or_historical_context",
            "tenant_or_security_domain",
        ):
            object.__setattr__(
                self, name, _required(getattr(self, name), "INVALID_RELATION")
            )
        if not self.relation_types or not all(
            isinstance(item, RelationType) for item in self.relation_types
        ):
            raise GraphProjectionError("INVALID_RELATION_TYPE")
        if len(set(self.relation_types)) != len(self.relation_types):
            raise GraphProjectionError("DUPLICATE_RELATION_TYPE")
        if not isinstance(self.layer, GraphLayer) or not isinstance(
            self.declared_cardinality, Cardinality
        ):
            raise GraphProjectionError("INVALID_RELATION_ENUM")
        if not isinstance(self.state, Phase) or not isinstance(
            self.path_class, PathClass
        ):
            raise GraphProjectionError("INVALID_RELATION_ENUM")
        if not isinstance(self.display_priority, int) or isinstance(
            self.display_priority, bool
        ):
            raise GraphProjectionError("INVALID_DISPLAY_PRIORITY")
        for value in (self.observed_source_count, self.observed_target_count):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise GraphProjectionError("INVALID_OBSERVED_CARDINALITY")
        object.__setattr__(
            self, "evidence_ids", _stable_strings(self.evidence_ids, "INVALID_EVIDENCE")
        )
        if (
            RelationType.BLOCKS in self.relation_types
            and self.blocking_class == "INFORMATIONAL"
        ):
            raise GraphProjectionError("BLOCKS_REQUIRES_BLOCKING_CLASS")
        if (
            RelationType.COMPENSATES in self.relation_types
            and self.path_class != PathClass.COMPENSATION
        ):
            raise GraphProjectionError("COMPENSATES_REQUIRES_COMPENSATION_PATH")


@dataclass(frozen=True, slots=True)
class RawRelation:
    relation_id: str
    source_node_id: str
    target_node_id: str
    relation_types: tuple[RelationType, ...]
    layer: GraphLayer
    direction: Direction
    declared_cardinality: Cardinality
    observed_source_count: int
    observed_target_count: int
    state: Phase
    evidence_ids: tuple[str, ...]
    display_priority: int
    projection_visibility: ProjectionVisibility
    semantic_discriminator: str
    path_class: PathClass
    blocking_class: str
    authorization_class: str
    evidence_authority_class: str
    execution_or_historical_context: str
    tenant_or_security_domain: str
    aggregation_key: str | None


@dataclass(frozen=True, slots=True)
class CanonicalGraph:
    graph_snapshot_id: str
    context: SnapshotContext
    nodes: tuple[GraphNode, ...]
    relations: tuple[RawRelation, ...]


def _node_sort(node: GraphNode) -> tuple[int, str, str]:
    return (_NODE_RANK[node.node_type], node.entity_id, node.node_id)


def _relation_sort(relation: RawRelation) -> tuple[object, ...]:
    return (
        relation.source_node_id,
        relation.target_node_id,
        relation.direction.value,
        relation.display_priority,
        _CARDINALITY_RANK[relation.declared_cardinality],
        relation.relation_id,
    )


def build_graph(
    context: SnapshotContext,
    node_specs: Sequence[NodeSpec],
    relation_specs: Sequence[RelationSpec],
) -> CanonicalGraph:
    """Build and validate one canonical graph from normalized upstream facts."""
    if not node_specs:
        raise GraphProjectionError("GRAPH_REQUIRES_NODES")
    snapshot_id = context.snapshot_id
    nodes_by_entity: dict[str, GraphNode] = {}
    for spec in node_specs:
        if spec.entity_id in nodes_by_entity:
            raise GraphProjectionError("DUPLICATE_ENTITY_ID")
        node_id = _identity(
            "gpn:v0.2-candidate",
            (snapshot_id, spec.node_type, spec.entity_id, spec.occurrence_context),
        )
        nodes_by_entity[spec.entity_id] = GraphNode(
            node_id=node_id,
            node_type=spec.node_type,
            entity_id=spec.entity_id,
            label_key=spec.label_key,
            phase=spec.phase,
            progress=spec.progress,
            execution_identity=spec.execution_identity,
            summary=spec.summary,
            evidence_ids=spec.evidence_ids,
            limitation_codes=spec.limitation_codes,
            visibility=spec.visibility,
            group_kind=spec.group_kind,
            group_parent_id=spec.group_parent_id,
        )

    relations: list[RawRelation] = []
    relation_ids: set[str] = set()
    for spec in relation_specs:
        try:
            source = nodes_by_entity[spec.source_entity_id]
            target = nodes_by_entity[spec.target_entity_id]
        except KeyError as exc:
            raise GraphProjectionError("UNKNOWN_RELATION_ENDPOINT") from exc
        ordered_types = tuple(
            sorted(spec.relation_types, key=lambda item: (_TYPE_RANK[item], item.value))
        )
        relation_id = _identity(
            "gpr:v0.2-candidate",
            (
                snapshot_id,
                spec.layer,
                source.node_id,
                target.node_id,
                Direction.SOURCE_TO_TARGET,
                tuple(sorted(item.value for item in ordered_types)),
                spec.declared_cardinality,
                spec.state,
                spec.semantic_discriminator,
            ),
        )
        if relation_id in relation_ids:
            raise GraphProjectionError("DUPLICATE_RELATION_ID")
        relation_ids.add(relation_id)
        relations.append(
            RawRelation(
                relation_id=relation_id,
                source_node_id=source.node_id,
                target_node_id=target.node_id,
                relation_types=ordered_types,
                layer=spec.layer,
                direction=Direction.SOURCE_TO_TARGET,
                declared_cardinality=spec.declared_cardinality,
                observed_source_count=spec.observed_source_count,
                observed_target_count=spec.observed_target_count,
                state=spec.state,
                evidence_ids=spec.evidence_ids,
                display_priority=spec.display_priority,
                projection_visibility=spec.projection_visibility,
                semantic_discriminator=spec.semantic_discriminator,
                path_class=spec.path_class,
                blocking_class=spec.blocking_class,
                authorization_class=spec.authorization_class,
                evidence_authority_class=spec.evidence_authority_class,
                execution_or_historical_context=spec.execution_or_historical_context,
                tenant_or_security_domain=spec.tenant_or_security_domain,
                aggregation_key=spec.aggregation_key,
            )
        )
    ordered_nodes = tuple(sorted(nodes_by_entity.values(), key=_node_sort))
    ordered_relations = tuple(sorted(relations, key=_relation_sort))
    _validate_execution_dependency_dag(ordered_nodes, ordered_relations)
    return CanonicalGraph(snapshot_id, context, ordered_nodes, ordered_relations)


def _validate_execution_dependency_dag(
    nodes: Sequence[GraphNode], relations: Sequence[RawRelation]
) -> None:
    node_ids = {node.node_id for node in nodes}
    indegree = dict.fromkeys(node_ids, 0)
    dependents: dict[str, list[str]] = defaultdict(list)
    for relation in relations:
        if relation.layer != GraphLayer.EXECUTION_DEPENDENCY:
            continue
        if RelationType.DEPENDS_ON not in relation.relation_types:
            raise GraphProjectionError("INVALID_EXECUTION_DEPENDENCY_RELATION")
        # DEPENDS_ON is dependent -> prerequisite, so reverse it for traversal.
        indegree[relation.source_node_id] += 1
        dependents[relation.target_node_id].append(relation.source_node_id)
    ready = deque(sorted(node for node, degree in indegree.items() if degree == 0))
    visited = 0
    while ready:
        node = ready.popleft()
        visited += 1
        for dependent in sorted(dependents[node]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
    if visited != len(node_ids):
        raise GraphProjectionError("EXECUTION_DEPENDENCY_CYCLE")


@dataclass(frozen=True, slots=True)
class VisualEdge:
    aggregation_id: str
    source_node_id: str
    target_node_id: str
    primary_type: RelationType
    secondary_types: tuple[RelationType, ...]
    remaining_type_count: int
    cardinalities: tuple[Cardinality, ...]
    raw_relation_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VisualGroup:
    group_id: str
    group_kind: GroupKind
    parent_id: str
    member_node_ids: tuple[str, ...]
    member_count: int
    phase_summary: Mapping[Phase, int]
    evidence_ids: tuple[str, ...]
    limitation_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "phase_summary", MappingProxyType(dict(self.phase_summary))
        )


@dataclass(frozen=True, slots=True)
class GraphView:
    graph_snapshot_id: str
    context: ProjectionContext
    nodes: tuple[GraphNode, ...]
    groups: tuple[VisualGroup, ...]
    edges: tuple[VisualEdge, ...]
    raw_relations: tuple[RawRelation, ...]


def _visible(visibility: ProjectionVisibility, context: ProjectionContext) -> bool:
    return visibility == ProjectionVisibility.BOTH or visibility.value == context.value


def _aggregate_relations(
    graph: CanonicalGraph,
    context: ProjectionContext,
    relations: Sequence[RawRelation],
    endpoint_aliases: Mapping[str, str],
) -> tuple[VisualEdge, ...]:
    buckets: dict[tuple[object, ...], list[RawRelation]] = defaultdict(list)
    for relation in relations:
        source = endpoint_aliases.get(relation.source_node_id, relation.source_node_id)
        target = endpoint_aliases.get(relation.target_node_id, relation.target_node_id)
        key = (
            source,
            target,
            relation.direction,
            context,
            relation.tenant_or_security_domain,
            relation.execution_or_historical_context,
            relation.path_class,
            relation.blocking_class,
            relation.authorization_class,
            relation.evidence_authority_class,
            relation.aggregation_key,
        )
        buckets[key].append(relation)
    result: list[VisualEdge] = []
    for key, members in buckets.items():
        ordered = sorted(
            members,
            key=lambda item: (
                item.display_priority,
                min(_TYPE_RANK[kind] for kind in item.relation_types),
                item.relation_id,
            ),
        )
        types: list[RelationType] = []
        for relation in ordered:
            for relation_type in relation.relation_types:
                if relation_type not in types:
                    types.append(relation_type)
        relation_ids = tuple(sorted(item.relation_id for item in members))
        aggregation_id = _identity(
            "gpa:v0.2-candidate", (graph.graph_snapshot_id, key, relation_ids)
        )
        cardinalities = tuple(
            sorted(
                {item.declared_cardinality for item in members},
                key=lambda item: (_CARDINALITY_RANK[item], item.value),
            )
        )
        result.append(
            VisualEdge(
                aggregation_id=aggregation_id,
                source_node_id=str(key[0]),
                target_node_id=str(key[1]),
                primary_type=types[0],
                secondary_types=tuple(types[1:3]),
                remaining_type_count=max(0, len(types) - 3),
                cardinalities=cardinalities,
                raw_relation_ids=relation_ids,
                evidence_ids=tuple(
                    sorted(
                        {evidence for item in members for evidence in item.evidence_ids}
                    )
                ),
            )
        )
    return tuple(
        sorted(
            result,
            key=lambda item: (
                item.source_node_id,
                item.target_node_id,
                item.aggregation_id,
            ),
        )
    )


def _build_groups(
    graph: CanonicalGraph,
    context: ProjectionContext,
    nodes: Sequence[GraphNode],
    *,
    threshold: int,
    expanded_group_ids: frozenset[str],
) -> tuple[tuple[VisualGroup, ...], dict[str, str], set[str]]:
    candidates: dict[tuple[GroupKind, str], list[GraphNode]] = defaultdict(list)
    for node in nodes:
        if node.group_kind is not None and node.group_parent_id is not None:
            candidates[(node.group_kind, node.group_parent_id)].append(node)
    groups: list[VisualGroup] = []
    aliases: dict[str, str] = {}
    hidden: set[str] = set()
    for (kind, parent), members in sorted(
        candidates.items(), key=lambda item: (_GROUP_RANK[item[0][0]], item[0][1])
    ):
        if len(members) < threshold:
            continue
        member_ids = tuple(sorted(item.node_id for item in members))
        group_id = _identity(
            "gpg:v0.2-candidate",
            (
                graph.context.policy_version,
                context,
                graph.context.security_domain,
                kind,
                parent,
                member_ids,
            ),
        )
        if group_id in expanded_group_ids:
            continue
        phases: dict[Phase, int] = defaultdict(int)
        for member in members:
            phases[member.phase] += 1
            aliases[member.node_id] = group_id
            hidden.add(member.node_id)
        groups.append(
            VisualGroup(
                group_id=group_id,
                group_kind=kind,
                parent_id=parent,
                member_node_ids=member_ids,
                member_count=len(members),
                phase_summary=dict(
                    sorted(phases.items(), key=lambda item: item[0].value)
                ),
                evidence_ids=tuple(
                    sorted({value for item in members for value in item.evidence_ids})
                ),
                limitation_codes=tuple(
                    sorted(
                        {value for item in members for value in item.limitation_codes}
                    )
                ),
            )
        )
    return tuple(groups), aliases, hidden


def project_graph(
    graph: CanonicalGraph,
    context: ProjectionContext,
    *,
    expanded_group_ids: Sequence[str] = (),
    grouping_threshold: int = 4,
) -> GraphView:
    """Derive one view without discovering or changing canonical relationships."""
    if not isinstance(context, ProjectionContext):
        raise GraphProjectionError("INVALID_PROJECTION_CONTEXT")
    if grouping_threshold < 1:
        raise GraphProjectionError("INVALID_GROUP_THRESHOLD")
    visible_nodes = tuple(
        node for node in graph.nodes if _visible(node.visibility, context)
    )
    visible_ids = {node.node_id for node in visible_nodes}
    visible_relations = tuple(
        relation
        for relation in graph.relations
        if _visible(relation.projection_visibility, context)
        and relation.source_node_id in visible_ids
        and relation.target_node_id in visible_ids
    )
    groups, aliases, hidden = _build_groups(
        graph,
        context,
        visible_nodes,
        threshold=grouping_threshold,
        expanded_group_ids=frozenset(expanded_group_ids),
    )
    displayed_nodes = tuple(
        node for node in visible_nodes if node.node_id not in hidden
    )
    edges = _aggregate_relations(graph, context, visible_relations, aliases)
    return GraphView(
        graph_snapshot_id=graph.graph_snapshot_id,
        context=context,
        nodes=displayed_nodes,
        groups=groups,
        edges=edges,
        raw_relations=visible_relations,
    )


def product_graph_view(graph: CanonicalGraph, **kwargs: Any) -> GraphView:
    return project_graph(graph, ProjectionContext.PRODUCT, **kwargs)


def technical_graph_view(graph: CanonicalGraph, **kwargs: Any) -> GraphView:
    return project_graph(graph, ProjectionContext.TECHNICAL, **kwargs)
