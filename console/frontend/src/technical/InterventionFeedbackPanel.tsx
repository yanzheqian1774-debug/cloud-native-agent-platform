import { useEffect, useState } from "react";
import { appendInterventionLifecycle, fetchInterventionFeedback, InterventionFeedbackApiError } from "../api/interventionFeedback";
import { useI18n } from "../i18n/useI18n";
import type { InterventionFeedbackResponse } from "../shared/interventionFeedbackTypes";

export function InterventionFeedbackPanel({ journeyId }: { journeyId: string }) {
  const { t } = useI18n();
  const [projection, setProjection] = useState<InterventionFeedbackResponse | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetchInterventionFeedback(journeyId, controller.signal).then(setProjection).catch((error: unknown) => {
      if (!controller.signal.aborted) setFailure(error instanceof InterventionFeedbackApiError ? `${error.state}:${error.reasonCode}` : "UNAVAILABLE:INTERVENTION_FEEDBACK_ERROR");
    });
    return () => controller.abort();
  }, [journeyId]);
  if (failure && !projection) return <section className="feedback-state" role="alert"><strong>{t("feedback.unavailable")}</strong><span className="stable-id">{failure}</span></section>;
  if (!projection) return <section className="feedback-state" role="status">{t("feedback.loading")}</section>;
  const view = projection.technical;
  const latestIntervention = view.interventions.at(-1);
  return <section className="intervention-feedback technical-feedback" aria-labelledby="technical-feedback-title"><header><p className="eyebrow">{view.identity.provenance}</p><h2 id="technical-feedback-title">{t("feedback.technical.title")}</h2><p>{t("feedback.technical.description")}</p></header>{failure && <p className="feedback-error" role="alert">{failure}</p>}<dl className="evidence-list"><dt>tenantId</dt><dd className="stable-id">{view.identity.tenantId}</dd><dt>securityDomain</dt><dd className="stable-id">{view.identity.securityDomain}</dd><dt>predecessorRevisionId</dt><dd className="stable-id">{view.identity.predecessorRevisionId ?? "NOT_APPLICABLE"}</dd><dt>successorRevisionId</dt><dd className="stable-id">{view.identity.successorRevisionId}</dd><dt>platformExecutionIdentity</dt><dd className="stable-id">{view.identity.platformExecutionIdentity}</dd><dt>outcomeId</dt><dd className="stable-id">{view.identity.outcomeId}</dd></dl><div className="feedback-record-list">{view.interventions.map((record) => <article key={record.recordId}><h3>{record.eventKind} · {record.lifecycle}</h3><p className="stable-id">{record.interventionEventId}<br />{record.recordId}<br />{record.recordDigest}</p><p className="stable-id">{record.affectedElementReference} · {record.correctionPatchReference} · {record.reasonCode}</p><p className="stable-id">{record.optimizationUseConsentDecision} · {record.principalId} · {record.decisionTime}</p></article>)}{view.outcomeFeedback.map((item) => <article key={item.record.feedbackId}><h3>{item.record.assessment} · {item.lifecycle}</h3><p className="stable-id">{item.record.feedbackId}<br />{item.record.feedbackDigest}</p><p className="stable-id">{item.record.outcomeId} · {item.record.evidenceId}</p><p className="stable-id">{item.record.reasonCodes.join(" · ")}</p></article>)}</div>{latestIntervention && latestIntervention.lifecycle !== "TOMBSTONED" && <button className="danger-button" onClick={() => appendInterventionLifecycle(journeyId, latestIntervention.interventionEventId, "TOMBSTONED").then(setProjection).catch((error: InterventionFeedbackApiError) => setFailure(`${error.state}:${error.reasonCode}`))}>{t("feedback.intervention.tombstone")}</button>}</section>;
}
