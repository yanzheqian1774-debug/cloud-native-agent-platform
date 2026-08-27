export type JourneyStep = "QUESTION" | "PLAN" | "APPROVAL" | "EXECUTION" | "OUTCOME";
export type ApprovalState = "PENDING_HUMAN_REVIEW" | "APPROVED" | "REJECTED";
export type ExecutionState = "NOT_STARTED" | "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED" | "UNKNOWN";

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

export interface RawRelation {
  id: string;
  type: string;
  direction: "SOURCE_TO_TARGET";
  cardinality: "ONE_TO_ONE" | "ONE_TO_MANY" | "MANY_TO_ONE" | "MANY_TO_MANY";
  evidenceIds: string[];
}

export interface ProductEdge {
  id: string;
  source: string;
  target: string;
  rawRelations: RawRelation[];
}

export interface ProductNode {
  id: string;
  type: string;
  labelKey: string;
  phase: ExecutionState;
}

export interface ProductFixture {
  classification: readonly ["DETERMINISTIC", "SYNTHETIC", "NON_AUTHORITATIVE", "TECHNICAL_PREVIEW"];
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

export interface JourneyState {
  step: JourneyStep;
  question: string;
  selectedEmployeeId: string;
  revision: string;
  correction: string;
  diffClassification: "NO_CHANGE" | "MATERIAL";
  approval: ApprovalState;
  decidedAt: string | null;
  approvedFingerprint: string | null;
  approvalError: "APPROVAL_REPLAY_MISMATCH" | "MALFORMED_APPROVAL_DECISION" | null;
  execution: ExecutionState;
  executionPresentationCount: number;
  scenario: "ALLOW" | "DENY" | "UNKNOWN" | "FAILURE" | "EMPTY" | "LOADING" | "ERROR";
}
