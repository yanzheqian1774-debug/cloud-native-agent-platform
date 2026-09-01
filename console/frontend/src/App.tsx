import {
  BrowserRouter,
  Link,
  Navigate,
  NavLink,
  Route,
  Routes,
  useLocation,
  useSearchParams,
  useNavigate,
} from "react-router-dom";
import { useEffect, useState } from "react";

import { ConsoleShell } from "./components/ConsoleShell";
import { WorkflowDetailPage } from "./pages/WorkflowDetailPage";
import { WorkflowRunsPage } from "./pages/WorkflowRunsPage";
import { ProductViewPage } from "./pages/ProductViewPage";
import { SelectedExecutionContext } from "./shared/SelectedExecutionContext";
import { TechPage } from "./pages/Technical\u0056iewPage";
import "./styles/app.css";
import { ExecutionPreviewError, fetchExecutionPreview, type PreviewMode } from "./api/executionPreview";
import { configureProductPreview, loadLiveProductPreview } from "./product/adapter";
import { configureTechnicalPreview, loadLiveTechnicalPreview } from "./technical/adapter";
import type { SharedExecutionSnapshot } from "./shared/executionSnapshotTypes";
import { fetchLivePlanningJourney } from "./api/livePlanningJourney";
import type { LivePlanningJourney, JourneyTaskProjection } from "./shared/livePlanningJourneyTypes";
import { ProblemPlanningPage } from "./problems/ProblemPlanningPage";
import { PlanningDirectoryPage } from "./problems/PlanningDirectoryPage";
import { AgentWorkbenchPage } from "./resources/AgentWorkbenchPage";
import { SkillWorkbenchPage } from "./resources/SkillWorkbenchPage";
import { McpWorkbenchPage } from "./resources/McpWorkbenchPage";
import { KnowledgeWorkbenchPage } from "./resources/KnowledgeWorkbenchPage";
import { WorkflowWorkbenchPage } from "./workflows/WorkflowWorkbenchPage";
import { RuntimeProfileWorkbenchPage } from "./runtime/RuntimeProfileWorkbenchPage";
import { ProductDashboardPage } from "./dashboard/ProductDashboardPage";
import { ResourceCatalogPage } from "./catalog/ResourceCatalogPage";
import { RelationshipsPage as UnifiedRelationshipsPage } from "./relationships/RelationshipsPage";
import { AttentionPage } from "./attention/AttentionPage";
import { DigitalEmployeesPage } from "./digital-employees/DigitalEmployeesPage";
import { EvidenceInspector } from "./shared/EvidenceInspector";
import { parseUrlContext } from "./shared/urlContext";
import { ControlledState } from "./shared/ControlledState";
import { getProductTraceability, type ProductAssemblyError, type TraceabilityDTO } from "./api/productAssembly";

function EvidencePage() {
  const location=useLocation(),navigate=useNavigate(),parsed=parseUrlContext(location.search);
  const context=parsed.state==="VALID"?parsed.context:{};
  const [traceability,setTraceability]=useState<TraceabilityDTO|null>(null),[traceabilityError,setTraceabilityError]=useState<ProductAssemblyError|null>(null),[retry,setRetry]=useState(0);
  useEffect(()=>{if(!context.kind||!context.resourceId||!context.revisionId||!context.digest)return;let active=true;getProductTraceability(context.kind,context.resourceId,context.revisionId,context.digest).then(value=>{if(active){setTraceability(value);setTraceabilityError(null)}}).catch(value=>active&&setTraceabilityError(value));return()=>{active=false}},[context.kind,context.resourceId,context.revisionId,context.digest,retry]);
  if(parsed.state==="INVALID"||!parsed.context.resourceId)return <main className="assembly-page"><ControlledState kind="not-found" title="Evidence context unavailable" detail="The URL context is invalid or unsupported."/></main>;
  const close=()=>{navigate(parsed.context.claimKey?`/product-view?${location.search.slice(1)}`:parsed.context.factKey?`/technical-view?${location.search.slice(1)}`:parsed.context.returnTo&&parsed.context.returnTo.startsWith("/")?parsed.context.returnTo:"/catalog");setTimeout(()=>document.getElementById(parsed.context.claimKey?`claim-${parsed.context.claimKey}`:`fact-${parsed.context.factKey}`)?.focus(),0)};
  return <EvidenceInspector context={parsed.context} onClose={close} data={traceability} error={traceabilityError} retry={()=>setRetry(value=>value+1)}/>;
}

type AppPreviewState = "LOADING" | "READY" | "DENIED" | "NOT_FOUND" | "AUTHORITY_MISSING" | "ERROR";

function useDemoJourney(journeyId: string | null) {
  const [loaded, setLoaded] = useState<{ id: string; journey: LivePlanningJourney | null } | null>(null);
  useEffect(() => {
    if (!journeyId) return;
    const controller = new AbortController();
    fetchLivePlanningJourney(journeyId, controller.signal).then(journey=>setLoaded({id:journeyId,journey})).catch(() => setLoaded({id:journeyId,journey:null}));
    return () => controller.abort();
  }, [journeyId]);
  return journeyId && loaded?.id === journeyId ? loaded.journey : null;
}

function Breadcrumb({ current, detail }: { current: string; detail?: string }) {
  return <nav className="demo-breadcrumb" aria-label="面包屑"><Link to="/workspace">工作台</Link><span>/</span><span>{current}</span>{detail&&<><span>/</span><strong>{detail}</strong></>}</nav>;
}

function technicalQuery(journey: LivePlanningJourney, task: JourneyTaskProjection, objectType: string, objectId: string) {
  const identity = journey.successor.identity;
  return `/technical?${new URLSearchParams({ objectType, objectId, revisionId: identity.canonicalWorkflowRevisionId, snapshotId: identity.sharedSnapshotId, step: objectType === "TASK" ? "plan" : "team", taskId: task.taskId })}`;
}

function demoStatus(value: string) {
  return ({PUBLISHED:"已发布",MATCHABLE:"已允许匹配",READY:"已准备",NOT_STARTED:"尚未开始",WAITING_DEPENDENCY:"等待前置任务",RUNNING:"进行中",SUCCEEDED:"已完成",FAILED:"未能完成",PENDING:"等待审批",APPROVED:"已批准",NOT_REQUESTED:"尚未执行",AUTHORIZED_HANDOFF:"已授权执行",PLACED:"已就绪",UNAVAILABLE:"当前不可用"} as Record<string,string>)[value]??"状态尚未采集";
}

function taskResponsibility(task: JourneyTaskProjection) {
  return task.actions.includes("REVIEW") ? "审查整改计划与执行边界。" : task.actions.includes("ANALYZE") ? "分析质量异常并形成有依据的根因判断。" : "汇总脱敏质量输入并形成可分析的证据集。";
}

function compactIdentity(value: string) { return value.length > 22 ? `${value.slice(0,10)}…${value.slice(-8)}` : value; }

type RelationshipNode={type:string;id:string;label:string;icon:string;task:JourneyTaskProjection};
function relationshipNodes(journey:LivePlanningJourney){
  const identity=journey.successor.identity; const outcome=journey.successor.outcome; const nodes:RelationshipNode[]=[];
  for(const task of journey.successor.projectedTasks) nodes.push(
    {type:"TASK",id:task.taskId,label:task.title,icon:"▣",task},
    ...task.definitionId?[{type:"AGENT_DEFINITION",id:task.definitionId,label:task.requiredRole,icon:"🤖",task}]:[],
    ...task.actions.map(id=>({type:"BUSINESS_CAPABILITY",id,label:id,icon:"🧭",task})),
    ...task.skills.map(id=>({type:"SKILL",id,label:id,icon:"🧰",task})),
    ...task.mcpCapabilities.map(id=>({type:"MCP_CAPABILITY",id,label:id,icon:"🔌",task})),
    ...task.knowledgeRefs.map(id=>({type:"KNOWLEDGE",id,label:id,icon:"📚",task})),
    ...task.runtimeRefs.map(id=>({type:"RUNTIME",id,label:id,icon:"⚙",task})),
  );
  const first=journey.successor.projectedTasks[0];
  if(first&&identity.platformExecutionIdentity) nodes.push({type:"EXECUTION_IDENTITY",id:identity.platformExecutionIdentity,label:"本次执行身份",icon:"◎",task:first});
  if(first) for(const id of identity.evidenceIds) nodes.push({type:"EVIDENCE",id,label:"执行证据",icon:"◇",task:first});
  if(first&&outcome) nodes.push({type:"OUTCOME",id:outcome.outcomeId,label:"业务结果",icon:"✓",task:first});
  return [...new Map(nodes.map(node=>[`${node.type}:${node.id}`,node])).values()];
}
function RelationshipSummary({journey,subject}:{journey:LivePlanningJourney;subject?:string}){
  const current=useLocation();
  const nodes=relationshipNodes(journey); const visible=subject?nodes.filter(node=>node.task.taskId===subject||node.id===subject):nodes;
  const types=new Set(visible.map(node=>node.type)).size;
  return <aside className="relationship-summary"><strong>{visible.length} 个相关对象 · {types} 种类型</strong><span>完整多对多关系仅在对象关系视图呈现。</span><Link to={`/relationships?${new URLSearchParams({selected:subject??visible[0]?.id??"",returnTo:current.pathname+current.search})}`}>打开完整对象关系 →</Link></aside>;
}
function RelationshipGraph({journey,task}:{journey:LivePlanningJourney;task:JourneyTaskProjection}){return <RelationshipSummary journey={journey} subject={task.taskId}/>}
function RelationshipsPage({journeyId}:{journeyId:string|null}){
  const journey=useDemoJourney(journeyId); const [params,setParams]=useSearchParams(); const filter=params.get("type")??"ALL"; const zoom=Math.min(3,Math.max(1,Number(params.get("zoom")??2))); const nodes=journey?relationshipNodes(journey):[]; const shown=filter==="ALL"?nodes:nodes.filter(node=>node.type===filter); const selectedId=params.get("selected")??shown[0]?.id; const selected=nodes.find(node=>node.id===selectedId)??shown[0]; const types=[...new Set(nodes.map(node=>node.type))];
  function update(key:string,value:string){const next=new URLSearchParams(params);next.set(key,value);setParams(next)}
  return <main className="demo-page"><Breadcrumb current="对象关系" detail={selected?.label}/><header className="demo-page-header"><p className="eyebrow">Object Relationships</p><h1>完整对象关系</h1><p>此处是当前旅程完整多对多关系的唯一图视图；对象清单在各功能页保持为列表或表格。</p></header>{!journey?<section className="empty-state"><h2>尚无关系快照</h2><p>先完成受控供应商质量旅程。</p><Link to="/product">提出问题</Link></section>:<section className="relationship-panel dedicated" aria-label="完整对象关系图"><div className="relationship-controls"><label>关系对象类型<select value={filter} onChange={event=>update("type",event.target.value)}><option value="ALL">全部类型</option>{types.map(type=><option key={type}>{type}</option>)}</select></label><div aria-label="图缩放"><button disabled={zoom===1} onClick={()=>update("zoom",String(zoom-1))}>缩小</button><span>{zoom===1?"紧凑":zoom===2?"标准":"放大"}</span><button disabled={zoom===3} onClick={()=>update("zoom",String(zoom+1))}>放大</button></div></div><div className={`semantic-graph graph-zoom-${zoom}`}>{shown.map(node=><button key={`${node.type}:${node.id}`} className={selected?.id===node.id?"semantic-node selected":"semantic-node"} aria-pressed={selected?.id===node.id} onClick={()=>update("selected",node.id)}><span aria-hidden="true">{node.icon}</span><strong>{node.label}</strong><small>{node.type}</small></button>)}</div>{selected&&<aside className="relationship-detail"><p className="eyebrow">当前选择</p><h2>{selected.label}</h2><p>与任务“{selected.task.title}”直接关联；筛选不会改变所选对象身份。</p><details><summary>查看精确技术身份与修订</summary><span className="technical-value">{selected.type} · {selected.id}</span><span className="technical-value">Revision · {journey.successor.identity.canonicalWorkflowRevisionId}</span><span className="technical-value">Snapshot · {journey.successor.identity.sharedSnapshotId}</span></details><div className="relationship-links"><Link to={technicalQuery(journey,selected.task,selected.type,selected.id)}>打开精确对象详情 →</Link>{params.get("returnTo")&&<Link to={params.get("returnTo")!}>返回原上下文</Link>}</div></aside>}</section>}</main>;
}

function WorkspacePage({ journeyId }: { journeyId: string | null }) {
  const journey = useDemoJourney(journeyId); const revision = journey?.successor;
  const running = revision?.projectedTasks.filter(task=>task.state==="RUNNING").length??0;
  const completed = revision?.projectedTasks.filter(task=>task.state==="SUCCEEDED").length??0;
  const pending = revision?.approvalState==="PENDING"?1:0;
  const employees = new Set(revision?.projectedTasks.map(task=>task.definitionId).filter(Boolean)).size;
  return <main className="demo-page workspace-page"><Breadcrumb current="工作台"/><header className="workspace-hero"><p className="eyebrow">工作台 · Workspace</p><h1>从业务问题到有依据的结果</h1><p>提出问题，审查系统理解与数字员工团队，批准精确计划，再查看执行和 Evidence。</p><Link className="primary-link" to="/product">提出问题</Link></header><section className="workspace-question"><div><p className="eyebrow">我可以解决什么问题？</p><h2>供应商交付质量下降分析与整改</h2><p>示例：某供应商近期交付质量持续下降，请分析原因，制定整改计划，并在审批后执行和验证改善效果。</p></div><Link to="/product">发起供应商质量分析 →</Link></section><div className="workspace-grid"><section><h2>任务进展</h2><dl className="workspace-counts"><div><dt>运行中</dt><dd>{running}</dd></div><div><dt>等待审批</dt><dd>{pending}</dd></div><div><dt>已完成</dt><dd>{completed}</dd></div></dl><Link to="/tasks">打开任务中心</Link></section><section><h2>需要我处理</h2>{pending?<p><strong>供应商质量整改计划</strong><br/>等待审查并批准精确计划。</p>:<p className="empty-state">当前没有等待审批的操作。</p>}{revision&&<Link to="/product?step=approval">返回当前旅程</Link>}</section><section><h2>最近完成</h2>{revision?.outcome?<p><strong>{revision.outcome.summary}</strong><br/>{revision.outcome.comparableMetric} = {revision.outcome.comparableValue}</p>:<p className="empty-state">当前 Demo 尚无已完成结果。</p>}</section><section><h2>数字员工团队</h2>{revision?<p>{employees} 个数字员工定义参与当前方案，承担 {revision.projectedTasks.length} 个任务。</p>:<p className="empty-state">提出问题后，将显示本次方案匹配的数字员工。</p>}<Link to="/employees">查看数字员工</Link></section></div><section className="demo-scope"><h2>当前 Demo 的能力和限制</h2><p>仅支持经过脱敏的供应商质量问题。理解、分解与计划由受限确定性规则生成；执行使用进程内受控权威，不代表生产 SLA、HA、持久化 Agent Instance 或 Model 参与。</p><p className="future-note">后续边界：v0.2.1 将提供动态问题理解、Blueprint 匹配与资源选择；v0.2.2 将提供更广泛的 Runtime/OpenClaw 执行与反馈闭环。本 Demo 未实现这些能力。</p></section></main>;
}

function TaskCenterPage({ journeyId }: { journeyId: string | null }) {
  const journey=useDemoJourney(journeyId); const [params]=useSearchParams(); const filter=params.get("filter")??"all"; const tasks=journey?.successor.projectedTasks??[];
  const visible=tasks.filter(task=>filter==="all"||(filter==="running"&&task.state==="RUNNING")||(filter==="approval"&&journey?.successor.approvalState==="PENDING")||(filter==="failed"&&task.state==="FAILED")||(filter==="completed"&&task.state==="SUCCEEDED"));
  const filters=[["all","全部"],["running","运行中"],["approval","等待审批"],["failed","执行失败"],["completed","已完成"]];
  return <main className="demo-page"><Breadcrumb current="任务"/><header className="demo-page-header"><p className="eyebrow">任务中心 · Task Center</p><h1>任务</h1><p>查看当前受控旅程中的业务任务、负责人和下一步操作。</p></header><nav className="filter-tabs" aria-label="任务筛选">{filters.map(([id,label])=><Link className={filter===id?"active":""} key={id} to={`/tasks?filter=${id}`}>{label}</Link>)}</nav>{visible.length===0?<section className="empty-state"><h2>当前没有{filters.find(item=>item[0]===filter)?.[1]}任务</h2><p>这里不会生成虚构任务；请从工作台发起受支持的问题。</p><Link to="/workspace">返回工作台</Link></section>:<div className="task-center-list">{visible.map(task=><article key={task.taskId}><div><p className="eyebrow">第 {tasks.indexOf(task)+1} 步任务</p><h2>{task.title}</h2><p>{taskResponsibility(task)}</p></div><dl><dt>当前旅程步骤</dt><dd>{journey?.successor.outcome?"结果":"修正与审批"}</dd><dt>负责数字员工</dt><dd>{task.requiredRole} · {task.matchedRole}</dd><dt>业务状态</dt><dd>{demoStatus(task.state)}</dd><dt>最后更新</dt><dd>当前快照未采集更新时间</dd><dt>下一步</dt><dd>{journey?.successor.outcome?"查看结果与 Evidence":journey?.successor.approvalState==="PENDING"?"人工审查并批准":"等待前置任务"}</dd></dl><Link to={`/product?${new URLSearchParams({taskId:task.taskId,objectType:"TASK",objectId:task.taskId,revisionId:journey!.successor.identity.canonicalWorkflowRevisionId,snapshotId:journey!.successor.identity.sharedSnapshotId,step:"plan"})}`}>打开精确任务 →</Link></article>)}</div>}</main>;
}

function EmployeesPage({ journeyId }: { journeyId: string | null }) {
  const journey=useDemoJourney(journeyId); const tasks=journey?.successor.projectedTasks??[]; const ids=[...new Set(tasks.map(task=>task.definitionId).filter((id):id is string=>Boolean(id)))]; const [params,setParams]=useSearchParams(); const selectedId=params.get("employee")??ids[0]; const used=tasks.filter(task=>task.definitionId===selectedId); const first=used[0]; const section=params.get("section")??"overview";
  const tabs=[["overview","概览"],["tasks","负责的任务"],["capabilities","业务能力"],["tools","Skill与工具"],["knowledge","Knowledge"],["runtime","Runtime"],["records","执行记录"],["relationships","对象关系"]];
  function choose(next:Record<string,string>){const value=new URLSearchParams(params);Object.entries(next).forEach(([key,item])=>value.set(key,item));setParams(value)}
  return <main className="demo-page"><Breadcrumb current="数字员工" detail={first?.requiredRole}/><header className="demo-page-header"><p className="eyebrow">数字员工 · Digital Employees</p><h1>当前 Demo 可用的数字员工</h1><p>仅显示当前供应商质量旅程实际引用的已发布定义。</p></header>{ids.length===0?<section className="empty-state"><h2>当前没有已匹配数字员工</h2><p>提出问题后，系统将显示实际匹配结果，不会创建虚构员工。</p><Link to="/product">提出问题</Link></section>:<div className="master-detail"><nav className="master-list" aria-label="数字员工列表">{ids.map(id=>{const item=tasks.find(task=>task.definitionId===id)!;return <button aria-pressed={selectedId===id} className={selectedId===id?"selected":""} key={id} onClick={()=>choose({employee:id})}><strong>{item.requiredRole}</strong><small>{item.matchedRole}</small></button>})}</nav><div className="detail-pane"><nav className="context-tabs" aria-label="数字员工详情导航">{tabs.map(([id,label])=><button aria-pressed={section===id} key={id} onClick={()=>choose({section:id})}>{label}</button>)}</nav>{first&&<article className="primary-object-detail"><p className="eyebrow">Agent Definition</p><h2>{first.requiredRole}</h2><p>{first.matchedRole}</p>{section==="overview"&&<><dl><dt>业务责任</dt><dd>{first.actions.includes("REVIEW")?"审查整改计划、Human 边界与执行条件。":"汇总并分析脱敏供应商质量事实，形成有依据的判断。"}</dd><dt>可用性与授权</dt><dd>{demoStatus(first.publicationState)} · {demoStatus(first.matchAuthorization)} · {demoStatus(first.readiness)}<details><summary>查看原始状态</summary><span className="technical-value">{first.publicationState} · {first.matchAuthorization} · {first.readiness}</span></details></dd><dt>当前或最近参与</dt><dd>{used.map(task=>`${task.title} (${demoStatus(task.state)})`).join("、")}</dd></dl><RelationshipSummary journey={journey!} subject={first.taskId}/></>}{section==="tasks"&&<dl><dt>分配任务</dt><dd>{used.map(task=>task.title).join("、")}</dd><dt>业务目标</dt><dd>完成分配任务并为当前供应商质量整改计划提供可核验产出。</dd><dt>Task-specific bindings</dt><dd>{used.flatMap(task=>[...task.skills,...task.mcpCapabilities]).join("、")}</dd></dl>}{section==="capabilities"&&<dl><dt>业务能力</dt><dd>{[...new Set(used.flatMap(task=>task.actions))].join("、")}</dd><dt>覆盖任务</dt><dd>{used.map(task=>task.title).join("、")}</dd></dl>}{section==="tools"&&<dl><dt>Skills</dt><dd>{[...new Set(used.flatMap(task=>task.skills))].join("、")}</dd><dt>MCP/Tools</dt><dd>{[...new Set(used.flatMap(task=>task.mcpCapabilities))].join("、")}</dd><dt>调用就绪</dt><dd>{demoStatus(first.readiness)}</dd></dl>}{section==="knowledge"&&<dl><dt>Knowledge</dt><dd>{[...new Set(used.flatMap(task=>task.knowledgeRefs))].join("、")}</dd><dt>引用与影响</dt><dd>{journey!.successor.citations.length} 个授权引用</dd></dl>}{section==="runtime"&&<dl><dt>Runtime 要求</dt><dd>{[...new Set(used.flatMap(task=>task.runtimeRefs))].join("、")}</dd><dt>Placement</dt><dd>{compactIdentity(journey!.successor.identity.placementDecisionId)}</dd><dt>真实可用性</dt><dd>{demoStatus(first.readiness)}</dd></dl>}{section==="records"&&<dl><dt>执行记录</dt><dd>{used.map(task=>`${task.title} · ${demoStatus(task.state)}`).join("、")}</dd><dt>执行身份</dt><dd>{journey!.successor.identity.platformExecutionIdentity?compactIdentity(journey!.successor.identity.platformExecutionIdentity):"尚未签发"}</dd><dt>Evidence</dt><dd>{journey!.successor.identity.evidenceIds.length} 条</dd></dl>}{section==="relationships"&&<RelationshipSummary journey={journey!} subject={selectedId}/>}<Link to={technicalQuery(journey!,first,"AGENT_DEFINITION",selectedId!)}>查看业务/技术映射 →</Link></article>}</div></div>}</main>;
}

function ResourcesPage({ journeyId }: { journeyId: string | null }) {
  const journey=useDemoJourney(journeyId); const tasks=journey?.successor.projectedTasks??[]; const groups=[{id:"capability",title:"业务能力",en:"Business Capability",type:"BUSINESS_CAPABILITY",field:"actions" as const},{id:"skill",title:"Skill",en:"Skill",type:"SKILL",field:"skills" as const},{id:"mcp",title:"MCP与工具",en:"MCP / Tools",type:"MCP_CAPABILITY",field:"mcpCapabilities" as const},{id:"knowledge",title:"Knowledge",en:"Knowledge",type:"KNOWLEDGE",field:"knowledgeRefs" as const}]; const [params,setParams]=useSearchParams(); const active=groups.find(item=>item.id===(params.get("category")??"capability"))??groups[0]; const ids=[...new Set(tasks.flatMap(task=>task[active.field]))]; const selected=params.get("object")??ids[0]; const used=tasks.filter(task=>task[active.field].includes(selected)); const first=used[0];
  function choose(next:Record<string,string>){const value=new URLSearchParams(params);Object.entries(next).forEach(([key,item])=>value.set(key,item));if(next.category)value.delete("object");setParams(value)}
  return <main className="demo-page"><Breadcrumb current="能力与资源" detail={selected}/><header className="demo-page-header"><p className="eyebrow">能力与资源 · Capabilities and Resources</p><h1>当前 Demo 可用的能力与资源</h1><p>业务能力、Skill、MCP/Tool 与 Knowledge 保持独立语义。</p></header>{tasks.length===0?<section className="empty-state"><h2>当前没有资源映射</h2><p>资源只在真实旅程引用后出现。</p><Link to="/product">提出问题</Link></section>:<><nav className="context-tabs" aria-label="资源类别导航">{groups.map(group=><button aria-pressed={active.id===group.id} key={group.id} onClick={()=>choose({category:group.id})}>{group.title}</button>)}</nav><div className="master-detail"><nav className="master-list" aria-label={`${active.title}列表`}>{ids.map(id=><button aria-pressed={selected===id} className={selected===id?"selected":""} key={id} onClick={()=>choose({object:id})}><strong>{id}</strong><small>{active.en}</small></button>)}</nav>{first&&<div className="detail-pane"><article className="primary-object-detail"><p className="eyebrow">{active.en}</p><h2>{selected}</h2><dl><dt>这是什么</dt><dd>{active.title}对象</dd><dt>能解决什么问题</dt><dd>{used.map(task=>taskResponsibility(task)).join("；")}</dd><dt>使用它的数字员工</dt><dd>{[...new Set(used.map(task=>task.matchedRole))].join("、")}</dd><dt>使用任务</dt><dd>{used.map(task=>task.title).join("、")}</dd><dt>依赖</dt><dd>{active.field==="actions"?[...new Set(used.flatMap(task=>task.skills))].join("、")||"未采集":active.field==="skills"?[...new Set(used.flatMap(task=>task.mcpCapabilities))].join("、")||"未采集":"当前版本尚未采集该依赖事实"}</dd><dt>可用与授权</dt><dd>{used.every(task=>task.readiness==="READY")?"已允许且可用":"当前不可用"}</dd></dl><RelationshipGraph journey={journey!} task={first}/><Link to={technicalQuery(journey!,first,active.type,selected!)}>查看精确技术身份 →</Link></article></div>}</div></>}</main>;
}

function RuntimePage({ journeyId }: { journeyId: string | null }) {
  const journey=useDemoJourney(journeyId); const revision=journey?.successor; const tasks=revision?.projectedTasks??[]; const runtime=[...new Set(tasks.flatMap(task=>task.runtimeRefs))][0]; const first=tasks[0]; const [params,setParams]=useSearchParams(); const section=params.get("section")??"overview"; const tabs=[["overview","概览"],["placement","运行位置"],["participants","参与对象"],["records","执行记录"],["events","事件"],["limits","运行限制"]];
  return <main className="demo-page"><Breadcrumb current="运行环境" detail={runtime}/><header className="demo-page-header"><p className="eyebrow">运行环境 · Runtime</p><h1>当前 Demo Runtime</h1><p>说明当前旅程在哪里运行、如何放置，以及哪些事实尚未采集。</p></header>{!revision||!runtime?<section className="empty-state"><h2>尚未建立 Runtime 映射</h2><p>先发起受支持的问题；系统不会推断 Provider、Model 或遥测。</p><Link to="/product">提出问题</Link></section>:<><nav className="context-tabs" aria-label="Runtime 详情导航">{tabs.map(([id,label])=><button aria-pressed={section===id} key={id} onClick={()=>{const next=new URLSearchParams(params);next.set("section",id);setParams(next)}}>{label}</button>)}</nav><section className="runtime-overview"><h2>{runtime} <small>Runtime</small></h2>{section==="overview"&&<dl><dt>Runtime 类型</dt><dd>{runtime}</dd><dt>当前服务或执行状态</dt><dd>{demoStatus(revision.executionState)}</dd><dt>已采集运行事实</dt><dd>{revision.identity.platformExecutionIdentity?<><span>执行身份 {compactIdentity(revision.identity.platformExecutionIdentity)}</span><details><summary>查看精确技术标识</summary><span className="technical-value">{revision.identity.platformExecutionIdentity}</span></details></>:"尚未签发执行身份"}</dd></dl>}{section==="placement"&&<dl><dt>运行位置</dt><dd>本机受控非生产 Demo 进程</dd><dt>Placement</dt><dd>{compactIdentity(revision.identity.placementDecisionId)}<details><summary>查看精确技术标识</summary><span className="technical-value">{revision.identity.placementDecisionId}</span></details></dd></dl>}{section==="participants"&&<dl><dt>数字员工</dt><dd>{[...new Set(tasks.map(task=>task.requiredRole))].join("、")}</dd><dt>任务</dt><dd>{tasks.map(task=>task.title).join("、")}</dd></dl>}{section==="records"&&<dl><dt>执行身份</dt><dd>{revision.identity.platformExecutionIdentity?compactIdentity(revision.identity.platformExecutionIdentity):"尚未签发"}<details><summary>查看精确技术标识</summary><span className="technical-value">{revision.identity.platformExecutionIdentity??"NOT_ISSUED"}</span></details></dd><dt>任务状态</dt><dd>{tasks.map(task=>`${task.title} · ${demoStatus(task.state)}`).join("、")}</dd></dl>}{section==="events"&&<div className="empty-state"><h3>事件由执行现场提供</h3><p>{revision.identity.platformExecutionIdentity?"打开技术视图查看当前执行的权威事件序列。":"尚未执行，因此没有执行事件。"}</p></div>}{section==="limits"&&<dl><dt>Provider / Model / 遥测</dt><dd>当前版本尚未采集该运行信息。</dd><dt>限制</dt><dd>非生产 Demo；不声明 SLA、HA、持久化 Agent Instance 或 Model 参与。</dd></dl>}<RelationshipGraph journey={journey!} task={first}/><Link to={technicalQuery(journey!,first,"EXECUTION_RUNTIME",revision.identity.platformExecutionIdentity??runtime)}>打开 Runtime 技术视图 →</Link></section></>}</main>;
}

// Preserved v0.2.0 reference projections remain compiled but are not routed in
// the v0.2.1 production review surface.
void [RelationshipsPage,WorkspacePage,TaskCenterPage,EmployeesPage,ResourcesPage,RuntimePage];

function configuredMode(): PreviewMode {
  return import.meta.env.VITE_EXECUTION_PREVIEW_MODE === "live" ? "live" : "synthetic-preview";
}

function LiveExecutionView({ snapshot, context }: { snapshot: SharedExecutionSnapshot; context: "PRODUCT" | "TECHNICAL" }) {
  const product = loadLiveProductPreview();
  const technical = loadLiveTechnicalPreview();
  if (product.platformExecutionIdentity !== technical.selectedContext.executionId || product.graphSnapshotId !== technical.selectedContext.graphSnapshotId) {
    throw new Error("CROSS_VIEW_IDENTITY_MISMATCH");
  }
  return <main className={context === "PRODUCT" ? "product-page" : "technical-page"}>
    <nav className="view-switcher" aria-label="Product and Technical views"><NavLink to="/product">Product View</NavLink><NavLink to="/technical">Technical View</NavLink></nav>
    <header className={context === "PRODUCT" ? "product-hero" : "technical-hero"}><p className="eyebrow">AUTHORIZED LIVE TECHNICAL PREVIEW</p><h1>{context === "PRODUCT" ? "Execution Product View" : "Execution Technical View"}</h1><p>Sibling projection over one authorized, fixed-high-water execution snapshot.</p></header>
    <section className="preview-warning" role="status"><strong>LIVE · {snapshot.readModelState}</strong><span>Never backed by synthetic fixture data.</span></section>
    <section className="product-section panel-pad" aria-labelledby="live-identity"><h2 id="live-identity">Shared execution identity</h2><dl className="evidence-list"><dt>Platform Execution Identity</dt><dd className="stable-id">{snapshot.selectedContext.executionId}</dd><dt>Shared snapshot identity</dt><dd className="stable-id">{snapshot.sharedSnapshotId}</dd><dt>Canonical Graph identity</dt><dd className="stable-id">{snapshot.selectedContext.graphSnapshotId}</dd><dt>Read-model state</dt><dd className="stable-id">{snapshot.readModelState}</dd></dl></section>
    <section className="product-section panel-pad" aria-labelledby="live-outcome"><h2 id="live-outcome">Authorization and outcome</h2><dl className="evidence-list"><dt>Decision</dt><dd className="stable-id">{snapshot.authorization.decision}</dd><dt>Reason code</dt><dd className="stable-id">{snapshot.authorization.reasonCode}</dd><dt>Provider calls</dt><dd>{snapshot.authorization.providerCallCount}</dd><dt>Execution outcome</dt><dd className="stable-id">{snapshot.outcome.status}</dd></dl>{snapshot.outcome.status !== "PASS" && <p role="alert">This execution is not presented as a verified success.</p>}{snapshot.readModelState !== "COMPLETE" && <p role="alert">The execution outcome is preserved, but this evidence snapshot is not complete and must not be treated as verified complete.</p>}</section>
    <section className="product-section panel-pad" aria-labelledby="live-graph"><h2 id="live-graph">Canonical Graph evidence</h2><p>{snapshot.nodes.length} nodes · {(snapshot.canonicalRelations ?? []).length} relations. Relations are rendered exactly as supplied by the authorized snapshot.</p>{(snapshot.canonicalRelations ?? []).map((relation) => <details key={relation.relation_id}><summary className="stable-id">{relation.source_node_id} → {relation.target_node_id}</summary><p className="stable-id">{relation.relation_types.join(" · ")} · {relation.declared_cardinality} · {relation.evidence_ids.join(", ")}</p></details>)}</section>
    <section className="product-section panel-pad" aria-labelledby="live-evidence"><h2 id="live-evidence">Evidence and citations</h2><p className="stable-id">{(snapshot.authorizedEvidenceReferences ?? []).map((item) => item.referenceIdentity).join(", ") || "NO_EVIDENCE_REFERENCES"}</p><p className="stable-id">{(snapshot.authorizedCitations ?? []).map((item) => item.referenceIdentity).join(", ") || "NO_AUTHORIZED_CITATIONS"}</p>{snapshot.limitations.map((code) => <p className="stable-id" key={code}>{code}</p>)}</section>
  </main>;
}

function App() {
  const technicalPath = "/technical";
  const mode = configuredMode();
  const supplierQualityLive = import.meta.env.VITE_SUPPLIER_QUALITY_DEMO_MODE === "live";
  const [previewState, setPreviewState] = useState<AppPreviewState>(mode === "live" ? "LOADING" : "READY");
  const [reasonCode, setReasonCode] = useState(mode === "live" ? "PREVIEW_LOADING" : "SYNTHETIC_PREVIEW_EXPLICIT");
  const [liveSnapshot, setLiveSnapshot] = useState<SharedExecutionSnapshot | null>(null);
  useEffect(() => {
    if (supplierQualityLive) return;
    if (mode === "synthetic-preview") {
      configureProductPreview(mode);
      configureTechnicalPreview(mode);
      return;
    }
    const controller = new AbortController();
    const namespace = import.meta.env.VITE_EXECUTION_PREVIEW_NAMESPACE ?? "agent-workloads";
    const workflow = import.meta.env.VITE_EXECUTION_PREVIEW_WORKFLOW ?? "example-workflow";
    const task = import.meta.env.VITE_EXECUTION_PREVIEW_TASK ?? "example-task";
    fetchExecutionPreview(namespace, workflow, task, controller.signal).then((snapshot) => {
      configureProductPreview("live", snapshot);
      configureTechnicalPreview("live", snapshot);
      setLiveSnapshot(snapshot);
      setReasonCode(snapshot.readModelState ?? "ERROR");
      setPreviewState("READY");
    }).catch((error: unknown) => {
      if (controller.signal.aborted) return;
      const failure = error instanceof ExecutionPreviewError ? error : new ExecutionPreviewError("ERROR", "PREVIEW_INTERNAL_ERROR");
      setReasonCode(failure.reasonCode);
      setPreviewState(failure.state);
    });
    return () => controller.abort();
  }, [mode, supplierQualityLive]);
  if (supplierQualityLive) {
    return <BrowserRouter><SelectedExecutionContext><ConsoleShell><Routes><Route path="/" element={<Navigate to="/dashboard" replace />} /><Route path="/dashboard" element={<ProductDashboardPage/>}/><Route path="/catalog" element={<ResourceCatalogPage/>}/><Route path="/digital-employees" element={<DigitalEmployeesPage/>}/><Route path="/attention" element={<AttentionPage/>}/><Route path="/relationships" element={<UnifiedRelationshipsPage/>}/><Route path="/problems" element={<ProblemPlanningPage/>} /><Route path="/agents" element={<AgentWorkbenchPage/>} /><Route path="/skills" element={<SkillWorkbenchPage/>} /><Route path="/mcp" element={<McpWorkbenchPage/>} /><Route path="/knowledge" element={<KnowledgeWorkbenchPage/>} /><Route path="/workflow-definitions" element={<WorkflowWorkbenchPage/>} /><Route path="/runtime-profiles" element={<RuntimeProfileWorkbenchPage/>} /><Route path="/workspace" element={<PlanningDirectoryPage kind="workspace"/>} /><Route path="/product" element={<PlanningDirectoryPage kind="workspace"/>} /><Route path="/product-view" element={<ProductViewPage/>}/><Route path="/technical-view" element={<TechPage/>}/><Route path="/evidence" element={<EvidencePage/>}/><Route path="/tasks" element={<PlanningDirectoryPage kind="plans"/>} /><Route path="/employees" element={<DigitalEmployeesPage/>} /><Route path="/resources" element={<ResourceCatalogPage/>} /><Route path="/runtime" element={<PlanningDirectoryPage kind="runtime"/>} /><Route path={technicalPath} element={<PlanningDirectoryPage kind="technical"/>} /><Route path="*" element={<Navigate to="/dashboard" replace />} /></Routes></ConsoleShell></SelectedExecutionContext></BrowserRouter>;
  }
  if (previewState !== "READY") {
    return <main className="product-page"><section className="preview-warning" role={previewState === "LOADING" ? "status" : "alert"} aria-live="polite"><strong>{mode.toUpperCase()} · {previewState}</strong><span className="stable-id">{reasonCode}</span></section></main>;
  }
  if (mode === "live" && liveSnapshot) {
    return <BrowserRouter><ConsoleShell><Routes><Route path="/" element={<Navigate to="/product" replace />} /><Route path="/product" element={<LiveExecutionView snapshot={liveSnapshot} context="PRODUCT" />} /><Route path={technicalPath} element={<LiveExecutionView snapshot={liveSnapshot} context="TECHNICAL" />} /><Route path="*" element={<Navigate to="/product" replace />} /></Routes></ConsoleShell></BrowserRouter>;
  }
  return (
    <BrowserRouter>
      <SelectedExecutionContext>
        <ConsoleShell>
        <div className="preview-warning" role="status"><strong>{mode === "live" ? `LIVE · ${reasonCode}` : "SYNTHETIC · NON-AUTHORITATIVE"}</strong></div>
        <Routes>
          <Route
            path="/"
            element={
              <Navigate
                to="/product"
                replace
              />
            }
          />

          <Route path="/product" element={<ProductViewPage />} />

          <Route path={technicalPath} element={<TechPage />} />

          <Route
            path="/workflows"
            element={<WorkflowRunsPage />}
          />

          <Route
            path="/workflows/:namespace/:name"
            element={<WorkflowDetailPage />}
          />
        </Routes>
        </ConsoleShell>
      </SelectedExecutionContext>
    </BrowserRouter>
  );
}

export default App;
