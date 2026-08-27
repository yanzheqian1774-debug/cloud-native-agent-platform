import { useI18n } from "../i18n/useI18n";
const states = [
  ["NATIVE", "AVAILABLE", "COMPONENT_TESTED_CANDIDATE", "NOT_CERTIFIED"],
  ["OPENCLAW", "EXPERIMENTAL", "CURRENTLY_UNAVAILABLE", "SUPPORT_NOT_GRANTED"],
  ["HERMES", "EXPERIMENTAL", "NOT_CURRENTLY_CERTIFIABLE", "SUPPORT_NOT_GRANTED"],
];
export function RuntimeSupport() { const { t } = useI18n(); return <section className="product-section" aria-labelledby="runtime-title"><div className="section-heading"><h2 id="runtime-title">{t("product.runtime.title")}</h2><p>{t("product.runtime.description")}</p></div><div className="runtime-grid">{states.map(([id, ...status]) => <article className="runtime-card" key={id}><h3 className="stable-id">{id}</h3>{status.map((item) => <p className="status-with-icon stable-id" key={item}>◆ {item}</p>)}</article>)}</div></section> }
