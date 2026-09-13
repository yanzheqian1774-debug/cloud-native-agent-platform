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
import { WorkbenchErrorNotice, type WorkbenchOperation } from "./WorkbenchErrorNotice";

type Workspace={detail:BusinessProblemDetail;criteria:CriterionRevision[];sets:CriteriaSetRevision[]};
type Draft={title:string;description:string;criterion:string};
type AuthorizationState={continuation?:ProblemCreatorContinuation;request?:GrantRequestStatus;requestKey?:string};
type Failure={error:unknown;operation:WorkbenchOperation;mutation?:boolean};
const EMPTY:Draft={title:"",description:"",criterion:""};
const latest=<T extends {revision:number}>(values:T[])=>[...values].sort((a,b)=>b.revision-a.revision)[0];
const readable=(value:string)=>new Intl.DateTimeFormat("zh-CN",{year:"numeric",month:"long",day:"numeric",hour:"2-digit",minute:"2-digit",timeZoneName:"short"}).format(new Date(value));
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
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[failure,setFailure]=useState<Failure|null>(null),[loginRequired,setLoginRequired]=useState(false),[submitted,setSubmitted]=useState(false);
  const epoch=useRef(0),idempotency=useRef<Record<string,{fingerprint:string;key:string}>>({}),initialProblem=useRef(params.get("problem")),initialRequest=useRef(params.get("request")),selectedId=params.get("problem"),dirty=JSON.stringify(draft)!==JSON.stringify(saved);

  function operationKey(operation:string,payload:unknown){const fingerprint=JSON.stringify(payload),current=idempotency.current[operation];if(current?.fingerprint===fingerprint)return current.key;const key=newIdempotencyKey(operation);idempotency.current[operation]={fingerprint,key};return key}
  function completeOperation(...operations:string[]){for(const operation of operations)delete idempotency.current[operation]}

  const applyProblem=useCallback((detail:BusinessProblemDetail,sets:CriteriaSetRevision[]=[],criteria:CriterionRevision[]=[])=>{
    const problemRevision=detail.revisions.find(item=>item.revision_id===detail.problem.current_revision_id)??latest(detail.revisions);
    const set=latest(sets),criterion=set?criteria.find(item=>item.revision_id===set.ordered_criterion_revision_ids[0]):undefined;
    const next={title:problemRevision?.title??"",description:problemRevision?.description??"",criterion:String(criterion?.measurement.rubric??"")};
    setWorkspace({detail,sets,criteria});setCreatedRevision(problemRevision??null);setDraft(next);setSaved(next);setFailure(null);setSubmitted(false);
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
  }catch(error){if(active){setLoginRequired(error instanceof WorkbenchRequestError&&error.status===401);setFailure({error,operation:"恢复工作区"})}}finally{if(active)setLoading(false)}})();return()=>{active=false;epoch.current+=1}},[loadWorkspace,recoverRequest]);
  useEffect(()=>{const warn=(event:BeforeUnloadEvent)=>{if(dirty){event.preventDefault();event.returnValue=""}};window.addEventListener("beforeunload",warn);return()=>window.removeEventListener("beforeunload",warn)},[dirty]);

  async function select(problemId:string){if(dirty&&!window.confirm("当前问题有未保存修改。确定放弃并切换吗？"))return;setParams({problem:problemId});setBusy(true);setFailure(null);setAuthorization({});try{await loadWorkspace(problemId)}catch(error){setFailure({error,operation:"打开业务问题"})}finally{setBusy(false)}}
  async function create(){setSubmitted(true);if(!session||busy||!draft.title.trim()||!draft.description.trim())return;const payload={title:draft.title.trim(),description:draft.description.trim(),ownerId:session.principal.principalId};setBusy(true);setFailure(null);try{
    const created=await createBusinessProblem(session.csrfToken,{...payload,idempotencyKey:operationKey("create-problem",payload)});
    completeOperation("create-problem");const problemId=created.revision.business_problem_id,next:AuthorizationState={continuation:created.creatorContinuation};
    setCreatedRevision(created.revision);setAuthorization(next);persistAuthorization(problemId,next);
    setParams({problem:problemId});setSaved({...draft,title:payload.title,description:payload.description});setSubmitted(false);
    try{await reloadList()}catch(error){setFailure({error,operation:"恢复工作区"})}
    if(created.creatorContinuation.requestId){
      try{await recoverRequest(problemId,created.creatorContinuation.requestId);setParams({problem:problemId,request:created.creatorContinuation.requestId})}
      catch(error){setFailure({error,operation:"恢复授权状态"})}
    }
  }catch(error){setFailure({error,operation:"创建业务问题",mutation:true})}finally{setBusy(false)}}
  async function requestAccess(){const continuation=authorization.continuation;if(!session||!selectedId||!continuation?.continuationId||continuation.state!=="AVAILABLE"||busy)return;const requestKey=authorization.requestKey??newIdempotencyKey("request-problem-read"),pending={...authorization,requestKey};setAuthorization(pending);persistAuthorization(selectedId,pending);setBusy(true);setFailure(null);try{
    const request=await submitProblemReadGrantRequest(session.csrfToken,continuation.continuationId,requestKey);
    const next={...pending,request};setAuthorization(next);persistAuthorization(selectedId,next);setParams({problem:selectedId,request:request.requestId});
  }catch(error){setFailure({error,operation:"申请查看权限",mutation:true})}finally{setBusy(false)}}
  async function refreshAuthorization(){if(!selectedId||!authorization.request||busy)return;setBusy(true);setFailure(null);try{await recoverRequest(selectedId,authorization.request.requestId)}catch(error){setFailure({error,operation:"刷新授权状态"})}finally{setBusy(false)}}
  async function saveProblem(){setSubmitted(true);if(!session||!workspace||busy||!draft.title.trim()||!draft.description.trim())return;const current=workspace.detail.revisions.find(item=>item.revision_id===workspace.detail.problem.current_revision_id)??latest(workspace.detail.revisions);if(!current)return;const payload={predecessorRevisionId:current.revision_id,expectedVersion:workspace.detail.problem.aggregate_version,title:draft.title.trim(),description:draft.description.trim(),ownerId:current.owner_id};setBusy(true);setFailure(null);try{await reviseBusinessProblem(session.csrfToken,workspace.detail.problem.business_problem_id,{...payload,idempotencyKey:operationKey("revise-problem",payload)});completeOperation("revise-problem");await reloadList();await loadWorkspace(workspace.detail.problem.business_problem_id)}catch(error){setFailure({error,operation:"保存业务问题",mutation:true})}finally{setBusy(false)}}
  async function saveCriterion(){
    if(!session||!workspace||busy||!draft.criterion.trim())return;
    const problemId=workspace.detail.problem.business_problem_id,currentProblem=workspace.detail.revisions.find(item=>item.revision_id===workspace.detail.problem.current_revision_id)??latest(workspace.detail.revisions),currentSet=latest(workspace.sets),currentCriterion=currentSet?workspace.criteria.find(item=>item.revision_id===currentSet.ordered_criterion_revision_ids[0]):undefined;
    const criterionPayload={...(currentCriterion?{successCriterionId:currentCriterion.success_criterion_id,predecessorRevisionId:currentCriterion.revision_id,expectedVersion:currentCriterion.revision}:{}),criterionType:"HUMAN_EVALUATED" as const,measurement:{rubric:draft.criterion.trim()},requiredEvidenceKinds:[] as string[],evaluatorType:"HUMAN",evaluatorVersion:"v1",applicability:{}};
    setBusy(true);setFailure(null);
    try{const criterion=await writeCriterion(session.csrfToken,{...criterionPayload,idempotencyKey:operationKey("write-criterion",criterionPayload)});const setPayload={problemRevisionId:currentProblem.revision_id,...(currentSet?{predecessorSetRevisionId:currentSet.set_revision_id}:{}),orderedCriterionRevisionIds:[criterion.revision.revision_id],expectedVersion:workspace.detail.problem.aggregate_version};await writeCriteriaSet(session.csrfToken,problemId,{...setPayload,idempotencyKey:operationKey("write-criteria-set",setPayload)});completeOperation("write-criterion","write-criteria-set");await loadWorkspace(problemId)}catch(error){setFailure({error,operation:"保存成功标准",mutation:true})}finally{setBusy(false)}
  }
  function startNew(){if(dirty&&!window.confirm("放弃未保存修改并新建？"))return;epoch.current+=1;setParams({});setWorkspace(null);setCreatedRevision(null);setAuthorization({});setDraft(EMPTY);setSaved(EMPTY);setFailure(null);setSubmitted(false)}

  const selected=useMemo(()=>workspace?.detail.problem.business_problem_id===selectedId?workspace:null,[selectedId,workspace]);
  const canonical=selected?.detail.revisions.find(item=>item.revision_id===selected.detail.problem.current_revision_id)??createdRevision??problems.find(item=>item.business_problem_id===selectedId);
  const titleError=submitted&&!draft.title.trim()?"请输入标题。":draft.title.length>200?"标题不能超过 200 个字符。":"";
  const descriptionError=submitted&&!draft.description.trim()?"请输入问题描述。":draft.description.length>2_000?"问题描述不能超过 2000 个字符。":"";
  async function cancelForm(){
    if(dirty&&!window.confirm(selected?"放弃当前未保存修改？":"取消新建并放弃当前输入？"))return;
    setFailure(null);setSubmitted(false);
    if(selected){applyProblem(selected.detail,selected.sets,selected.criteria);return}
    const fallback=problems.at(-1);
    if(!fallback){setDraft(EMPTY);setSaved(EMPTY);return}
    setParams({problem:fallback.business_problem_id});setBusy(true);
    try{await loadWorkspace(fallback.business_problem_id)}catch(error){setFailure({error,operation:"打开业务问题"})}finally{setBusy(false)}
  }
  if(loading)return <main className="px-page"><section className="px-state" role="status"><span className="px-spinner"/><strong>正在恢复可信业务工作区</strong></section></main>;
  if(loginRequired)return <main className="px-page"><section className="px-state"><h1>需要登录可信工作台</h1><p>请重新登录。身份只来自受保护的浏览器会话，不接受页面提供的身份信息。</p><a className="px-primary-button" href="/api/workbench/v1/login">登录可信工作台</a></section>{failure&&<WorkbenchErrorNotice {...failure}/>}</main>;
  return <main className="px-page px-workspace"><header className="px-page-title"><div><p>工作与流程 <small>Trusted Business Workspace</small></p><h1>业务问题工作台</h1><span>填写需要解决的问题；创建成功后，可申请查看该问题。</span></div></header>{failure&&<WorkbenchErrorNotice {...failure}/>}<div className="px-workspace-grid">
    <aside className="px-work-list"><h2>业务问题</h2>{selectedId?<button disabled={busy} onClick={startNew}>＋ 新建业务问题</button>:<p className="px-list-mode" aria-current="step">正在新建业务问题</p>}<nav aria-label="业务问题列表">{[...problems].reverse().map(problem=><button disabled={busy} className={selectedId===problem.business_problem_id?"selected":""} key={problem.business_problem_id} onClick={()=>select(problem.business_problem_id)}><span><strong>{problem.title}</strong><small>修订 {problem.revision} · {readable(problem.created_at)}</small></span></button>)}</nav></aside>
    <section className="px-work-main"><section className="px-work-status" aria-label="当前任务和状态"><span className="px-eyebrow">当前任务</span><h2>{selected?"查看并修订业务问题":selectedId?"申请查看刚创建的问题":"创建一个业务问题"}</h2><p>{selected?"你正在查看已授权的权威内容。修改后可保存新修订。":selectedId?"问题已创建。提交查看申请并等待独立管理员批准后，即可打开详情。":"先填写标题和问题描述。提交期间页面会冻结操作，失败时保留输入。"}</p></section>
    <section className="px-work-card px-problem-form" aria-label={selected?"修订业务问题表单":"创建业务问题表单"}><Heading eyebrow="问题" title={selected?"修订业务问题":selectedId?"问题已创建":"填写问题"}/><div className="px-form-fields"><label className="px-field" htmlFor="problem-title"><span>标题</span><input id="problem-title" maxLength={200} value={draft.title} aria-invalid={Boolean(titleError)} aria-describedby={`problem-title-help${titleError?" problem-title-error":""}`} disabled={busy||Boolean(selectedId&&!selected)} onChange={event=>setDraft(value=>({...value,title:event.target.value}))}/><small id="problem-title-help">用一句话说明要解决的业务问题，最多 200 个字符。</small>{titleError&&<strong id="problem-title-error" className="px-field-error">{titleError}</strong>}</label><label className="px-field" htmlFor="problem-description"><span>问题描述</span><textarea id="problem-description" maxLength={2_000} value={draft.description} aria-invalid={Boolean(descriptionError)} aria-describedby={`problem-description-help${descriptionError?" problem-description-error":""}`} disabled={busy||Boolean(selectedId&&!selected)} onChange={event=>setDraft(value=>({...value,description:event.target.value}))}/><small id="problem-description-help">补充背景、影响和希望得到的结果，最多 2000 个字符。</small>{descriptionError&&<strong id="problem-description-error" className="px-field-error">{descriptionError}</strong>}</label></div>{dirty&&<p className="px-dirty-note" role="status">当前输入尚未保存。</p>}{!selectedId&&<div className="px-form-actions"><button type="button" disabled={busy||!dirty} onClick={()=>void cancelForm()}>取消新建</button><button type="button" className="px-primary-button" disabled={busy} onClick={create}>{busy?"正在创建…":"创建业务问题"}</button></div>}{selected&&<div className="px-form-actions"><button type="button" disabled={busy||!dirty} onClick={()=>void cancelForm()}>放弃修改</button><button type="button" className="px-primary-button" disabled={busy||!dirty} onClick={saveProblem}>{busy?"正在保存…":"保存业务问题"}</button></div>}{selected&&<Identity detail={selected.detail}/>} {!selected&&canonical&&<CreatedIdentity revision={canonical}/>}</section>
    {selected?<section className="px-work-card"><Heading eyebrow="下一步" title="定义成功标准" status={latest(selected.sets)?`标准修订 ${latest(selected.sets).revision}`:"尚未建立"}/><label className="px-field" htmlFor="problem-criterion"><span>人工验收标准</span><textarea id="problem-criterion" value={draft.criterion} disabled={busy} onChange={event=>setDraft(value=>({...value,criterion:event.target.value}))}/><small>说明人工判断问题是否解决时要检查的结果和依据。</small></label><button className="px-primary-button" disabled={busy||!draft.criterion.trim()} onClick={saveCriterion}>{latest(selected.criteria)?"修订成功标准":"保存成功标准"}</button></section>:selectedId?<AuthorizationCard state={authorization} busy={busy} onRequest={requestAccess} onRefresh={refreshAuthorization}/>:<section className="px-next-step"><span className="px-eyebrow">下一步</span><strong>创建后申请查看权限</strong><p>创建成功后，你可以提交查看申请。独立管理员批准后，返回本页刷新状态即可打开详情。</p></section>}</section>
    <aside className="px-work-context"><section><span className="px-eyebrow">当前支持范围</span><h2>问题创建与查看授权</h2><p>当前可创建问题、申请查看权限，并在批准后读取和修订。计划、执行和结果仍未接入本页面。</p><div className="px-scope-status"><span className="px-status warning">部分实现</span><span>问题与授权可用；后续业务链尚未接线。</span></div></section><section><details><summary>会话范围与到期时间</summary><dl><dt>租户</dt><dd>{session?.principal.tenantId}</dd><dt>安全范围</dt><dd>{session?.principal.securityDomain}</dd><dt>会话到期</dt><dd>{session?readable(session.session.expiresAt):"不可用"}</dd></dl></details></section><section><span className="px-eyebrow">独立审批</span><h3>管理员使用申请编号处理</h3><p>审批不在申请人页面进行。管理员需在独立会话中打开审批入口，并输入精确申请编号。</p><a href="/authorization-admin">打开授权审批页</a></section><section><details><summary>技术边界详情</summary><p>系统保存精确 creator continuation；本批不伪造 Workflow / Plan、执行、Human Intervention、Evidence 或 Outcome。</p><p>数字员工、资源可选项、已绑定与实际使用保持分离；只有 Attempt 事实才能证明本次实际使用。</p><p>规划采用的知识引用不是执行成功证据。已发布、已绑定、已选择、已检索、已引用彼此独立；尚无该页面可调用的 HTTP 投影，本批不调用 <code>getKnowledge</code>，也不据此新增功能。</p><p>未配置、未绑定、未执行、暂不可用与执行失败均保持为不同状态。</p></details></section></aside>
  </div></main>;
}

function AuthorizationCard({state,busy,onRequest,onRefresh}:{state:AuthorizationState;busy:boolean;onRequest:()=>void;onRefresh:()=>void}){
  const continuation=state.continuation,request=state.request;
  return <section className="px-work-card px-authorization-card"><Heading eyebrow="下一步" title="申请查看刚创建的问题"/>{continuation?.state==="AVAILABLE"&&!request&&<><p>问题已经创建，但查看正文需要独立授权。提交申请后，请把申请编号交给管理员。</p><button className="px-primary-button" disabled={busy} onClick={onRequest}>{busy?"正在提交…":"申请查看权限"}</button></>}{continuation?.state==="CONSUMED"&&!request&&<p className="px-truth-note">查看申请已经提交。页面会恢复原申请，不会重复提交。</p>}{continuation?.state==="EXPIRED"&&<p className="px-truth-note">本次申请窗口已过期。已创建的问题仍保留；页面不会自动延长窗口或重复创建问题。</p>}{request&&<><div className="px-request-status"><span className={`px-status ${request.state==="APPROVED"?"success":request.state==="REJECTED"?"danger":"warning"}`}>{request.state==="APPROVED"?"已批准":request.state==="REJECTED"?"已拒绝":"等待管理员处理"}</span><p>{request.state==="PENDING"?"将下面的申请编号交给独立管理员。处理完成后，在本页刷新授权状态。":request.state==="REJECTED"?"管理员已拒绝这次申请；页面不会读取问题正文。":"授权已生效，页面正在通过正式的精确读取打开问题。"}</p></div><dl><dt>申请编号</dt><dd><code>{request.requestId}</code></dd><dt>状态版本</dt><dd>{request.aggregateVersion}</dd></dl><button disabled={busy} onClick={onRefresh}>{busy?"正在刷新…":"刷新授权状态"}</button></>}{continuation&&<details><summary>授权技术详情</summary><dl><dt>Continuation 状态</dt><dd>{continuation.state}</dd><dt>申请窗口到期</dt><dd>{readable(continuation.expiresAt)}</dd></dl></details>}</section>;
}
function CreatedIdentity({revision}:{revision:BusinessProblemRevision}){return <details><summary>查看已创建问题的精确身份</summary><dl><dt>Problem ID</dt><dd><code>{revision.business_problem_id}</code></dd><dt>Problem Revision</dt><dd><code>{revision.revision_id}</code></dd><dt>Digest</dt><dd><code>{revision.digest}</code></dd></dl></details>}
function Identity({detail}:{detail:BusinessProblemDetail}){const current=detail.revisions.find(item=>item.revision_id===detail.problem.current_revision_id)??latest(detail.revisions);return <details><summary>权威身份与版本</summary><dl><dt>Problem ID</dt><dd><code>{detail.problem.business_problem_id}</code></dd><dt>Problem Revision</dt><dd><code>{current?.revision_id}</code></dd><dt>Digest</dt><dd><code>{current?.digest}</code></dd><dt>Aggregate Version</dt><dd>{detail.problem.aggregate_version}</dd><dt>Owner</dt><dd>{detail.problem.owner_id}</dd><dt>最后更新</dt><dd>{readable(detail.problem.updated_at)}</dd></dl></details>}
function Heading({eyebrow,title,status}:{eyebrow:string;title:string;status?:string}){return <div className="px-section-heading"><div><span className="px-eyebrow">{eyebrow}</span><h3>{title}</h3></div>{status&&<span className="px-status info">{status}</span>}</div>}
