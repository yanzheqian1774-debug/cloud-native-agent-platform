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

const reason=(error:unknown)=>error instanceof WorkbenchRequestError?`${error.reasonCode}${error.requestId?` · ${error.requestId}`:""}`:"WORKBENCH_UNAVAILABLE";

export function GrantAdministrationPage(){
  const [params,setParams]=useSearchParams(),[session,setSession]=useState<WorkbenchSession|null>(null),[requestId,setRequestId]=useState(params.get("request")??""),[request,setRequest]=useState<GrantRequestStatus|null>(null),[error,setError]=useState(""),[busy,setBusy]=useState(false),[loginRequired,setLoginRequired]=useState(false);
  const decisionKeys=useRef<Record<string,string>>({});
  useEffect(()=>{readWorkbenchSession().then(setSession).catch(failure=>{setLoginRequired(failure instanceof WorkbenchRequestError&&failure.status===401);setError(reason(failure))})},[]);

  async function inspect(){const exact=requestId.trim();if(!exact||busy)return;setBusy(true);setError("");try{const value=await inspectGrantRequest(exact);setRequest(value);setParams({request:exact})}catch(failure){setRequest(null);setError(reason(failure))}finally{setBusy(false)}}
  async function decide(decision:"APPROVE"|"REJECT"){if(!session||!request||request.state!=="PENDING"||busy)return;const fingerprint=JSON.stringify({requestId:request.requestId,expectedVersion:request.aggregateVersion,decision}),key=decisionKeys.current[fingerprint]??newIdempotencyKey("grant-decision");decisionKeys.current[fingerprint]=key;setBusy(true);setError("");try{await decideGrantRequest(session.csrfToken,request.requestId,{expectedVersion:request.aggregateVersion,decision,reasonCategory:decision==="APPROVE"?"ASSIGNED_BUSINESS_DUTY":"REQUEST_NOT_JUSTIFIED",basisType:"TICKET",basisReference:`S5-V023-IMPL-299:${request.requestId}`,...(decision==="APPROVE"?{expiresAt:new Date(Date.now()+60*60*1000).toISOString()}:{}),idempotencyKey:key});delete decisionKeys.current[fingerprint];setRequest(await inspectGrantRequest(request.requestId))}catch(failure){setError(reason(failure))}finally{setBusy(false)}}

  if(loginRequired)return <main className="px-page"><section className="px-state"><h1>管理员需独立登录</h1><p>请在独立浏览器 context 中使用具有精确 GRANT_ADMIN 权限的凭据登录。</p><a className="px-primary-button" href="/api/workbench/v1/login">登录授权管理工作台</a>{error&&<code>{error}</code>}</section></main>;
  return <main className="px-page px-admin-page"><header className="px-page-title"><div><p>Governance <small>Exact Grant Administration</small></p><h1>授权申请审批</h1><span>{session?`${session.principal.principalId} · ${session.principal.tenantId} / ${session.principal.securityDomain}`:"正在恢复独立管理员会话"}</span></div><a href="/work">返回申请人工作台</a></header>
    {error&&<section className="px-state danger" role="alert"><strong>操作未完成</strong><code>{error}</code></section>}
    <section className="px-admin-card"><span className="px-eyebrow">精确入口</span><h2>按 Request ID 检查</h2><p className="px-truth-note">本页不提供跨主体列表、搜索、计数或枚举；未知或越权 requestId 统一失败关闭。</p><label>Request ID<input value={requestId} disabled={busy} onChange={event=>setRequestId(event.target.value)}/></label><button className="px-primary-button" disabled={busy||!requestId.trim()} onClick={inspect}>{busy?"处理中…":"检查授权申请"}</button></section>
    {request&&<section className="px-admin-card"><span className="px-eyebrow">最小状态</span><h2>{request.state}</h2><dl><dt>Request ID</dt><dd><code>{request.requestId}</code></dd><dt>Aggregate Version</dt><dd>{request.aggregateVersion}</dd><dt>Purpose</dt><dd>{request.purpose}</dd><dt>Requested Actions</dt><dd>{request.requestedActions.join(", ")}</dd></dl>{request.state==="PENDING"?<div className="px-admin-actions"><button disabled={busy} onClick={()=>decide("REJECT")}>拒绝</button><button className="px-primary-button" disabled={busy} onClick={()=>decide("APPROVE")}>批准精确读取</button></div>:<p className="px-truth-note">终态不可由本页覆盖；重新检查同一 requestId 可恢复决定。</p>}</section>}
  </main>;
}
