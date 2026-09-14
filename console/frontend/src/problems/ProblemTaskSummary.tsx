import {useEffect,useRef,useState} from "react";
import type {BusinessProblemDetail,BusinessProblemRevision,GrantRequestStatus,ProblemCreatorContinuation} from "../api/businessWorkspace";

type AuthorizationSummary={continuation?:ProblemCreatorContinuation;request?:GrantRequestStatus};
type Props={revision?:BusinessProblemRevision;detail?:BusinessProblemDetail;authorization:AuthorizationSummary;busy:boolean;readFailed:boolean;contextKey:string;onLocateProblem:()=>void;onLocateAuthorization:()=>void};

const latest=<T extends {revision:number}>(values:T[])=>[...values].sort((a,b)=>b.revision-a.revision)[0];

export function ProblemTaskSummary({revision,detail,authorization,busy,readFailed,contextKey,onLocateProblem,onLocateAuthorization}:Props){
  const trigger=useRef<HTMLButtonElement>(null),dialog=useRef<HTMLDialogElement>(null),activeContext=useRef(contextKey),[copiedContext,setCopiedContext]=useState("");
  const exact=detail?.revisions.find(item=>item.revision_id===detail.problem.current_revision_id)??(detail?latest(detail.revisions):undefined),formal=exact??revision;
  useEffect(()=>{activeContext.current=contextKey;if(dialog.current?.open)dialog.current.close()},[contextKey]);
  function open(){dialog.current?.showModal()}
  function close(){dialog.current?.close();trigger.current?.focus()}
  async function copyRequest(){const requestId=authorization.request?.requestId,expectedContext=activeContext.current;if(!requestId)return;try{await navigator.clipboard.writeText(requestId);if(activeContext.current===expectedContext)setCopiedContext(expectedContext)}catch{if(activeContext.current===expectedContext)setCopiedContext("")}}
  function locate(target:()=>void){if(dialog.current?.open)dialog.current.close();requestAnimationFrame(target)}
  const content=<SummaryContent revision={formal} exact={exact} authorization={authorization} busy={busy} readFailed={readFailed} copied={copiedContext===contextKey} onCopy={()=>void copyRequest()} onLocateProblem={()=>locate(onLocateProblem)} onLocateAuthorization={()=>locate(onLocateAuthorization)}/>;
  return <div className="px-task-summary">
    <button ref={trigger} type="button" className="px-task-summary-trigger" aria-label="本任务" aria-haspopup="dialog" onClick={open}>本任务</button>
    <aside className="px-task-summary-panel" aria-labelledby="task-summary-title"><h2 id="task-summary-title">本任务</h2><p>只读汇总当前正式响应，不是第二份业务记录。</p>{content}</aside>
    <dialog ref={dialog} className="px-task-summary-dialog" aria-labelledby="task-summary-dialog-title" onCancel={event=>{event.preventDefault();close()}} onClose={()=>trigger.current?.focus()}><header><div><span className="px-eyebrow">当前上下文</span><h2 id="task-summary-dialog-title">本任务</h2></div><button type="button" aria-label="关闭本任务" autoFocus onClick={close}>关闭</button></header>{content}</dialog>
  </div>;
}

function SummaryContent({revision,exact,authorization,busy,readFailed,copied,onCopy,onLocateProblem,onLocateAuthorization}:{revision?:BusinessProblemRevision;exact?:BusinessProblemRevision;authorization:AuthorizationSummary;busy:boolean;readFailed:boolean;copied:boolean;onCopy:()=>void;onLocateProblem:()=>void;onLocateAuthorization:()=>void}){
  const request=authorization.request,continuation=authorization.continuation;
  const readState=exact?"读取成功":request?.state==="APPROVED"?(busy?"正在读取":readFailed?"读取失败":"已批准，等待读取"):request?.state==="REJECTED"?"未获读取权限":request?.state==="PENDING"?"等待审批":continuation?.state==="EXPIRED"?"申请窗口已过期":revision?"尚未申请查看":"尚未创建";
  const next=exact?"可返回问题详情；修改仍需 REVISE 权限。":request?.state==="APPROVED"?(readFailed?"回到授权卡片重新读取。":"等待正式精确读取完成。"):request?.state==="REJECTED"?"如仍需查看，请按正式流程重新取得授权。":request?.state==="PENDING"?"由独立管理员处理后，在授权卡片刷新。":continuation?.state==="AVAILABLE"?"回到授权卡片申请查看权限。":continuation?.state==="EXPIRED"?"已创建问题保留；本页不会自动延长申请窗口。":"先在对话中确认并创建问题。";
  return <div className="px-task-summary-content">
    <section><span className="px-eyebrow">问题摘要</span>{revision?<><h3>{revision.title}</h3><p>{exact?exact.description:"受保护正文尚未通过 exact GET 读取；这里不使用本地草稿补全。"}</p><dl><dt>修订</dt><dd>{revision.revision}</dd><dt>查看结果</dt><dd>{readState}</dd></dl><button type="button" onClick={onLocateProblem}>定位问题消息</button></>:<p>确认创建后，这里显示正式响应中的问题摘要。</p>}</section>
    <section><span className="px-eyebrow">查看申请</span><h3>{request?request.state==="PENDING"?"等待审批":request.state==="APPROVED"?"已批准":"已拒绝":continuation?.state==="EXPIRED"?"已过期":revision?"尚未申请":"暂无申请"}</h3><p>{next}</p>{request&&<><code>{request.requestId}</code><button type="button" onClick={onCopy}>复制申请编号</button><span className="px-copy-status" aria-live="polite">{copied?"已复制":""}</span></>} {(request||continuation)&&<button type="button" onClick={onLocateAuthorization}>定位授权消息</button>}</section>
  </div>;
}
