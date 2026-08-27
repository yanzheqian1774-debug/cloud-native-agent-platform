import { useI18n } from "../i18n/useI18n";
import type { TechnicalProjection } from "../shared/executionSnapshotTypes";

export function ExecutionIdentityPanel({ view }: { view: TechnicalProjection }) {
  const { t } = useI18n();
  const entries = [
    [t("technical.identity.employee"), view.selectedContext.employeeId],
    [t("technical.identity.definition"), view.definition.id],
    [t("technical.identity.revision"), view.selectedContext.revisionId],
    [t("technical.identity.work"), view.selectedContext.workId],
    [t("technical.identity.workflow"), view.selectedContext.workflowId],
    [t("technical.identity.task"), view.selectedContext.taskId],
    [t("technical.identity.execution"), view.selectedContext.executionId],
    [t("technical.identity.snapshot"), view.selectedContext.graphSnapshotId],
  ];
  return <section id="identity" className="technical-section panel-pad" aria-labelledby="technical-identity-title">
    <div className="section-heading"><h2 id="technical-identity-title">{t("technical.identity.title")}</h2><p>{t("technical.identity.description")}</p></div>
    <dl className="technical-definition-list">{entries.map(([label, value]) => <div key={label}><dt>{label}</dt><dd className="stable-id">{value}</dd></div>)}</dl>
    <h3>{t("technical.instances.title")}</h3>
    <ul className="technical-list">{view.instances.map((instance) => <li key={instance.id}><strong className="stable-id">{instance.id}</strong><span>{instance.selected ? t("technical.instances.selected") : t("technical.instances.notSelected")}</span><span className="stable-id">{instance.reasonCode}</span></li>)}</ul>
  </section>;
}
