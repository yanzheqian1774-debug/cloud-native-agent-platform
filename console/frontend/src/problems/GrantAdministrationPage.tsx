import {useEffect,useRef,useState} from "react";
import {useSearchParams} from "react-router-dom";
import {
  WorkbenchRequestError,
  decideGrantRequest,
  inspectGrantRequest,
  newIdempotencyKey,
  readWorkbenchSession,
  type GrantRequestStatus,
  type WorkbenchSession,
} from "../api/businessWorkspace";
import { WorkbenchErrorNotice, type WorkbenchOperation } from "./WorkbenchErrorNotice";

type Failure={error:unknown;operation:WorkbenchOperation;mutation?:boolean};

export function GrantAdministrationPage(){
  const [params,setParams]=useSearchParams(),[session,setSession]=useState<WorkbenchSession|null>(null),[requestId,setRequestId]=useState(params.get("request")??""),[request,setRequest]=useState<GrantRequestStatus|null>(null),[failure,setFailure]=useState<Failure|null>(null),[busy,setBusy]=useState(false),[loginRequired,setLoginRequired]=useState(false);
  const decisionKeys=useRef<Record<string,string>>({});
  useEffect(()=>{readWorkbenchSession().then(setSession).catch(error=>{setLoginRequired(error instanceof WorkbenchRequestError&&error.status===401);setFailure({error,operation:"恢复管理员会话"})})},[]);

  async function inspect(){const exact=requestId.trim();if(!exact||busy)return;setBusy(true);setFailure(null);try{const value=await inspectGrantRequest(exact);setRequest(value);setParams({request:exact})}catch(error){setRequest(null);setFailure({error,operation:"检查授权申请"})}finally{setBusy(false)}}
  async function decide(decision:"APPROVE"|"REJECT"){if(!session||!request||request.state!=="PENDING"||busy)return;const fingerprint=JSON.stringify({requestId:request.requestId,expectedVersion:request.aggregateVersion,decision}),key=decisionKeys.current[fingerprint]??newIdempotencyKey("grant-decision");decisionKeys.current[fingerprint]=key;setBusy(true);setFailure(null);try{await decideGrantRequest(session.csrfToken,request.requestId,{expectedVersion:request.aggregateVersion,decision,reasonCategory:decision==="APPROVE"?"ASSIGNED_BUSINESS_DUTY":"REQUEST_NOT_JUSTIFIED",basisType:"TICKET",basisReference:`S5-V023-IMPL-299:${request.requestId}`,...(decision==="APPROVE"?{expiresAt:new Date(Date.now()+60*60*1000).toISOString()}:{}),idempotencyKey:key});delete decisionKeys.current[fingerprint];setRequest(await inspectGrantRequest(request.requestId))}catch(error){setFailure({error,operation:"提交授权决定",mutation:true})}finally{setBusy(false)}}

  if(loginRequired)return <main className="px-page px-admin-page"><section className="px-state"><h1>管理员需独立登录</h1><p>请使用具备精确审批权限的独立管理员会话重新登录。</p><a className="px-primary-button" href="/api/workbench/v1/login">登录授权管理工作台</a></section>{failure&&<WorkbenchErrorNotice {...failure}/>}</main>;
  return <main className="px-page px-admin-page"><header className="px-page-title"><div><p>授权管理 <small>Exact Grant Administration</small></p><h1>授权申请审批</h1><span>只处理你输入的精确申请编号；本页不提供申请列表或搜索。</span></div><a href="/work">返回申请人工作台</a></header>
    {failure&&<WorkbenchErrorNotice {...failure}/>}<section className="px-admin-status" aria-label="当前任务和状态"><span className="px-eyebrow">当前任务</span><h2>{request?"核对并处理授权申请":"检查一项授权申请"}</h2><p>{request?"先核对当前状态；只有等待处理的申请可以批准或拒绝。":"输入申请人提供的完整申请编号。未知或不可见的申请不会被进一步区分。"}</p></section>
    <section className="px-admin-card"><span className="px-eyebrow">精确入口</span><h2>检查申请编号</h2><label className="px-field" htmlFor="grant-request-id"><span>申请编号</span><input id="grant-request-id" value={requestId} disabled={busy} onChange={event=>setRequestId(event.target.value)}/><small>请粘贴申请人页面显示的完整编号；这不是诊断 ID。</small></label><button className="px-primary-button" disabled={busy||!requestId.trim()} onClick={inspect}>{busy?"正在检查…":"检查授权申请"}</button><p className="px-boundary-note">为保护资源边界，本页不提供跨主体列表、搜索、计数或枚举。</p></section>
    {request&&<section className="px-admin-card"><span className="px-eyebrow">当前状态</span><h2>{request.state==="PENDING"?"等待处理":request.state==="APPROVED"?"已批准":"已拒绝"}</h2><p>{request.state==="PENDING"?"请核对申请用途和请求操作，再作出一次明确决定。":request.state==="APPROVED"?"该申请已经批准。申请人可返回原工作台刷新授权状态。":"该申请已经拒绝。申请人页面不会继续受保护操作。"}</p><dl><dt>申请编号</dt><dd><code>{request.requestId}</code></dd><dt>状态版本</dt><dd>{request.aggregateVersion}</dd><dt>申请用途</dt><dd>{request.purpose}</dd><dt>请求操作</dt><dd>{request.requestedActions.join(", ")}</dd></dl>{request.state==="PENDING"?<div className="px-admin-actions"><button disabled={busy} onClick={()=>decide("REJECT")}>拒绝申请</button><button className="px-primary-button" disabled={busy} onClick={()=>decide("APPROVE")}>批准精确权限</button></div>:<p className="px-boundary-note">这是不可覆盖的终态。再次检查同一申请编号可恢复当前决定。</p>}</section>}
  </main>;
}
