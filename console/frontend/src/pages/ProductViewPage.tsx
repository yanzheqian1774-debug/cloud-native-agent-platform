import { Link, NavLink, useLocation } from "react-router-dom";
import { useI18n } from "../i18n/useI18n";
import { QuestionToOutcomeJourney } from "../product/QuestionToOutcomeJourney";
import { TraceabilityProjection } from "../shared/EvidenceInspector";
import { parseUrlContext } from "../shared/urlContext";
import { ControlledState } from "../shared/ControlledState";
import { useEffect, useState } from "react";
import { getProductTraceability, type ProductAssemblyError, type TraceabilityDTO } from "../api/productAssembly";

export function ProductViewPage({ supplierQualityJourneyId, onJourneyStarted }: { supplierQualityJourneyId?: string; onJourneyStarted?: (id: string) => void }) {
  const { t } = useI18n();
  const { search } = useLocation();
  const parsed = parseUrlContext(search);
  const context=parsed.state==="VALID"?parsed.context:{};
  const [traceability,setTraceability]=useState<TraceabilityDTO|null>(null),[traceabilityError,setTraceabilityError]=useState<ProductAssemblyError|null>(null),[retry,setRetry]=useState(0);
  useEffect(()=>{if(!context.kind||!context.resourceId||!context.revisionId||!context.digest)return;let active=true;getProductTraceability(context.kind,context.resourceId,context.revisionId,context.digest).then(value=>{if(active){setTraceability(value);setTraceabilityError(null)}}).catch(value=>active&&setTraceabilityError(value));return()=>{active=false}},[context.kind,context.resourceId,context.revisionId,context.digest,retry]);
  if (parsed.state === "INVALID") return <main className="product-page"><ControlledState kind="not-found" title="Resource context unavailable" detail="The URL context is invalid or unsupported."/></main>;
  if (parsed.context.resourceId) return <main className="product-page"><TraceabilityProjection context={parsed.context} perspective="product" data={traceability} error={traceabilityError} retry={()=>setRetry(value=>value+1)}/></main>;
  return <main className="product-page question-to-outcome-page"><nav className="demo-breadcrumb" aria-label="面包屑"><Link to="/workspace">工作台</Link><span>/</span><Link to="/tasks">任务</Link><span>/</span><strong>{supplierQualityJourneyId?"供应商质量整改":"提出问题"}</strong></nav><nav className="view-switcher" aria-label={t("nav.views")}><NavLink to={{ pathname: "/product", search }}>业务视图</NavLink><NavLink to={{ pathname: "/technical", search }}>技术视图</NavLink></nav><QuestionToOutcomeJourney journeyId={supplierQualityJourneyId} onJourneyStarted={onJourneyStarted} /></main>;
}
