export type PreviewClassification =
  | "DETERMINISTIC"
  | "SYNTHETIC"
  | "NON_AUTHORITATIVE"
  | "TECHNICAL_PREVIEW"
  | "LIVE"
  | "NO_NETWORK"
  | "NO_RUNTIME_OR_PROVIDER_INVOCATION";

export type ExecutionState =
  | "NOT_STARTED"
  | "QUEUED"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "SKIPPED"
  | "BLOCKED"
  | "DENIED"
  | "UNKNOWN"
  | "UNAVAILABLE"
  | "DOWNSTREAM";

export type ApprovalState = "PENDING_HUMAN_REVIEW" | "APPROVED" | "REJECTED";
export type ProjectionVisibility = "PRODUCT" | "TECHNICAL" | "BOTH" | "DETAIL_ONLY";
export type Cardinality = "ONE_TO_ONE" | "ONE_TO_MANY" | "MANY_TO_ONE" | "MANY_TO_MANY";

export interface DigitalEmployee {
  id: string;
  nameKey: string;
  roleKey: string;
  descriptionKey: string;
  responsibilityKeys: string[];
  allowedKeys: string[];
  prohibitedKeys: string[];
  capabilities: string[];
  runtimeId: "NATIVE";
  previewInstanceCount: number;
  previewState: string;
}

export interface SnapshotNode {
  id: string;
  type: string;
  labelKey: string;
  phase: ExecutionState;
  visibility: ProjectionVisibility;
  evidenceIds: string[];
  limitationCodes: string[];
}

export interface SnapshotRelation {
  id: string;
  source: string;
  target: string;
  type: string;
  direction: "SOURCE_TO_TARGET";
  cardinality: Cardinality;
  evidenceIds: string[];
  visibility: ProjectionVisibility;
}

export interface SnapshotEdge {
  id: string;
  source: string;
  target: string;
  rawRelations: SnapshotRelation[];
}

export interface CanonicalRelation {
  relation_id: string;
  source_node_id: string;
  target_node_id: string;
  relation_types: string[];
  layer: string;
  direction: "SOURCE_TO_TARGET";
  declared_cardinality: Cardinality;
  observed_source_count: number;
  observed_target_count: number;
  state: string;
  evidence_ids: string[];
  display_priority: number;
  projection_visibility: ProjectionVisibility;
  semantic_discriminator: string;
  path_class: string;
  blocking_class: string;
  authorization_class: string | null;
  evidence_authority_class: string;
  execution_or_historical_context: string;
  tenant_or_security_domain: string;
  aggregation_key: string | null;
}

export interface AuthorizedReferenceProjection {
  referenceIdentity: string;
  referenceType: "EVIDENCE" | "CITATION";
  namespace: string;
  securityDomain: string;
  authorizationDecision: "ALLOW";
  reasonCode: string;
  visibility: ProjectionVisibility;
  sourceIdentity: string;
  provenance: string;
}

export interface RuntimeSupportRecord {
  id: "NATIVE" | "OPENCLAW" | "HERMES";
  classification: string;
  availability: string;
  support: string;
  providerCorrelationId: string | null;
}

export interface SelectedExecutionContextValue {
  employeeId: string;
  revisionId: string;
  workId: string;
  workflowId: string;
  taskId: string;
  executionId: string;
  graphSnapshotId: string;
}

export interface SharedExecutionSnapshot {
  snapshotKind: "BOUNDED_SYNTHETIC_FRONTEND_SNAPSHOT" | "AUTHORIZED_LIVE_EXECUTION_SNAPSHOT";
  readModelState?: "COMPLETE" | "PARTIAL" | "STALE";
  sharedSnapshotId?: string;
  classification: readonly PreviewClassification[];
  selectedContext: SelectedExecutionContextValue;
  questionKey: string;
  questions: string[];
  correctionRevision: string;
  taskKeys: string[];
  employees: DigitalEmployee[];
  nodes: SnapshotNode[];
  edges: SnapshotEdge[];
  canonicalRelations?: CanonicalRelation[];
  authorizedEvidenceReferences?: AuthorizedReferenceProjection[];
  authorizedCitations?: AuthorizedReferenceProjection[];
  groups: { id: string; kind: string; memberNodeIds: string[] }[];
  approval: { state: ApprovalState; decidedAt: string | null; decisionFingerprint: string };
  authorization: { decision: "ALLOW" | "DENY"; reasonCode: string; providerCallCount: number; requestId: string };
  outcome: { id: string; status: "PASS" | "FAIL" | "UNKNOWN"; summaryKey: string; evidenceIds: string[] };
  citations: { citationId: string; evidenceId: string; assetId: string; revisionId: string; labelKey: string }[];
  runtimeSupport: RuntimeSupportRecord[];
  requestedRuntimeId: "NATIVE";
  effectiveRuntimeId: "NATIVE";
  definition: { id: string; revisionId: string };
  instances: { id: string; eligible: boolean; selected: boolean; reasonCode: string }[];
  conditions: { owner: string; state: ExecutionState; reasonCode: string }[];
  recovery: { state: "DOWNSTREAM"; reasonCode: string; exactlyOnce: false };
  limitations: string[];
}

export interface RawRelation {
  id: string;
  type: string;
  direction: "SOURCE_TO_TARGET";
  cardinality: Cardinality;
  evidenceIds: string[];
}

export interface ProductEdge { id: string; source: string; target: string; rawRelations: RawRelation[] }
export interface ProductNode { id: string; type: string; labelKey: string; phase: ExecutionState }

export interface ProductFixture {
  classification: readonly PreviewClassification[];
  readModelState?: "COMPLETE" | "PARTIAL" | "STALE";
  sharedSnapshotId?: string;
  platformExecutionIdentity: string;
  graphSnapshotId: string;
  projectionContext: "PRODUCT";
  securityFiltered: true;
  questionKey: string;
  questions: string[];
  planRevision: string;
  correctionRevision: string;
  workflowId: string;
  taskKeys: string[];
  employees: DigitalEmployee[];
  nodes: ProductNode[];
  edges: ProductEdge[];
  groups: { id: string; kind: string; memberNodeIds: string[] }[];
  approval: { state: ApprovalState; decidedAt: string | null; decisionFingerprint: string };
  outcome: { status: "PASS" | "FAIL" | "UNKNOWN"; summaryKey: string; evidenceIds: string[] };
  citations: { evidenceId: string; assetId: string; revisionId: string; labelKey: string }[];
  capability: { decision: "ALLOW" | "DENY"; reasonCode: string; providerCallCount: number };
}

export interface TechnicalProjection {
  classification: readonly PreviewClassification[];
  selectedContext: SelectedExecutionContextValue;
  definition: SharedExecutionSnapshot["definition"];
  instances: SharedExecutionSnapshot["instances"];
  nodes: SnapshotNode[];
  edges: SnapshotEdge[];
  approval: SharedExecutionSnapshot["approval"];
  authorization: SharedExecutionSnapshot["authorization"];
  outcome: SharedExecutionSnapshot["outcome"];
  citations: SharedExecutionSnapshot["citations"];
  runtimeSupport: RuntimeSupportRecord[];
  requestedRuntimeId: "NATIVE";
  effectiveRuntimeId: "NATIVE";
  conditions: SharedExecutionSnapshot["conditions"];
  recovery: SharedExecutionSnapshot["recovery"];
  limitations: string[];
}
