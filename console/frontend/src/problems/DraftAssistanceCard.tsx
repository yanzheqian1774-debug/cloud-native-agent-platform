import {DraftAuthorizationStatus} from "./DraftAuthorizationStatus";
import type { DraftAssistanceResult } from "../api/businessWorkspace";

type Props = {
  result: DraftAssistanceResult;
  compact?: boolean;
  contentAvailable?: boolean;
  canResubmit?: boolean;
  originalText?: string;
  onSuccessor?: () => void;
  busy: boolean;
  onRefresh: () => void;
  onAnswer?: () => void;
  onObserve: () => void;
  onCancel: () => void;
  onReject: () => void;
  onManualFallback: () => void;
};

export function DraftAssistanceCard({result,compact=false,contentAvailable=false,canResubmit=true,originalText,onSuccessor,busy,onAnswer,onRefresh,onObserve,onCancel,onReject,onManualFallback}:Props){
  const pending=result.state==="AUTHORIZATION_PENDING"||result.state==="REQUESTED_AWAITING_CONTENT";
  const unknown=result.state==="OUTCOME_UNKNOWN"||result.state==="CANCELLATION_REQUESTED";
  const finished=result.state==="SUCCEEDED";
  const draftReady=finished&&result.resultKind==="DRAFT_READY";
  const clarification=finished&&result.resultKind==="NEEDS_CLARIFICATION";
  const statusLabel=clarification?"等待补充信息":({AUTHORIZATION_PENDING:"等待授权",REQUESTED_AWAITING_CONTENT:"等待正文重交",OUTCOME_UNKNOWN:"结果待确认",CANCELLATION_REQUESTED:"取消已请求，停止未确认",CANCELLATION_CONFIRMED:"收到取消确认",REJECTED_BY_USER:"已拒绝",SUCCEEDED:draftReady?"草稿已生成":"辅助已完成",FAILED:"辅助失败",FAILED_PRE_DISPATCH:"派发前未通过"} as Record<string,string>)[result.state]??"状态已更新";
  const Wrapper=compact?"details":"section";
  return <Wrapper {...(compact&&result.settlementStatus&&!["NOT_MEASURED","ESTIMATE_SETTLED"].includes(result.settlementStatus)?{open:true}:{})} id="draft-assistance-message" tabIndex={-1} className="px-inline-card px-assistance-card" aria-label="AI 问题理解与草稿辅助">
    {compact&&<summary>AI 辅助来源与调用状态</summary>}
    <header><div><span className="px-eyebrow">{clarification?"AI 需要你补充":"AI 建议草稿（尚未创建）"}</span><h2>{pending?"等待精确授权":unknown?"调用结果尚不确定":result.resultKind==="NEEDS_CLARIFICATION"?"需要补充信息":result.resultKind==="DRAFT_READY"?"可修改草稿已生成":"辅助状态已更新"}</h2></div><span className={`px-status ${clarification?"warning":finished?"success":result.state.includes("REJECT")||result.state.includes("FAIL")?"danger":"warning"}`}>{statusLabel}</span></header>
    <p className="px-truth-note">{result.transport==="SYNTHETIC"?"本次使用明确标识的模拟辅助生成，没有调用真实 AI 服务。":draftReady?"本次草稿来自已授权的真实 AI 服务；仍需人工核对和确认。":clarification?"本次补问来自已授权的真实 AI 服务；尚未生成可确认草稿。":"本次辅助使用真实 AI 服务通道；是否完成以调用状态为准。"}</p>
    {result.settlementStatus&&result.settlementStatus!=="NOT_MEASURED"&&<p role="status">费用核对：{result.settlementStatus==="ESTIMATE_SETTLED"?"已记录估算，供应商账单未核实":result.settlementStatus==="SETTLEMENT_WRITE_PENDING"?"结算写入待恢复；停止后继调用，仅核对原调用":"用量待核对，预留保留；不得自动重发"}。业务结果与费用状态分别判定。</p>}
    {(unknown||result.state==="CANCELLATION_CONFIRMED")&&<p>取消请求不等于底层工作已停止。本地 worker：{result.localWorkerState==="REAPED"?"已回收":result.localWorkerState==="CLEANUP_NOT_PROVEN"?"回收未证实":"尚无退出证据"}；远端停止和停止计费均未证实。</p>}
    {result.clarificationQuestion&&<div className="px-assistance-question"><strong>请补充以下关键信息</strong><p>{result.clarificationQuestion}</p>{onAnswer&&<button type="button" className="px-primary-button" disabled={busy} onClick={onAnswer}>回答补问</button>}</div>}
    {result.reasonCode&&<p className="px-mode-note">状态说明：<code>{result.reasonCode}</code>{result.reasonCode==="RESULT_CONTENT_NOT_RETAINED"?"。服务端可恢复调用事实，但不会恢复原草稿正文；请明确选择手工草稿或新 successor。":""}</p>}
    {result.state==="FAILED_PRE_DISPATCH"&&<p role="alert">本次在模型派发前被拒绝。请核对配置、精确权限及预算准入；修复后通过正式后继流程继续，旧记录保持失败，不重复使用旧标识发送新内容。</p>}
    {result.state==="FAILED"&&["OUTPUT_SCHEMA_INVALID","PROVIDER_RESPONSE_INVALID"].includes(result.reasonCode??"")&&<p role="alert">模型返回内容未通过契约校验，生成未完成。不能将本次结果作为可确认草稿；请保留原调用证据并按后继修正流程处理。</p>}
    {pending&&<div className="px-mode-note"><strong>待独立准入，不是模型超时</strong><p>草稿辅助与模型调用分别保留正式授权记录。登录成功不会自动取得这些权限。审批人请在独立浏览器配置或隐私窗口打开链接；同浏览器的新标签不隔离账号，不要在本业务会话切换身份。</p><p><a target="_blank" rel="noreferrer" href={`/authorization-admin?context=${encodeURIComponent(result.contextId)}`}>核对本 context 的独立调用准入</a></p>{result.requestAuthorizationRequestId&&<p><a target="_blank" rel="noreferrer" href={`/authorization-admin?request=${encodeURIComponent(result.requestAuthorizationRequestId)}`}>查看本次草稿辅助申请</a></p>}{result.modelAuthorizationRequestId&&<p><a target="_blank" rel="noreferrer" href={`/authorization-admin?request=${encodeURIComponent(result.modelAuthorizationRequestId)}`}>查看本次模型调用申请</a></p>}</div>}
    {pending&&<><DraftAuthorizationStatus result={result}/>{contentAvailable?<><p>原始提交正文仍保留在本页内存中，输入框清空不代表正文丢失。查询授权不会重交；下方单独按钮才会请求实际调用。离开或刷新后正文不能从服务端恢复。</p><details><summary>查看本页保留的用户原文</summary><p>{originalText}</p></details></>:<p role="status">原始提交正文在本页不可用，服务端只保存元数据和校验承诺，无法恢复原文。本次不能重交；保留原对象与摘要，可明确填写关联后继，不能冒充原正文。</p>}</>}
    {unknown&&<p>系统只会检查原调用的后续结果；不会把待确认状态显示为成功，也不会自动发起替代调用。</p>}
    <div className={`px-card-actions${clarification?" px-secondary-actions":""}`}>
      {pending&&contentAvailable&&<button type="button" className="px-primary-button" disabled={busy||!canResubmit} onClick={onRefresh}>使用已保留正文继续 AI 调用</button>}
      {pending&&!contentAvailable&&onSuccessor&&<button type="button" disabled={busy} onClick={onSuccessor}>填写关联后继（保留原记录）</button>}
      {unknown&&<button type="button" className="px-primary-button" disabled={busy} onClick={onObserve}>观察原调用</button>}
      {!finished&&<button type="button" disabled={busy} onClick={onCancel}>请求取消</button>}
      {finished&&<button type="button" disabled={busy} onClick={onReject}>{draftReady?"拒绝 AI 草稿":"拒绝本次辅助"}</button>}
      <button type="button" disabled={busy||!contentAvailable} onClick={onManualFallback}>切换为手工草稿</button>
    </div>
    <details><summary>技术事实</summary><dl><dt>技术状态</dt><dd><code>{result.state}</code></dd><dt>Transport</dt><dd><code>{result.transport}</code></dd><dt>Invocation</dt><dd><code>{result.invocationId}</code></dd><dt>Turn</dt><dd><code>{result.turnId}</code> / v{result.turnVersion}</dd><dt>辅助授权申请</dt><dd><code>{result.requestAuthorizationRequestId??"尚未提交"}</code></dd><dt>模型授权申请</dt><dd><code>{result.modelAuthorizationRequestId??"尚未提交"}</code></dd><dt>正文处置</dt><dd>{result.contentDisposition}</dd><dt>Resource Use</dt><dd>{result.resourceUseRecorded?"已建立；标识需独立 READ 授权":"尚未建立"}</dd><dt>Evidence</dt><dd>{result.evidenceRecorded?"已补记；引用与内容需独立授权":"尚未建立"}</dd></dl><p>Draft Assistance 不是 Attempt；技术调用成功不表示业务问题已经解决。</p></details>
  </Wrapper>;
}
