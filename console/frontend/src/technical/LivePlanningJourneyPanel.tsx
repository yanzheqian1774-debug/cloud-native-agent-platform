import type { LivePlanningJourney } from "../shared/livePlanningJourneyTypes";
import { useI18n } from "../i18n/useI18n";

export function LivePlanningJourneyPanel({ journey }: { journey: LivePlanningJourney }) {
  const { t } = useI18n(); const identity = journey.technical.identity; const revision = journey.technical.revision;
  return <section className="live-journey technical-live-journey" aria-labelledby="technical-live-title"><h2 id="technical-live-title">{t("liveJourney.technical.title")}</h2><dl className="evidence-list"><dt>canonicalWorkflowRevisionId</dt><dd className="stable-id">{identity.canonicalWorkflowRevisionId}</dd><dt>canonicalDigest</dt><dd className="stable-id">{identity.canonicalDigest}</dd><dt>sharedSnapshotId</dt><dd className="stable-id">{identity.sharedSnapshotId}</dd><dt>graphSnapshotId</dt><dd className="stable-id">{identity.graphSnapshotId}</dd><dt>platformExecutionIdentity</dt><dd className="stable-id">{identity.platformExecutionIdentity ?? "NOT_ISSUED"}</dd><dt>approvalId</dt><dd className="stable-id">{identity.approvalId}</dd><dt>placementDecisionId</dt><dd className="stable-id">{identity.placementDecisionId}</dd></dl><p className="stable-id">{revision.lifecycle} · {revision.executionState}</p>{revision.limitationCodes.map((code) => <p className="stable-id" key={code}>{code}</p>)}</section>;
}
