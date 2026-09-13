import {useCallback,useEffect,useMemo,useRef,useState} from "react";
import {useSearchParams} from "react-router-dom";
import {
  WorkbenchRequestError,
  createBusinessProblem,
  inspectGrantRequest,
  listBusinessProblems,
  newIdempotencyKey,
  readBusinessProblem,
  readCriteriaSets,
  readProblemCriteria,
  readWorkbenchSession,
  reviseBusinessProblem,
  submitProblemReadGrantRequest,
  writeCriteriaSet,
  writeCriterion,
  type BusinessProblemDetail,
  type BusinessProblemRevision,
  type CriteriaSetRevision,
  type CriterionRevision,
  type GrantRequestStatus,
  type ProblemCreatorContinuation,
  type WorkbenchSession,
} from "../api/businessWorkspace";

type Workspace={detail:BusinessProblemDetail;criteria:CriterionRevision[];sets:CriteriaSetRevision[]};
type Draft={title:string;description:string;criterion:string};
type AuthorizationState={continuation?:ProblemCreatorContinuation;request?:GrantRequestStatus;requestKey?:string};
const EMPTY:Draft={title:"",description:"",criterion:""};
const latest=<T extends {revision:number}>(values:T[])=>[...values].sort((a,b)=>b.revision-a.revision)[0];
const readable=(value:string)=>new Intl.DateTimeFormat("zh-CN",{year:"numeric",month:"long",day:"numeric",hour:"2-digit",minute:"2-digit",timeZoneName:"short"}).format(new Date(value));
const reason=(error:unknown)=>error instanceof WorkbenchRequestError?`${error.reasonCode}${error.requestId?` · ${error.requestId}`:""}`:"WORKBENCH_UNAVAILABLE";
const storageKey=(problemId:string)=>`impl299.authorization.${problemId}`;

function storedAuthorization(problemId:string):AuthorizationState{
  try{return JSON.parse(sessionStorage.getItem(storageKey(problemId))??"{}") as AuthorizationState}catch{return {}}
}
function persistAuthorization(problemId:string,state:AuthorizationState){
  sessionStorage.setItem(storageKey(problemId),JSON.stringify(state));
}

export function ProblemWorkspacePage(){
  const [params,setParams]=useSearchParams();
  const [session,setSession]=useState<WorkbenchSession|null>(null),[problems,setProblems]=useState<BusinessProblemRevision[]>([]),[workspace,setWorkspace]=useState<Workspace|null>(null);
  const [createdRevision,setCreatedRevision]=useState<BusinessProblemRevision|null>(null),[authorization,setAuthorization]=useState<AuthorizationState>({});
  const [draft,setDraft]=useState<Draft>(EMPTY),[saved,setSaved]=useState<Draft>(EMPTY);
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(""),[loginRequired,setLoginRequired]=useState(false);
  const epoch=useRef(0),idempotency=useRef<Record<string,{fingerprint:string;key:string}>>({}),initialProblem=useRef(params.get("problem")),initialRequest=useRef(params.get("request")),selectedId=params.get("problem"),dirty=JSON.stringify(draft)!==JSON.stringify(saved);

  function operationKey(operation:string,payload:unknown){const fingerprint=JSON.stringify(payload),current=idempotency.current[operation];if(current?.fingerprint===fingerprint)return current.key;const key=newIdempotencyKey(operation);idempotency.current[operation]={fingerprint,key};return key}
  function completeOperation(...operations:string[]){for(const operation of operations)delete idempotency.current[operation]}

  const applyProblem=useCallback((detail:BusinessProblemDetail,sets:CriteriaSetRevision[]=[],criteria:CriterionRevision[]=[])=>{
    const problemRevision=detail.revisions.find(item=>item.revision_id===detail.problem.current_revision_id)??latest(detail.revisions);
    const set=latest(sets),criterion=set?criteria.find(item=>item.revision_id===set.ordered_criterion_revision_ids[0]):undefined;
    const next={title:problemRevision?.title??"",description:problemRevision?.description??"",criterion:String(criterion?.measurement.rubric??"")};
    setWorkspace({detail,sets,criteria});setCreatedRevision(problemRevision??null);setDraft(next);setSaved(next);setError("");
  },[]);
  const loadWorkspace=useCallback(async(problemId:string)=>{
    const token=++epoch.current;
    const [detail,sets,criteria]=await Promise.all([readBusinessProblem(problemId),readCriteriaSets(problemId),readProblemCriteria(problemId)]);
    if(token!==epoch.current)return;
    applyProblem(detail,sets.revisions,criteria.revisions);
  },[applyProblem]);
  const loadExactProblem=useCallback(async(problemId:string)=>{
    const token=++epoch.current,detail=await readBusinessProblem(problemId);
    if(token!==epoch.current)return;
    applyProblem(detail);
  },[applyProblem]);
  const reloadList=useCallback(async()=>setProblems((await listBusinessProblems()).problems),[]);

  const recoverRequest=useCallback(async(problemId:string,requestId:string)=>{
    const request=await inspectGrantRequest(requestId),next={...storedAuthorization(problemId),request};
    setAuthorization(next);persistAuthorization(problemId,next);
    if(request.state==="APPROVED")await loadExactProblem(problemId);
  },[loadExactProblem]);

  useEffect(()=>{let active=true;(async()=>{try{
    const current=await readWorkbenchSession();if(!active)return;setSession(current);
    const listed=await listBusinessProblems();if(!active)return;setProblems(listed.problems);
    const problemId=initialProblem.current;if(!problemId)return;
    setCreatedRevision(listed.problems.find(item=>item.business_problem_id===problemId)??null);
    const stored=storedAuthorization(problemId),requestId=initialRequest.current??stored.request?.requestId;
    setAuthorization(stored);
    if(requestId)await recoverRequest(problemId,requestId);
    else if(!stored.continuation)await loadWorkspace(problemId);
  }catch(failure){if(active){setLoginRequired(failure instanceof WorkbenchRequestError&&failure.status===401);setError(reason(failure))}}finally{if(active)setLoading(false)}})();return()=>{active=false;epoch.current+=1}},[loadWorkspace,recoverRequest]);
  useEffect(()=>{const warn=(event:BeforeUnloadEvent)=>{if(dirty){event.preventDefault();event.returnValue=""}};window.addEventListener("beforeunload",warn);return()=>window.removeEventListener("beforeunload",warn)},[dirty]);

  async function select(problemId:string){if(dirty&&!window.confirm("当前问题有未保存修改。确定放弃并切换吗？"))return;setParams({problem:problemId});setBusy(true);setError("");setAuthorization({});try{await loadWorkspace(problemId)}catch(failure){setError(reason(failure))}finally{setBusy(false)}}
  async function create(){if(!session||busy||!draft.title.trim()||!draft.description.trim())return;const payload={title:draft.title.trim(),description:draft.description.trim(),ownerId:session.principal.principalId};setBusy(true);setError("");try{
    const created=await createBusinessProblem(session.csrfToken,{...payload,idempotencyKey:operationKey("create-problem",payload)});
    completeOperation("create-problem");const problemId=created.revision.business_problem_id,next:AuthorizationState={continuation:created.creatorContinuation};
    if(created.creatorContinuation.requestId)next.request=await inspectGrantRequest(created.creatorContinuation.requestId);
    setCreatedRevision(created.revision);setAuthorization(next);persistAuthorization(problemId,next);
    setParams({problem:problemId,...(next.request?{request:next.request.requestId}:{})});await reloadList();
    if(next.request?.state==="APPROVED")await loadExactProblem(problemId);
  }catch(failure){setError(reason(failure))}finally{setBusy(false)}}
  async function requestAccess(){const continuation=authorization.continuation;if(!session||!selectedId||!continuation?.continuationId||continuation.state!=="AVAILABLE"||busy)return;const requestKey=authorization.requestKey??newIdempotencyKey("request-problem-read"),pending={...authorization,requestKey};setAuthorization(pending);persistAuthorization(selectedId,pending);setBusy(true);setError("");try{
    const request=await submitProblemReadGrantRequest(session.csrfToken,continuation.continuationId,requestKey);
    const next={...pending,request};setAuthorization(next);persistAuthorization(selectedId,next);setParams({problem:selectedId,request:request.requestId});
  }catch(failure){setError(reason(failure))}finally{setBusy(false)}}
  async function refreshAuthorization(){if(!selectedId||!authorization.request||busy)return;setBusy(true);setError("");try{await recoverRequest(selectedId,authorization.request.requestId)}catch(failure){setError(reason(failure))}finally{setBusy(false)}}
  async function saveProblem(){if(!session||!workspace||busy)return;const current=workspace.detail.revisions.find(item=>item.revision_id===workspace.detail.problem.current_revision_id)??latest(workspace.detail.revisions);if(!current)return;const payload={predecessorRevisionId:current.revision_id,expectedVersion:workspace.detail.problem.aggregate_version,title:draft.title.trim(),description:draft.description.trim(),ownerId:current.owner_id};setBusy(true);setError("");try{await reviseBusinessProblem(session.csrfToken,workspace.detail.problem.business_problem_id,{...payload,idempotencyKey:operationKey("revise-problem",payload)});completeOperation("revise-problem");await reloadList();await loadWorkspace(workspace.detail.problem.business_problem_id)}catch(failure){setError(reason(failure))}finally{setBusy(false)}}
  async function saveCriterion(){
    if(!session||!workspace||busy||!draft.criterion.trim())return;
    const problemId=workspace.detail.problem.business_problem_id,currentProblem=workspace.detail.revisions.find(item=>item.revision_id===workspace.detail.problem.current_revision_id)??latest(workspace.detail.revisions),currentSet=latest(workspace.sets),currentCriterion=currentSet?workspace.criteria.find(item=>item.revision_id===currentSet.ordered_criterion_revision_ids[0]):undefined;
    const criterionPayload={...(currentCriterion?{successCriterionId:currentCriterion.success_criterion_id,predecessorRevisionId:currentCriterion.revision_id,expectedVersion:currentCriterion.revision}:{}),criterionType:"HUMAN_EVALUATED" as const,measurement:{rubric:draft.criterion.trim()},requiredEvidenceKinds:[] as string[],evaluatorType:"HUMAN",evaluatorVersion:"v1",applicability:{}};
    setBusy(true);setError("");
    try{const criterion=await writeCriterion(session.csrfToken,{...criterionPayload,idempotencyKey:operationKey("write-criterion",criterionPayload)});const setPayload={problemRevisionId:currentProblem.revision_id,...(currentSet?{predecessorSetRevisionId:currentSet.set_revision_id}:{}),orderedCriterionRevisionIds:[criterion.revision.revision_id],expectedVersion:workspace.detail.problem.aggregate_version};await writeCriteriaSet(session.csrfToken,problemId,{...setPayload,idempotencyKey:operationKey("write-criteria-set",setPayload)});completeOperation("write-criterion","write-criteria-set");await loadWorkspace(problemId)}catch(failure){setError(reason(failure))}finally{setBusy(false)}
  }
  function startNew(){if(dirty&&!window.confirm("放弃未保存修改并新建？"))return;epoch.current+=1;setParams({});setWorkspace(null);setCreatedRevision(null);setAuthorization({});setDraft(EMPTY);setSaved(EMPTY)}

  const selected=useMemo(()=>workspace?.detail.problem.business_problem_id===selectedId?workspace:null,[selectedId,workspace]);
  const canonical=selected?.detail.revisions.find(item=>item.revision_id===selected.detail.problem.current_revision_id)??createdRevision??problems.find(item=>item.business_problem_id===selectedId);
  if(loading)return <main className="px-page"><section className="px-state" role="status"><span className="px-spinner"/><strong>正在恢复可信业务工作区</strong></section></main>;
  if(loginRequired)return <main className="px-page"><section className="px-state"><h1>需要登录可信工作台</h1><p>身份由 HttpOnly 浏览器会话建立，不接受身份 header 或客户端 scope。</p><a className="px-primary-button" href="/api/workbench/v1/login">登录可信工作台</a>{error&&<code>{error}</code>}</section></main>;
  return <main className="px-page px-workspace"><header className="px-page-title"><div><p>工作与流程 <small>Trusted Business Workspace</small></p><h1>业务问题工作台</h1><span>{session?`${session.principal.principalId} · ${session.principal.tenantId} / ${session.principal.securityDomain}`:"会话不可用"}</span></div><button className="px-primary-button" disabled={busy||!draft.title.trim()||!draft.description.trim()||Boolean(selectedId&&!selected)} onClick={selected?saveProblem:create}>{busy?"处理中…":selected?"保存业务问题":"创建业务问题"}</button></header>{error&&<section className="px-state danger" role="alert"><strong>操作未完成</strong><code>{error}</code></section>}<div className="px-workspace-grid">
    <aside className="px-work-list"><h2>业务问题</h2><button className={!selectedId?"selected":""} disabled={busy} onClick={startNew}>＋ 新建业务问题</button><nav aria-label="业务问题列表">{[...problems].reverse().map(problem=><button disabled={busy} className={selectedId===problem.business_problem_id?"selected":""} key={problem.business_problem_id} onClick={()=>select(problem.business_problem_id)}><span><strong>{problem.title}</strong><small>修订 {problem.revision} · {readable(problem.created_at)}</small></span></button>)}</nav></aside>
    <section className="px-work-main"><section className="px-work-card"><Heading eyebrow="Problem" title={selected?"修订业务问题":selectedId?"可信身份已创建":"创建业务问题"}/><label>标题<input value={draft.title} disabled={busy||Boolean(selectedId&&!selected)} onChange={event=>setDraft(value=>({...value,title:event.target.value}))}/></label><label>问题描述<textarea value={draft.description} disabled={busy||Boolean(selectedId&&!selected)} onChange={event=>setDraft(value=>({...value,description:event.target.value}))}/></label>{dirty&&<p className="px-truth-note">有未保存修改</p>}{selected&&<Identity detail={selected.detail}/>} {!selected&&canonical&&<CreatedIdentity revision={canonical}/>}</section>
    {selected?<section className="px-work-card"><Heading eyebrow="Criteria" title="成功标准" status={latest(selected.sets)?`Criteria Set 修订 ${latest(selected.sets).revision}`:"尚未建立"}/><label>人工验收标准<textarea value={draft.criterion} disabled={busy} onChange={event=>setDraft(value=>({...value,criterion:event.target.value}))}/></label><button className="px-primary-button" disabled={busy||!draft.criterion.trim()} onClick={saveCriterion}>{latest(selected.criteria)?"修订成功标准":"保存成功标准"}</button></section>:selectedId?<AuthorizationCard state={authorization} busy={busy} onRequest={requestAccess} onRefresh={refreshAuthorization}/>:<section className="px-empty large"><strong>先创建一个业务问题</strong><p>创建后保存权威身份与精确 creator continuation，再提交授权申请。</p></section>}</section>
    <aside className="px-work-context"><section><span className="px-eyebrow">可信会话</span><h2>{session?.principal.principalId??"不可用"}</h2><dl><dt>Tenant</dt><dd>{session?.principal.tenantId}</dd><dt>Scope</dt><dd>{session?.principal.securityDomain}</dd><dt>会话到期</dt><dd>{session?readable(session.session.expiresAt):"不可用"}</dd></dl></section><section><span className="px-eyebrow">授权管理</span><h3>独立管理员入口</h3><p className="px-truth-note">审批能力不在申请人页面。管理员只可凭精确 requestId 进入。</p><a href="/authorization-admin">打开授权审批页</a></section><section><span className="px-eyebrow">Workflow / Plan · 执行 / 结果</span><h3>尚未接线</h3><p className="px-truth-note">本批不伪造 Plan、执行、Evidence 或 Outcome；Human Intervention 也不在本闭环。未配置、未绑定、未执行、暂不可用与执行失败均保持显式状态。</p></section><section><span className="px-eyebrow">数字员工与资源</span><h3>尚未接线</h3><p className="px-truth-note">可选、已绑定与实际使用保持分离；只有 Attempt 事实才能证明本次实际使用，不由当前授权闭环推断。</p></section><section><span className="px-eyebrow">Knowledge / Evidence 边界</span><h3>尚无该页面可调用的 HTTP 投影</h3><p className="px-truth-note">规划采用的知识引用不是执行成功证据。已发布、已绑定、已选择、已检索、已引用是彼此独立的状态；本批不调用 <code>getKnowledge</code>，也不据此新增功能。</p></section></aside>
  </div></main>;
}

function AuthorizationCard({state,busy,onRequest,onRefresh}:{state:AuthorizationState;busy:boolean;onRequest:()=>void;onRefresh:()=>void}){
  const continuation=state.continuation,request=state.request;
  return <section className="px-work-card px-authorization-card"><Heading eyebrow="Exact READ authorization" title="读取授权"/>{continuation&&<p>Creator continuation：<strong>{continuation.state}</strong> · 到期 {readable(continuation.expiresAt)}</p>}{continuation?.state==="AVAILABLE"&&!request&&<button className="px-primary-button" disabled={busy} onClick={onRequest}>提交精确读取授权申请</button>}{continuation?.state==="CONSUMED"&&<p className="px-truth-note">已恢复原授权申请，不重复消费 continuation。</p>}{continuation?.state==="EXPIRED"&&<p className="px-truth-note">授权窗口已过期。Problem 身份保留；不补发、不延长、不重新创建。</p>}{request&&<><dl><dt>Request ID</dt><dd><code>{request.requestId}</code></dd><dt>状态</dt><dd><strong>{request.state}</strong></dd><dt>版本</dt><dd>{request.aggregateVersion}</dd></dl><button disabled={busy} onClick={onRefresh}>刷新授权状态</button>{request.state==="PENDING"&&<p className="px-truth-note">等待独立管理员决定；当前不视为已授权。</p>}{request.state==="REJECTED"&&<p className="px-truth-note">申请已拒绝；不会请求 Problem 正文。</p>}{request.state==="APPROVED"&&<p className="px-truth-note">已批准，正在使用正式 exact Problem READ。</p>}</>}</section>;
}
function CreatedIdentity({revision}:{revision:BusinessProblemRevision}){return <details open><summary>已提交的 canonical identity</summary><dl><dt>Problem ID</dt><dd><code>{revision.business_problem_id}</code></dd><dt>Problem Revision</dt><dd><code>{revision.revision_id}</code></dd><dt>Digest</dt><dd><code>{revision.digest}</code></dd></dl></details>}
function Identity({detail}:{detail:BusinessProblemDetail}){const current=detail.revisions.find(item=>item.revision_id===detail.problem.current_revision_id)??latest(detail.revisions);return <details><summary>权威身份与版本</summary><dl><dt>Problem ID</dt><dd><code>{detail.problem.business_problem_id}</code></dd><dt>Problem Revision</dt><dd><code>{current?.revision_id}</code></dd><dt>Digest</dt><dd><code>{current?.digest}</code></dd><dt>Aggregate Version</dt><dd>{detail.problem.aggregate_version}</dd><dt>Owner</dt><dd>{detail.problem.owner_id}</dd><dt>最后更新</dt><dd>{readable(detail.problem.updated_at)}</dd></dl></details>}
function Heading({eyebrow,title,status}:{eyebrow:string;title:string;status?:string}){return <div className="px-section-heading"><div><span className="px-eyebrow">{eyebrow}</span><h3>{title}</h3></div>{status&&<span className="px-status info">{status}</span>}</div>}
