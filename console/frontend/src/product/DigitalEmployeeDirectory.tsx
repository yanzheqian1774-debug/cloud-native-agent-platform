import { useI18n } from "../i18n/useI18n";
import type { DigitalEmployee } from "./types";

interface Props { employees: DigitalEmployee[]; selectedId: string; onSelect: (id: string) => void }
export function DigitalEmployeeDirectory({ employees, selectedId, onSelect }: Props) {
  const { t } = useI18n();
  return <section id="employees" className="product-section" aria-labelledby="employees-title">
    <div className="section-heading"><h2 id="employees-title">{t("product.employees.title")}</h2><p>{t("product.employees.description")}</p></div>
    <div className="employee-grid">{employees.map((employee) => <article key={employee.id} className={`employee-card ${selectedId === employee.id ? "selected" : ""}`}>
      <p className="eyebrow">{t(employee.nameKey as never)}</p><h3>{t(employee.roleKey as never)}</h3><p>{t(employee.descriptionKey as never)}</p>
      <dl><dt>{t("product.responsibilities")}</dt><dd>{employee.responsibilityKeys.map((key) => t(key as never)).join(" · ")}</dd>
        <dt>{t("product.allowed")}</dt><dd>{employee.allowedKeys.map((key) => t(key as never)).join(" · ")}</dd>
        <dt>{t("product.prohibited")}</dt><dd>{employee.prohibitedKeys.map((key) => t(key as never)).join(" · ")}</dd>
        <dt>{t("product.capabilities")}</dt><dd className="stable-id">{employee.capabilities.join(", ")}</dd></dl>
      <p className="honesty-note"><strong>{t("product.instances.preview")}: {employee.previewInstanceCount}</strong> · <span className="stable-id">{employee.previewState}</span></p>
      <button className="secondary-button" aria-pressed={selectedId === employee.id} onClick={() => onSelect(employee.id)}>{t("product.employee.select")}</button>
    </article>)}</div>
  </section>;
}
