import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { readWorkbenchSession } from "../api/businessWorkspace";
import * as api from "./api";
import "./planning.css";
import { JourneySteps } from "../journey/JourneySteps";
import { formatTime } from "../journey/formatTime";
import { artifactLabel, resourceKinds } from "./planningPresentation";

const labels: Record<string, string> = { MATCHED: "已匹配", MISSING: "待准备", UNKNOWN: "待核实", UNREADABLE: "不可读或不可用", VERSION_MISMATCH: "版本不符", UNAVAILABLE: "不可用", NOT_REQUIRED: "可选 · 未选择" };

export function PlanningPage() {
  const { proposalId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const requested = Number(params.get("revision")) || null;
  const [view, setView] = useState<{ data: api.ProposalRead; history: api.History } | null>(null);
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
  const plan = data.proposal.semantics;
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
  const optional = plan.requirements.filter(r => !r.required);
  const optionalUnmatched = optional.filter(r => status(r) !== "MATCHED");
  const kinds = [...new Set(plan.requirements.map(r => r.kind))];
  const resourceBadge = (r: api.Requirement) => <span className={`planning-badge is-${status(r).toLowerCase()}`}>{labels[status(r)] ?? "待核实"}</span>;
  return <section className="planning-page journey-page">
    <header className="planning-heading"><div><p>问题工作台 <span aria-hidden="true">›</span> 制定方案</p><h1>{plan.title}</h1></div><Link className="journey-secondary" to={`/work?problem=${encodeURIComponent(plan.target.problem.resource_id)}`}>返回问题</Link></header>
    <div className="planning-layout"><main>
      <JourneySteps current={3} />
      <p className="journey-guidance"><span aria-hidden="true">✦</span> 先核对目标与方案，再确认计划。资源缺口会保留，确认不会启动执行。</p>
      <section className="planning-card planning-goal"><h2><span aria-hidden="true">◎</span> 目标与完成标准</h2><ul>{plan.business_rules.map(rule => <li key={rule}>{rule}</li>)}</ul><details className="journey-technical"><summary>问题与标准的准确版本</summary><dl><dt>问题</dt><dd>{plan.target.problem.revision_id}</dd><dt>成功标准</dt><dd>{plan.target.criteria.revision_id}</dd></dl></details></section>
      <section className="planning-card planning-proposal"><h2><span aria-hidden="true">☷</span> 建议方案 <small>v{data.proposal.revision} · {plan.stages.length}阶段 / {plan.tasks.length}任务</small></h2>{plan.stages.map((stage, index) => <div className="planning-stage" key={stage.stage_id}><div className="planning-stage-title"><span>{index + 1}</span><h3>{stage.title}</h3></div>{stage.task_ids.map(id => {
        const task = plan.tasks.find(t => t.task_id === id)!;
        const employee = plan.requirements.find(r => r.requirement_id === task.employee_requirement_id);
        const resources = task.requirement_ids.map(rid => plan.requirements.find(r => r.requirement_id === rid)).filter((r): r is api.Requirement => Boolean(r));
        return <details className="planning-task" key={id}><summary><span className="planning-task-overview"><strong>{task.title}</strong><span className="planning-task-responsibility">职责：{task.responsibility}</span><span className="planning-task-meta">数字员工：{employee?.name ?? "待明确"} · {resources.map(r => r.name).join(" / ") || "暂无资源需求"}</span></span><span className="planning-expand" aria-hidden="true">⌄</span></summary>
          <div className="planning-task-detail"><p>数字员工：{employee?.name ?? "待明确"} {employee && resourceBadge(employee)}</p><dl><dt>前置依赖</dt><dd>{task.depends_on.map(dep => plan.tasks.find(t => t.task_id === dep)?.title ?? "依赖任务待核实").join("、") || "无前置任务"}</dd><dt>业务输入</dt><dd>{task.inputs.map(input => artifactLabel(input, plan)).join("、") || "无"}</dd><dt>预期输出</dt><dd>{task.outputs.map(output => artifactLabel(output, plan)).join("、")}（尚未生成）</dd></dl>
          <table><thead><tr><th>资源</th><th>本任务用途</th><th>状态</th></tr></thead><tbody>{resources.map(r => <tr key={r.requirement_id}><td><a href={`#requirement-${r.requirement_id}`}>{resourceKinds[r.kind] ?? r.kind} · {r.name}</a></td><td>{r.purpose}</td><td>{resourceBadge(r)}</td></tr>)}</tbody></table>
          <details className="journey-technical"><summary>任务与输入输出标识</summary><p>任务：{id} · 依赖：{task.depends_on.join("、") || "无"}</p><p>输入：{task.inputs.join("、")} · 输出：{task.outputs.join("、")}</p></details></div>
        </details>;
      })}</div>)}</section>
      <div className="planning-confirm" aria-live="polite">{approved ? <><h2>计划已确认{missing.length ? "，资源待准备" : ""}，尚未开始执行</h2><p>计划版本 {approved.plan.version} · {formatTime(approved.approval.decided_at)}</p><details className="journey-technical"><summary>查看持久化确认关联</summary><dl><dt>计划</dt><dd>{approved.plan.plan_id}</dd><dt>批准</dt><dd>{approved.approval.approval_decision_id}</dd><dt>摘要</dt><dd><code>{approved.digest}</code></dd></dl></details></> : <><p>确认仅保存当前计划。{missing.length ? `仍有 ${missing.length} 项必要资源待准备或核实。` : ""}</p><button type="button" disabled={busy || data.proposal.revision !== latest} onClick={() => void act("confirm")}>{busy ? "正在保存…" : "确认计划"}</button></>}{error && <p role="alert">{error}。可重试原操作或刷新读回；不会自动再次生成建议。</p>}</div>
      <section className="planning-card planning-resources"><h2 id="planning-resource-summary"><span aria-hidden="true">◇</span> 资源需求与缺口</h2><p>共享资源只准备一次，可供多个任务复用。匹配不代表已调用。</p>{kinds.map(kind => <section className="planning-resource-group" key={kind}><h3>{resourceKinds[kind] ?? kind}<small>{plan.requirements.filter(r => r.kind === kind).length} 项</small></h3>{plan.requirements.filter(r => r.kind === kind).map(r => <details id={`requirement-${r.requirement_id}`} className="planning-resource" key={r.requirement_id}><summary><strong>{r.name}</strong><span>{resourceBadge(r)}<small>{r.required ? "必要" : "可选"}</small></span></summary><p>{r.purpose}</p><p>准备说明：{r.preparation}</p><p>用于：{plan.tasks.filter(t => t.employee_requirement_id === r.requirement_id || t.requirement_ids.includes(r.requirement_id)).map(t => t.title).join("、") || "可选增强，不影响当前必要任务"}</p>{r.selected && <details className="journey-technical"><summary>准确版本与技术引用</summary><dl><dt>资源</dt><dd>{r.selected.resource_id}</dd><dt>修订</dt><dd>{r.selected.revision_id}</dd><dt>摘要</dt><dd><code>{r.selected.digest}</code></dd></dl></details>}</details>)}</section>)}</section>
    </main><aside>
      <section className="planning-card"><h2><span aria-hidden="true">◉</span> 当前阶段</h2><span className="planning-badge">制定方案 · {approved ? "计划已确认" : "等待确认"}</span><p>{approved ? "确认已保存，可查看资源缺口与历史。" : "请核对左侧目标、任务分工与资源用途。"}</p><p className="journey-muted">执行尚未开始</p></section>
      <section className="planning-card"><h2><span aria-hidden="true">◇</span> 资源状态</h2><div className="planning-counts"><div><b>{plan.requirements.length}</b>项需求</div><div><b>{matched}</b>已匹配</div><div><b>{missing.length}</b>必要缺口</div></div><p className="planning-count-explanation">{matched} 项已匹配 + {missing.length} 项必要待准备或核实 + {optionalUnmatched.length} 项可选未匹配 = {plan.requirements.length} 项需求。可选需求共 {optional.length} 项，不阻塞计划确认。</p><a href="#planning-resource-summary">查看资源用途与缺口 →</a><button disabled={busy} onClick={() => void act("refresh")}>刷新资源状态</button><p className="journey-muted">{data.snapshot ? `核对时间：${formatTime(data.snapshot.checked_at)}` : "尚未核对资源，已选版本保持待核实。"}</p></section>
      <section className="planning-card"><h2><span aria-hidden="true">☑</span> 需要你处理</h2><p>{approved ? (missing.length ? `计划已保存，仍有 ${missing.length} 项必要缺口。资源由各自管理入口准备。` : "本页规划确认已完成，未授予执行权限。") : "核对后，在方案下方确认计划。"}</p><ul>{plan.boundaries.map(b => <li key={b}>{b}</li>)}</ul><p className="journey-muted">不自动生产或发布资源。</p></section>
      <section className="planning-card planning-version"><h2><span aria-hidden="true">◷</span> 方案版本</h2><label>查看历史建议<select value={data.proposal.revision} onChange={e => setParams({ revision: e.target.value })}>{history.proposals.map(p => <option key={p.revision} value={p.revision}>修订 {p.revision}</option>)}</select></label><p className="journey-muted">历史批准保留；修改语义须形成后继建议并重新确认。</p></section>
    </aside></div>
  </section>;
}
