import { useI18n } from "../i18n/useI18n";
import type { TechnicalProjection } from "../shared/executionSnapshotTypes";

export function CapabilityEvidencePanel({ view }: { view: TechnicalProjection }) {
  const { t } = useI18n();
  return <section id="capability" className="technical-section panel-pad" aria-labelledby="technical-capability-title">
    <div className="section-heading"><h2 id="technical-capability-title">{t("technical.capability.title")}</h2><p>{t("technical.capability.description")}</p></div>
    <dl className="technical-definition-list"><div><dt>{t("technical.capability.decision")}</dt><dd className="stable-id">{view.authorization.decision}</dd></div><div><dt>{t("technical.capability.reason")}</dt><dd className="stable-id">{view.authorization.reasonCode}</dd></div><div><dt>{t("technical.capability.request")}</dt><dd className="stable-id">{view.authorization.requestId}</dd></div><div><dt>{t("technical.capability.calls")}</dt><dd>{view.authorization.providerCallCount}</dd></div></dl>
    {view.authorization.decision === "DENY" && <p role="status" className="honesty-note">{t("technical.capability.denied")}</p>}
    <h3>{t("technical.citations.title")}</h3><ul className="technical-list">{view.citations.map((citation) => <li key={citation.citationId}><strong className="stable-id">{citation.citationId}</strong><span className="stable-id">{citation.evidenceId}</span><span>{t("technical.citations.synthetic")}</span></li>)}</ul>
  </section>;
}
