import {
  messages,
  type MessageKey,
} from "./messages";
import type {
  EdgeType,
  NodePhase,
  WorkflowPhase,
} from "../types/workflow";

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
