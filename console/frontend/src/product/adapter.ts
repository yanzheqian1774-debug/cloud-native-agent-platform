import { productFixture } from "./fixture";
import type { ProductFixture } from "./types";
import type { SharedExecutionSnapshot } from "../shared/executionSnapshotTypes";
import { sharedExecutionSnapshot } from "../shared/executionSnapshotFixture";
import { projectProductSnapshot } from "../shared/projections";

const REQUIRED_CLASSIFICATIONS = ["DETERMINISTIC", "SYNTHETIC", "NON_AUTHORITATIVE", "TECHNICAL_PREVIEW"];
const CARDINALITIES = new Set(["ONE_TO_ONE", "ONE_TO_MANY", "MANY_TO_ONE", "MANY_TO_MANY"]);
let mode: "live" | "synthetic-preview" = import.meta.env.VITE_EXECUTION_PREVIEW_MODE === "live" ? "live" : "synthetic-preview";
let liveSnapshot: SharedExecutionSnapshot | null = null;
const liveProductPlaceholder: ProductFixture = {
  classification: ["LIVE", "TECHNICAL_PREVIEW"],
  platformExecutionIdentity: "pei-live-loading",
  graphSnapshotId: "gps:v0.2-candidate:live-loading",
  projectionContext: "PRODUCT",
  securityFiltered: true,
  questionKey: "live.loading",
  questions: [],
  planRevision: "live-loading",
  correctionRevision: "live-loading",
  workflowId: "live-loading",
  taskKeys: [],
  employees: [],
  nodes: [],
  edges: [],
  groups: [],
  approval: { state: "PENDING_HUMAN_REVIEW", decidedAt: null, decisionFingerprint: "live-loading" },
  outcome: { status: "UNKNOWN", summaryKey: "live.loading", evidenceIds: [] },
  citations: [],
  capability: { decision: "DENY", reasonCode: "LIVE_PREVIEW_NOT_LOADED", providerCallCount: 0 },
};

function projectLiveProduct(source: SharedExecutionSnapshot): ProductFixture {
  return {
    classification: source.classification,
    readModelState: source.readModelState,
    sharedSnapshotId: source.sharedSnapshotId,
    platformExecutionIdentity: source.selectedContext.executionId,
    graphSnapshotId: source.selectedContext.graphSnapshotId,
    projectionContext: "PRODUCT",
    securityFiltered: true,
    questionKey: source.questionKey,
    questions: source.questions,
    planRevision: source.selectedContext.revisionId,
    correctionRevision: source.correctionRevision,
    workflowId: source.selectedContext.workflowId,
    taskKeys: source.taskKeys,
    employees: source.employees,
    nodes: source.nodes.map(({ id, type, labelKey, phase }) => ({ id, type, labelKey, phase })),
    edges: source.edges.map((edge) => ({ id: edge.id, source: edge.source, target: edge.target, rawRelations: edge.rawRelations.map(({ id, type, direction, cardinality, evidenceIds }) => ({ id, type, direction, cardinality, evidenceIds })) })),
    groups: source.groups,
    approval: source.approval,
    outcome: { status: source.outcome.status, summaryKey: source.outcome.summaryKey, evidenceIds: source.outcome.evidenceIds },
    citations: source.citations.map(({ evidenceId, assetId, revisionId, labelKey }) => ({ evidenceId, assetId, revisionId, labelKey })),
    capability: { decision: source.authorization.decision, reasonCode: source.authorization.reasonCode, providerCallCount: source.authorization.providerCallCount },
  };
}

export function configureProductPreview(nextMode: typeof mode, snapshot?: SharedExecutionSnapshot): void {
  mode = nextMode;
  liveSnapshot = snapshot ?? null;
  if (nextMode === "live" && snapshot) {
    Object.assign(liveProductPlaceholder, projectLiveProduct(snapshot));
    deepFreeze(liveProductPlaceholder);
  }
}

function deepFreeze<T>(value: T): Readonly<T> {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    Object.values(value).forEach((item) => deepFreeze(item));
  }
  return value;
}

export function loadProductPreview(): ProductFixture {
  if (mode === "live" && liveSnapshot === null) return liveProductPlaceholder;
  const source = mode === "live" ? liveSnapshot! : sharedExecutionSnapshot;
  const siblingProjection = mode === "live" ? projectLiveProduct(source) : projectProductSnapshot(source);
  if (mode === "synthetic-preview" && (productFixture.platformExecutionIdentity !== siblingProjection.platformExecutionIdentity || productFixture.graphSnapshotId !== siblingProjection.graphSnapshotId)) {
    throw new Error("PRODUCT_SHARED_PROJECTION_MISMATCH");
  }
  if (mode === "synthetic-preview" && productFixture.classification.some((value, index) => value !== REQUIRED_CLASSIFICATIONS[index])) {
    throw new Error("PRODUCT_PREVIEW_CLASSIFICATION_INVALID");
  }
  const projected = mode === "live" ? siblingProjection : productFixture;
  if (!projected.platformExecutionIdentity.startsWith("pei-")) {
    throw new Error("PLATFORM_EXECUTION_IDENTITY_REQUIRED");
  }
  if (!projected.graphSnapshotId.startsWith("gps:v0.2-candidate:")) {
    throw new Error("CANONICAL_GRAPH_SNAPSHOT_REQUIRED");
  }
  if (projected.projectionContext !== "PRODUCT" || projected.securityFiltered !== true) {
    throw new Error("PRODUCT_PROJECTION_CONTEXT_REQUIRED");
  }
  const nodeIds = new Set(projected.nodes.map((node) => node.id));
  if (nodeIds.size !== projected.nodes.length) throw new Error("DUPLICATE_PRODUCT_NODE");
  for (const edge of projected.edges) {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target) || edge.rawRelations.length === 0) {
      throw new Error("INVALID_CANONICAL_PRODUCT_EDGE");
    }
    for (const relation of edge.rawRelations) {
      if (relation.direction !== "SOURCE_TO_TARGET" || !CARDINALITIES.has(relation.cardinality) || relation.evidenceIds.length === 0) {
        throw new Error("INVALID_RAW_RELATION_EVIDENCE");
      }
    }
  }
  const fixtureSix = projected.edges.find((edge) => edge.id === "aggregate.fixture-6");
  if (mode === "synthetic-preview" && fixtureSix?.rawRelations.map((item) => item.type).join("/") !== "DEPENDS_ON/TRIGGERS/DATA_FLOW") {
    throw new Error("FIXTURE_6_PRESENTATION_ORDER_REQUIRED");
  }
  if (projected.capability.decision === "DENY" && projected.capability.providerCallCount !== 0) {
    throw new Error("DENY_REQUIRES_ZERO_PROVIDER_EFFECTS");
  }
  if (mode === "synthetic-preview") {
    return deepFreeze(productFixture) as ProductFixture;
  }
  return deepFreeze(projected) as ProductFixture;
}
