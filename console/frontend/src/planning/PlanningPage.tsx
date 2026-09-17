import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { readWorkbenchSession } from "../api/businessWorkspace";
import * as api from "./api";
import "./planning.css";

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
  return <section className="planning-page">
    <header className="planning-heading"><div><p>问题工作台 / 制定方案</p><h1>{plan.title}</h1><span>建议修订 {data.proposal.revision} · 尚未开始执行</span></div><Link to={`/work?problem=${encodeURIComponent(plan.target.problem.resource_id)}`}>返回问题</Link></header>
    <ol className="planning-steps" aria-label="当前阶段"><li>✓ 理解问题</li><li>✓ 确认目标</li><li aria-current="step">3 制定方案</li><li>4 执行</li><li>5 验收结果</li></ol>
    <div className="planning-layout"><main>
      <section className="planning-card"><h2>目标与完成标准</h2><h3>{plan.title}</h3><ul>{plan.business_rules.map(rule => <li key={rule}>{rule}</li>)}</ul><details><summary>问题与标准的准确版本</summary><p>问题：{plan.target.problem.revision_id}</p><p>标准：{plan.target.criteria.revision_id}</p></details></section>
      <section className="planning-card"><h2>建议方案 <small>v{data.proposal.revision}</small></h2>{plan.stages.map((stage, index) => <div className="planning-stage" key={stage.stage_id}><div className="planning-stage-title"><span>{index + 1}</span><h3>{stage.title}</h3></div>{stage.task_ids.map(id => {
        const task = plan.tasks.find(t => t.task_id === id)!;
        const employee = plan.requirements.find(r => r.requirement_id === task.employee_requirement_id);
        return <details className="planning-task" key={id}><summary><span>{task.title}</span><small>{id} · {employee?.name}</small></summary><p>职责：{task.responsibility}</p><p>数字员工：{employee?.name} <span className="planning-badge">{employee && labels[status(employee)]}</span></p><dl><dt>前置依赖</dt><dd>{task.depends_on.join("、") || "无"}</dd><dt>输入</dt><dd>{task.inputs.join("、")}</dd><dt>预期输出</dt><dd>{task.outputs.join("、")}（尚未生成）</dd></dl><table><thead><tr><th>资源</th><th>本任务用途</th><th>状态</th></tr></thead><tbody>{task.requirement_ids.map(rid => { const r = plan.requirements.find(r => r.requirement_id === rid)!; return <tr key={rid}><td><a href={`#requirement-${rid}`}>{r.kind} · {r.name}</a></td><td>{r.purpose}</td><td>{labels[status(r)]}</td></tr>; })}</tbody></table></details>;
      })}</div>)}</section>
      <div className="planning-confirm" aria-live="polite">{approved ? <><h2>计划已确认{missing.length ? "，资源待准备" : ""}，尚未开始执行</h2><p>计划版本 {approved.plan.version} · 批准时间 {new Date(approved.approval.decided_at).toLocaleString()}</p><details><summary>查看持久化确认关联</summary><p>批准：{approved.approval.approval_decision_id}</p><code>{approved.digest}</code></details></> : <><p>确认仅保存当前计划。{missing.length ? `仍有 ${missing.length} 项必要资源待准备或核实。` : ""}</p><button type="button" disabled={busy || data.proposal.revision !== latest} onClick={() => void act("confirm")}>{busy ? "正在保存…" : "确认计划"}</button></>}{error && <p role="alert">{error}。可重试原操作或刷新读回；不会自动再次生成建议。</p>}</div>
      <section className="planning-card"><h2 id="planning-resource-summary">资源需求与缺口</h2><p>资源独立维护，同一需求可供多个任务复用。匹配不代表已调用。</p>{plan.requirements.map(r => <details id={`requirement-${r.requirement_id}`} className="planning-resource" key={r.requirement_id}><summary>{r.name}<span>{labels[status(r)]} · {r.required ? "必要" : "可选"}</span></summary><p>{r.purpose}</p><p>{r.preparation}</p>{r.selected && <dl><dt>准确引用</dt><dd>{r.selected.resource_id} / {r.selected.revision_id}</dd><dt>摘要</dt><dd><code>{r.selected.digest}</code></dd></dl>}</details>)}</section>
    </main><aside><section className="planning-card"><h2>执行边界</h2><ul>{plan.boundaries.map(b => <li key={b}>{b}</li>)}</ul><p>本轮只确认规划，不执行采购操作。</p></section><section className="planning-card"><h2>资源状态</h2><a href="#planning-resource-summary">查看全部资源与缺口</a><div className="planning-counts"><div><b>{plan.requirements.length}</b>项需求</div><div><b>{matched}</b>已匹配</div><div><b>{missing.length}</b>必要缺口</div></div><button disabled={busy} onClick={() => void act("refresh")}>刷新资源状态</button><p>{data.snapshot ? `核对时间：${new Date(data.snapshot.checked_at).toLocaleString()}` : "尚未核对资源，已选版本保持待核实。"}</p></section><section className="planning-card"><h2>方案版本</h2><label>查看历史建议<select value={data.proposal.revision} onChange={e => setParams({ revision: e.target.value })}>{history.proposals.map(p => <option key={p.revision} value={p.revision}>修订 {p.revision}</option>)}</select></label><p>历史版本与批准保留，修改语义需产生后继建议并重新确认。</p></section></aside></div>
  </section>;
}
