import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { ProductAssemblyError, type TraceabilityDTO } from "../api/productAssembly";
import { ControlledState } from "./ControlledState";
import { resourceViewLink } from "./ResourceContext";
import type { CanonicalUrlContext } from "./urlContext";
import { withUrlContext } from "./urlContext";

function Failure({error,retry}:{error:ProductAssemblyError;retry:()=>void}) {
  const hidden=error.status===403||error.status===404;
  return <ControlledState kind={hidden?(error.status===403?"denied":"not-found"):"unavailable"} title={hidden?"Resource context unavailable":"Evidence service unavailable"} detail={hidden?"The resource is absent or unavailable in your authorized scope.":error.reasonCode} action={!hidden?<button onClick={retry}>Retry</button>:undefined}/>;
}

export function TraceabilityProjection({context,perspective,data,error,retry}:{context:CanonicalUrlContext;perspective:"product"|"technical";data:TraceabilityDTO|null;error:ProductAssemblyError|null;retry:()=>void}) {
  if(error)return <Failure error={error} retry={retry}/>;
  if(!data)return <ControlledState kind="loading" title="Loading exact resource context"/>;
  return <section className="traceability-projection">
    <header><p className="eyebrow">{perspective} projection</p><h1>{data.subject.kind} · {data.subject.resourceId}</h1><p><code>{data.subject.revisionId}</code> · <code>{data.subject.digest}</code></p></header>
    <ViewLinks context={context}/>
    {perspective==="product"?<div className="traceability-list">{data.claims.map(claim=><article tabIndex={-1} id={`claim-${claim.claimKey}`} key={claim.claimKey}><h2>{claim.productLabel}</h2><span className={`badge ${claim.status==="SUPPORTED"?"":"warning"}`}>{claim.status}</span>{claim.limitationCodes.map(code=><code key={code}>{code}</code>)}<div>{claim.evidenceRefs.map(id=><Link key={id} to={resourceViewLink(withUrlContext(context,{evidenceId:id,claimKey:claim.claimKey}),"evidence")}>Evidence {id}</Link>)}</div>{claim.technicalFactKeys.map(key=><Link key={key} to={resourceViewLink(withUrlContext(context,{factKey:key,claimKey:claim.claimKey}),"technical")}>Technical fact {key}</Link>)}{claim.affectedBusinessStepIds.map(step=><span tabIndex={-1} id={`business-step-${step}`} key={step}>Business step: {step}</span>)}</article>)}</div>:<div className="traceability-list">{data.technicalFacts.map(fact=><article tabIndex={-1} id={`fact-${fact.factKey}`} key={fact.factKey}><h2>{fact.factKey}</h2><span className="badge">{fact.valueClassification}</span><pre>{JSON.stringify(fact.provenance,null,2)}</pre>{fact.affectedClaimKeys.map(key=><Link key={key} to={resourceViewLink(withUrlContext(context,{claimKey:key,factKey:fact.factKey}),"product")}>Affected claim {key}</Link>)}{fact.affectedBusinessStepIds.map(step=><Link key={step} to={resourceViewLink(withUrlContext(context,{businessStepId:step,factKey:fact.factKey}),"product")}>Affected business step {step}</Link>)}</article>)}</div>}
  </section>;
}

function ViewLinks({context}:{context:CanonicalUrlContext}) {return <nav className="view-switcher" aria-label="Resource projections"><Link to={resourceViewLink(context,"product")}>Product</Link><Link to={resourceViewLink(context,"technical")}>Technical</Link><Link to={resourceViewLink(context,"evidence")}>Evidence</Link></nav>}

export function EvidenceInspector({context,onClose,data,error,retry}:{context:CanonicalUrlContext;onClose:()=>void;data:TraceabilityDTO|null;error:ProductAssemblyError|null;retry:()=>void}) {
  const closeRef=useRef<HTMLButtonElement>(null);
  useEffect(()=>{closeRef.current?.focus()},[]);
  const selected=data?.evidence.find(item=>item.evidenceId===context.evidenceId)??data?.evidence[0];
  return <div className="evidence-backdrop" role="presentation"><section className="evidence-inspector" role="dialog" aria-modal="true" aria-labelledby="evidence-title"><header><div><p className="eyebrow">Derived private read model</p><h1 id="evidence-title">Evidence Inspector</h1></div><button ref={closeRef} onClick={onClose} aria-label="Close Evidence Inspector">Close</button></header>{error?<Failure error={error} retry={retry}/>:!data?<ControlledState kind="loading" title="Loading exact Evidence"/>:<><ViewLinks context={context}/>{selected?<article><h2>{selected.evidenceType}</h2><code>{selected.evidenceId}</code><dl><dt>Subject</dt><dd>{selected.subject.resourceId}</dd><dt>Revision</dt><dd>{selected.subject.revisionId}</dd><dt>Digest</dt><dd>{selected.subject.digest}</dd><dt>Observed</dt><dd>{selected.observedAt??"NOT_RECORDED"}</dd></dl><pre>{JSON.stringify(selected.provenance,null,2)}</pre></article>:<ControlledState kind="empty" title="No Evidence is recorded" detail="Absence is not represented as success or measured zero."/>}<div className="traceability-links">{data.claims.filter(item=>!context.claimKey||item.claimKey===context.claimKey).map(item=><Link key={item.claimKey} to={resourceViewLink(withUrlContext(context,{claimKey:item.claimKey}),"product")}>Claim: {item.productLabel}</Link>)}{data.technicalFacts.filter(item=>!context.factKey||item.factKey===context.factKey).map(item=><Link key={item.factKey} to={resourceViewLink(withUrlContext(context,{factKey:item.factKey}),"technical")}>Fact: {item.factKey}</Link>)}</div></>}</section></div>;
}
