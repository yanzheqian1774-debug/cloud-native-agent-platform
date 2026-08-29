import {
  messages,
  type MessageKey,
} from "./messages";
import type {
  EdgeType,
  NodePhase,
  WorkflowPhase,
} from "../types/workflow";
import type {
  FeedbackReasonCode,
  OutcomeAssessment,
} from "../shared/interventionFeedbackTypes";

export type Translate = (
  key: MessageKey,
) => string;

const phaseKeys = {
  Pending: "phase.Pending",
  Running: "phase.Running",
  Succeeded: "phase.Succeeded",
  Failed: "phase.Failed",
  TimedOut: "phase.TimedOut",
  Skipped: "phase.Skipped",
} as const satisfies Record<
  WorkflowPhase | NodePhase,
  MessageKey
>;

const edgeKeys = {
  control: "edge.control",
  data: "edge.data",
} as const satisfies Record<EdgeType, MessageKey>;

const feedbackAssessmentKeys = {
  SATISFIED: "feedback.assessment.SATISFIED",
  PARTIALLY_SATISFIED: "feedback.assessment.PARTIALLY_SATISFIED",
  UNSATISFIED: "feedback.assessment.UNSATISFIED",
} as const satisfies Record<OutcomeAssessment, MessageKey>;

const feedbackReasonKeys = {
  MISSING_TASK: "feedback.reason.MISSING_TASK",
  EXTRA_TASK: "feedback.reason.EXTRA_TASK",
  WRONG_DATA: "feedback.reason.WRONG_DATA",
  INSUFFICIENT_DATA: "feedback.reason.INSUFFICIENT_DATA",
  WRONG_KNOWLEDGE: "feedback.reason.WRONG_KNOWLEDGE",
  WRONG_ROLE: "feedback.reason.WRONG_ROLE",
  WRONG_SKILL: "feedback.reason.WRONG_SKILL",
  WRONG_CAPABILITY: "feedback.reason.WRONG_CAPABILITY",
  WRONG_ORDER: "feedback.reason.WRONG_ORDER",
  MISSING_CONSTRAINT: "feedback.reason.MISSING_CONSTRAINT",
  WRONG_OUTPUT_FORMAT: "feedback.reason.WRONG_OUTPUT_FORMAT",
  CITATION_NOT_USEFUL: "feedback.reason.CITATION_NOT_USEFUL",
} as const satisfies Record<FeedbackReasonCode, MessageKey>;

export function formatPhase(
  phase: WorkflowPhase | NodePhase,
  t: Translate,
): string {
  return t(phaseKeys[phase]);
}

export function formatReason(
  reason: string | null,
  t: Translate,
): string {
  if (!reason) {
    return t("common.notAvailable");
  }

  const candidate = `reason.${reason}`;

  if (
    Object.prototype.hasOwnProperty.call(
      messages["en-US"],
      candidate,
    )
  ) {
    return t(candidate as MessageKey);
  }

  return reason;
}

export function formatBoolean(
  value: boolean | null,
  t: Translate,
): string {
  if (value === null) {
    return t("common.notAvailable");
  }

  return value
    ? t("common.yes")
    : t("common.no");
}

export function formatAttempts(
  attempts: number | null,
  t: Translate,
): string {
  if (attempts === null) {
    return t("node.noExecution");
  }

  return `${attempts} ${
    attempts === 1
      ? t("attempt.one")
      : t("attempt.other")
  }`;
}

export function formatEdgeType(
  type: EdgeType,
  t: Translate,
): string {
  return t(edgeKeys[type]);
}

export function formatFeedbackAssessment(
  value: OutcomeAssessment,
  t: Translate,
): string {
  return t(feedbackAssessmentKeys[value]);
}

export function formatFeedbackReasonExplanation(
  value: FeedbackReasonCode,
  t: Translate,
): string {
  return t(feedbackReasonKeys[value]);
}

export function formatTimestamp(
  value: string | null,
  locale: string,
  t: Translate,
): string {
  if (!value) {
    return t("common.notAvailable");
  }

  return new Date(value).toLocaleString(locale);
}

/** Machine identifiers, enums, digests, and reason codes are never translated. */
export function preserveTechnicalCode(value: string): string {
  return value;
}
