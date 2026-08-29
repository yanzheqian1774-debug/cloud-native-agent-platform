import { journeyEventTypes, type JourneyEventEnvelope } from "../shared/livePlanningJourneyEventTypes";

export interface JourneyStreamCallbacks { onEvent: (serialized: string, event: JourneyEventEnvelope) => void; onFailure: (reason: string) => void; }

export function subscribeLivePlanningJourney(journeyId: string, callbacks: JourneyStreamCallbacks): () => void {
  const source = new EventSource(`/api/internal/preview/v1/live-planning-journeys/${encodeURIComponent(journeyId)}/events`);
  const receive = (delivery: MessageEvent<string>) => {
    try { callbacks.onEvent(delivery.data, JSON.parse(delivery.data) as JourneyEventEnvelope); }
    catch { source.close(); callbacks.onFailure("JOURNEY_EVENT_MALFORMED"); }
  };
  for (const eventType of journeyEventTypes) source.addEventListener(eventType, receive as EventListener);
  source.onerror = () => { source.close(); callbacks.onFailure("JOURNEY_STREAM_UNAVAILABLE"); };
  return () => source.close();
}
