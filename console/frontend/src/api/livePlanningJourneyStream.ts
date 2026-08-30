import { applyJourneyStreamDisconnect, applyJourneyStreamEvent, initialJourneyStreamState, journeyEventTypes, type JourneyEventEnvelope, type JourneyStreamBinding } from "../shared/livePlanningJourneyEventTypes";

export interface JourneyStreamCallbacks { onEvent: (serialized: string, event: JourneyEventEnvelope) => void; onFailure: (reason: string) => void; }

export function subscribeLivePlanningJourney(binding: JourneyStreamBinding, callbacks: JourneyStreamCallbacks): () => void {
  const { journeyId } = binding;
  const source = new EventSource(`/api/internal/preview/v1/live-planning-journeys/${encodeURIComponent(journeyId)}/events`);
  let state = initialJourneyStreamState;
  let disposed = false;
  const receive = (expectedType: string, delivery: MessageEvent<string>) => {
    if (disposed) return;
    const previousCount = state.events.events.length;
    state = applyJourneyStreamEvent(state, delivery.data, binding);
    const event = state.events.events[state.events.events.length - 1];
    if (!state.failure && event?.eventType !== expectedType) state = { ...state, phase: "FAILED", failure: "JOURNEY_EVENT_TYPE_MISMATCH" };
    if (state.failure) { disposed = true; source.close(); callbacks.onFailure(state.failure); return; }
    if (state.events.events.length > previousCount) callbacks.onEvent(delivery.data, state.events.events[state.events.events.length - 1]);
    if (state.phase === "TERMINAL") source.close();
  };
  for (const eventType of journeyEventTypes) source.addEventListener(eventType, ((delivery: MessageEvent<string>) => receive(eventType, delivery)) as EventListener);
  source.onerror = () => {
    if (disposed) return;
    const next = applyJourneyStreamDisconnect(state);
    if (next === state) return;
    state = next; disposed = true; source.close(); callbacks.onFailure("JOURNEY_STREAM_UNAVAILABLE");
  };
  return () => { disposed = true; source.close(); };
}
