import { sharedExecutionSnapshot } from "../shared/executionSnapshotFixture.ts";
import { projectTechnicalSnapshot } from "../shared/projections.ts";
import type { SelectedExecutionContextValue, SharedExecutionSnapshot, TechnicalProjection } from "../shared/executionSnapshotTypes.ts";
import type { AuthorizedReferenceProjection, CanonicalRelation } from "../shared/executionSnapshotTypes.ts";

let mode: "live" | "synthetic-preview" = "synthetic-preview";
let liveSnapshot: SharedExecutionSnapshot | null = null;

export function configureTechnicalPreview(nextMode: typeof mode, snapshot?: SharedExecutionSnapshot): void {
  mode = nextMode;
  liveSnapshot = snapshot ?? null;
}

export function loadLiveTechnicalPreview(): {
  selectedContext: SelectedExecutionContextValue;
  sharedSnapshotId: string;
  canonicalRelations: readonly CanonicalRelation[];
  evidenceReferences: readonly AuthorizedReferenceProjection[];
  citations: readonly AuthorizedReferenceProjection[];
} {
  if (mode !== "live" || liveSnapshot === null) throw new Error("LIVE_PREVIEW_NOT_LOADED");
  return deepFreeze({
    selectedContext: liveSnapshot.selectedContext,
    sharedSnapshotId: liveSnapshot.sharedSnapshotId ?? "",
    canonicalRelations: liveSnapshot.canonicalRelations ?? [],
    evidenceReferences: liveSnapshot.authorizedEvidenceReferences ?? [],
    citations: liveSnapshot.authorizedCitations ?? [],
  });
}

function deepFreeze<T>(value: T): Readonly<T> {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    Object.values(value).forEach((item) => deepFreeze(item));
  }
  return value;
}

export function loadTechnicalPreview(selection: SelectedExecutionContextValue = sharedExecutionSnapshot.selectedContext): TechnicalProjection {
  if (mode === "live" && liveSnapshot === null) throw new Error("LIVE_PREVIEW_NOT_LOADED");
  const source = mode === "live" ? liveSnapshot! : sharedExecutionSnapshot;
  const effectiveSelection = mode === "live" && selection.executionId !== source.selectedContext.executionId ? source.selectedContext : selection;
  const view = mode === "live" ? structuredClone({
    classification: source.classification,
    selectedContext: source.selectedContext,
    definition: source.definition,
    instances: source.instances,
    nodes: source.nodes,
    edges: source.edges,
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
  }) : projectTechnicalSnapshot(source);
  const stableKeys = ["workId", "workflowId", "taskId", "executionId", "graphSnapshotId"] as const;
  const validEmployee = source.employees.some((employee) => employee.id === effectiveSelection.employeeId);
  const validRevision = [source.selectedContext.revisionId, source.correctionRevision].includes(effectiveSelection.revisionId);
  if (!validEmployee || !validRevision || stableKeys.some((key) => effectiveSelection[key] !== source.selectedContext[key])) throw new Error("CROSS_VIEW_IDENTITY_MISMATCH");
  view.selectedContext = structuredClone(effectiveSelection);
  if (view.authorization.decision === "DENY" && (view.authorization.providerCallCount !== 0 || view.citations.length !== 0)) throw new Error("DENY_REQUIRES_ZERO_PROVIDER_EFFECTS");
  if (view.edges.some((edge) => edge.rawRelations.some((relation) => relation.source !== edge.source || relation.target !== edge.target))) throw new Error("TECHNICAL_RELATION_RECONSTRUCTION_REJECTED");
  return deepFreeze(view) as TechnicalProjection;
}
