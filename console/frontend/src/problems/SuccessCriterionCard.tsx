import type {SuccessCriterionDraft,SuccessCriterionTurn} from "./successCriteriaModel";

type Props={
  turn:SuccessCriterionTurn;
  busy:boolean;
  composerEditing:boolean;
  onConfirm:()=>void;
  onEdit:()=>void;
  onCancel:()=>void;
  onChange:(draft:SuccessCriterionDraft)=>void;
};

export function SuccessCriterionCard({turn,busy,composerEditing,onConfirm,onEdit,onCancel,onChange}:Props){
  const active=turn.phase==="DRAFT"||turn.phase==="EDITING",confirmed=turn.phase==="CONFIRMED";
  return <section id="draft-success-criterion-message" tabIndex={-1} className={`px-inline-card px-criterion-card is-${turn.phase.toLowerCase()}`} aria-label="成功标准待确认卡片">
    <header><div><span className="px-eyebrow">{confirmed?"成功标准确认":"成功标准草稿"}</span><h2>{confirmed?"已确认，尚未保存":"怎样才算解决？"}</h2></div><span className={`px-status ${confirmed?"warning":turn.phase==="CANCELLED"?"neutral":"warning"}`}>{confirmed?"待保存":turn.phase==="CANCELLED"?"已取消":"待确认"}</span></header>
    {turn.phase==="CANCELLED"?<p>已取消本地成功标准草稿，没有调用正式保存接口。</p>:<>
      <p className="px-truth-note">以下内容保留你的原文。系统没有补写阈值、期限、数据或目标，也没有用关键词推断标准类型。</p>
      <blockquote>{turn.draft.text}</blockquote>
      <fieldset disabled={busy||confirmed||composerEditing}>
        <legend>由你明确选择标准类型</legend>
        <label><input type="radio" name={`criterion-kind-${turn.id}`} checked={turn.draft.kind==="HUMAN_EVALUATED"} onChange={()=>onChange({...turn.draft,kind:"HUMAN_EVALUATED"})}/> 人工验收标准</label>
        <small>由人根据这段原文判断是否满足。数值阈值、证据存在等其他类型本批尚未接入，系统不会代填技术字段。</small>
      </fieldset>
      <small>草稿版本 {turn.version} · 关联当前 Problem <code>{turn.problemId}</code>。确认前只保存在当前页面。</small>
      {composerEditing&&<p className="px-mode-note">正在底部同一个输入框修改标准原文；采用或取消前，卡片确认操作不可用。</p>}
    </>}
    {active&&!composerEditing&&<div className="px-card-actions"><button type="button" disabled={busy} onClick={onCancel}>取消</button><button type="button" disabled={busy} onClick={onEdit}>修改原文</button><button type="button" className="px-primary-button" disabled={busy||!turn.draft.text.trim()||turn.draft.kind!=="HUMAN_EVALUATED"} onClick={onConfirm}>确认成功标准</button></div>}
  </section>;
}
