import { sharedExecutionSnapshot } from "../shared/executionSnapshotFixture";
import { projectTechnicalSnapshot } from "../shared/projections";
import type { TechnicalProjection } from "../shared/executionSnapshotTypes";

function deepFreeze<T>(value: T): Readonly<T> {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    Object.values(value).forEach((item) => deepFreeze(item));
  }
  return value;
}

export function loadTechnicalPreview(): TechnicalProjection {
  const view = projectTechnicalSnapshot(sharedExecutionSnapshot);
  if (view.selectedContext.executionId !== sharedExecutionSnapshot.selectedContext.executionId || view.selectedContext.graphSnapshotId !== sharedExecutionSnapshot.selectedContext.graphSnapshotId) throw new Error("CROSS_VIEW_IDENTITY_MISMATCH");
  if (view.authorization.decision === "DENY" && (view.authorization.providerCallCount !== 0 || view.citations.length !== 0)) throw new Error("DENY_REQUIRES_ZERO_PROVIDER_EFFECTS");
  if (view.edges.some((edge) => edge.rawRelations.some((relation) => relation.source !== edge.source || relation.target !== edge.target))) throw new Error("TECHNICAL_RELATION_RECONSTRUCTION_REJECTED");
  return deepFreeze(view) as TechnicalProjection;
}
