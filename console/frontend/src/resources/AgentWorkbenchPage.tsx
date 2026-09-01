import { useEffect, useState } from "react";
import {
  AgentDefinitionRequestError,
  createAgentDefinition,
  getAgentDefinition,
  lifecycleAgentDefinition,
  listAgentDefinitions,
  publishAgentDefinition,
  reviewAgentDefinition,
  successorAgentDefinition,
  validateAgentDefinition,
  type AgentDefinition,
  type AgentContent,
  type AgentProjection,
} from "../api/agentDefinitions";
import { AgentTechnicalProjection } from "./AgentTechnicalProjection";
import { AgentBuilderPage } from "./AgentBuilderPage";
import { AgentVersionComparison } from "./AgentVersionComparison";

const supplierQuality = { title: "Supplier Quality Analyst", duties: ["analyze supplier quality"], data: ["quality records"], knowledge: ["supplier quality policy"], skills: ["root cause analysis"], capabilities: ["supplier-quality-analysis"], runtimes: ["native"], businessPurpose:"Analyze supplier quality", bindings:{skills:[],mcpTools:[],knowledge:[]} };

export function AgentWorkbenchPage() {
  const [items,setItems]=useState<AgentDefinition[]>([]); const [selected,setSelected]=useState<AgentProjection|null>(null);
  const [manifest,setManifest]=useState<string|null>(null);
  const [state,setState]=useState<"LOADING"|"READY"|"SAVING"|"ERROR">("LOADING"); const [error,setError]=useState<string|null>(null);
  async function refresh(id?:string){setState("LOADING");try{const definitions=await listAgentDefinitions();setItems(definitions);if(id)setSelected(await getAgentDefinition(id));setError(null);setState("READY")}catch(reason){setError(reason instanceof AgentDefinitionRequestError?reason.reasonCode:"AGENT_DEFINITION_UNAVAILABLE");setState("ERROR")}}
  useEffect(()=>{let active=true;listAgentDefinitions().then(definitions=>{if(!active)return;setItems(definitions);setState("READY")}).catch(reason=>{if(!active)return;setError(reason instanceof AgentDefinitionRequestError?reason.reasonCode:"AGENT_DEFINITION_UNAVAILABLE");setState("ERROR")});return()=>{active=false}},[]);
  async function create(){setState("SAVING");try{const value=await createAgentDefinition("Supplier Quality Analysis Agent",supplierQuality);await refresh(value.definition.definitionId)}catch(reason){setError(reason instanceof AgentDefinitionRequestError?reason.reasonCode:"CREATE_FAILED");setState("ERROR")}}
  async function createFromBuilder(name:string,content:AgentContent){setState("SAVING");try{const value=await createAgentDefinition(name,content);await refresh(value.definition.definitionId)}catch(reason){setError(reason instanceof AgentDefinitionRequestError?reason.reasonCode:"CREATE_FAILED");setState("ERROR")}}
  async function act(operation:(value:AgentDefinition)=>Promise<AgentProjection>){if(!selected)return;setState("SAVING");try{const value=await operation(selected.definition);setSelected(value);setItems(await listAgentDefinitions());setError(null);setState("READY")}catch(reason){setError(reason instanceof AgentDefinitionRequestError?reason.reasonCode:"ACTION_FAILED");setState("ERROR")}}
  const definition=selected?.definition; const draft=definition?.revisions.find(item=>item.revisionId===definition.currentDraftRevisionId); const review=definition?.reviews.at(-1);
  return <main className="agent-workbench"><header><p className="eyebrow">Enterprise Resource Workbench</p><h1>Agent Workbench</h1><p>Create, review, publish and inspect canonical Agent Definitions. PostgreSQL is authoritative; browser state is never lifecycle authority.</p></header>
    {state==="LOADING"&&<p role="status" className="agent-state">Loading authoritative Agent Definitions…</p>}
    {error&&<div role="alert" className="qto-alert"><strong>Action unavailable</strong><span className="technical-value">{error}</span><button onClick={()=>void refresh(definition?.definitionId)}>Retry</button></div>}
    <section className="agent-dashboard"><article><strong>{items.length}</strong><span>Definitions in scope</span></article><article><strong>{items.filter(item=>item.publishedRevisionId!==null&&item.enabled&&!item.archived&&!(["DEPRECATED","ARCHIVED"].includes(item.lifecycleState))).length}</strong><span>Published and eligible</span></article><article><strong>{items.filter(item=>item.currentDraftRevisionId!==null).length}</strong><span>Drafts requiring review</span></article></section>
    <AgentBuilderPage onCreate={createFromBuilder} saving={state==="SAVING"}/><div className="agent-layout"><aside><div className="agent-list-heading"><h2>Definitions</h2><button onClick={create} disabled={state==="SAVING"}>Create supplier-quality Agent</button></div>{items.length===0&&state==="READY"?<p className="agent-empty">No Agent Definitions yet. Create the first governed draft.</p>:<ul className="agent-list">{items.map(item=><li key={item.definitionId}><button className={definition?.definitionId===item.definitionId?"selected":""} onClick={()=>void refresh(item.definitionId)}><strong>{item.name}</strong><span>{item.lifecycleState} · v{item.aggregateVersion}</span></button></li>)}</ul>}</aside>
    <section className="agent-detail">{!definition?<div className="agent-empty"><h2>Select a Definition</h2><p>Its lifecycle, exact digests, relationships and history appear here.</p></div>:<><header><p className="eyebrow">{definition.lifecycleState} · {definition.enabled?"Enabled":"Disabled"}</p><h2>{definition.name}</h2><span className="technical-value">{definition.definitionId}</span></header>
      {draft&&<section className="agent-review-card"><h3>Current draft</h3><p>{draft.content.title}</p><div className="agent-tags">{draft.content.capabilities.map(item=><span key={item}>{item}</span>)}</div><label>Exact revision digest<input readOnly value={draft.digest}/></label><div className="agent-actions">{draft.state==="DRAFT"&&<button onClick={()=>act(value=>validateAgentDefinition(value.definitionId,value.aggregateVersion))}>Validate draft</button>}{draft.state==="VALIDATED"&&<button onClick={()=>act(value=>reviewAgentDefinition(value.definitionId,value.aggregateVersion,draft.digest))}>Human review exact digest</button>}{draft.state==="HUMAN_REVIEWED"&&review&&<button className="primary" onClick={()=>act(value=>publishAgentDefinition(value.definitionId,value.aggregateVersion,draft.digest,review.reviewId))}>Publish immutable revision</button>}</div></section>}
      <section><h3>Lifecycle actions</h3><div className="agent-actions">{definition.publishedRevisionId&&!definition.currentDraftRevisionId&&<button onClick={()=>act(value=>successorAgentDefinition(value.definitionId,value.aggregateVersion))}>Clone as successor draft</button>}<button onClick={()=>setManifest(JSON.stringify({manifestVersion:"agent-definition.v1",definitionId:definition.definitionId,revisionId:(draft??definition.revisions.at(-1))?.revisionId,digest:(draft??definition.revisions.at(-1))?.digest,content:(draft??definition.revisions.at(-1))?.content},null,2))}>Export bounded manifest</button><button onClick={()=>act(value=>lifecycleAgentDefinition(value.definitionId,value.enabled?"DISABLE":"ENABLE",value.aggregateVersion))}>{definition.enabled?"Disable":"Enable"}</button>{definition.publishedRevisionId&&<button onClick={()=>act(value=>lifecycleAgentDefinition(value.definitionId,"DEPRECATE",value.aggregateVersion))}>Deprecate</button>}<button onClick={()=>act(value=>lifecycleAgentDefinition(value.definitionId,"ARCHIVE",value.aggregateVersion))}>Archive</button></div>{manifest&&<pre aria-label="Bounded Agent manifest" className="technical-value">{manifest}</pre>}</section>
      <section><h3>Revision history</h3><ol className="agent-history">{definition.revisions.map(item=><li key={item.revisionId}><strong>{item.state}</strong><span className="technical-value">{item.revisionId}</span><span>{item.createdAt}</span></li>)}</ol><h3>Relationships and consumers</h3><p>{definition.relationships.length===0?"No authorized consumers recorded.":`${definition.relationships.length} consumers`}</p></section>
      <AgentVersionComparison revisions={definition.revisions}/><AgentTechnicalProjection projection={selected}/></>}</section></div>
  </main>;
}
