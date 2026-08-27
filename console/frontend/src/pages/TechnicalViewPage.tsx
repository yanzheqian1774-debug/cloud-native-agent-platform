import { useState } from "react";
import { useI18n } from "../i18n/useI18n";
import { ViewSwitcher } from "../shared/ViewSwitcher";
import { loadTechnicalPreview } from "../technical/adapter";
import { CapabilityEvidencePanel } from "../technical/CapabilityEvidencePanel";
import { ExecutionIdentityPanel } from "../technical/ExecutionIdentityPanel";
import { OutcomeRecoveryPanel } from "../technical/OutcomeRecoveryPanel";
import { RuntimeProviderPanel } from "../technical/RuntimeProviderPanel";
import { TechnicalGraph } from "../technical/TechnicalGraph";
import { TechnicalNavigation } from "../technical/TechnicalNavigation";

const view = loadTechnicalPreview();

export function TechPage() {
  const { t } = useI18n();
  const [active, setActive] = useState("identity");
  function navigate(section: string) { setActive(section); document.getElementById(section)?.scrollIntoView({ behavior: "smooth", block: "start" }); }
  return <main className="technical-page"><ViewSwitcher /><header className="technical-hero"><p className="eyebrow">{t("technical.preview.label")}</p><h1>{t("technical.title")}</h1><p>{t("technical.description")}</p></header><div className="preview-warning" role="status"><strong>{view.classification.join(" · ")}</strong><span>{t("technical.preview.warning")}</span></div><TechnicalNavigation active={active} onSelect={navigate} /><ExecutionIdentityPanel view={view} /><TechnicalGraph view={view} /><RuntimeProviderPanel view={view} /><CapabilityEvidencePanel view={view} /><OutcomeRecoveryPanel view={view} /></main>;
}
