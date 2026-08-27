import type { ProductFixture, SharedExecutionSnapshot, TechnicalProjection } from "./executionSnapshotTypes.ts";

function clone<T>(value: T): T {
  return structuredClone(value);
}

function assertSharedSnapshot(source: SharedExecutionSnapshot): void {
  if (source?.snapshotKind !== "BOUNDED_SYNTHETIC_FRONTEND_SNAPSHOT") throw new Error("SHARED_SNAPSHOT_REQUIRED");
  const required = ["DETERMINISTIC", "SYNTHETIC", "NON_AUTHORITATIVE", "TECHNICAL_PREVIEW", "NO_NETWORK", "NO_RUNTIME_OR_PROVIDER_INVOCATION"];
  if (required.some((label, index) => source.classification[index] !== label)) throw new Error("SHARED_SNAPSHOT_CLASSIFICATION_INVALID");
  if (!source.selectedContext.executionId.startsWith("pei-") || !source.selectedContext.graphSnapshotId.startsWith("gps:v0.2-candidate:")) throw new Error("SHARED_IDENTITY_INVALID");
  const nodes = new Set(source.nodes.map((node) => node.id));
  if (nodes.size !== source.nodes.length) throw new Error("DUPLICATE_SHARED_NODE");
  for (const edge of source.edges) {
    if (!nodes.has(edge.source) || !nodes.has(edge.target) || edge.rawRelations.length === 0) throw new Error("INVALID_SHARED_EDGE");
    for (const relation of edge.rawRelations) {
      if (relation.source !== edge.source || relation.target !== edge.target || relation.direction !== "SOURCE_TO_TARGET" || relation.evidenceIds.length === 0) throw new Error("INVALID_SHARED_RELATION");
    }
  }
  if (source.authorization.decision === "DENY" && (source.authorization.providerCallCount !== 0 || source.citations.length !== 0)) throw new Error("DENY_REQUIRES_ZERO_PROVIDER_EFFECTS");
  if (source.recovery.exactlyOnce !== false) throw new Error("EXACTLY_ONCE_CLAIM_PROHIBITED");
}

function visible(value: "PRODUCT" | "TECHNICAL" | "BOTH" | "DETAIL_ONLY", context: "PRODUCT" | "TECHNICAL") {
  return value === "BOTH" || value === context || (context === "TECHNICAL" && value === "DETAIL_ONLY");
}

export function projectProductSnapshot(source: SharedExecutionSnapshot): ProductFixture {
  assertSharedSnapshot(source);
  const visibleNodes = source.nodes.filter((node) => visible(node.visibility, "PRODUCT"));
  const nodeIds = new Set(visibleNodes.map((node) => node.id));
  return clone({
    classification: ["DETERMINISTIC", "SYNTHETIC", "NON_AUTHORITATIVE", "TECHNICAL_PREVIEW"] as const,
    platformExecutionIdentity: source.selectedContext.executionId,
    graphSnapshotId: source.selectedContext.graphSnapshotId,
    projectionContext: "PRODUCT" as const,
    securityFiltered: true as const,
    questionKey: source.questionKey,
    questions: source.questions,
    planRevision: source.selectedContext.revisionId,
    correctionRevision: source.correctionRevision,
    workflowId: source.selectedContext.workflowId,
    taskKeys: source.taskKeys,
    employees: source.employees,
    nodes: visibleNodes.map(({ id, type, labelKey, phase }) => ({ id, type, labelKey, phase })),
    edges: source.edges.flatMap((edge) => {
      const rawRelations = edge.rawRelations.filter((relation) => visible(relation.visibility, "PRODUCT"));
      return nodeIds.has(edge.source) && nodeIds.has(edge.target) && rawRelations.length
        ? [{ id: edge.id, source: edge.source, target: edge.target, rawRelations: rawRelations.map(({ id, type, direction, cardinality, evidenceIds }) => ({ id, type, direction, cardinality, evidenceIds })) }]
        : [];
    }),
    groups: source.groups,
    approval: source.approval,
    outcome: { status: source.outcome.status, summaryKey: source.outcome.summaryKey, evidenceIds: source.outcome.evidenceIds },
    citations: source.citations.map(({ evidenceId, assetId, revisionId, labelKey }) => ({ evidenceId, assetId, revisionId, labelKey })),
    capability: { decision: source.authorization.decision, reasonCode: source.authorization.reasonCode, providerCallCount: source.authorization.providerCallCount },
  });
}

export function projectTechnicalSnapshot(source: SharedExecutionSnapshot): TechnicalProjection {
  assertSharedSnapshot(source);
  const nodes = source.nodes.filter((node) => visible(node.visibility, "TECHNICAL"));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = source.edges.flatMap((edge) => {
    const rawRelations = edge.rawRelations.filter((relation) => visible(relation.visibility, "TECHNICAL"));
    return nodeIds.has(edge.source) && nodeIds.has(edge.target) && rawRelations.length ? [{ ...edge, rawRelations }] : [];
  });
  return clone({
    classification: source.classification,
    selectedContext: source.selectedContext,
    definition: source.definition,
    instances: source.instances,
    nodes,
    edges,
    approval: source.approval,
    authorization: source.authorization,
    outcome: source.outcome,
    citations: source.citations,
    runtimeSupport: source.runtimeSupport,
    requestedRuntimeId: source.requestedRuntimeId,
    effectiveRuntimeId: source.effectiveRuntimeId,
    conditions: source.conditions,
    recovery: source.recovery,
    limitations: source.limitations,
  });
}
