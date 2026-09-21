import { Fragment, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { readWorkbenchSession } from "../api/businessWorkspace";
import * as api from "./api";
import "./planning.css";
import { JourneySteps } from "../journey/JourneySteps";
import { formatTime } from "../journey/formatTime";
import {PlanningDialogue} from "./PlanningDialogue";
import {UserMessage, SystemMessage} from "../problems/ProblemConversation";
import { artifactLabel, resourceKinds } from "./planningPresentation";

const labels: Record<string, string> = { MATCHED: "已匹配", MISSING: "待准备", UNKNOWN: "待核实", UNREADABLE: "无权读取", VERSION_MISMATCH: "版本不符", UNAVAILABLE: "不可用", NOT_REQUIRED: "可选 · 未选择" };

export function PlanningPage() {
  const { proposalId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const requested = Number(params.get("revision")) || null;
  const [view, setView] = useState<{ data: api.ProposalRead; history: api.History } | null>(null);
  const [original, setOriginal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const epoch = useRef(0);
  const command = useRef<{ target: string; key: string } | null>(null);
  useEffect(() => {
    const token = ++epoch.current;
    Promise.all([api.history(proposalId), readWorkbenchSession()]).then(async ([history]) => {
      const version = requested ?? Math.max(...history.proposals.map(p => p.revision));
      const data = await api.proposal(proposalId, version);
      if (token === epoch.current) { setView({ data, history }); setError(""); setBusy(false); }
    }).catch(e => { if (token === epoch.current) setError(String(e.message)); });
    return () => { epoch.current = token + 1; };
  }, [proposalId, requested]);
  if (!view || view.data.proposal.proposal_id !== proposalId || (requested && view.data.proposal.revision !== requested)) return <section className="planning-page"><h1>读取计划</h1><p role="status">{error || "正在读取持久化的建议与批准…"}</p><Link to="/work">返回问题工作台</Link></section>;
  const { data, history } = view;
  const translation = data.display_translation;
  const plan = !original && translation ? translation.semantics : data.proposal.semantics;
  const approved = history.plans.find(p => p.plan.source_proposal_revision === data.proposal.revision);
  const observations = new Map(data.snapshot?.observations.map(o => [o.requirement_id, o.status]) ?? []);
  const status = (r: api.Requirement) => observations.get(r.requirement_id) ?? (r.selected ? "UNKNOWN" : r.required ? "MISSING" : "NOT_REQUIRED");
  const missing = plan.requirements.filter(r => r.required && status(r) !== "MATCHED");
  const matched = plan.requirements.filter(r => status(r) === "MATCHED").length;
  const latest = Math.max(...history.proposals.map(p => p.revision));
  async function act(kind: "confirm" | "refresh") {
    if (busy) return;
    const token = epoch.current;
    setBusy(true); setError("");
    try {
      const session = await readWorkbenchSession();
      if (kind === "refresh") {
        const result = await api.refresh(proposalId, data.proposal.revision, session.csrfToken);
        if (epoch.current === token) setView({ data: { ...data, snapshot: result.snapshot }, history });
      } else {
        const target = `${proposalId}:${data.proposal.revision}:${data.digest}`;
        if (command.current?.target !== target) command.current = { target, key: crypto.randomUUID() };
        await api.confirm(proposalId, data.proposal.revision, data.digest, Math.max(0, ...history.plans.map(p => p.plan.version)), session.csrfToken, command.current.key);
        const fresh = await api.history(proposalId);
        if (epoch.current === token) setView({ data, history: fresh });
      }
    } catch (e) { if (epoch.current === token) setError(e instanceof Error ? e.message : "读取失败，请重试原操作"); }
    finally { if (epoch.current === token) setBusy(false); }
  }
  const previous = history.proposals.find(p => p.revision === data.proposal.revision - 1);
  const changedTasks = previous ? [...new Set([...previous.semantics.tasks.map(t=>t.task_id), ...data.proposal.semantics.tasks.map(t=>t.task_id)])].filter(id=>JSON.stringify(previous.semantics.tasks.find(t=>t.task_id===id))!==JSON.stringify(data.proposal.semantics.tasks.find(t=>t.task_id===id))) : [];
  const criteriaChanged = previous && (["resource_id", "revision_id", "digest"] as const).some(key => previous.semantics.target.criteria[key] !== plan.target.criteria[key]);
  const optional = plan.requirements.filter(r => !r.required);
  const optionalUnmatched = optional.filter(r => status(r) !== "MATCHED");
  const kinds = [...new Set(plan.requirements.map(r => r.kind))];
  const resourceBadge = (r: api.Requirement) => <span className={`planning-badge is-${status(r).toLowerCase()}`}>{labels[status(r)] ?? "待核实"}</span>;
  return <section className="planning-page journey-page">
    <header className="planning-heading"><div><p>问题工作台 <span aria-hidden="true">›</span> 制定方案</p><h1>{plan.title}</h1></div><Link className="journey-secondary" to={`/work?problem=${encodeURIComponent(plan.target.problem.resource_id)}`}>返回问题</Link></header>
    <div className="planning-layout"><main>
      <JourneySteps current={3} />
      {translation && <details className="planning-translation"><summary>中文译文（原方案未修改） · <button type="button" onClick={e=>{e.preventDefault();setOriginal(!original)}}>{original ? "显示中文译文" : "查看原文"}</button></summary><p>{translation.metadata.source} · 译文版本 {translation.metadata.translation_version} · {formatTime(translation.metadata.created_at)}</p><p>{translation.metadata.review_status}。不改变原确认。</p><code>来源 {translation.metadata.source_digest} · 译文 {translation.metadata.translation_digest}</code></details>}
      <p className="journey-guidance"><span aria-hidden="true">✦</span> {approved ? "计划确认已持久化。可继续提出修改，后继建议需要重新确认；旧批准保留。" : "先核对目标与方案，再确认计划。资源缺口会保留，确认不会启动执行。"}</p>
      <PlanningDialogue key={`${proposalId}:${data.proposal.revision}`} problem={plan.target.problem.resource_id} source={data} disabled={data.proposal.revision !== latest}>
      <section className="planning-conversation-history" aria-label="已保存的规划对话">
        {history.conversation?.length ? history.conversation.map(message => <Fragment key={message.invocation_id}>
          {message.request.answers.length > 0 && <UserMessage richContent authorLabel="已保存的规划输入" occurredAt={message.submitted_at}><span className="planning-context-note">该次请求携带的补充信息（可能包含前次上下文）</span>{message.request.answers.join("\n").length > 240 ? <details className="planning-saved-context"><summary>查看已保存的补充原文（含技术上下文）</summary><p style={{whiteSpace:"pre-wrap"}}>{message.request.answers.join("\n")}</p></details> : <span style={{whiteSpace:"pre-wrap"}}>{message.request.answers.join("\n")}</span>}</UserMessage>}
          {message.questions?.map(q=><SystemMessage label="模型补问记录" key={q} occurredAt={message.generated_at}><p>{q}</p></SystemMessage>)}
        </Fragment>) : <p className="journey-muted">当前读回未提供历史对话；仅展示已保存的方案和批准，不补造消息。</p>}
      </section>
      <SystemMessage label="持久方案记录" occurredAt={data.generated_at ?? undefined}>
      <p className="planning-fact-summary">{approved ? "当前方案已确认，旧批准保留。" : "建议已保存，等待你核对并显式确认。"} {missing.length} 项必要资源待准备或核实；当前没有执行任务。</p>
      <details className="planning-card planning-goal" open={!approved}><summary><h2><span aria-hidden="true">◎</span> 目标与完成标准 <small>{plan.business_rules.length}条 · 展开核对</small></h2></summary><ul>{plan.business_rules.map(rule => <li key={rule}>{rule}</li>)}</ul><details className="journey-technical"><summary>问题与标准的准确版本</summary><dl><dt>问题</dt><dd>{plan.target.problem.revision_id}</dd><dt>成功标准</dt><dd>{plan.target.criteria.revision_id}</dd></dl></details></details>
      <section className="planning-card planning-proposal"><h2><span aria-hidden="true">☷</span> 建议方案 <small>v{data.proposal.revision} · {plan.stages.length}阶段 / {plan.tasks.length}任务</small></h2>
        <table className="planning-task-table"><thead><tr><th scope="col">序号</th><th scope="col">任务名称与职责</th><th scope="col">前置任务</th><th scope="col">角色（定义）</th><th scope="col">预期输出</th><th scope="col">状态</th></tr></thead>
        {plan.stages.map((stage,index)=><tbody key={stage.stage_id}><tr className="planning-stage-row"><th colSpan={6} scope="rowgroup">{index+1} · {stage.title}（{stage.task_ids.length}项任务）</th></tr>{stage.task_ids.map(id=>{
          const task=plan.tasks.find(t=>t.task_id===id)!;
          const employee=plan.requirements.find(r=>r.requirement_id===task.employee_requirement_id);
          const resources=task.requirement_ids.map(rid=>plan.requirements.find(r=>r.requirement_id===rid)).filter((r):r is api.Requirement=>Boolean(r));
          return <Fragment key={id}><tr><td>{plan.tasks.indexOf(task)+1}</td><td><details className="planning-task"><summary className="planning-task-overview"><strong>{task.title}</strong><small>查看职责与输入</small></summary><p>{task.responsibility}</p><dl><dt>业务输入</dt><dd>{task.inputs.map(input=>artifactLabel(input,plan)).join("、")}</dd><dt>资源用途</dt><dd>{resources.map(r=>`${r.name}：${r.purpose}`).join("；") || "无额外需求"}</dd></dl><details className="journey-technical"><summary>准确标识</summary><p>任务 {id} · 依赖 {task.depends_on.join("、") || "无"}</p><p>输入标识：{task.inputs.join("、")} · 输出标识：{task.outputs.join("、")}</p></details></details></td><td>{task.depends_on.map(dep=>plan.tasks.findIndex(t=>t.task_id===dep)+1).join("、") || "无"}</td><td>{employee?.name ?? "待明确"}</td><td>{task.outputs.map(output=>artifactLabel(output,plan)).join("、")}</td><td><span className="planning-badge">尚未执行</span></td></tr></Fragment>;
        })}</tbody>)}</table><p className="journey-muted">以上是任务声明，预期输出尚未生成。角色定义不等于实例分工。</p>
      </section>
      {previous && <section className="planning-card"><h2>本次修订影响</h2><p>任务声明变化：{changedTasks.map(id=>plan.tasks.find(t=>t.task_id===id)?.title ?? `已移除 ${id}`).join("、") || "无"}</p><p>成功标准版本：{criteriaChanged ? "已变化，需要按新标准核对全部任务" : "保持原已确认版本"}。此比较展示持久化字段差异，不替代业务语义复核。</p></section>}
      <div className="planning-confirm" aria-live="polite">{approved ? <><h2>计划已确认{missing.length ? "，资源待准备" : ""}，尚未开始执行</h2><p>计划版本 {approved.plan.version} · 确认时间：{formatTime(approved.approval.decided_at)}</p><details className="journey-technical"><summary>查看持久化确认关联</summary><dl><dt>计划</dt><dd>{approved.plan.plan_id}</dd><dt>批准</dt><dd>{approved.approval.approval_decision_id}</dd><dt>摘要</dt><dd><code>{approved.digest}</code></dd></dl></details></> : <><p>确认仅保存当前计划。{missing.length ? `仍有 ${missing.length} 项必要资源待准备或核实。` : ""}</p><button type="button" disabled={busy || data.proposal.revision !== latest} onClick={() => void act("confirm")}>{busy ? "正在保存…" : "确认计划"}</button></>}{error && <p role="alert">{error}。可重试原操作或刷新读回；不会自动再次生成建议。</p>}</div>
      <section className="planning-card planning-resources"><h2 id="planning-resource-summary"><span aria-hidden="true">◇</span> 资源需求与缺口</h2><p>共享资源只准备一次，可供多个任务复用。匹配不代表已调用。</p>{kinds.map(kind => <section className="planning-resource-group" key={kind}><h3>{resourceKinds[kind] ?? kind}<small>{plan.requirements.filter(r => r.kind === kind).length} 项</small></h3>{plan.requirements.filter(r => r.kind === kind).map(r => <details id={`requirement-${r.requirement_id}`} className="planning-resource" key={r.requirement_id}><summary><strong>{r.name}</strong><span>{resourceBadge(r)}<small>{r.required ? "必要" : "可选"}</small></span></summary><p>{r.purpose}</p><p>准备说明：{r.preparation}</p><p>输入输出兼容与运行条件：{data.snapshot?.observations.find(o=>o.requirement_id===r.requirement_id)?.io_status === "DECLARED" ? "已有声明，仍需运行前核验" : "尚未核验"}；精确版本可读不代表执行就绪。</p><p>用于：{plan.tasks.filter(t => t.employee_requirement_id === r.requirement_id || t.requirement_ids.includes(r.requirement_id)).map(t => t.title).join("、") || "可选增强，不影响当前必要任务"}</p>{r.selected && <details className="journey-technical"><summary>准确版本与技术引用</summary><dl><dt>资源</dt><dd>{r.selected.resource_id}</dd><dt>修订</dt><dd>{r.selected.revision_id}</dd><dt>摘要</dt><dd><code>{r.selected.digest}</code></dd></dl></details>}</details>)}</section>)}</section>
      </SystemMessage>
      </PlanningDialogue>
    </main><aside>
      <section className="planning-card"><h2><span aria-hidden="true">◉</span> 当前阶段</h2><span className="planning-badge">制定方案 · {approved ? "计划已确认" : "等待确认"}</span><p>{approved ? "确认已保存，可查看资源缺口与历史。" : "请核对左侧目标、任务分工与资源用途。"}</p><p className="journey-muted">执行尚未开始</p></section>
      <section className="planning-card"><h2><span aria-hidden="true">◇</span> 资源状态</h2><div className="planning-counts"><div><b>{plan.requirements.length}</b>项需求</div><div><b>{matched}</b>已匹配</div><div><b>{missing.length}</b>必要缺口</div></div><p className="planning-count-explanation">{matched} 项已匹配 + {missing.length} 项必要待准备或核实 + {optionalUnmatched.length} 项可选未匹配 = {plan.requirements.length} 项需求。可选需求共 {optional.length} 项，不阻塞计划确认。</p><a href="#planning-resource-summary">查看资源用途与缺口 →</a><button disabled={busy} onClick={() => void act("refresh")}>刷新资源状态</button><p className="journey-muted">{data.snapshot ? `核对时间：${formatTime(data.snapshot.checked_at)}` : "尚未核对资源，已选版本保持待核实。"}</p></section>
      <section className="planning-card"><h2><span aria-hidden="true">☑</span> 需要你处理</h2><p>{approved ? (missing.length ? `计划已保存，仍有 ${missing.length} 项必要缺口。资源由各自管理入口准备。` : "本页规划确认已完成，未授予执行权限。") : "核对后，在方案下方确认计划。"}</p><ul>{plan.boundaries.map(b => <li key={b}>{b}</li>)}</ul><p className="journey-muted">不自动生产或发布资源。权限内候选发现尚缺正式 owner 接口；当前仅核验已选精确引用。</p></section>
      <section className="planning-card">      <p className="journey-muted">方案生成时间：{data.generated_at ? formatTime(data.generated_at) : "历史记录未提供，不能以刷新时间代替"}</p><p>契约校验：{data.validation?.status === "DECLARED_CONTRACT_VALID" ? "显式操作、数据流与标准引用通过；业务含义仍需人工核对" : "历史结构校验；不代表完整业务语义符合"}</p></section>
      <section className="planning-card planning-version"><h2><span aria-hidden="true">◷</span> 方案版本</h2><label>查看历史建议<select value={data.proposal.revision} onChange={e => setParams({ revision: e.target.value })}>{history.proposals.map(p => <option key={p.revision} value={p.revision}>修订 {p.revision}</option>)}</select></label><p className="journey-muted">历史批准保留；修改语义须形成后继建议并重新确认。</p></section>
    </aside></div>
  </section>;
}
