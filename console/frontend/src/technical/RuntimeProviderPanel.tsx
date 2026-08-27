import { useI18n } from "../i18n/useI18n";
import type { TechnicalProjection } from "../shared/executionSnapshotTypes";

export function RuntimeProviderPanel({ view }: { view: TechnicalProjection }) {
  const { t } = useI18n();
  return <section id="runtime" className="technical-section panel-pad" aria-labelledby="technical-runtime-title">
    <div className="section-heading"><h2 id="technical-runtime-title">{t("technical.runtime.title")}</h2><p>{t("technical.runtime.description")}</p></div>
    <div className="runtime-grid">{view.runtimeSupport.map((runtime) => <article className="runtime-card" key={runtime.id}><h3 className="stable-id">{runtime.id}</h3><p className="stable-id">{runtime.classification}</p><p className={`technical-state state-${runtime.availability.toLowerCase().replaceAll("_", "-")}`}>● <span className="stable-id">{runtime.availability}</span></p><p className="stable-id">{runtime.support}</p><p>{t("technical.runtime.correlation")}: <span className="stable-id">{runtime.providerCorrelationId ?? t("common.notAvailable")}</span></p><small>{t("technical.runtime.correlationOnly")}</small></article>)}</div>
  </section>;
}
