import type { JourneyState } from "./types";
import type { SharedExecutionSnapshot } from "../shared/executionSnapshotTypes.ts";

type SharedRevisionId = SharedExecutionSnapshot["selectedContext"]["revisionId"];

export const initialJourney: JourneyState = {
  step: "QUESTION", question: "", selectedEmployeeId: "de.synthetic.customer-insight.v1",
  revision: "plan-revision.synthetic.qi-1042.r1", correction: "", diffClassification: "NO_CHANGE",
  approval: "PENDING_HUMAN_REVIEW", decidedAt: null, approvedFingerprint: null,
  approvalError: null, execution: "NOT_STARTED", executionPresentationCount: 0,
  scenario: "ALLOW",
};

const DECIDED_AT = "2026-08-27T08:00:00Z";

function fingerprintFor(revision: SharedRevisionId): string | null {
  if (revision === "plan-revision.synthetic.qi-1042.r1") return "sha256:synthetic-plan-r1";
  if (revision === "plan-revision.synthetic.qi-1042.r2") return "sha256:synthetic-plan-r2";
  return null;
}

export function applyApprovalDecision(
  state: JourneyState,
  decision: "APPROVED" | "REJECTED" | null,
  decidedAt: string | null,
  fingerprint: string | null,
): JourneyState {
  const expected = fingerprintFor(state.revision);
  if (!decision || !decidedAt || !fingerprint || fingerprint !== expected) {
    return { ...state, approvalError: "MALFORMED_APPROVAL_DECISION", execution: "NOT_STARTED" };
  }
  if (state.approval !== "PENDING_HUMAN_REVIEW") {
    return state.approval === decision && state.decidedAt === decidedAt && state.approvedFingerprint === fingerprint
      ? state
      : { ...state, approvalError: "APPROVAL_REPLAY_MISMATCH", execution: "NOT_STARTED" };
  }
  return {
    ...state,
    step: "APPROVAL",
    approval: decision,
    decidedAt,
    approvedFingerprint: fingerprint,
    approvalError: null,
    execution: "NOT_STARTED",
  };
}

export type JourneyAction =
  | { type: "SELECT_QUESTION"; question: string }
  | { type: "SHOW_PLAN" }
  | { type: "SELECT_EMPLOYEE"; id: string }
  | { type: "APPROVE" }
  | { type: "REJECT" }
  | { type: "RUN" }
  | { type: "COMPLETE" }
  | { type: "CORRECT"; text: string }
  | { type: "SET_SCENARIO"; scenario: JourneyState["scenario"] };

export function journeyReducer(state: JourneyState, action: JourneyAction): JourneyState {
  switch (action.type) {
    case "SELECT_QUESTION": return { ...state, question: action.question };
    case "SHOW_PLAN": return state.question.trim() ? { ...state, step: "PLAN" } : state;
    case "SELECT_EMPLOYEE": return { ...state, selectedEmployeeId: action.id };
    case "APPROVE": return applyApprovalDecision(state, "APPROVED", DECIDED_AT, fingerprintFor(state.revision));
    case "REJECT": return applyApprovalDecision(state, "REJECTED", DECIDED_AT, fingerprintFor(state.revision));
    case "RUN": return state.approval === "APPROVED" && state.approvedFingerprint === fingerprintFor(state.revision) && state.approvalError === null && state.execution === "NOT_STARTED" ? { ...state, step: "EXECUTION", execution: "RUNNING", executionPresentationCount: 1 } : state;
    case "COMPLETE": return state.execution === "RUNNING" ? { ...state, step: "OUTCOME", execution: state.scenario === "FAILURE" ? "FAILED" : state.scenario === "UNKNOWN" ? "UNKNOWN" : "COMPLETED" } : state;
    case "CORRECT": return action.text.trim() ? { ...state, step: "PLAN", correction: action.text, revision: "plan-revision.synthetic.qi-1042.r2", diffClassification: "MATERIAL", approval: "PENDING_HUMAN_REVIEW", decidedAt: null, approvedFingerprint: null, approvalError: null, execution: "NOT_STARTED", executionPresentationCount: 0 } : state;
    case "SET_SCENARIO": return { ...state, scenario: action.scenario };
  }
}
