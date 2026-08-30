import { useEffect, useReducer, useState } from "react";
import { subscribeLivePlanningJourney } from "../api/livePlanningJourneyStream";
import { useI18n } from "../i18n/useI18n";
import { applyJourneyEvent, initialJourneyEventState } from "../shared/livePlanningJourneyEventTypes";
import type { LivePlanningJourney } from "../shared/livePlanningJourneyTypes";

export function LivePlanningJourneyPanel({ journey }: { journey: LivePlanningJourney }) {
  const { t } = useI18n(); const identity = journey.technical.identity; const revision = journey.technical.revision;
  const [stream, deliver] = useReducer(applyJourneyEvent, initialJourneyEventState); const [streamFailure, setStreamFailure] = useState<string | null>(null);
  useEffect(() => subscribeLivePlanningJourney({ journeyId: journey.journeyId, identity }, { onEvent: (serialized) => deliver(serialized), onFailure: setStreamFailure }), [journey.journeyId, identity]);
  return <section className="live-journey technical-live-journey" aria-labelledby="technical-live-title"><h2 id="technical-live-title">{t("liveJourney.technical.title")}</h2>{(streamFailure ?? stream.failure) && <p role="alert" className="stable-id">{streamFailure ?? stream.failure}</p>}<ol>{stream.events.map((event) => <li key={event.eventId}><span>{t(event.localizationKey as Parameters<typeof t>[0])}</span> <span className="stable-id">{event.eventId} · {event.eventType} · {event.sequence} · {event.reasonCode} · {event.provenance}</span></li>)}</ol><dl className="evidence-list"><dt>canonicalWorkflowRevisionId</dt><dd className="stable-id">{identity.canonicalWorkflowRevisionId}</dd><dt>canonicalDigest</dt><dd className="stable-id">{identity.canonicalDigest}</dd><dt>sharedSnapshotId</dt><dd className="stable-id">{identity.sharedSnapshotId}</dd><dt>graphSnapshotId</dt><dd className="stable-id">{identity.graphSnapshotId}</dd><dt>platformExecutionIdentity</dt><dd className="stable-id">{identity.platformExecutionIdentity ?? "NOT_ISSUED"}</dd><dt>approvalId</dt><dd className="stable-id">{identity.approvalId}</dd><dt>placementDecisionId</dt><dd className="stable-id">{identity.placementDecisionId}</dd></dl><p className="stable-id">{revision.lifecycle} · {revision.executionState}</p>{revision.limitationCodes.map((code) => <p className="stable-id" key={code}>{code}</p>)}</section>;
}
