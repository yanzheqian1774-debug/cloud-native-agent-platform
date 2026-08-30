import { useEffect, useMemo, useState } from "react";
import { useI18n } from "../i18n/useI18n";
import { ViewSwitcher } from "../shared/ViewSwitcher";
import { loadTechnicalPreview } from "../technical/adapter";
import { CapabilityEvidencePanel } from "../technical/CapabilityEvidencePanel";
import { ExecutionIdentityPanel } from "../technical/ExecutionIdentityPanel";
import { OutcomeRecoveryPanel } from "../technical/OutcomeRecoveryPanel";
import { RuntimeProviderPanel } from "../technical/RuntimeProviderPanel";
import { TechnicalGraph } from "../technical/TechnicalGraph";
import { TechnicalNavigation } from "../technical/TechnicalNavigation";
import { useSelectedExecution } from "../shared/SelectedExecutionContext";
import { fetchLivePlanningJourney, LivePlanningJourneyError } from "../api/livePlanningJourney";
import type { LivePlanningJourney } from "../shared/livePlanningJourneyTypes";
import { LivePlanningJourneyPanel } from "../technical/LivePlanningJourneyPanel";
import { InterventionFeedbackPanel } from "../technical/InterventionFeedbackPanel";
import { NavLink } from "react-router-dom";

export function TechPage({ supplierQualityJourneyId }: { supplierQualityJourneyId?: string }) {
  const { t } = useI18n();
  const { selection } = useSelectedExecution();
  const view = useMemo(() => loadTechnicalPreview(selection), [selection]);
  const [active, setActive] = useState("identity");
  const [liveJourney, setLiveJourney] = useState<LivePlanningJourney | null>(null);
  const [liveFailure, setLiveFailure] = useState<string | null>(null);
  const liveJourneyId = supplierQualityJourneyId ?? import.meta.env.VITE_LIVE_PLANNING_JOURNEY_ID as string | undefined;
  useEffect(() => { if (!liveJourneyId) return; const controller = new AbortController(); fetchLivePlanningJourney(liveJourneyId, controller.signal).then(setLiveJourney).catch((error: unknown) => { if (!controller.signal.aborted) setLiveFailure(error instanceof LivePlanningJourneyError ? `${error.state}:${error.reasonCode}` : "ERROR:LIVE_JOURNEY_ERROR"); }); return () => controller.abort(); }, [liveJourneyId]);
  function navigate(section: string) { setActive(section); document.getElementById(section)?.scrollIntoView({ behavior: "smooth", block: "start" }); }
  if (supplierQualityJourneyId) return <main className="technical-page supplier-quality-live"><style>{`.supplier-quality-live .evidence-list{grid-template-columns:minmax(15rem,auto) minmax(0,1fr)}.supplier-quality-live .evidence-list dt,.supplier-quality-live .evidence-list dd{min-width:0;overflow-wrap:anywhere}@media(max-width:600px){.supplier-quality-live .evidence-list{grid-template-columns:minmax(0,1fr)}}`}</style><nav className="view-switcher" aria-label={t("nav.views")}><NavLink to="/product">{t("nav.productView")}</NavLink><NavLink to="/technical">{t("nav.technicalView")}</NavLink></nav><header className="technical-hero"><p className="eyebrow">LIVE_EXECUTION</p><h1>{t("supplierQuality.technical.title")}</h1><p>{t("supplierQuality.technical.description")}</p></header><div className="preview-warning" role="status"><strong>LIVE_EXECUTION</strong><span>{t("supplierQuality.liveOnly")}</span></div>{liveFailure && <div className="preview-warning" role="alert"><strong>{t("liveJourney.unavailable")}</strong><span className="stable-id">{liveFailure}</span></div>}{liveJourney && <LivePlanningJourneyPanel journey={liveJourney} />}<InterventionFeedbackPanel journeyId={supplierQualityJourneyId} /></main>;
  return <main className="technical-page"><ViewSwitcher /><header className="technical-hero"><p className="eyebrow">{t("technical.preview.label")}</p><h1>{t("technical.title")}</h1><p>{t("technical.description")}</p></header>{liveFailure && <div className="preview-warning" role="alert"><strong>{t("liveJourney.unavailable")}</strong><span className="stable-id">{liveFailure}</span></div>}{liveJourney && <LivePlanningJourneyPanel journey={liveJourney} />}{liveJourneyId && <InterventionFeedbackPanel journeyId={liveJourneyId} />}<div className="preview-warning" role="status"><strong>{view.classification.join(" · ")}</strong><span>{t("technical.preview.warning")}</span></div><TechnicalNavigation active={active} onSelect={navigate} /><ExecutionIdentityPanel view={view} /><TechnicalGraph view={view} /><RuntimeProviderPanel view={view} /><CapabilityEvidencePanel view={view} /><OutcomeRecoveryPanel view={view} /></main>;
}
