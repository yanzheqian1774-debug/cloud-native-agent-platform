import { useEffect, useState } from "react";
import { captureIntervention, captureOutcomeFeedback, fetchInterventionFeedback, InterventionFeedbackApiError } from "../api/interventionFeedback";
import { formatFeedbackAssessment, formatFeedbackReasonExplanation, preserveTechnicalCode } from "../i18n/presentation";
import { useI18n } from "../i18n/useI18n";
import type { FeedbackReasonCode, InterventionFeedbackResponse, OutcomeAssessment } from "../shared/interventionFeedbackTypes";

const assessments: OutcomeAssessment[] = ["SATISFIED", "PARTIALLY_SATISFIED", "UNSATISFIED"];
const reasons: FeedbackReasonCode[] = ["MISSING_TASK", "EXTRA_TASK", "WRONG_DATA", "INSUFFICIENT_DATA", "WRONG_KNOWLEDGE", "WRONG_ROLE", "WRONG_SKILL", "WRONG_CAPABILITY", "WRONG_ORDER", "MISSING_CONSTRAINT", "WRONG_OUTPUT_FORMAT", "CITATION_NOT_USEFUL"];

export function InterventionFeedback({ journeyId }: { journeyId: string }) {
  const { t } = useI18n();
  const [projection, setProjection] = useState<InterventionFeedbackResponse | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [assessment, setAssessment] = useState<OutcomeAssessment>("PARTIALLY_SATISFIED");
  const [reason, setReason] = useState<FeedbackReasonCode>("MISSING_CONSTRAINT");
  const [consent, setConsent] = useState<"GRANTED" | "DENIED">("DENIED");

  useEffect(() => {
    const controller = new AbortController();
    fetchInterventionFeedback(journeyId, controller.signal).then(setProjection).catch((error: unknown) => {
      if (!controller.signal.aborted) setFailure(error instanceof InterventionFeedbackApiError ? `${error.state}:${error.reasonCode}` : "UNAVAILABLE:INTERVENTION_FEEDBACK_ERROR");
    });
    return () => controller.abort();
  }, [journeyId]);

  function run(command: Promise<InterventionFeedbackResponse>) {
    setPending(true);
    setFailure(null);
    command.then(setProjection).catch((error: unknown) => setFailure(error instanceof InterventionFeedbackApiError ? `${error.state}:${error.reasonCode}` : "UNAVAILABLE:INTERVENTION_FEEDBACK_ERROR")).finally(() => setPending(false));
  }

  if (failure && !projection) return <section className="feedback-state" role="alert"><strong>{t("feedback.unavailable")}</strong><span className="stable-id">{failure}</span></section>;
  if (!projection) return <section className="feedback-state" role="status">{t("feedback.loading")}</section>;
  const view = projection.product;
  const identity = view.identity;
  const evidenceId = identity.evidenceIds[0];
  const currentFeedback = [...view.outcomeFeedback].reverse().find((item) => item.lifecycle === "RECORDED")?.record ?? null;
  const canCaptureIntervention = Boolean(identity.predecessorRevisionId && evidenceId);

  return <section className="intervention-feedback product-feedback" aria-labelledby="product-feedback-title">
    <header><p className="eyebrow">{preserveTechnicalCode(identity.provenance)}</p><h2 id="product-feedback-title">{t("feedback.product.title")}</h2><p>{t("feedback.product.description")}</p></header>
    {failure && <p className="feedback-error" role="alert">{t("feedback.captureFailed")} <span className="stable-id">{failure}</span></p>}
    <div className="feedback-grid">
      <article><h3>{t("feedback.intervention.title")}</h3><p>{t("feedback.intervention.description")}</p><label htmlFor="optimization-consent">{t("feedback.optimizationConsent")}</label><select id="optimization-consent" value={consent} onChange={(event) => setConsent(event.target.value as "GRANTED" | "DENIED")}><option value="DENIED">{t("feedback.optimizationDenied")}</option><option value="GRANTED">{t("feedback.optimizationGranted")}</option></select><button disabled={pending || !canCaptureIntervention} onClick={() => run(captureIntervention(journeyId, { predecessorRevisionId: identity.predecessorRevisionId!, successorRevisionId: identity.successorRevisionId, outcomeId: identity.outcomeId, evidenceId, eventKind: "CONSTRAINT_CHANGED", affectedElementReference: "CONSTRAINT", correctionPatchReference: "CONSTRAINT_PATCH", reasonCode: "MISSING_CONSTRAINT", optimizationUseConsentDecision: consent }))}>{t("feedback.intervention.capture")}</button><p className="feedback-count">{t("feedback.intervention.count")}: {view.interventions.length}</p></article>
      <article><h3>{t("feedback.outcome.title")}</h3><label htmlFor="feedback-assessment">{t("feedback.assessment")}</label><select id="feedback-assessment" value={assessment} onChange={(event) => setAssessment(event.target.value as OutcomeAssessment)}>{assessments.map((value) => <option value={value} key={value}>{formatFeedbackAssessment(value, t)}</option>)}</select><label htmlFor="feedback-reason">{t("feedback.reason")}</label><select id="feedback-reason" value={reason} onChange={(event) => setReason(event.target.value as FeedbackReasonCode)}>{reasons.map((value) => <option value={value} key={value}>{formatFeedbackReasonExplanation(value, t)}</option>)}</select><button disabled={pending || !evidenceId} onClick={() => run(captureOutcomeFeedback(journeyId, { outcomeId: identity.outcomeId, evidenceId, assessment, reasonCodes: [reason], supersedesFeedbackId: currentFeedback?.feedbackId ?? null }))}>{currentFeedback ? t("feedback.outcome.update") : t("feedback.outcome.capture")}</button></article>
    </div>
    {currentFeedback && <div className="feedback-summary" role="status"><strong>{formatFeedbackAssessment(currentFeedback.assessment, t)}</strong><span className="stable-id">{preserveTechnicalCode(currentFeedback.assessment)} · {preserveTechnicalCode(currentFeedback.reasonCodes.join(", "))}</span><span>{formatFeedbackReasonExplanation(currentFeedback.reasonCodes[0], t)}</span></div>}
  </section>;
}
