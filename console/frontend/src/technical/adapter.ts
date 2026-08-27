import { sharedExecutionSnapshot } from "../shared/executionSnapshotFixture.ts";
import { projectTechnicalSnapshot } from "../shared/projections.ts";
import type { SelectedExecutionContextValue, TechnicalProjection } from "../shared/executionSnapshotTypes.ts";

function deepFreeze<T>(value: T): Readonly<T> {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    Object.values(value).forEach((item) => deepFreeze(item));
  }
  return value;
}

export function loadTechnicalPreview(selection: SelectedExecutionContextValue = sharedExecutionSnapshot.selectedContext): TechnicalProjection {
  const view = projectTechnicalSnapshot(sharedExecutionSnapshot);
  const stableKeys = ["workId", "workflowId", "taskId", "executionId", "graphSnapshotId"] as const;
  const validEmployee = sharedExecutionSnapshot.employees.some((employee) => employee.id === selection.employeeId);
  const validRevision = [sharedExecutionSnapshot.selectedContext.revisionId, sharedExecutionSnapshot.correctionRevision].includes(selection.revisionId);
  if (!validEmployee || !validRevision || stableKeys.some((key) => selection[key] !== sharedExecutionSnapshot.selectedContext[key])) throw new Error("CROSS_VIEW_IDENTITY_MISMATCH");
  view.selectedContext = structuredClone(selection);
  if (view.authorization.decision === "DENY" && (view.authorization.providerCallCount !== 0 || view.citations.length !== 0)) throw new Error("DENY_REQUIRES_ZERO_PROVIDER_EFFECTS");
  if (view.edges.some((edge) => edge.rawRelations.some((relation) => relation.source !== edge.source || relation.target !== edge.target))) throw new Error("TECHNICAL_RELATION_RECONSTRUCTION_REJECTED");
  return deepFreeze(view) as TechnicalProjection;
}
