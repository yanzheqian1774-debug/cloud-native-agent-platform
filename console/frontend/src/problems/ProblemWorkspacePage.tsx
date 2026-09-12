import {useCallback,useEffect,useMemo,useRef,useState} from "react";
import {useSearchParams} from "react-router-dom";
import {WorkbenchRequestError,createBusinessProblem,listBusinessProblems,newIdempotencyKey,readBusinessProblem,readCriteriaSets,readProblemCriteria,readWorkbenchSession,reviseBusinessProblem,writeCriteriaSet,writeCriterion,type BusinessProblemDetail,type BusinessProblemRevision,type CriteriaSetRevision,type CriterionRevision,type WorkbenchSession} from "../api/businessWorkspace";

type Workspace={detail:BusinessProblemDetail;criteria:CriterionRevision[];sets:CriteriaSetRevision[]};
type Draft={title:string;description:string;criterion:string};
const EMPTY:Draft={title:"",description:"",criterion:""};
const latest=<T extends {revision:number}>(values:T[])=>[...values].sort((a,b)=>b.revision-a.revision)[0];
const readable=(value:string)=>new Intl.DateTimeFormat("zh-CN",{year:"numeric",month:"long",day:"numeric",hour:"2-digit",minute:"2-digit",timeZoneName:"short"}).format(new Date(value));
const reason=(error:unknown)=>error instanceof WorkbenchRequestError?`${error.reasonCode}${error.requestId?` · ${error.requestId}`:""}`:"WORKBENCH_UNAVAILABLE";

export function ProblemWorkspacePage(){
  const [params,setParams]=useSearchParams();
  const [session,setSession]=useState<WorkbenchSession|null>(null),[problems,setProblems]=useState<BusinessProblemRevision[]>([]),[workspace,setWorkspace]=useState<Workspace|null>(null);
  const [draft,setDraft]=useState<Draft>(EMPTY),[saved,setSaved]=useState<Draft>(EMPTY);
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(""),[loginRequired,setLoginRequired]=useState(false);
  const epoch=useRef(0),idempotency=useRef<Record<string,{fingerprint:string;key:string}>>({}),initialProblem=useRef(params.get("problem")),selectedId=params.get("problem"),dirty=JSON.stringify(draft)!==JSON.stringify(saved);

  function operationKey(operation:string,payload:unknown){const fingerprint=JSON.stringify(payload),current=idempotency.current[operation];if(current?.fingerprint===fingerprint)return current.key;const key=newIdempotencyKey(operation);idempotency.current[operation]={fingerprint,key};return key}
  function completeOperation(...operations:string[]){for(const operation of operations)delete idempotency.current[operation]}

  const loadWorkspace=useCallback(async(problemId:string)=>{
    const token=++epoch.current;
    const [detail,sets,criteria]=await Promise.all([readBusinessProblem(problemId),readCriteriaSets(problemId),readProblemCriteria(problemId)]);
    if(token!==epoch.current)return;
    const problemRevision=detail.revisions.find(item=>item.revision_id===detail.problem.current_revision_id)??latest(detail.revisions);
    const set=latest(sets.revisions),criterion=set?criteria.revisions.find(item=>item.revision_id===set.ordered_criterion_revision_ids[0]):undefined;
    const next={title:problemRevision?.title??"",description:problemRevision?.description??"",criterion:String(criterion?.measurement.rubric??"")};
    setWorkspace({detail,sets:sets.revisions,criteria:criteria.revisions});setDraft(next);setSaved(next);setError("");
  },[]);
  const reloadList=useCallback(async()=>setProblems((await listBusinessProblems()).problems),[]);

  useEffect(()=>{let active=true;(async()=>{try{const current=await readWorkbenchSession();if(!active)return;setSession(current);const listed=await listBusinessProblems();if(!active)return;setProblems(listed.problems);if(initialProblem.current)await loadWorkspace(initialProblem.current)}catch(failure){if(active){setLoginRequired(failure instanceof WorkbenchRequestError&&failure.status===401);setError(reason(failure))}}finally{if(active)setLoading(false)}})();return()=>{active=false;epoch.current+=1}},[loadWorkspace]);
  useEffect(()=>{const warn=(event:BeforeUnloadEvent)=>{if(dirty){event.preventDefault();event.returnValue=""}};window.addEventListener("beforeunload",warn);return()=>window.removeEventListener("beforeunload",warn)},[dirty]);

  async function select(problemId:string){if(dirty&&!window.confirm("当前问题有未保存修改。确定放弃并切换吗？"))return;setParams({problem:problemId});setBusy(true);setError("");try{await loadWorkspace(problemId)}catch(failure){setError(reason(failure))}finally{setBusy(false)}}
  async function create(){if(!session||busy||!draft.title.trim()||!draft.description.trim())return;const payload={title:draft.title.trim(),description:draft.description.trim(),ownerId:session.principal.principalId};setBusy(true);setError("");try{const created=await createBusinessProblem(session.csrfToken,{...payload,idempotencyKey:operationKey("create-problem",payload)});completeOperation("create-problem");const problemId=created.revision.business_problem_id;setParams({problem:problemId});await reloadList();await loadWorkspace(problemId)}catch(failure){setError(reason(failure))}finally{setBusy(false)}}
  async function saveProblem(){if(!session||!workspace||busy)return;const current=workspace.detail.revisions.find(item=>item.revision_id===workspace.detail.problem.current_revision_id)??latest(workspace.detail.revisions);if(!current)return;const payload={predecessorRevisionId:current.revision_id,expectedVersion:workspace.detail.problem.aggregate_version,title:draft.title.trim(),description:draft.description.trim(),ownerId:current.owner_id};setBusy(true);setError("");try{await reviseBusinessProblem(session.csrfToken,workspace.detail.problem.business_problem_id,{...payload,idempotencyKey:operationKey("revise-problem",payload)});completeOperation("revise-problem");await reloadList();await loadWorkspace(workspace.detail.problem.business_problem_id)}catch(failure){setError(reason(failure))}finally{setBusy(false)}}
  async function saveCriterion(){
    if(!session||!workspace||busy||!draft.criterion.trim())return;
    const problemId=workspace.detail.problem.business_problem_id,currentProblem=workspace.detail.revisions.find(item=>item.revision_id===workspace.detail.problem.current_revision_id)??latest(workspace.detail.revisions),currentSet=latest(workspace.sets),currentCriterion=currentSet?workspace.criteria.find(item=>item.revision_id===currentSet.ordered_criterion_revision_ids[0]):undefined;
    const criterionPayload={...(currentCriterion?{successCriterionId:currentCriterion.success_criterion_id,predecessorRevisionId:currentCriterion.revision_id,expectedVersion:currentCriterion.revision}:{}),criterionType:"HUMAN_EVALUATED" as const,measurement:{rubric:draft.criterion.trim()},requiredEvidenceKinds:[] as string[],evaluatorType:"HUMAN",evaluatorVersion:"v1",applicability:{}};
    setBusy(true);setError("");
    try{
      const criterion=await writeCriterion(session.csrfToken,{...criterionPayload,idempotencyKey:operationKey("write-criterion",criterionPayload)});
      const setPayload={problemRevisionId:currentProblem.revision_id,...(currentSet?{predecessorSetRevisionId:currentSet.set_revision_id}:{}),orderedCriterionRevisionIds:[criterion.revision.revision_id],expectedVersion:workspace.detail.problem.aggregate_version};
      await writeCriteriaSet(session.csrfToken,problemId,{...setPayload,idempotencyKey:operationKey("write-criteria-set",setPayload)});
      completeOperation("write-criterion","write-criteria-set");await loadWorkspace(problemId);
    }catch(failure){setError(reason(failure))}finally{setBusy(false)}
  }
  function startNew(){if(dirty&&!window.confirm("放弃未保存修改并新建？"))return;epoch.current+=1;setParams({});setWorkspace(null);setDraft(EMPTY);setSaved(EMPTY)}

  const selected=useMemo(()=>workspace?.detail.problem.business_problem_id===selectedId?workspace:null,[selectedId,workspace]);
  if(loading)return <main className="px-page"><section className="px-state" role="status"><span className="px-spinner"/><strong>正在恢复可信业务工作区</strong></section></main>;
  if(loginRequired)return <main className="px-page"><section className="px-state"><h1>需要登录可信工作台</h1><p>身份由 HttpOnly 浏览器会话建立，不接受身份 header 或客户端 scope。</p><a className="px-primary-button" href="/api/workbench/v1/login">登录可信工作台</a>{error&&<code>{error}</code>}</section></main>;
  return <main className="px-page px-workspace"><header className="px-page-title"><div><p>工作与流程 <small>Trusted Business Workspace</small></p><h1>业务问题工作台</h1><span>{session?`${session.principal.principalId} · ${session.principal.tenantId} / ${session.principal.securityDomain}`:"会话不可用"}</span></div><button className="px-primary-button" disabled={busy||!draft.title.trim()||!draft.description.trim()} onClick={selected?saveProblem:create}>{busy?"正在保存…":selected?"保存业务问题":"创建业务问题"}</button></header>{error&&<section className="px-state danger" role="alert"><strong>操作未完成</strong><code>{error}</code></section>}<div className="px-workspace-grid">
    <aside className="px-work-list"><h2>业务问题</h2><button className={!selected?"selected":""} disabled={busy} onClick={startNew}>＋ 新建业务问题</button><nav aria-label="业务问题列表">{[...problems].reverse().map(problem=><button disabled={busy} className={selectedId===problem.business_problem_id?"selected":""} key={problem.business_problem_id} onClick={()=>select(problem.business_problem_id)}><span><strong>{problem.title}</strong><small>修订 {problem.revision} · {readable(problem.created_at)}</small></span></button>)}</nav></aside>
    <section className="px-work-main"><section className="px-work-card"><Heading eyebrow="Problem" title={selected?"修订业务问题":"创建业务问题"}/><label>标题<input value={draft.title} disabled={busy} onChange={event=>setDraft(value=>({...value,title:event.target.value}))}/></label><label>问题描述<textarea value={draft.description} disabled={busy} onChange={event=>setDraft(value=>({...value,description:event.target.value}))}/></label>{dirty&&<p className="px-truth-note">有未保存修改</p>}{selected&&<Identity detail={selected.detail}/>}</section>{selected?<section className="px-work-card"><Heading eyebrow="Criteria" title="成功标准" status={latest(selected.sets)?`Criteria Set 修订 ${latest(selected.sets).revision}`:"尚未建立"}/><label>人工验收标准<textarea value={draft.criterion} disabled={busy} onChange={event=>setDraft(value=>({...value,criterion:event.target.value}))}/></label><button className="px-primary-button" disabled={busy||!draft.criterion.trim()} onClick={saveCriterion}>{latest(selected.criteria)?"修订成功标准":"保存成功标准"}</button>{latest(selected.criteria)&&<details><summary>精确 Criteria 身份</summary><code>{latest(selected.criteria).success_criterion_id}</code><code>{latest(selected.criteria).revision_id}</code><code>{latest(selected.criteria).digest}</code></details>}</section>:<section className="px-empty large"><strong>先创建一个业务问题</strong><p>创建后从权威 owner 读回同一身份，再允许修订成功标准。</p></section>}</section>
    <aside className="px-work-context"><section><span className="px-eyebrow">可信会话</span><h2>{session?.principal.principalId??"不可用"}</h2><dl><dt>Tenant</dt><dd>{session?.principal.tenantId}</dd><dt>Scope</dt><dd>{session?.principal.securityDomain}</dd><dt>会话到期</dt><dd>{session?readable(session.session.expiresAt):"不可用"}</dd></dl></section><section><span className="px-eyebrow">Plan / 执行 / 结果</span><h3>尚未接线</h3><p className="px-truth-note">本批只交付 Problem 与 Criteria 闭环，不伪造 Plan、执行、Evidence 或 Outcome。</p></section><section><span className="px-eyebrow">数字员工与资源</span><h3>候选接线</h3><p className="px-truth-note">310 不提供本批业务操作端口；可选、已绑定和实际使用将在正式 owner 接线后分别展示。</p></section></aside>
  </div></main>;
}

function Identity({detail}:{detail:BusinessProblemDetail}){const current=detail.revisions.find(item=>item.revision_id===detail.problem.current_revision_id)??latest(detail.revisions);return <details><summary>权威身份与版本</summary><dl><dt>Problem ID</dt><dd><code>{detail.problem.business_problem_id}</code></dd><dt>Problem Revision</dt><dd><code>{current?.revision_id}</code></dd><dt>Digest</dt><dd><code>{current?.digest}</code></dd><dt>Aggregate Version</dt><dd>{detail.problem.aggregate_version}</dd><dt>Owner</dt><dd>{detail.problem.owner_id}</dd><dt>最后更新</dt><dd>{readable(detail.problem.updated_at)}</dd></dl></details>}
function Heading({eyebrow,title,status}:{eyebrow:string;title:string;status?:string}){return <div className="px-section-heading"><div><span className="px-eyebrow">{eyebrow}</span><h3>{title}</h3></div>{status&&<span className="px-status info">{status}</span>}</div>}
