import type { LivePlanningJourney } from "../shared/livePlanningJourneyTypes";

export class LivePlanningJourneyError extends Error {
  readonly state: "DENIED" | "NOT_FOUND" | "AUTHORITY_MISSING" | "STALE" | "ERROR";
  readonly reasonCode: string;
  constructor(state: "DENIED" | "NOT_FOUND" | "AUTHORITY_MISSING" | "STALE" | "ERROR", reasonCode: string) { super(reasonCode); this.state = state; this.reasonCode = reasonCode; }
}

function record(value: unknown, code: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new LivePlanningJourneyError("ERROR", code);
  return value as Record<string, unknown>;
}

function sameIdentity(payload: LivePlanningJourney): boolean {
  return JSON.stringify(payload.product.identity) === JSON.stringify(payload.technical.identity)
    && JSON.stringify(payload.product.revision) === JSON.stringify(payload.technical.revision);
}

function validate(payload: unknown): LivePlanningJourney {
  const root = record(payload, "LIVE_JOURNEY_ENVELOPE_INVALID") as unknown as LivePlanningJourney;
  if (root.schemaVersion !== 1 || root.provenance !== "LIVE_EXECUTION") throw new LivePlanningJourneyError("ERROR", "LIVE_JOURNEY_VERSION_OR_PROVENANCE_INVALID");
  if (!sameIdentity(root)) throw new LivePlanningJourneyError("ERROR", "PRODUCT_TECHNICAL_IDENTITY_MISMATCH");
  const identity = root.successor.identity;
  if (!identity?.tenantId || !identity.securityDomain || !identity.canonicalDigest || identity.canonicalDigest.length !== 64) throw new LivePlanningJourneyError("ERROR", "LIVE_JOURNEY_IDENTITY_INVALID");
  if (root.successor.knowledgeState === "DENIED" && (root.successor.citations.length || identity.citationIds.length)) throw new LivePlanningJourneyError("ERROR", "DENIED_KNOWLEDGE_DISCLOSURE");
  for (const citation of root.successor.citations) if (!citation.citationId || !citation.authorizationDecisionId || !citation.documentDigest) throw new LivePlanningJourneyError("ERROR", "LIVE_CITATION_INVALID");
  return root;
}

async function request(journeyId: string, suffix = "", init?: RequestInit): Promise<LivePlanningJourney> {
  let response: Response;
  try { response = await fetch(`/api/internal/preview/v1/live-planning-journeys/${encodeURIComponent(journeyId)}${suffix}`, { headers: { Accept: "application/json", "Content-Type": "application/json" }, ...init }); }
  catch { throw new LivePlanningJourneyError("ERROR", "LIVE_JOURNEY_NETWORK_UNAVAILABLE"); }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = record(record(payload, "LIVE_JOURNEY_ERROR_INVALID").detail, "LIVE_JOURNEY_ERROR_INVALID");
    const state = detail.state;
    const reason = detail.reasonCode;
    if (typeof state !== "string" || typeof reason !== "string") throw new LivePlanningJourneyError("ERROR", "LIVE_JOURNEY_ERROR_INVALID");
    throw new LivePlanningJourneyError(state as LivePlanningJourneyError["state"], reason);
  }
  return validate(payload);
}

export const fetchLivePlanningJourney = (journeyId: string, signal?: AbortSignal) => request(journeyId, "", { signal });
export const submitSemanticCorrection = (journeyId: string, predecessorRevisionId: string, predecessorDigest: string, objective: string) => request(journeyId, "/corrections", { method: "POST", body: JSON.stringify({ predecessorRevisionId, predecessorDigest, objective, reasonCode: "CONSTRAINT_CHANGED" }) });
export const submitExactApproval = (journeyId: string, candidateDigest: string) => request(journeyId, "/approvals", { method: "POST", body: JSON.stringify({ candidateDigest, decision: "APPROVE", reasonCode: "HUMAN_APPROVED", replayIdentity: `ui-approval:${candidateDigest}` }) });
export const requestBoundedRerun = (journeyId: string, canonicalWorkflowRevisionId: string, canonicalDigest: string) => request(journeyId, "/reruns", { method: "POST", body: JSON.stringify({ canonicalWorkflowRevisionId, canonicalDigest }) });
