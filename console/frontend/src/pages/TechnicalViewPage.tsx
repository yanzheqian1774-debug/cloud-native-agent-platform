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

export function TechPage() {
  const { t } = useI18n();
  const { selection } = useSelectedExecution();
  const view = useMemo(() => loadTechnicalPreview(selection), [selection]);
  const [active, setActive] = useState("identity");
  const [liveJourney, setLiveJourney] = useState<LivePlanningJourney | null>(null);
  const [liveFailure, setLiveFailure] = useState<string | null>(null);
  const liveJourneyId = import.meta.env.VITE_LIVE_PLANNING_JOURNEY_ID as string | undefined;
  useEffect(() => { if (!liveJourneyId) return; const controller = new AbortController(); fetchLivePlanningJourney(liveJourneyId, controller.signal).then(setLiveJourney).catch((error: unknown) => { if (!controller.signal.aborted) setLiveFailure(error instanceof LivePlanningJourneyError ? `${error.state}:${error.reasonCode}` : "ERROR:LIVE_JOURNEY_ERROR"); }); return () => controller.abort(); }, [liveJourneyId]);
  function navigate(section: string) { setActive(section); document.getElementById(section)?.scrollIntoView({ behavior: "smooth", block: "start" }); }
  return <main className="technical-page"><ViewSwitcher /><header className="technical-hero"><p className="eyebrow">{t("technical.preview.label")}</p><h1>{t("technical.title")}</h1><p>{t("technical.description")}</p></header>{liveFailure && <div className="preview-warning" role="alert"><strong>{t("liveJourney.unavailable")}</strong><span className="stable-id">{liveFailure}</span></div>}{liveJourney && <LivePlanningJourneyPanel journey={liveJourney} />}{liveJourneyId && <InterventionFeedbackPanel journeyId={liveJourneyId} />}<div className="preview-warning" role="status"><strong>{view.classification.join(" · ")}</strong><span>{t("technical.preview.warning")}</span></div><TechnicalNavigation active={active} onSelect={navigate} /><ExecutionIdentityPanel view={view} /><TechnicalGraph view={view} /><RuntimeProviderPanel view={view} /><CapabilityEvidencePanel view={view} /><OutcomeRecoveryPanel view={view} /></main>;
}
