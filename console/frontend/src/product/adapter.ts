import { productFixture } from "./fixture";
import type { ProductFixture } from "./types";

const REQUIRED_CLASSIFICATIONS = ["DETERMINISTIC", "SYNTHETIC", "NON_AUTHORITATIVE", "TECHNICAL_PREVIEW"];

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
  if (productFixture.capability.decision === "DENY" && productFixture.capability.providerCallCount !== 0) {
    throw new Error("DENY_REQUIRES_ZERO_PROVIDER_EFFECTS");
  }
  return productFixture;
}
