import {useEffect,useRef,useState,type ReactNode} from "react";
import type {BusinessProblemDetail,BusinessProblemRevision,CriteriaSetRevision,CriterionRevision,GrantRequestStatus,ProblemCreatorContinuation} from "../api/businessWorkspace";

import type {UnderstandingItem} from "../api/draftAssistanceTypes";
import {fieldLabels,isUnstructuredStatement} from "./problemUnderstandingModel";

type AuthorizationSummary={continuation?:ProblemCreatorContinuation;request?:GrantRequestStatus};
type Props={draftSummary?:ReactNode;description?:string;understanding?:UnderstandingItem[];clarification?:string|null;revision?:BusinessProblemRevision;detail?:BusinessProblemDetail;criteria:CriterionRevision[];sets:CriteriaSetRevision[];authorization:AuthorizationSummary;busy:boolean;readFailed:boolean;contextKey:string;onLocateProblem:()=>void;onLocateAuthorization:()=>void};

const latest=<T extends {revision:number}>(values:T[])=>[...values].sort((a,b)=>b.revision-a.revision)[0];

export function ProblemTaskSummary({draftSummary,description="",understanding,clarification,revision,detail,criteria,sets,authorization,busy,readFailed,contextKey,onLocateProblem,onLocateAuthorization}:Props){
  const trigger=useRef<HTMLButtonElement>(null),dialog=useRef<HTMLDialogElement>(null),activeContext=useRef(contextKey),[copiedContext,setCopiedContext]=useState("");
  const exact=detail?.revisions.find(item=>item.revision_id===detail.problem.current_revision_id)??(detail?latest(detail.revisions):undefined),formal=exact??revision;
  useEffect(()=>{activeContext.current=contextKey;if(dialog.current?.open)dialog.current.close()},[contextKey]);
  function open(){dialog.current?.showModal()}
  function close(){dialog.current?.close();trigger.current?.focus()}
  async function copyRequest(){const requestId=authorization.request?.requestId,expectedContext=activeContext.current;if(!requestId)return;try{await navigator.clipboard.writeText(requestId);if(activeContext.current===expectedContext)setCopiedContext(expectedContext)}catch{if(activeContext.current===expectedContext)setCopiedContext("")}}
  function locate(target:()=>void){if(dialog.current?.open)dialog.current.close();requestAnimationFrame(target)}
  const content=(expandedDescription=false)=>!formal&&draftSummary?draftSummary:<SummaryContent expandedDescription={expandedDescription} description={description} understanding={understanding} clarification={clarification} revision={formal} exact={exact} criteria={criteria} sets={sets} authorization={authorization} busy={busy} readFailed={readFailed} copied={copiedContext===contextKey} onCopy={()=>void copyRequest()} onLocateProblem={()=>locate(onLocateProblem)} onLocateAuthorization={()=>locate(onLocateAuthorization)}/>;
  return <div className="px-task-summary">
    <button ref={trigger} type="button" className="px-task-summary-trigger" aria-label="本任务" aria-haspopup="dialog" onClick={open}><span><strong>本任务</strong><small>查看摘要与授权状态</small></span><span aria-hidden="true">›</span></button>
    <aside className="px-task-summary-panel" aria-labelledby="task-summary-title"><h2 id="task-summary-title">本任务</h2><p>根据当前问题与授权状态汇总。</p>{content()}</aside>
    <dialog ref={dialog} className="px-task-summary-dialog" aria-labelledby="task-summary-dialog-title" onCancel={event=>{event.preventDefault();close()}} onClose={()=>trigger.current?.focus()}><header><div><span className="px-eyebrow">当前上下文</span><h2 id="task-summary-dialog-title">本任务</h2></div><button type="button" aria-label="关闭本任务" autoFocus onClick={close}>关闭</button></header>{content(true)}</dialog>
  </div>;
}

function SummaryContent({expandedDescription=false,description="",understanding,clarification,revision,exact,criteria,sets,authorization,busy,readFailed,copied,onCopy,onLocateProblem,onLocateAuthorization}:{expandedDescription?:boolean;description?:string;understanding?:UnderstandingItem[];clarification?:string|null;revision?:BusinessProblemRevision;exact?:BusinessProblemRevision;criteria:CriterionRevision[];sets:CriteriaSetRevision[];authorization:AuthorizationSummary;busy:boolean;readFailed:boolean;copied:boolean;onCopy:()=>void;onLocateProblem:()=>void;onLocateAuthorization:()=>void}){
  const request=authorization.request,continuation=authorization.continuation;
  const authorizationState=request?.state==="PENDING"?"等待审批":request?.state==="APPROVED"?"已批准":request?.state==="REJECTED"?"已拒绝":continuation?.state==="AVAILABLE"?"待申请":continuation?.state==="EXPIRED"?"申请已过期":revision?"尚未申请":"暂无申请";
  const readState=exact?"读取成功":request?.state==="APPROVED"&&busy?"正在读取":request?.state==="APPROVED"&&readFailed?"暂时无法读取":"尚未读取";
  const next=exact?"可返回问题详情；修改此问题需要另行授权。":request?.state==="APPROVED"?(readFailed?"回到授权卡片重新读取。":"正在读取获准的问题详情。"):request?.state==="REJECTED"?"如仍需查看，请按正式流程重新取得授权。":request?.state==="PENDING"?"由独立管理员处理后，在授权卡片刷新。":continuation?.state==="AVAILABLE"?"回到授权卡片申请查看权限。":continuation?.state==="EXPIRED"?"已创建问题保留；本页不会自动延长申请窗口。":"先在对话中确认并创建问题。";
  const highest=[...sets].sort((a,b)=>b.revision-a.revision)[0],members=highest?.ordered_criterion_revision_ids.map(id=>criteria.find(item=>item.revision_id===id)).filter((item):item is CriterionRevision=>Boolean(item))??[];
  const organized=understanding?.filter(item=>item.source!=="UNKNOWN"&&!isUnstructuredStatement(item,description))??[];
  const unorganized=understanding?.filter(item=>item.source==="UNKNOWN")??[];
  const RequestContainer=exact?"details":"section";
  if(!revision)return <div className="px-task-summary-content">
    <section><span className="px-eyebrow">当前阶段 · {understanding?.length&&!clarification?"确认目标":"理解问题"}</span><h3>{clarification?"等待你补充":understanding?.length?"核对你提供的信息":"从你的问题开始"}</h3>{understanding?.length?<><p>{organized.length?`当前卡片单独列出 ${organized.length} 项内容，请对照原文核对来源。`:"当前保留你提供的信息，尚未形成单独整理的字段。"}</p>{unorganized.length>0&&<p className="px-summary-open-items">尚未单独整理：{[...new Set(unorganized.map(item=>fieldLabels[item.field]))].join("、")}。这不代表你未提供，不据此判断原文缺少信息。</p>}</>:<p>{clarification?"在左侧回答补问，也可以直接说明要修正的内容。":"描述希望解决的问题，补齐关键信息后，再核对当前卡片。"}</p>}</section>
    <section><span className="px-eyebrow">需要你处理</span><p>{clarification?"回答补问后更新理解；现在尚未创建正式问题。":"在对话中补充或修正内容，核对卡片后确认创建。未提交内容仅保留在本页。"}</p></section>
  </div>;
  return <div className="px-task-summary-content">
    <section><span className="px-eyebrow">问题摘要</span>{revision?<><h3>{revision.title}</h3>{exact?(expandedDescription?<p>{exact.description}</p>:<><p>已保存修订 {revision.revision}，完整内容见左侧。</p><details><summary>查看正式描述</summary><p>{exact.description}</p></details></>):<p>{readFailed?"本次读取暂时失败，旧的问题详情已撤下。":"获得查看权限后显示问题详情。"}</p>}<dl><dt>修订</dt><dd>{revision.revision}</dd><dt>授权状态</dt><dd>{authorizationState}</dd><dt>内容读取</dt><dd>{readState}</dd></dl><button type="button" onClick={onLocateProblem}>定位问题消息</button><details><summary>技术详情</summary><p>问题详情仅在 fresh exact GET 成功后显示；摘要不会用本地草稿补全正式响应。</p></details></>:<p>确认创建后，这里显示正式响应中的问题摘要。</p>}</section>
    <RequestContainer className="px-summary-request">{exact?<summary>查看申请 · 已批准</summary>:<span className="px-eyebrow">查看申请</span>}<h3>{authorizationState}</h3><p>{next}</p>{request&&<><details><summary>申请编号与复制</summary><code>{request.requestId}</code><button type="button" onClick={onCopy}>复制申请编号</button><span className="px-copy-status" aria-live="polite">{copied?"已复制":""}</span></details></>} {(request||continuation)&&<button type="button" onClick={onLocateAuthorization}>定位授权消息</button>}</RequestContainer>
    <section className={highest?undefined:"px-summary-empty"}><span className="px-eyebrow">已保存成功标准</span>{highest?<><h3>{members.length} 项正式成员</h3><p>{members.map(item=>String(item.measurement.rubric??item.criterion_type)).join("；")}</p><dl><dt>显示依据</dt><dd>正式返回历史中的最高修订，不代表自动选择</dd><dt>成功标准集合修订</dt><dd>{highest.revision}</dd></dl><details><summary>集合技术标识</summary><code>{highest.set_revision_id}</code></details><button type="button" onClick={()=>document.getElementById("saved-success-criteria-message")?.scrollIntoView({behavior:"smooth",block:"center"})}>定位成功标准</button></>:<details><summary>尚无正式集合响应</summary><p>尚无正式成功标准集合响应；本地草稿和页内补充不会出现在这里。</p></details>}</section>
  </div>;
}
