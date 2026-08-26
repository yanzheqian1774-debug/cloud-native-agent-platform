import type { JourneyState } from "./types";

export const initialJourney: JourneyState = {
  step: "QUESTION", question: "", selectedEmployeeId: "de.synthetic.customer-insight.v1",
  revision: "plan-revision.synthetic.qi-1042.r1", correction: "", diffClassification: "NO_CHANGE",
  approval: "PENDING_HUMAN_REVIEW", decidedAt: null, approvedFingerprint: null,
  execution: "NOT_STARTED", scenario: "ALLOW",
};

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
    case "APPROVE": return { ...state, step: "APPROVAL", approval: "APPROVED", decidedAt: "2026-08-27T08:00:00Z", approvedFingerprint: "sha256:synthetic-plan-r1" };
    case "REJECT": return { ...state, step: "APPROVAL", approval: "REJECTED", decidedAt: "2026-08-27T08:00:00Z", approvedFingerprint: null, execution: "NOT_STARTED" };
    case "RUN": return state.approval === "APPROVED" && state.approvedFingerprint === "sha256:synthetic-plan-r1" ? { ...state, step: "EXECUTION", execution: "RUNNING" } : state;
    case "COMPLETE": return state.execution === "RUNNING" ? { ...state, step: "OUTCOME", execution: state.scenario === "FAILURE" ? "FAILED" : state.scenario === "UNKNOWN" ? "UNKNOWN" : "COMPLETED" } : state;
    case "CORRECT": return action.text.trim() ? { ...state, step: "PLAN", correction: action.text, revision: "plan-revision.synthetic.qi-1042.r2", diffClassification: "MATERIAL", approval: "PENDING_HUMAN_REVIEW", decidedAt: null, approvedFingerprint: null, execution: "NOT_STARTED" } : state;
    case "SET_SCENARIO": return { ...state, scenario: action.scenario };
  }
}
