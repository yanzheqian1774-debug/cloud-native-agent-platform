import type { JourneyIdentity } from "./livePlanningJourneyTypes";

export const journeyEventTypes = [
  "JOURNEY_REGISTERED", "CORRECTION_ACCEPTED", "APPROVAL_RECORDED",
  "EXECUTION_AUTHORIZED", "EXECUTION_STARTED", "EXECUTION_SUCCEEDED",
  "EXECUTION_FAILED", "JOURNEY_STALE", "JOURNEY_UNAVAILABLE",
  "JOURNEY_ERROR", "RESUME_UNAVAILABLE",
] as const;
export type JourneyEventType = typeof journeyEventTypes[number];

export interface JourneyEventEnvelope {
  schemaVersion: "journey-event.v1"; journeyId: string; eventId: string; sequence: number;
  occurredAt: string; eventType: JourneyEventType;
  stage: "JOURNEY" | "CORRECTION" | "APPROVAL" | "EXECUTION" | "RESUME";
  status: "REGISTERED" | "ACCEPTED" | "APPROVED" | "REJECTED" | "AUTHORIZED" | "STARTED" | "SUCCEEDED" | "FAILED" | "STALE" | "UNAVAILABLE" | "ERROR";
  terminal: boolean; reasonCode: string; localizationKey: string; provenance: "LIVE_EXECUTION";
  identity: JourneyIdentity;
  payload: { revision: number | null; approvalId: string | null; platformExecutionIdentity: string | null; sharedSnapshotId: string | null; graphSnapshotId: string | null; evidenceIds: string[]; citationIds: string[]; limitationCodes: string[]; };
}

export interface JourneyEventState { events: JourneyEventEnvelope[]; serializedById: Readonly<Record<string, string>>; terminal: boolean; failure: string | null; }
export const initialJourneyEventState: JourneyEventState = { events: [], serializedById: {}, terminal: false, failure: null };
const identifier = (value: unknown): value is string => typeof value === "string" && value.length > 0 && value.length <= 200;
const record = (value: unknown): Record<string, unknown> => { if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("JOURNEY_EVENT_MALFORMED"); return value as Record<string, unknown>; };

export function parseJourneyEvent(serialized: string): JourneyEventEnvelope {
  if (new TextEncoder().encode(serialized).length > 32 * 1024) throw new Error("JOURNEY_EVENT_OVERSIZED");
  const root = record(JSON.parse(serialized));
  const allowed = new Set(["schemaVersion", "journeyId", "eventId", "sequence", "occurredAt", "eventType", "stage", "status", "terminal", "reasonCode", "localizationKey", "provenance", "identity", "payload"]);
  if (Object.keys(root).some((key) => !allowed.has(key))) throw new Error("JOURNEY_EVENT_UNKNOWN_FIELD");
  if (root.schemaVersion !== "journey-event.v1" || root.provenance !== "LIVE_EXECUTION") throw new Error("JOURNEY_EVENT_VERSION_INVALID");
  if (!identifier(root.journeyId) || !identifier(root.eventId) || !Number.isSafeInteger(root.sequence) || (root.sequence as number) < 1) throw new Error("JOURNEY_EVENT_IDENTITY_INVALID");
  if (!journeyEventTypes.includes(root.eventType as JourneyEventType) || !identifier(root.reasonCode) || !identifier(root.localizationKey)) throw new Error("JOURNEY_EVENT_ENUM_INVALID");
  if (typeof root.terminal !== "boolean" || typeof root.occurredAt !== "string" || !(root.occurredAt.endsWith("Z") || root.occurredAt.endsWith("+00:00"))) throw new Error("JOURNEY_EVENT_TIME_INVALID");
  const identity = record(root.identity);
  if (!identifier(identity.tenantId) || !identifier(identity.securityDomain) || !identifier(identity.canonicalWorkflowRevisionId) || !identifier(identity.sharedSnapshotId) || !identifier(identity.graphSnapshotId)) throw new Error("JOURNEY_EVENT_CANONICAL_IDENTITY_INVALID");
  const payload = record(root.payload);
  const payloadAllowed = new Set(["revision", "approvalId", "platformExecutionIdentity", "sharedSnapshotId", "graphSnapshotId", "evidenceIds", "citationIds", "limitationCodes"]);
  if (Object.keys(payload).some((key) => !payloadAllowed.has(key)) || new TextEncoder().encode(JSON.stringify(payload)).length > 16 * 1024) throw new Error("JOURNEY_EVENT_PAYLOAD_INVALID");
  return root as unknown as JourneyEventEnvelope;
}

export function applyJourneyEvent(state: JourneyEventState, serialized: string): JourneyEventState {
  if (state.failure) return state;
  let event: JourneyEventEnvelope;
  try { event = parseJourneyEvent(serialized); } catch (error) { return { ...state, failure: error instanceof Error ? error.message : "JOURNEY_EVENT_MALFORMED" }; }
  const duplicate = state.serializedById[event.eventId];
  if (duplicate !== undefined) return duplicate === serialized ? state : { ...state, failure: "JOURNEY_EVENT_CONFLICTING_DUPLICATE" };
  if (state.terminal) return { ...state, failure: "JOURNEY_EVENT_AFTER_TERMINAL" };
  const first = state.events[0];
  if (first && (event.journeyId !== first.journeyId || event.identity.tenantId !== first.identity.tenantId || event.identity.securityDomain !== first.identity.securityDomain)) return { ...state, failure: "JOURNEY_EVENT_SCOPE_MISMATCH" };
  const expected = state.events.length ? state.events[state.events.length - 1].sequence + 1 : event.sequence;
  if (event.sequence !== expected) return { ...state, failure: "JOURNEY_EVENT_SEQUENCE_GAP" };
  return { events: [...state.events, event], serializedById: { ...state.serializedById, [event.eventId]: serialized }, terminal: event.terminal, failure: null };
}
