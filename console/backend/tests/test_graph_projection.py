"""Component acceptance tests for the internal graph projection foundation."""

from dataclasses import replace

import pytest
from agent_console.graph_projection import (
    Cardinality,
    GraphLayer,
    GraphProjectionError,
    GroupKind,
    NodeSpec,
    NodeType,
    PathClass,
    Phase,
    ProjectionEffects,
    ProjectionVisibility,
    RelationSpec,
    RelationType,
    SnapshotContext,
    build_graph,
    product_graph_view,
    technical_graph_view,
)
from agent_console.shared_views import AuthorizationDecision, PlatformExecutionIdentity

CONTEXT = SnapshotContext(
    authoritative_input_id="fixture-authority",
    approved_plan_revision="plan-revision-001",
    execution_snapshot_id="execution-snapshot-001",
    security_domain="fixture-authorized-domain",
)
PEI = PlatformExecutionIdentity("pei-fixture-001")


def node(
    entity_id: str,
    node_type: NodeType = NodeType.TASK,
    *,
    phase: Phase = Phase.PENDING,
    visibility: ProjectionVisibility = ProjectionVisibility.BOTH,
    evidence: tuple[str, ...] = (),
    group_kind: GroupKind | None = None,
    group_parent_id: str | None = None,
) -> NodeSpec:
    return NodeSpec(
        node_type=node_type,
        entity_id=entity_id,
        label_key=f"node.{entity_id}",
        phase=phase,
        execution_identity=PEI,
        evidence_ids=evidence,
        visibility=visibility,
        group_kind=group_kind,
        group_parent_id=group_parent_id,
    )


def relation(
    source: str,
    target: str,
    relation_type: RelationType,
    cardinality: Cardinality,
    *,
    evidence: tuple[str, ...],
    layer: GraphLayer = GraphLayer.ASSIGNMENT,
    visibility: ProjectionVisibility = ProjectionVisibility.BOTH,
    aggregation_key: str | None = None,
    state: Phase = Phase.PENDING,
    semantic_discriminator: str | None = None,
    blocking_class: str = "INFORMATIONAL",
    authorization_class: str = "UNCLASSIFIED",
    path_class: PathClass = PathClass.NORMAL,
    observed: tuple[int, int] = (1, 1),
) -> RelationSpec:
    return RelationSpec(
        source_entity_id=source,
        target_entity_id=target,
        relation_types=(relation_type,),
        layer=layer,
        declared_cardinality=cardinality,
        evidence_ids=evidence,
        projection_visibility=visibility,
        aggregation_key=aggregation_key,
        state=state,
        semantic_discriminator=semantic_discriminator
        or f"{source}-{relation_type.value}-{target}",
        blocking_class=blocking_class,
        authorization_class=authorization_class,
        path_class=path_class,
        observed_source_count=observed[0],
        observed_target_count=observed[1],
        tenant_or_security_domain=CONTEXT.security_domain,
    )


def serial_fixture():
    nodes = [
        node(
            "problem",
            NodeType.BUSINESS_PROBLEM,
            visibility=ProjectionVisibility.PRODUCT,
        ),
        node("plan", NodeType.PLAN),
        node("workflow", NodeType.WORKFLOW),
        node("A"),
        node("B"),
        node("C"),
        node(
            "definition",
            NodeType.DEFINITION,
            visibility=ProjectionVisibility.TECHNICAL,
        ),
        node(
            "instance",
            NodeType.INSTANCE,
            visibility=ProjectionVisibility.TECHNICAL,
        ),
        node(
            "runtime",
            NodeType.RUNTIME_REALIZATION,
            visibility=ProjectionVisibility.TECHNICAL,
        ),
        node("outcome", NodeType.OUTCOME),
    ]
    relations = [
        relation(
            "problem",
            "plan",
            RelationType.DECOMPOSES_TO,
            Cardinality.ONE_TO_ONE,
            evidence=("ev-plan",),
            layer=GraphLayer.PLAN,
            visibility=ProjectionVisibility.PRODUCT,
        ),
        relation(
            "workflow",
            "A",
            RelationType.CONTAINS,
            Cardinality.ONE_TO_MANY,
            evidence=("ev-topology-a",),
            layer=GraphLayer.PLAN,
            observed=(1, 3),
        ),
        relation(
            "workflow",
            "B",
            RelationType.CONTAINS,
            Cardinality.ONE_TO_MANY,
            evidence=("ev-topology-b",),
            layer=GraphLayer.PLAN,
            observed=(1, 3),
        ),
        relation(
            "workflow",
            "C",
            RelationType.CONTAINS,
            Cardinality.ONE_TO_MANY,
            evidence=("ev-topology-c",),
            layer=GraphLayer.PLAN,
            observed=(1, 3),
        ),
        relation(
            "B",
            "A",
            RelationType.DEPENDS_ON,
            Cardinality.ONE_TO_ONE,
            evidence=("ev-dep-ab",),
            layer=GraphLayer.EXECUTION_DEPENDENCY,
        ),
        relation(
            "C",
            "B",
            RelationType.DEPENDS_ON,
            Cardinality.ONE_TO_ONE,
            evidence=("ev-dep-bc",),
            layer=GraphLayer.EXECUTION_DEPENDENCY,
        ),
        relation(
            "A",
            "definition",
            RelationType.ASSIGNED_TO,
            Cardinality.MANY_TO_ONE,
            evidence=("ev-assign-a",),
            observed=(3, 1),
            visibility=ProjectionVisibility.TECHNICAL,
        ),
        relation(
            "B",
            "definition",
            RelationType.ASSIGNED_TO,
            Cardinality.MANY_TO_ONE,
            evidence=("ev-assign-b",),
            observed=(3, 1),
            visibility=ProjectionVisibility.TECHNICAL,
        ),
        relation(
            "C",
            "definition",
            RelationType.ASSIGNED_TO,
            Cardinality.MANY_TO_ONE,
            evidence=("ev-assign-c",),
            observed=(3, 1),
            visibility=ProjectionVisibility.TECHNICAL,
        ),
        relation(
            "definition",
            "instance",
            RelationType.CONTAINS,
            Cardinality.ONE_TO_MANY,
            evidence=("ev-instance",),
            visibility=ProjectionVisibility.DETAIL_ONLY,
        ),
        relation(
            "instance",
            "runtime",
            RelationType.EXECUTED_BY,
            Cardinality.MANY_TO_ONE,
            evidence=("ev-runtime-binding",),
            visibility=ProjectionVisibility.TECHNICAL,
        ),
        relation(
            "C",
            "outcome",
            RelationType.PRODUCES,
            Cardinality.ONE_TO_ONE,
            evidence=("ev-outcome",),
            layer=GraphLayer.DATA_EVIDENCE,
            visibility=ProjectionVisibility.TECHNICAL,
        ),
        relation(
            "plan",
            "workflow",
            RelationType.TRIGGERS,
            Cardinality.ONE_TO_ONE,
            evidence=("ev-plan-revision",),
            layer=GraphLayer.PLAN,
        ),
    ]
    return build_graph(CONTEXT, nodes, relations)


def parallel_fixture():
    nodes = [
        node(name, NodeType.WORKFLOW if name == "workflow" else NodeType.TASK)
        for name in ("workflow", "A", "B", "C", "D")
    ]
    nodes += [
        node(
            "definition",
            NodeType.DEFINITION,
            visibility=ProjectionVisibility.TECHNICAL,
        ),
        node(
            "instance",
            NodeType.INSTANCE,
            visibility=ProjectionVisibility.TECHNICAL,
        ),
        node("outcome", NodeType.OUTCOME),
    ]
    relations = [
        relation(
            "workflow",
            name,
            RelationType.CONTAINS,
            Cardinality.ONE_TO_MANY,
            evidence=(f"ev-topology-{name.lower()}",),
            layer=GraphLayer.PLAN,
            observed=(1, 4),
        )
        for name in ("A", "B", "C", "D")
    ]
    relations += [
        relation(
            "B",
            "A",
            RelationType.DEPENDS_ON,
            Cardinality.MANY_TO_ONE,
            evidence=("ev-dep-ba",),
            layer=GraphLayer.EXECUTION_DEPENDENCY,
            observed=(2, 1),
        ),
        relation(
            "C",
            "A",
            RelationType.DEPENDS_ON,
            Cardinality.MANY_TO_ONE,
            evidence=("ev-dep-ca",),
            layer=GraphLayer.EXECUTION_DEPENDENCY,
            observed=(2, 1),
        ),
        relation(
            "D",
            "B",
            RelationType.DEPENDS_ON,
            Cardinality.ONE_TO_MANY,
            evidence=("ev-dep-db",),
            layer=GraphLayer.EXECUTION_DEPENDENCY,
            observed=(1, 2),
            visibility=ProjectionVisibility.TECHNICAL,
        ),
        relation(
            "D",
            "C",
            RelationType.DEPENDS_ON,
            Cardinality.ONE_TO_MANY,
            evidence=("ev-dep-dc",),
            layer=GraphLayer.EXECUTION_DEPENDENCY,
            observed=(1, 2),
            visibility=ProjectionVisibility.TECHNICAL,
        ),
        relation(
            "A",
            "instance",
            RelationType.ASSIGNED_TO,
            Cardinality.MANY_TO_ONE,
            evidence=("ev-assignment-a",),
            observed=(2, 1),
            visibility=ProjectionVisibility.TECHNICAL,
        ),
        relation(
            "D",
            "instance",
            RelationType.ASSIGNED_TO,
            Cardinality.MANY_TO_ONE,
            evidence=("ev-assignment-d",),
            observed=(2, 1),
            visibility=ProjectionVisibility.TECHNICAL,
        ),
        relation(
            "D",
            "outcome",
            RelationType.PRODUCES,
            Cardinality.ONE_TO_ONE,
            evidence=("ev-outcome",),
            layer=GraphLayer.DATA_EVIDENCE,
            visibility=ProjectionVisibility.TECHNICAL,
        ),
    ]
    return build_graph(CONTEXT, nodes, relations)


def definition_instances_fixture(count: int = 3):
    names = [
        f"I{index}" if count == 3 else f"I{index:02d}" for index in range(1, count + 1)
    ]
    nodes = [node("definition", NodeType.DEFINITION)]
    if count == 3:
        nodes.append(
            node(
                "runtime",
                NodeType.RUNTIME_REALIZATION,
                visibility=ProjectionVisibility.TECHNICAL,
            )
        )
    nodes += [
        node(
            name,
            NodeType.INSTANCE,
            evidence=(
                f"ev-select-i{index}" if count == 3 else f"ev-instance-{index:02d}",
            ),
            group_kind=GroupKind.DEFINITION_INSTANCES,
            group_parent_id="definition",
        )
        for index, name in enumerate(names, 1)
    ]
    relations = []
    for index, name in enumerate(names, 1):
        relations.append(
            relation(
                "definition",
                name,
                RelationType.CONTAINS,
                Cardinality.ONE_TO_MANY,
                evidence=(
                    f"ev-select-i{index}" if count == 3 else f"ev-instance-{index:02d}",
                ),
                observed=(1, count),
            )
        )
        relations.append(
            relation(
                name,
                "definition",
                RelationType.REFERENCES,
                Cardinality.MANY_TO_ONE,
                evidence=(
                    f"ev-select-i{index}" if count == 3 else f"ev-instance-{index:02d}",
                ),
                observed=(count, 1),
                visibility=ProjectionVisibility.TECHNICAL,
            )
        )
    if count == 3:
        relations.append(
            relation(
                names[0],
                "runtime",
                RelationType.EXECUTED_BY,
                Cardinality.MANY_TO_ONE,
                evidence=("ev-runtime-binding",),
                visibility=ProjectionVisibility.TECHNICAL,
            )
        )
    return build_graph(CONTEXT, nodes, relations)


def assignment_fixture():
    nodes = [node(name) for name in ("T1", "T2", "T3")] + [
        node("I1", NodeType.INSTANCE)
    ]
    relations = [
        relation(
            name,
            "I1",
            RelationType.ASSIGNED_TO,
            Cardinality.MANY_TO_ONE,
            evidence=(f"ev-assignment-{name.lower()}",),
            observed=(3, 1),
        )
        for name in ("T1", "T2", "T3")
    ]
    return build_graph(CONTEXT, nodes, relations)


def shared_evidence_fixture():
    nodes = [
        node(
            name,
            NodeType.TASK
            if name.startswith("T")
            else NodeType.CAPABILITY
            if name.startswith("C")
            else NodeType.KNOWLEDGE,
            visibility=ProjectionVisibility.TECHNICAL
            if name.startswith("K")
            else ProjectionVisibility.BOTH,
        )
        for name in ("T1", "T2", "C1", "C2", "K1", "K2")
    ]
    relations = []
    for task in ("T1", "T2"):
        for capability in ("C1", "C2"):
            relations.append(
                relation(
                    task,
                    capability,
                    RelationType.REQUESTS,
                    Cardinality.MANY_TO_MANY,
                    evidence=(f"ev-cap-{task.lower()}-{capability.lower()}",),
                    observed=(2, 2),
                )
            )
        for knowledge in ("K1", "K2"):
            relations.append(
                relation(
                    task,
                    knowledge,
                    RelationType.REFERENCES,
                    Cardinality.MANY_TO_MANY,
                    evidence=(f"ev-knowledge-{task.lower()}-{knowledge.lower()}",),
                    layer=GraphLayer.DATA_EVIDENCE,
                    observed=(2, 2),
                    visibility=ProjectionVisibility.TECHNICAL,
                )
            )
    return build_graph(CONTEXT, nodes, relations)


def same_pair_fixture():
    nodes = [node("A"), node("B")]
    relations = [
        relation(
            "A",
            "B",
            RelationType.DEPENDS_ON,
            Cardinality.ONE_TO_ONE,
            evidence=("ev-dependency",),
            aggregation_key="f06-g01",
        ),
        relation(
            "A",
            "B",
            RelationType.DATA_FLOW,
            Cardinality.ONE_TO_MANY,
            evidence=("ev-data",),
            layer=GraphLayer.DATA_EVIDENCE,
            aggregation_key="f06-g01",
        ),
        relation(
            "A",
            "B",
            RelationType.TRIGGERS,
            Cardinality.MANY_TO_MANY,
            evidence=("ev-trigger",),
            aggregation_key="f06-g01",
        ),
    ]
    return build_graph(CONTEXT, nodes, relations)


def denied_fixture():
    nodes = [
        node("task"),
        node("capability", NodeType.CAPABILITY),
        node("approval", NodeType.APPROVAL, phase=Phase.DENIED),
        node("outcome", NodeType.OUTCOME, phase=Phase.DENIED),
    ]
    relations = [
        relation(
            "task",
            "capability",
            RelationType.REQUESTS,
            Cardinality.MANY_TO_MANY,
            evidence=("ev-request",),
        ),
        relation(
            "capability",
            "approval",
            RelationType.AUTHORIZED_BY,
            Cardinality.MANY_TO_ONE,
            evidence=("ev-deny",),
            layer=GraphLayer.APPROVAL_DECISION,
            state=Phase.DENIED,
            visibility=ProjectionVisibility.TECHNICAL,
        ),
        relation(
            "approval",
            "task",
            RelationType.BLOCKS,
            Cardinality.ONE_TO_MANY,
            evidence=("ev-deny",),
            layer=GraphLayer.APPROVAL_DECISION,
            state=Phase.BLOCKED,
            blocking_class="AUTHORIZATION",
        ),
        relation(
            "task",
            "outcome",
            RelationType.PRODUCES,
            Cardinality.ONE_TO_ONE,
            evidence=("ev-deny",),
            layer=GraphLayer.DATA_EVIDENCE,
            state=Phase.DENIED,
        ),
    ]
    return build_graph(
        CONTEXT,
        nodes,
        relations,
        effects=ProjectionEffects(AuthorizationDecision.DENY, 0),
    )


def approval_fixture():
    nodes = [
        node("plan", NodeType.PLAN),
        node("approval", NodeType.APPROVAL),
        node("task"),
    ]
    relations = [
        relation(
            "plan",
            "approval",
            RelationType.REQUESTS,
            Cardinality.ONE_TO_MANY,
            evidence=("ev-plan-revision",),
            layer=GraphLayer.APPROVAL_DECISION,
            authorization_class="HUMAN_APPROVAL_REQUEST",
        ),
        relation(
            "approval",
            "task",
            RelationType.BLOCKS,
            Cardinality.ONE_TO_MANY,
            evidence=("ev-decided-at",),
            layer=GraphLayer.APPROVAL_DECISION,
            blocking_class="HUMAN_APPROVAL",
        ),
        relation(
            "plan",
            "approval",
            RelationType.APPROVED_BY,
            Cardinality.ONE_TO_ONE,
            evidence=("ev-actor", "ev-decided-at", "ev-plan-revision"),
            layer=GraphLayer.APPROVAL_DECISION,
            authorization_class="HUMAN_APPROVAL_DECISION",
        ),
    ]
    return build_graph(CONTEXT, nodes, relations)


def failure_fixture():
    nodes = [
        node("workflow", NodeType.WORKFLOW),
        node("A", phase=Phase.FAILED),
        node("B", phase=Phase.SKIPPED),
        node("outcome", NodeType.OUTCOME, phase=Phase.FAILED),
    ]
    relations = [
        relation(
            "workflow",
            "A",
            RelationType.CONTAINS,
            Cardinality.ONE_TO_MANY,
            evidence=("ev-topology-a",),
            layer=GraphLayer.PLAN,
            observed=(1, 2),
        ),
        relation(
            "workflow",
            "B",
            RelationType.CONTAINS,
            Cardinality.ONE_TO_MANY,
            evidence=("ev-topology-b",),
            layer=GraphLayer.PLAN,
            observed=(1, 2),
        ),
        relation(
            "B",
            "A",
            RelationType.DEPENDS_ON,
            Cardinality.ONE_TO_MANY,
            evidence=("ev-skip-b",),
            layer=GraphLayer.EXECUTION_DEPENDENCY,
        ),
        relation(
            "A",
            "B",
            RelationType.BLOCKS,
            Cardinality.ONE_TO_MANY,
            evidence=("ev-failure-a", "ev-skip-b"),
            state=Phase.BLOCKED,
            blocking_class="FAILURE",
            path_class=PathClass.FAILURE,
        ),
        relation(
            "A",
            "outcome",
            RelationType.PRODUCES,
            Cardinality.ONE_TO_ONE,
            evidence=("ev-failure-a",),
            layer=GraphLayer.DATA_EVIDENCE,
            state=Phase.FAILED,
            path_class=PathClass.FAILURE,
        ),
    ]
    return build_graph(CONTEXT, nodes, relations)


def unknown_fixture():
    return build_graph(
        CONTEXT,
        [
            node("task"),
            node(
                "runtime",
                NodeType.RUNTIME_REALIZATION,
                visibility=ProjectionVisibility.TECHNICAL,
            ),
            node("outcome", NodeType.OUTCOME, phase=Phase.UNKNOWN),
        ],
        [
            relation(
                "task",
                "runtime",
                RelationType.EXECUTED_BY,
                Cardinality.MANY_TO_ONE,
                evidence=("ev-runtime-binding",),
                visibility=ProjectionVisibility.TECHNICAL,
            ),
            relation(
                "task",
                "outcome",
                RelationType.PRODUCES,
                Cardinality.ONE_TO_ONE,
                evidence=("ev-ambiguous-effect",),
                layer=GraphLayer.DATA_EVIDENCE,
                state=Phase.UNKNOWN,
            ),
        ],
    )


def all_fixtures():
    serial = serial_fixture()
    return [
        serial,
        parallel_fixture(),
        definition_instances_fixture(),
        assignment_fixture(),
        shared_evidence_fixture(),
        same_pair_fixture(),
        denied_fixture(),
        approval_fixture(),
        failure_fixture(),
        unknown_fixture(),
        definition_instances_fixture(12),
        serial,
    ]


def test_all_twelve_fixtures_have_the_complete_cardinality_contract() -> None:
    fixtures = all_fixtures()
    assert [len(item.nodes) for item in fixtures] == [
        10,
        8,
        5,
        4,
        6,
        2,
        4,
        3,
        4,
        3,
        13,
        10,
    ]
    assert [len(item.relations) for item in fixtures] == [
        13,
        11,
        7,
        3,
        8,
        3,
        4,
        3,
        5,
        2,
        24,
        13,
    ]
    assert sum(len(item.relations) for item in fixtures) == 96
    assert {
        relation.declared_cardinality
        for graph in fixtures
        for relation in graph.relations
    } == set(Cardinality)
    assert fixtures[0].graph_snapshot_id == fixtures[11].graph_snapshot_id
    assert len({item.graph_snapshot_id for item in fixtures[:11]}) == 11
    assert tuple(item.relation_id for item in fixtures[0].relations) == tuple(
        item.relation_id for item in fixtures[11].relations
    )


def _initial_entities(view) -> frozenset[str]:
    return frozenset(item.entity_id for item in view.nodes)


def test_all_twelve_fixtures_match_the_complete_view_visibility_contract() -> None:
    fixtures = all_fixtures()
    product = [product_graph_view(item) for item in fixtures]
    technical = [technical_graph_view(item) for item in fixtures]

    expected_product_entities = [
        {"problem", "plan", "workflow", "A", "B", "C", "outcome"},
        {"workflow", "A", "B", "C", "D", "outcome"},
        {"definition", "I1", "I2", "I3"},
        {"T1", "T2", "T3", "I1"},
        {"T1", "T2", "C1", "C2"},
        {"A", "B"},
        {"task", "capability", "approval", "outcome"},
        {"plan", "approval", "task"},
        {"workflow", "A", "B", "outcome"},
        {"task", "outcome"},
        {"definition"},
        {"problem", "plan", "workflow", "A", "B", "C", "outcome"},
    ]
    expected_technical_entities = [
        {
            "plan",
            "workflow",
            "A",
            "B",
            "C",
            "definition",
            "instance",
            "runtime",
            "outcome",
        },
        {"workflow", "A", "B", "C", "D", "definition", "instance", "outcome"},
        {"definition", "I1", "I2", "I3", "runtime"},
        {"T1", "T2", "T3", "I1"},
        {"T1", "T2", "C1", "C2", "K1", "K2"},
        {"A", "B"},
        {"task", "capability", "approval", "outcome"},
        {"plan", "approval", "task"},
        {"workflow", "A", "B", "outcome"},
        {"task", "runtime", "outcome"},
        {"definition"},
        {
            "plan",
            "workflow",
            "A",
            "B",
            "C",
            "definition",
            "instance",
            "runtime",
            "outcome",
        },
    ]
    assert [_initial_entities(item) for item in product] == [
        frozenset(item) for item in expected_product_entities
    ]
    assert [_initial_entities(item) for item in technical] == [
        frozenset(item) for item in expected_technical_entities
    ]
    assert [len(item.nodes) + len(item.groups) for item in product] == [
        7,
        6,
        4,
        4,
        4,
        2,
        4,
        3,
        4,
        2,
        2,
        7,
    ]
    assert [len(item.nodes) + len(item.groups) for item in technical] == [
        9,
        8,
        5,
        4,
        6,
        2,
        4,
        3,
        4,
        3,
        2,
        9,
    ]
    assert [len(item.raw_relations) for item in product] == [
        7,
        6,
        3,
        3,
        4,
        3,
        3,
        3,
        5,
        1,
        12,
        7,
    ]
    assert [len(item.raw_relations) for item in technical] == [
        11,
        11,
        7,
        3,
        8,
        3,
        4,
        3,
        5,
        2,
        24,
        11,
    ]
    assert [len(item.edges) for item in product] == [7, 6, 3, 3, 4, 1, 3, 3, 5, 1, 1, 7]
    assert [len(item.edges) for item in technical] == [
        11,
        11,
        7,
        3,
        8,
        1,
        4,
        3,
        5,
        2,
        2,
        11,
    ]
    assert [len(item.groups) for item in product] == [0] * 10 + [1, 0]
    assert [len(item.groups) for item in technical] == [0] * 10 + [1, 0]
    for views in (product, technical):
        group = views[10].groups[0]
        graph = fixtures[10]
        entity_by_id = {item.node_id: item.entity_id for item in graph.nodes}
        assert tuple(entity_by_id[item] for item in group.member_node_ids) == tuple(
            f"I{index:02d}" for index in range(1, 13)
        )


def test_fixture_input_permutation_is_byte_stable() -> None:
    graph = parallel_fixture()
    node_specs = [
        NodeSpec(
            node_type=item.node_type,
            entity_id=item.entity_id,
            label_key=item.label_key,
            phase=item.phase,
            progress=item.progress,
            execution_identity=item.execution_identity,
            summary=item.summary,
            evidence_ids=item.evidence_ids,
            limitation_codes=item.limitation_codes,
            visibility=item.visibility,
            group_kind=item.group_kind,
            group_parent_id=item.group_parent_id,
        )
        for item in reversed(graph.nodes)
    ]
    by_id = {item.node_id: item.entity_id for item in graph.nodes}
    relation_specs = [
        RelationSpec(
            source_entity_id=by_id[item.source_node_id],
            target_entity_id=by_id[item.target_node_id],
            relation_types=item.relation_types,
            layer=item.layer,
            declared_cardinality=item.declared_cardinality,
            state=item.state,
            evidence_ids=item.evidence_ids,
            display_priority=item.display_priority,
            projection_visibility=item.projection_visibility,
            semantic_discriminator=item.semantic_discriminator,
            path_class=item.path_class,
            blocking_class=item.blocking_class,
            authorization_class=item.authorization_class,
            evidence_authority_class=item.evidence_authority_class,
            execution_or_historical_context=item.execution_or_historical_context,
            tenant_or_security_domain=item.tenant_or_security_domain,
            aggregation_key=item.aggregation_key,
            observed_source_count=item.observed_source_count,
            observed_target_count=item.observed_target_count,
        )
        for item in reversed(graph.relations)
    ]
    rebuilt = build_graph(CONTEXT, node_specs, relation_specs)
    assert graph.graph_snapshot_id == rebuilt.graph_snapshot_id
    assert [item.node_id for item in graph.nodes] == [
        item.node_id for item in rebuilt.nodes
    ]
    assert [item.relation_id for item in graph.relations] == [
        item.relation_id for item in rebuilt.relations
    ]


def test_snapshot_identity_changes_with_authoritative_graph_or_effect_facts() -> None:
    original = denied_fixture()
    changed_relation = relation(
        "task",
        "capability",
        RelationType.REQUESTS,
        Cardinality.MANY_TO_MANY,
        evidence=("ev-request-changed",),
    )
    changed_graph = build_graph(
        CONTEXT,
        [node("task"), node("capability", NodeType.CAPABILITY)],
        [changed_relation],
    )
    original_subset = build_graph(
        CONTEXT,
        [node("task"), node("capability", NodeType.CAPABILITY)],
        [
            relation(
                "task",
                "capability",
                RelationType.REQUESTS,
                Cardinality.MANY_TO_MANY,
                evidence=("ev-request",),
            )
        ],
    )
    assert changed_graph.graph_snapshot_id != original_subset.graph_snapshot_id
    allowed = build_graph(
        CONTEXT,
        [
            node("task"),
            node(
                "capability",
                NodeType.CAPABILITY,
                evidence=("ev-citation",),
            ),
        ],
        [
            relation(
                "task",
                "capability",
                RelationType.REQUESTS,
                Cardinality.MANY_TO_MANY,
                evidence=("ev-request",),
            )
        ],
        effects=ProjectionEffects(AuthorizationDecision.ALLOW, 1, ("ev-citation",)),
    )
    assert allowed.graph_snapshot_id != original_subset.graph_snapshot_id
    assert original.graph_snapshot_id != allowed.graph_snapshot_id


def test_only_execution_dependency_cycles_fail_closed() -> None:
    nodes = [node("A"), node("B")]
    cycle = [
        relation(
            "A",
            "B",
            RelationType.DEPENDS_ON,
            Cardinality.ONE_TO_ONE,
            evidence=("ev-ab",),
            layer=GraphLayer.EXECUTION_DEPENDENCY,
        ),
        relation(
            "B",
            "A",
            RelationType.DEPENDS_ON,
            Cardinality.ONE_TO_ONE,
            evidence=("ev-ba",),
            layer=GraphLayer.EXECUTION_DEPENDENCY,
        ),
    ]
    with pytest.raises(GraphProjectionError, match="EXECUTION_DEPENDENCY_CYCLE"):
        build_graph(CONTEXT, nodes, cycle)
    general = [
        replace(
            item,
            layer=GraphLayer.DATA_EVIDENCE,
            relation_types=(RelationType.REFERENCES,),
        )
        for item in cycle
    ]
    assert len(build_graph(CONTEXT, nodes, general).relations) == 2


def test_same_pair_aggregation_preserves_raw_semantics_and_cardinalities() -> None:
    graph = same_pair_fixture()
    view = technical_graph_view(graph)
    assert len(view.edges) == 1
    edge = view.edges[0]
    assert edge.primary_type == RelationType.DEPENDS_ON
    assert edge.secondary_types == (RelationType.TRIGGERS, RelationType.DATA_FLOW)
    assert set(edge.cardinalities) == set(Cardinality) - {Cardinality.MANY_TO_ONE}
    assert len(edge.raw_relation_ids) == 3
    assert edge.evidence_ids == ("ev-data", "ev-dependency", "ev-trigger")


def test_aggregation_key_is_metadata_not_a_gp06_safety_discriminator() -> None:
    graph = build_graph(
        CONTEXT,
        [node("A"), node("B")],
        [
            relation(
                "A",
                "B",
                RelationType.DEPENDS_ON,
                Cardinality.ONE_TO_ONE,
                evidence=("ev-dependency",),
                aggregation_key="fixture-handle-a",
            ),
            relation(
                "A",
                "B",
                RelationType.DATA_FLOW,
                Cardinality.ONE_TO_MANY,
                evidence=("ev-data",),
                aggregation_key="fixture-handle-b",
            ),
            relation(
                "A",
                "B",
                RelationType.TRIGGERS,
                Cardinality.MANY_TO_MANY,
                evidence=("ev-trigger",),
            ),
        ],
    )
    edge = technical_graph_view(graph).edges[0]
    assert len(technical_graph_view(graph).edges) == 1
    assert len(edge.raw_relation_ids) == 3


def test_safety_discriminators_prevent_unsafe_merges() -> None:
    graph = same_pair_fixture()
    by_id = {item.node_id: item.entity_id for item in graph.nodes}
    specs = []
    for index, item in enumerate(graph.relations):
        specs.append(
            RelationSpec(
                source_entity_id=by_id[item.source_node_id],
                target_entity_id=by_id[item.target_node_id],
                relation_types=item.relation_types,
                layer=item.layer,
                declared_cardinality=item.declared_cardinality,
                evidence_ids=item.evidence_ids,
                semantic_discriminator=item.semantic_discriminator,
                aggregation_key=item.aggregation_key,
                evidence_authority_class="OTHER" if index == 0 else "UPSTREAM",
                tenant_or_security_domain=CONTEXT.security_domain,
            )
        )
    split = build_graph(CONTEXT, [node("A"), node("B")], specs)
    assert len(technical_graph_view(split).edges) == 2


def test_product_and_technical_views_consume_identical_raw_ids() -> None:
    graph = approval_fixture()
    product = product_graph_view(graph)
    technical = technical_graph_view(graph)
    assert product.graph_snapshot_id == technical.graph_snapshot_id
    assert {item.relation_id for item in product.raw_relations} == {
        item.relation_id for item in technical.raw_relations
    }
    blocks = next(
        item for item in graph.relations if RelationType.BLOCKS in item.relation_types
    )
    entities = {item.node_id: item.entity_id for item in graph.nodes}
    assert (entities[blocks.source_node_id], entities[blocks.target_node_id]) == (
        "approval",
        "task",
    )


def test_grouping_is_presentation_only_and_expansion_restores_members() -> None:
    graph = definition_instances_fixture(12)
    collapsed = technical_graph_view(graph)
    assert len(collapsed.groups) == 1
    group = collapsed.groups[0]
    assert group.member_count == 12
    assert group.evidence_ids == tuple(
        f"ev-instance-{index:02d}" for index in range(1, 13)
    )
    assert len(collapsed.raw_relations) == 24
    expanded = technical_graph_view(graph, expanded_group_ids=(group.group_id,))
    assert expanded.groups == ()
    assert len(expanded.nodes) == 13
    assert len(expanded.edges) == 24
    assert [item.relation_id for item in collapsed.raw_relations] == [
        item.relation_id for item in expanded.raw_relations
    ]


def test_unknown_and_distinct_failure_skip_states_are_preserved() -> None:
    unknown = unknown_fixture()
    assert (
        next(item for item in unknown.nodes if item.entity_id == "outcome").phase
        == Phase.UNKNOWN
    )
    failure = failure_fixture()
    phases = {item.entity_id: item.phase for item in failure.nodes}
    assert phases["A"] == Phase.FAILED
    assert phases["B"] == Phase.SKIPPED
    assert len(technical_graph_view(failure).edges) == 5


def test_security_and_denial_effect_evidence_fail_closed() -> None:
    mismatched = replace(
        relation(
            "A",
            "B",
            RelationType.REFERENCES,
            Cardinality.ONE_TO_ONE,
            evidence=("ev",),
        ),
        tenant_or_security_domain="tenant-b",
    )
    with pytest.raises(GraphProjectionError, match="SECURITY_DOMAIN_INPUT_MISMATCH"):
        build_graph(CONTEXT, [node("A"), node("B")], [mismatched])
    with pytest.raises(
        GraphProjectionError, match="DENY_REQUIRES_ZERO_PROVIDER_EFFECTS"
    ):
        ProjectionEffects(AuthorizationDecision.DENY, 1)
    with pytest.raises(
        GraphProjectionError, match="DENY_REQUIRES_ZERO_PROVIDER_EFFECTS"
    ):
        ProjectionEffects(AuthorizationDecision.DENY, 0, ("ev-citation",))
    with pytest.raises(
        GraphProjectionError, match="ALLOW_REQUIRES_PROVIDER_CALL_EVIDENCE"
    ):
        ProjectionEffects(AuthorizationDecision.ALLOW, 0)

    authorization = relation(
        "capability",
        "approval",
        RelationType.AUTHORIZED_BY,
        Cardinality.MANY_TO_ONE,
        evidence=("ev-decision",),
        layer=GraphLayer.APPROVAL_DECISION,
    )
    authorization_nodes = [
        node("capability", NodeType.CAPABILITY),
        node("approval", NodeType.APPROVAL),
    ]
    with pytest.raises(
        GraphProjectionError, match="CAPABILITY_EFFECT_EVIDENCE_REQUIRED"
    ):
        build_graph(CONTEXT, authorization_nodes, [authorization])
    with pytest.raises(GraphProjectionError, match="CITATION_EVIDENCE_NOT_IN_GRAPH"):
        build_graph(
            CONTEXT,
            authorization_nodes,
            [authorization],
            effects=ProjectionEffects(
                AuthorizationDecision.ALLOW,
                1,
                ("ev-missing-citation",),
            ),
        )


@pytest.mark.parametrize(
    ("spec_factory", "code"),
    [
        (
            lambda: relation(
                "A",
                "missing",
                RelationType.REFERENCES,
                Cardinality.ONE_TO_ONE,
                evidence=("ev",),
            ),
            "UNKNOWN_RELATION_ENDPOINT",
        ),
        (
            lambda: relation(
                "A", "B", RelationType.BLOCKS, Cardinality.ONE_TO_ONE, evidence=("ev",)
            ),
            "BLOCKS_REQUIRES_BLOCKING_CLASS",
        ),
        (
            lambda: relation(
                "A",
                "B",
                RelationType.COMPENSATES,
                Cardinality.ONE_TO_ONE,
                evidence=("ev",),
            ),
            "COMPENSATES_REQUIRES_COMPENSATION_PATH",
        ),
    ],
)
def test_malformed_or_unsafe_evidence_fails_closed(spec_factory, code) -> None:
    with pytest.raises(GraphProjectionError, match=code):
        build_graph(CONTEXT, [node("A"), node("B")], [spec_factory()])
