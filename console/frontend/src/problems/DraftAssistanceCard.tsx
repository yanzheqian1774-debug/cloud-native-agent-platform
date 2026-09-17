import type { DraftAssistanceResult } from "../api/businessWorkspace";

type Props = {
  result: DraftAssistanceResult;
  compact?: boolean;
  busy: boolean;
  onRefresh: () => void;
  onAnswer?: () => void;
  onObserve: () => void;
  onCancel: () => void;
  onReject: () => void;
  onManualFallback: () => void;
};

export function DraftAssistanceCard({result,compact=false,busy,onAnswer,onRefresh,onObserve,onCancel,onReject,onManualFallback}:Props){
  const pending=result.state==="AUTHORIZATION_PENDING"||result.state==="REQUESTED_AWAITING_CONTENT";
  const unknown=result.state==="OUTCOME_UNKNOWN"||result.state==="CANCELLATION_REQUESTED";
  const finished=result.state==="SUCCEEDED";
  const draftReady=finished&&result.resultKind==="DRAFT_READY";
  const clarification=finished&&result.resultKind==="NEEDS_CLARIFICATION";
  const statusLabel=clarification?"等待补充信息":({AUTHORIZATION_PENDING:"等待授权",REQUESTED_AWAITING_CONTENT:"等待正文重交",OUTCOME_UNKNOWN:"结果待确认",CANCELLATION_REQUESTED:"正在请求取消",CANCELLATION_CONFIRMED:"已取消",REJECTED_BY_USER:"已拒绝",SUCCEEDED:draftReady?"草稿已生成":"辅助已完成",FAILED:"辅助失败"} as Record<string,string>)[result.state]??"状态已更新";
  const Wrapper=compact?"details":"section";
  return <Wrapper id="draft-assistance-message" tabIndex={-1} className="px-inline-card px-assistance-card" aria-label="AI 问题理解与草稿辅助">
    {compact&&<summary>AI 辅助来源与调用状态</summary>}
    <header><div><span className="px-eyebrow">{clarification?"AI 需要你补充":"AI 建议草稿（尚未创建）"}</span><h2>{pending?"等待精确授权":unknown?"调用结果尚不确定":result.resultKind==="NEEDS_CLARIFICATION"?"需要补充信息":result.resultKind==="DRAFT_READY"?"可修改草稿已生成":"辅助状态已更新"}</h2></div><span className={`px-status ${clarification?"warning":finished?"success":result.state.includes("REJECT")||result.state.includes("FAIL")?"danger":"warning"}`}>{statusLabel}</span></header>
    <p className="px-truth-note">{result.transport==="SYNTHETIC"?"本次使用明确标识的模拟辅助生成，没有调用真实 AI 服务。":draftReady?"本次草稿来自已授权的真实 AI 服务；仍需人工核对和确认。":clarification?"本次补问来自已授权的真实 AI 服务；尚未生成可确认草稿。":"本次辅助使用真实 AI 服务通道；是否完成以调用状态为准。"}</p>
    {result.clarificationQuestion&&<div className="px-assistance-question"><strong>请补充以下关键信息</strong><p>{result.clarificationQuestion}</p>{onAnswer&&<button type="button" className="px-primary-button" disabled={busy} onClick={onAnswer}>回答补问</button>}</div>}
    {result.reasonCode&&<p className="px-mode-note">状态说明：<code>{result.reasonCode}</code>{result.reasonCode==="RESULT_CONTENT_NOT_RETAINED"?"。服务端可恢复调用事实，但不会恢复原草稿正文；请明确选择手工草稿或新 successor。":""}</p>}
    {pending&&<p>服务端只保留非正文元数据。授权完成或连接恢复后，请用当前页面重交同一正文；页面不会自动重派。</p>}
    {unknown&&<p>系统只会检查原调用的后续结果；不会把待确认状态显示为成功，也不会自动发起替代调用。</p>}
    <div className={`px-card-actions${clarification?" px-secondary-actions":""}`}>
      {pending&&<button type="button" className="px-primary-button" disabled={busy} onClick={onRefresh}>重交正文并刷新授权</button>}
      {unknown&&<button type="button" className="px-primary-button" disabled={busy} onClick={onObserve}>观察原调用</button>}
      {!finished&&<button type="button" disabled={busy} onClick={onCancel}>请求取消</button>}
      {finished&&<button type="button" disabled={busy} onClick={onReject}>{draftReady?"拒绝 AI 草稿":"拒绝本次辅助"}</button>}
      <button type="button" disabled={busy} onClick={onManualFallback}>切换为手工草稿</button>
    </div>
    <details><summary>技术事实</summary><dl><dt>技术状态</dt><dd><code>{result.state}</code></dd><dt>Transport</dt><dd><code>{result.transport}</code></dd><dt>Invocation</dt><dd><code>{result.invocationId}</code></dd><dt>Turn</dt><dd><code>{result.turnId}</code> / v{result.turnVersion}</dd><dt>辅助授权申请</dt><dd><code>{result.requestAuthorizationRequestId??"尚未提交"}</code></dd><dt>模型授权申请</dt><dd><code>{result.modelAuthorizationRequestId??"尚未提交"}</code></dd><dt>正文处置</dt><dd>{result.contentDisposition}</dd><dt>Resource Use</dt><dd>{result.resourceUseRecorded?"已建立；标识需独立 READ 授权":"尚未建立"}</dd><dt>Evidence</dt><dd>{result.evidenceRecorded?"已补记；引用与内容需独立授权":"尚未建立"}</dd></dl><p>Draft Assistance 不是 Attempt；技术调用成功不表示业务问题已经解决。</p></details>
  </Wrapper>;
}
