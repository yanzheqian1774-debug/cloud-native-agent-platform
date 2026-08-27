import { useI18n } from "../i18n/useI18n";
import type { TechnicalProjection } from "../shared/executionSnapshotTypes";

export function OutcomeRecoveryPanel({ view }: { view: TechnicalProjection }) {
  const { t } = useI18n();
  return <section id="outcome" className="technical-section panel-pad" aria-labelledby="technical-outcome-title">
    <div className="section-heading"><h2 id="technical-outcome-title">{t("technical.outcome.title")}</h2><p>{t("technical.outcome.description")}</p></div>
    <dl className="technical-definition-list"><div><dt>{t("technical.outcome.id")}</dt><dd className="stable-id">{view.outcome.id}</dd></div><div><dt>{t("technical.outcome.state")}</dt><dd className="stable-id">{view.outcome.status}</dd></div><div><dt>{t("technical.recovery.state")}</dt><dd className="stable-id">{view.recovery.state}</dd></div><div><dt>{t("technical.recovery.reason")}</dt><dd className="stable-id">{view.recovery.reasonCode}</dd></div></dl>
    <h3>{t("technical.conditions.title")}</h3><ul className="technical-list">{view.conditions.map((condition) => <li key={condition.owner}><strong className="stable-id">{condition.owner}</strong><span className="stable-id">{condition.state}</span><span className="stable-id">{condition.reasonCode}</span></li>)}</ul>
    <p className="honesty-note" role="status">{t("technical.recovery.honesty")}</p>
    <h3>{t("technical.limitations.title")}</h3><ul>{view.limitations.map((limitation) => <li className="stable-id" key={limitation}>{limitation}</li>)}</ul>
  </section>;
}
