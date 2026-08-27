export type {
  ApprovalState,
  DigitalEmployee,
  ExecutionState,
  ProductEdge,
  ProductFixture,
  ProductNode,
  RawRelation,
} from "../shared/executionSnapshotTypes";

import type { ApprovalState, ExecutionState } from "../shared/executionSnapshotTypes";

export type JourneyStep = "QUESTION" | "PLAN" | "APPROVAL" | "EXECUTION" | "OUTCOME";

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
