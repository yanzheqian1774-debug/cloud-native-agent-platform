import {useState} from "react";
import { WorkbenchRequestError } from "../api/businessWorkspace";

export type WorkbenchOperation=
  |"恢复工作区"
  |"读取成功标准"
  |"打开业务问题"
  |"创建业务问题"
  |"保存业务问题"
  |"确认问题与完成标准"
  |"保存成功标准"
  |"申请成功标准权限"
  |"刷新成功标准权限"
  |"申请查看权限"
  |"刷新授权状态"
  |"恢复授权状态"
  |"请求 AI 草稿辅助"
  |"刷新 AI 草稿辅助"
  |"观察 AI 原调用"
  |"取消 AI 草稿辅助"
  |"拒绝 AI 草稿"
  |"补记草稿来源"
  |"恢复管理员会话"
  |"检查授权申请"
  |"提交授权决定";

type Props={error:unknown;operation:WorkbenchOperation;mutation?:boolean;onRetry?:()=>void;retryLabel?:string};

function message(error:unknown,operation:WorkbenchOperation,mutation:boolean){
  const status=error instanceof WorkbenchRequestError?error.status:0;
  const reason=error instanceof WorkbenchRequestError?error.reasonCode:"";
  const assistance=operation.includes("AI");
  if(reason==="DRAFT_ASSISTANCE_NOT_CONFIGURED" || (assistance&&status===405))return{title:"AI 草稿辅助当前不可用",detail:"当前服务未装配草稿辅助入口，本次没有进入模型派发。输入保留在本页；请提供下方诊断编号，由管理员完成服务装配与准入核验后，再明确发送。无需反复切换账号。"};
  if(assistance&&["TRANSPORT_AMBIGUOUS","TASK_DELEGATION_OUTCOME_UNKNOWN","TASK_DELEGATION_PENDING_RESERVATION","CONTEXT_ADMISSION_OUTCOME_UNKNOWN"].includes(reason))return{title:"AI 调用结果需要核验",detail:"存在结果未知或未结算预留。请查询原调用或使用正式恢复流程，不能作为普通失败再次发送。输入仍保留，页面不会自动重发。若没有可查询的原调用编号，请将诊断编号交给管理员定位，发送入口暂时停用。"};
  if(assistance&&["OUTPUT_SCHEMA_INVALID","INVALID_PROVIDER_RESPONSE"].includes(reason))return{title:"AI 生成内容未通过契约校验",detail:"本次生成未完成，不能作为成功草稿。请保留原调用记录，按正式修正或后继流程处理。"};
  if(assistance&&(status===403||reason==="DRAFT_AUTHORIZATION_UNAVAILABLE"))return{title:"AI 草稿辅助权限尚未就绪",detail:"需要草稿辅助与模型调用的精确准入。请在授权申请入口核对当前主体的申请；不会披露无权查看的对象，也不会因登录成功自动取得业务权限。输入仍保留。"};
  if(status===401)return{title:`${operation}前需要重新登录`,detail:"当前可信会话已失效。重新登录后返回本页，再继续当前操作。"};
  if(status===403)return{title:`无法完成${operation}`,detail:`当前会话不能执行这项操作。页面不会据此披露其他资源或权限信息。${mutation?"你的当前输入仍保留。":""}`};
  if(status===404)return{title:operation==="读取成功标准"?"无法打开成功标准内容":"无法打开该内容",detail:"该内容可能不存在，也可能对当前会话不可见。为保护资源信息，页面不会进一步区分。"};
  if(status===409)return{title:`${operation}遇到版本冲突`,detail:"服务器中的内容已经变化。你的输入仍保留在页面中；请刷新当前状态，核对后再提交。"};
  if(status===422)return{title:`${operation}的内容未通过校验`,detail:`请检查页面标出的必填项和长度限制，修改后再提交。${mutation?"你的当前输入仍保留。":""}`};
  if(status===503||status===0)return mutation
    ?{title:`${operation}的结果暂时无法确认`,detail:"你的输入仍保留在页面中。先核对原操作是否已保存或派发；结果未知时查询原记录，不直接重发。只有确认可恢复后才沿用原操作标识继续。"}
    :{title:`暂时无法${operation}`,detail:"服务当前不可用。请保留本页并稍后重试；页面不会把这次失败解释为资源不存在或无权限。"};
  return{title:`${operation}未完成`,detail:"你的当前输入没有被清除。请展开技术详情记录诊断信息，确认服务恢复后再重试。"};
}

export function WorkbenchErrorNotice({error,operation,mutation=false,onRetry,retryLabel="重试当前操作"}:Props){
  const [copyState,setCopyState]=useState("");
  const known=error instanceof WorkbenchRequestError;
  const copy=message(error,operation,mutation);
  return <section className="px-workbench-error" role="alert" aria-live="assertive">
    <strong>{copy.title}</strong>
    <p>{copy.detail}</p>
    {known&&error.requestId&&<p>诊断编号：<code>{error.requestId}</code> <button type="button" onClick={()=>{void navigator.clipboard.writeText(JSON.stringify({operation,status:error.status,reasonCode:error.reasonCode,requestId:error.requestId})).then(()=>setCopyState("诊断信息已复制"),()=>setCopyState("复制未完成，请选中诊断编号复制"))}}>复制诊断信息</button></p>}
    {copyState&&<p role="status">{copyState}</p>}
    {known&&operation.includes("AI")&&(error.status===403||error.reasonCode==="DRAFT_AUTHORIZATION_UNAVAILABLE")&&<a href="/authorization-admin">查看授权申请入口</a>}
    {onRetry&&<button type="button" onClick={onRetry}>{retryLabel}</button>}
    <details><summary>技术详情</summary><dl>
      <dt>操作</dt><dd>{operation}</dd>
      <dt>状态</dt><dd>{known&&error.status>0?error.status:"网络或响应不可用"}</dd>
      <dt>技术码</dt><dd><code>{known?error.reasonCode:"WORKBENCH_UNAVAILABLE"}</code></dd>
      {known&&error.requestId&&<><dt>诊断 ID</dt><dd><code>{error.requestId}</code></dd></>}
    </dl></details>
  </section>;
}
