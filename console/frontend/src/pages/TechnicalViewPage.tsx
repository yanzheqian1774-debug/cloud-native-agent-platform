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
import { Link, NavLink, useLocation } from "react-router-dom";
import { TraceabilityProjection } from "../shared/EvidenceInspector";
import { parseUrlContext } from "../shared/urlContext";
import { ControlledState } from "../shared/ControlledState";
import { getProductTraceability, type ProductAssemblyError, type TraceabilityDTO } from "../api/productAssembly";

export function TechPage(props: { supplierQualityJourneyId?: string; questionFirst?: boolean }) {
  const { search } = useLocation();
  const parsed = parseUrlContext(search);
  const context=parsed.state==="VALID"?parsed.context:{};
  const [traceability,setTraceability]=useState<TraceabilityDTO|null>(null),[traceabilityError,setTraceabilityError]=useState<ProductAssemblyError|null>(null),[retry,setRetry]=useState(0);
  useEffect(()=>{if(!context.kind||!context.resourceId||!context.revisionId||!context.digest)return;let active=true;getProductTraceability(context.kind,context.resourceId,context.revisionId,context.digest).then(value=>{if(active){setTraceability(value);setTraceabilityError(null)}}).catch(value=>active&&setTraceabilityError(value));return()=>{active=false}},[context.kind,context.resourceId,context.revisionId,context.digest,retry]);
  if (parsed.state === "INVALID") return <main className="technical-page"><ControlledState kind="not-found" title="Resource context unavailable" detail="The URL context is invalid or unsupported."/></main>;
  if (parsed.context.resourceId) return <main className="technical-page"><TraceabilityProjection context={parsed.context} perspective="technical" data={traceability} error={traceabilityError} retry={()=>setRetry(value=>value+1)}/></main>;
  return <LegacyTechPage {...props}/>;
}

function LegacyTechPage({ supplierQualityJourneyId, questionFirst = false }: { supplierQualityJourneyId?: string; questionFirst?: boolean }) {
  const { t } = useI18n();
  const { search } = useLocation();
  const { selection } = useSelectedExecution();
  const view = useMemo(() => loadTechnicalPreview(selection), [selection]);
  const [active, setActive] = useState("identity");
  const [liveJourney, setLiveJourney] = useState<LivePlanningJourney | null>(null);
  const [liveFailure, setLiveFailure] = useState<string | null>(null);
  const liveJourneyId = supplierQualityJourneyId ?? import.meta.env.VITE_LIVE_PLANNING_JOURNEY_ID as string | undefined;
  useEffect(() => { if (!liveJourneyId) return; const controller = new AbortController(); fetchLivePlanningJourney(liveJourneyId, controller.signal).then(setLiveJourney).catch((error: unknown) => { if (!controller.signal.aborted) setLiveFailure(error instanceof LivePlanningJourneyError ? `${error.state}:${error.reasonCode}` : "ERROR:LIVE_JOURNEY_ERROR"); }); return () => controller.abort(); }, [liveJourneyId]);
  function navigate(section: string) { setActive(section); document.getElementById(section)?.scrollIntoView({ behavior: "smooth", block: "start" }); }
  if (questionFirst && !supplierQualityJourneyId) return <main className="technical-page"><ViewSwitcher /><header className="technical-hero"><p className="eyebrow">技术视图（Technical View）</p><h1>尚未创建业务问题</h1><p>请先在业务视图中提交供应商质量问题。系统不会自动启动旅程，也不会显示合成执行结果。</p></header></main>;
  if (supplierQualityJourneyId) return <main className="technical-page supplier-quality-live"><style>{`.supplier-quality-live .evidence-list{grid-template-columns:minmax(15rem,auto) minmax(0,1fr)}.supplier-quality-live .evidence-list dt,.supplier-quality-live .evidence-list dd{min-width:0;overflow-wrap:anywhere}@media(max-width:600px){.supplier-quality-live .evidence-list{grid-template-columns:minmax(0,1fr)}}`}</style><nav className="demo-breadcrumb" aria-label="面包屑"><Link to="/workspace">工作台</Link><span>/</span><Link to="/tasks">任务</Link><span>/</span><Link to={{pathname:"/product",search}}>供应商质量整改</Link><span>/</span><strong>技术视图</strong></nav><nav className="view-switcher" aria-label={t("nav.views")}><NavLink to={{ pathname: "/product", search }}>业务视图</NavLink><NavLink to={{ pathname: "/technical", search }}>技术视图</NavLink></nav><header className="technical-hero"><p className="eyebrow">LIVE_EXECUTION</p><h1>{t("supplierQuality.technical.title")}</h1><p>{t("supplierQuality.technical.description")}</p></header><div className="preview-warning" role="status"><strong>LIVE_EXECUTION</strong><span>{t("supplierQuality.liveOnly")}</span></div>{liveFailure && <div className="preview-warning" role="alert"><strong>{t("liveJourney.unavailable")}</strong><span className="stable-id">{liveFailure}</span></div>}{liveJourney && <LivePlanningJourneyPanel journey={liveJourney} />}{liveJourney?.successor.outcome && <InterventionFeedbackPanel journeyId={supplierQualityJourneyId} />}</main>;
  return <main className="technical-page"><ViewSwitcher /><header className="technical-hero"><p className="eyebrow">{t("technical.preview.label")}</p><h1>{t("technical.title")}</h1><p>{t("technical.description")}</p></header>{liveFailure && <div className="preview-warning" role="alert"><strong>{t("liveJourney.unavailable")}</strong><span className="stable-id">{liveFailure}</span></div>}{liveJourney && <LivePlanningJourneyPanel journey={liveJourney} />}{liveJourneyId && <InterventionFeedbackPanel journeyId={liveJourneyId} />}<div className="preview-warning" role="status"><strong>{view.classification.join(" · ")}</strong><span>{t("technical.preview.warning")}</span></div><TechnicalNavigation active={active} onSelect={navigate} /><ExecutionIdentityPanel view={view} /><TechnicalGraph view={view} /><RuntimeProviderPanel view={view} /><CapabilityEvidencePanel view={view} /><OutcomeRecoveryPanel view={view} /></main>;
}
