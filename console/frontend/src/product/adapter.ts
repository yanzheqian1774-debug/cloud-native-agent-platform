import { productFixture } from "./fixture";
import type { ProductFixture } from "./types";

const REQUIRED_CLASSIFICATIONS = ["DETERMINISTIC", "SYNTHETIC", "NON_AUTHORITATIVE", "TECHNICAL_PREVIEW"];
const CARDINALITIES = new Set(["ONE_TO_ONE", "ONE_TO_MANY", "MANY_TO_ONE", "MANY_TO_MANY"]);

function deepFreeze<T>(value: T): Readonly<T> {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    Object.values(value).forEach((item) => deepFreeze(item));
  }
  return value;
}

export function loadProductPreview(): ProductFixture {
  if (productFixture.classification.some((value, index) => value !== REQUIRED_CLASSIFICATIONS[index])) {
    throw new Error("PRODUCT_PREVIEW_CLASSIFICATION_INVALID");
  }
  if (!productFixture.platformExecutionIdentity.startsWith("pei-")) {
    throw new Error("PLATFORM_EXECUTION_IDENTITY_REQUIRED");
  }
  if (!productFixture.graphSnapshotId.startsWith("gps:v0.2-candidate:")) {
    throw new Error("CANONICAL_GRAPH_SNAPSHOT_REQUIRED");
  }
  if (productFixture.projectionContext !== "PRODUCT" || productFixture.securityFiltered !== true) {
    throw new Error("PRODUCT_PROJECTION_CONTEXT_REQUIRED");
  }
  const nodeIds = new Set(productFixture.nodes.map((node) => node.id));
  if (nodeIds.size !== productFixture.nodes.length) throw new Error("DUPLICATE_PRODUCT_NODE");
  for (const edge of productFixture.edges) {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target) || edge.rawRelations.length === 0) {
      throw new Error("INVALID_CANONICAL_PRODUCT_EDGE");
    }
    for (const relation of edge.rawRelations) {
      if (relation.direction !== "SOURCE_TO_TARGET" || !CARDINALITIES.has(relation.cardinality) || relation.evidenceIds.length === 0) {
        throw new Error("INVALID_RAW_RELATION_EVIDENCE");
      }
    }
  }
  const fixtureSix = productFixture.edges.find((edge) => edge.id === "aggregate.fixture-6");
  if (fixtureSix?.rawRelations.map((item) => item.type).join("/") !== "DEPENDS_ON/TRIGGERS/DATA_FLOW") {
    throw new Error("FIXTURE_6_PRESENTATION_ORDER_REQUIRED");
  }
  if (productFixture.capability.decision === "DENY" && productFixture.capability.providerCallCount !== 0) {
    throw new Error("DENY_REQUIRES_ZERO_PROVIDER_EFFECTS");
  }
  return deepFreeze(productFixture) as ProductFixture;
}
