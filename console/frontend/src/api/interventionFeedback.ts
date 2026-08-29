import type {
  InterventionCaptureCommand,
  InterventionFeedbackResponse,
  InterventionLifecycle,
  OutcomeFeedbackCommand,
} from "../shared/interventionFeedbackTypes";

export class InterventionFeedbackApiError extends Error {
  readonly state: "DENIED" | "NOT_FOUND" | "CONFLICT" | "INVALID" | "UNAVAILABLE";
  readonly reasonCode: string;

  constructor(state: InterventionFeedbackApiError["state"], reasonCode: string) {
    super(reasonCode);
    this.state = state;
    this.reasonCode = reasonCode;
  }
}

function object(value: unknown, reasonCode: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new InterventionFeedbackApiError("INVALID", reasonCode);
  }
  return value as Record<string, unknown>;
}

function validate(payload: unknown): InterventionFeedbackResponse {
  const root = object(payload, "INTERVENTION_FEEDBACK_ENVELOPE_INVALID") as unknown as InterventionFeedbackResponse;
  if (root.schemaVersion !== 1 || root.state !== "READY") {
    throw new InterventionFeedbackApiError("INVALID", "INTERVENTION_FEEDBACK_VERSION_INVALID");
  }
  if (JSON.stringify(root.product.identity) !== JSON.stringify(root.technical.identity)) {
    throw new InterventionFeedbackApiError("INVALID", "PRODUCT_TECHNICAL_IDENTITY_MISMATCH");
  }
  if (JSON.stringify(root.product.interventions) !== JSON.stringify(root.technical.interventions)
    || JSON.stringify(root.product.outcomeFeedback) !== JSON.stringify(root.technical.outcomeFeedback)) {
    throw new InterventionFeedbackApiError("INVALID", "PRODUCT_TECHNICAL_RECORD_MISMATCH");
  }
  const identity = root.product.identity;
  if (!identity.journeyId || !identity.tenantId || !identity.securityDomain
    || !identity.successorRevisionId || !identity.platformExecutionIdentity
    || !identity.outcomeId || !identity.evidenceIds.length
    || !["LIVE_EXECUTION", "SYNTHETIC_PREVIEW"].includes(identity.provenance)) {
    throw new InterventionFeedbackApiError("INVALID", "INTERVENTION_FEEDBACK_IDENTITY_INVALID");
  }
  for (const item of root.product.interventions) {
    if (!item.recordId || !item.interventionEventId || item.recordDigest.length !== 64
      || item.tenantId !== identity.tenantId || item.securityDomain !== identity.securityDomain
      || item.platformExecutionIdentity !== identity.platformExecutionIdentity
      || item.outcomeId !== identity.outcomeId || item.provenance !== identity.provenance) {
      throw new InterventionFeedbackApiError("INVALID", "INTERVENTION_RECORD_INVALID");
    }
  }
  for (const item of root.product.outcomeFeedback) {
    const record = item.record;
    if (!record.feedbackId || record.feedbackDigest.length !== 64
      || record.tenantId !== identity.tenantId || record.securityDomain !== identity.securityDomain
      || record.platformExecutionIdentity !== identity.platformExecutionIdentity
      || record.outcomeId !== identity.outcomeId || record.provenance !== identity.provenance) {
      throw new InterventionFeedbackApiError("INVALID", "OUTCOME_FEEDBACK_RECORD_INVALID");
    }
  }
  return root;
}

async function request(journeyId: string, suffix: string, init?: RequestInit): Promise<InterventionFeedbackResponse> {
  let response: Response;
  try {
    response = await fetch(`/api/internal/preview/v1/live-planning-journeys/${encodeURIComponent(journeyId)}${suffix}`, {
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new InterventionFeedbackApiError("UNAVAILABLE", "INTERVENTION_FEEDBACK_NETWORK_UNAVAILABLE");
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = object(object(payload, "INTERVENTION_FEEDBACK_ERROR_INVALID").detail, "INTERVENTION_FEEDBACK_ERROR_INVALID");
    if (typeof detail.state !== "string" || typeof detail.reasonCode !== "string") {
      throw new InterventionFeedbackApiError("INVALID", "INTERVENTION_FEEDBACK_ERROR_INVALID");
    }
    throw new InterventionFeedbackApiError(detail.state as InterventionFeedbackApiError["state"], detail.reasonCode);
  }
  return validate(payload);
}

export const fetchInterventionFeedback = (journeyId: string, signal?: AbortSignal) => request(journeyId, "/intervention-feedback", { signal });
export const captureIntervention = (journeyId: string, command: InterventionCaptureCommand) => request(journeyId, "/interventions", { method: "POST", body: JSON.stringify(command) });
export const captureOutcomeFeedback = (journeyId: string, command: OutcomeFeedbackCommand) => request(journeyId, "/outcome-feedback", { method: "POST", body: JSON.stringify(command) });
export const appendInterventionLifecycle = (journeyId: string, interventionEventId: string, lifecycle: Exclude<InterventionLifecycle, "RECORDED">) => request(journeyId, `/interventions/${encodeURIComponent(interventionEventId)}/lifecycle`, { method: "POST", body: JSON.stringify({ lifecycle }) });
