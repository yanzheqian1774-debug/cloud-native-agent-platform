import type {CriteriaSetRevision,CriterionRevision,ExactGrantRequest,GrantRequestStatus} from "../api/businessWorkspace";
import type {CriteriaSetBase,SuccessCriterionDraft,SuccessCriterionTurn} from "./successCriteriaModel";

type CriteriaAuthorization={stage:"WORKSPACE"|"CRITERION"|"SET";requestKey:string;grants:ExactGrantRequest[];request?:GrantRequestStatus}|null;
type Props={turn:SuccessCriterionTurn;busy:boolean;composerEditing:boolean;authorization:CriteriaAuthorization;onConfirm:()=>void;onRecover:()=>void;onRequestAuthorization:()=>void;onRefreshAuthorization:()=>void;onRestartAfterConflict:()=>void;onEdit:()=>void;onCancel:()=>void;onChange:(draft:SuccessCriterionDraft)=>void};

export function SuccessCriterionCard({turn,busy,composerEditing,authorization,onConfirm,onRecover,onRequestAuthorization,onRefreshAuthorization,onRestartAfterConflict,onEdit,onCancel,onChange}:Props){
  const active=turn.phase==="DRAFT"||turn.phase==="EDITING",saving=turn.phase==="SAVING_CRITERION"||turn.phase==="SAVING_SET",unknown=turn.phase==="UNKNOWN_CRITERION"||turn.phase==="UNKNOWN_SET",saved=turn.phase==="SAVED";
  const status=active?"待确认":saving?"正在保存":unknown?"结果未知":turn.phase==="CRITERION_FAILED"?"标准未保存":turn.phase==="SET_FAILED"?"关联未完成":turn.phase==="CONFLICT"?"版本冲突":saved?"已保存":"已取消";
  return <section id="draft-success-criterion-message" tabIndex={-1} className={`px-inline-card px-criterion-card is-${turn.phase.toLowerCase()}`} aria-label="成功标准待确认卡片">
    <header><div><span className="px-eyebrow">{saved?"正式成功标准":"成功标准草稿"}</span><h2>{saved?"已保存并完成正式关联":turn.source?"修订已选中的成功标准":"怎样才算解决？"}</h2></div><span className={`px-status ${saved?"success":turn.phase==="CANCELLED"?"neutral":turn.phase==="CONFLICT"||unknown?"danger":"warning"}`}>{status}</span></header>
    {turn.phase==="CANCELLED"?<p>已取消本地成功标准草稿，没有调用正式保存接口。</p>:<>
      <p className="px-truth-note">以下内容保留你的原文。系统没有补写阈值、期限、数据或目标，也没有用关键词推断标准类型。</p>
      <blockquote>{turn.draft.text}</blockquote>
      <fieldset disabled={busy||!active||composerEditing}>
        <legend>由你明确选择标准类型</legend>
        <label><input type="radio" name={`criterion-kind-${turn.id}`} checked={turn.draft.kind==="HUMAN_EVALUATED"} onChange={()=>onChange({...turn.draft,kind:"HUMAN_EVALUATED"})}/> 人工验收标准</label>
        <small>由人根据这段原文判断是否满足。数值阈值、证据存在等其他类型本批尚未接入，系统不会代填技术字段。</small>
      </fieldset>
      <small>草稿版本 {turn.version} · 关联当前 Problem <code>{turn.problemId}</code>。{saved?"以上内容来自本次正式响应；刷新后将由正式读回恢复。":"确认前只保存在当前页面。"}</small>
      <details><summary>实际提交内容与精确修订</summary><dl><dt>类型</dt><dd>HUMAN_EVALUATED</dd><dt>Measurement rubric</dt><dd>{turn.draft.text}</dd><dt>Evidence kinds</dt><dd>空列表</dd><dt>Evaluator</dt><dd>HUMAN / v1</dd><dt>Applicability</dt><dd>空对象</dd>{turn.baseSet&&<><dt>基于 Criteria Set</dt><dd><code>{turn.baseSet.setRevisionId}</code>（修订 {turn.baseSet.revision}）</dd></>}{turn.source&&<><dt>修订 Criterion</dt><dd><code>{turn.source.revisionId}</code>（修订 {turn.source.revision}）</dd></>}</dl></details>
      {composerEditing&&<p className="px-mode-note">正在底部同一个输入框修改标准原文；采用或取消前，卡片确认操作不可用。</p>}
      {saving&&<p className="px-mode-note">{turn.phase==="SAVING_CRITERION"?"正在创建不可变标准修订。":"标准修订已返回，正在写入 Success Criteria Set 关联。"}你仍可在底部输入框记录新的页内补充。</p>}
      {unknown&&<p className="px-mode-note">原命令、payload 和幂等键已冻结。恢复只会重放这条命令，不会创建新标准。</p>}
      {turn.phase==="CRITERION_FAILED"&&<p className="px-mode-note">正式标准写入被拒绝或未完成，没有把草稿标成已保存。重试会沿用原标准命令。</p>}
      {turn.phase==="SET_FAILED"&&<p className="px-mode-note">标准 revision 已由正式接口返回，但 Criteria Set 关联未完成；它不会显示为 Problem 已保存标准。恢复会沿用原关联命令。</p>}
      {turn.phase==="CONFLICT"&&<p className="px-mode-note">服务器版本已经变化，原命令没有覆盖新版。请读取最新正式状态后重新确认关联基础。</p>}
      {authorization&&<section className="px-criterion-authorization" aria-label="成功标准权限申请"><h3>{authorization.stage==="CRITERION"?"标准写入权限":"标准关联权限"}</h3>{authorization.request?<><span className={`px-status ${authorization.request.state==="APPROVED"?"success":authorization.request.state==="REJECTED"?"danger":"warning"}`}>{authorization.request.state==="PENDING"?"等待独立审批":authorization.request.state==="APPROVED"?"已批准":"已拒绝"}</span><p>{authorization.request.state==="PENDING"?"把精确申请编号交给独立管理员；批准前不会把失败的 owner 命令标成成功。":authorization.request.state==="REJECTED"?"管理员已拒绝，本页保留原命令和输入，不会绕过授权。":"权限已批准，页面将恢复原命令。"}</p><dl><dt>申请编号</dt><dd><code>{authorization.request.requestId}</code></dd><dt>请求操作</dt><dd>{authorization.request.requestedActions.join(", ")}</dd></dl><div className="px-card-actions">{authorization.request.state==="PENDING"&&<a href={`/authorization-admin?request=${encodeURIComponent(authorization.request.requestId)}`} target="_blank" rel="noreferrer">在独立管理员窗口打开</a>}{authorization.request.state==="REJECTED"?<button type="button" disabled={busy} onClick={onRequestAuthorization}>重新提交新申请</button>:<button type="button" disabled={busy} onClick={onRefreshAuthorization}>{busy?"正在检查…":"刷新权限状态并继续"}</button>}</div></>:<p>正在提交正式精确权限申请；申请不是授权，仍需另一位有权管理员决定。</p>}<details><summary>申请的精确权限</summary><ul>{authorization.grants.map(item=><li key={`${item.owner}:${item.action}:${item.resource}`}><code>{item.owner} {item.action} {item.resource}</code></li>)}</ul></details></section>}
    </>}
    {active&&!composerEditing&&<div className="px-card-actions"><button type="button" disabled={busy} onClick={onCancel}>取消</button><button type="button" disabled={busy} onClick={onEdit}>修改原文</button><button type="button" className="px-primary-button" disabled={busy||!turn.draft.text.trim()||turn.draft.kind!=="HUMAN_EVALUATED"} onClick={onConfirm}>确认并保存</button></div>}
    {unknown&&<button type="button" className="px-primary-button" disabled={busy} onClick={onRecover}>{busy?"正在恢复原命令…":"恢复原保存结果"}</button>}
    {(turn.phase==="CRITERION_FAILED"||turn.phase==="SET_FAILED")&&!authorization?.request&&<button type="button" className="px-primary-button" disabled={busy} onClick={onRequestAuthorization}>{busy?"正在申请…":"申请所需精确权限"}</button>}
    {turn.phase==="CONFLICT"&&<button type="button" className="px-primary-button" disabled={busy} onClick={onRestartAfterConflict}>读取最新状态并选择精确集合</button>}
  </section>;
}

export function SavedCriteriaHistory({sets,criteria,busy,pendingText,onCreateFrom,onRevise}:{sets:CriteriaSetRevision[];criteria:CriterionRevision[];busy:boolean;pendingText:string;onCreateFrom:(base:CriteriaSetBase)=>void;onRevise:(base:CriteriaSetBase,criterion:CriterionRevision)=>void}){
  const byId=new Map(criteria.map(item=>[item.revision_id,item])),ordered=[...sets].sort((a,b)=>b.revision-a.revision);
  if(!ordered.length)return null;
  return <section id="saved-success-criteria-message" tabIndex={-1} className="px-inline-card px-saved-criteria" aria-label="已保存成功标准"><header><div><span className="px-eyebrow">正式读回</span><h2>已保存成功标准</h2></div><span className="px-status success">{ordered.length} 个集合修订</span></header><p className="px-truth-note">这里展示正式接口返回的不可变历史。列表按 revision 倒序显示不等于自动选择 latest；新增或修改必须点击明确的 exact 集合或标准。</p>{ordered.map(set=>{const base={setRevisionId:set.set_revision_id,revision:set.revision,orderedCriterionRevisionIds:set.ordered_criterion_revision_ids};return <article className="px-saved-set" key={set.set_revision_id}><header><strong>Criteria Set 修订 {set.revision}</strong><code>{set.set_revision_id}</code></header><ul>{set.ordered_criterion_revision_ids.map(id=>{const item=byId.get(id),rubric=item?.criterion_type==="HUMAN_EVALUATED"?String(item.measurement.rubric??""):"该标准类型本批只读";return <li key={id}><span><b>{rubric}</b><small>{item?`${item.criterion_type} · Criterion 修订 ${item.revision}`:"当前响应未包含可读成员详情"}</small></span>{item?.criterion_type==="HUMAN_EVALUATED"&&<button type="button" disabled={busy} onClick={()=>onRevise(base,item)}>修订此标准</button>}</li>})}</ul><button type="button" disabled={busy} onClick={()=>onCreateFrom(base)}>{pendingText.trim()?"明确采用当前输入并基于此集合保存":"基于此集合新增标准"}</button><details><summary>集合技术详情</summary><dl><dt>Problem Revision</dt><dd><code>{set.problem_revision_id}</code></dd><dt>Set Digest</dt><dd><code>{set.digest}</code></dd><dt>Predecessor</dt><dd><code>{set.predecessor_set_revision_id??"无"}</code></dd></dl></details></article>})}</section>;
}
