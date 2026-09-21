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
  if(status===401)return{title:`${operation}前需要重新登录`,detail:"当前可信会话已失效。重新登录后返回本页，再继续当前操作。"};
  if(status===403)return{title:`无法完成${operation}`,detail:`当前会话不能执行这项操作。页面不会据此披露其他资源或权限信息。${mutation?"你的当前输入仍保留。":""}`};
  if(status===404)return{title:operation==="读取成功标准"?"无法打开成功标准内容":"无法打开该内容",detail:"该内容可能不存在，也可能对当前会话不可见。为保护资源信息，页面不会进一步区分。"};
  if(status===409)return{title:`${operation}遇到版本冲突`,detail:"服务器中的内容已经变化。你的输入仍保留在页面中；请刷新当前状态，核对后再提交。"};
  if(status===422)return{title:`${operation}的内容未通过校验`,detail:`请检查页面标出的必填项和长度限制，修改后再提交。${mutation?"你的当前输入仍保留。":""}`};
  if(status===503||status===0)return mutation
    ?{title:`${operation}的结果暂时无法确认`,detail:"你的输入仍保留在页面中。服务恢复后请在当前页面重试；系统会沿用本次操作标识，避免另发一条重复命令。"}
    :{title:`暂时无法${operation}`,detail:"服务当前不可用。请保留本页并稍后重试；页面不会把这次失败解释为资源不存在或无权限。"};
  return{title:`${operation}未完成`,detail:"你的当前输入没有被清除。请展开技术详情记录诊断信息，确认服务恢复后再重试。"};
}

export function WorkbenchErrorNotice({error,operation,mutation=false,onRetry,retryLabel="重试当前操作"}:Props){
  const known=error instanceof WorkbenchRequestError;
  const copy=message(error,operation,mutation);
  return <section className="px-workbench-error" role="alert" aria-live="assertive">
    <strong>{copy.title}</strong>
    <p>{copy.detail}</p>
    {onRetry&&<button type="button" onClick={onRetry}>{retryLabel}</button>}
    <details><summary>技术详情</summary><dl>
      <dt>操作</dt><dd>{operation}</dd>
      <dt>状态</dt><dd>{known&&error.status>0?error.status:"网络或响应不可用"}</dd>
      <dt>技术码</dt><dd><code>{known?error.reasonCode:"WORKBENCH_UNAVAILABLE"}</code></dd>
      {known&&error.requestId&&<><dt>诊断 ID</dt><dd><code>{error.requestId}</code></dd></>}
    </dl></details>
  </section>;
}
