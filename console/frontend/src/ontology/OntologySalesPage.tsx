import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { readWorkbenchSession } from "../api/businessWorkspace";
import { preparedRequest, type ExecutionView, type Ref } from "../api/preparedExecution";
import { confirm } from "../planning/api";
import "./ontology.css";
import { dimensionName, ontologyError, reportTitle, validateDraftImport } from "./ontologyPresentation";

type Binding = { ontology: Ref; mapping_code: string; queries: { metric: string; dimensions: string[] }[] };
type Draft = { plan_id: string; semantics: { title: string; boundaries: string[] }; business_semantics: Binding; [key: string]: unknown };
type Prepared = { proposal: { proposal_id: string; revision: number }; digest: string; draft: Draft };
type Report = { metricName: string; rows: { currency: string; dimensions: Record<string, string>; baseline: string; current: string; delta: string; sourceRows: Record<string, string[]> }[]; excludedRows: { rowId: string; reason: string }[] };
type Artifact = { operation: string; reports: Report[]; bindingDigest: string; source: { periods?: string[]; snapshot: { rows: { sourceLine: number; values: Record<string, string> }[] } } };
async function post<T>(path: string, body: unknown): Promise<T> {
  const session = await readWorkbenchSession();
  const response = await fetch("/api/workbench/v1" + path, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRF-Token": session.csrfToken }, body: JSON.stringify(body) });
  const data = await response.json(); if (!response.ok) throw new Error(data.reasonCode ?? "当前操作未完成"); return data.result as T;
}
function checkedView(value: ExecutionView, identity: string, revision: string) {
  const actual = (value.preparation as unknown as { business_semantics?: Binding }).business_semantics?.ontology;
  if (actual?.resource_id !== identity || actual.revision_id !== revision) throw new Error("当前地址的口径修订与执行方案不一致，已停止显示结果和执行入口。请从业务本体目录重新进入。");
  return value;
}
export function OntologySalesPage() {
  const [params] = useSearchParams();
  return <OntologySalesContent key={params.toString()} />;
}
function OntologySalesContent() {
  const [params, setParams] = useSearchParams();
  const identity = params.get("ontology") ?? "sales-diagnosis", revision = params.get("revision") ?? "r1", digest = params.get("preparation") ?? "";
  const [draft, setDraft] = useState<Draft | null>(null), [prepared, setPrepared] = useState<Prepared | null>(null), [view, setView] = useState<ExecutionView | null>(null);
  const [candidates, setCandidates] = useState<{ digest: string; plan_version: number }[]>([]), [message, setMessage] = useState(""), [busy, setBusy] = useState(false);
  const [fileName, setFileName] = useState("");
  const [definition, setDefinition] = useState<{ name: string; returns: boolean } | null>(null);
  const [metricNames, setMetricNames] = useState<Record<string,string>>({});
  const [reason] = useState(() => { const key = "ontology-sales-command:" + identity + ":" + revision; const saved = sessionStorage.getItem(key); if (saved) return saved; const value = crypto.randomUUID(); sessionStorage.setItem(key,value); return value; });
  useEffect(() => { const abort = new AbortController(); fetch(`/api/workbench/v1/business-ontologies/${encodeURIComponent(identity)}/revisions/${encodeURIComponent(revision)}`,{credentials:"same-origin",signal:abort.signal}).then(r=>r.json()).then(body=>{if(!abort.signal.aborted && body.result) { setMetricNames(Object.fromEntries(body.result.content.metrics.map((m:{code:string;name:string})=>[m.code,m.name]))); setDefinition({ name: body.result.content.name, returns: body.result.content.rules.included_kinds.includes("RETURN") }); }}).catch(()=>{}); return ()=>abort.abort(); },[identity,revision]);
  useEffect(() => {
    const abort = new AbortController();
    fetch(`/api/workbench/v1/business-ontologies/${encodeURIComponent(identity)}/revisions/${encodeURIComponent(revision)}/sales-runs`, { credentials: "same-origin", signal: abort.signal }).then(r => r.json()).then(body => { if (!abort.signal.aborted) { if (body.result) setCandidates(body.result.items); else setMessage(body.reasonCode); } }).catch(e => { if (!abort.signal.aborted) setMessage(ontologyError(e)); });
    return () => abort.abort();
  }, [identity, revision, digest]);
  useEffect(() => { let active = true; if (digest) preparedRequest<ExecutionView>(digest).then(v => { if (active) {
      setView(checkedView(v, identity, revision));
    } }).catch(e => { if (active) setMessage(ontologyError(e)); }); return () => { active = false; }; }, [digest, identity, revision]);
  async function action(kind: string) {
    setBusy(true); setMessage("");
    try {
      if (kind === "prepare" && draft) {
        const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(draft)));
        const draftKey = Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2,"0")).join("");
        setPrepared(await post<Prepared>(`/business-ontologies/${encodeURIComponent(identity)}/execution-drafts`, { request_key: reason + "-" + draftKey, draft })); setMessage("口径与任务已固定，等待确认方案");
      } else if (kind === "confirm" && prepared) {
        const session = await readWorkbenchSession();
        const approved = await confirm(prepared.proposal.proposal_id, prepared.proposal.revision, prepared.digest, 0, session.csrfToken, reason + "-" + prepared.proposal.proposal_id + "-confirm");
        const p = { ...prepared.draft, plan_id: approved.plan.plan_id, plan_version: approved.plan.version, plan_digest: approved.digest, approval_id: approved.approval.approval_decision_id, semantics: approved.plan.semantics };
        const saved = await post<{ digest: string }>(`/planning-v2/${encodeURIComponent(approved.plan.plan_id)}/prepared-executions`, p);
        const next = new URLSearchParams(params); next.set("preparation", saved.digest); setParams(next); setMessage("方案已确认，执行准备已保存；执行准入需单独核对");
      } else if (kind === "refresh") { setView(checkedView(await preparedRequest<ExecutionView>(digest), identity, revision)); setMessage("已读取当前执行状态"); }
      else { const session = await readWorkbenchSession(); await preparedRequest(digest, kind, session.csrfToken, { idempotencyKey: reason + "-" + digest + "-" + kind }); setView(checkedView(await preparedRequest<ExecutionView>(digest), identity, revision)); setMessage(kind === "evaluate" ? "已完成独立评估" : "执行请求已提交"); }
    } catch (e) { setMessage(ontologyError(e)); } finally { setBusy(false); }
  }
  let report: Artifact | null = null;
  for (const artifact of view?.artifacts ?? []) { if (artifact.content) { try { const value = JSON.parse(artifact.content) as Artifact; if (value.operation === "RENDER_REPORT" && Array.isArray(value.reports)) report = value; } catch { /* Missing or unreadable artifacts remain absent. */ } } }
  const overview = report?.reports.find(r => r.rows.length > 0 && r.rows.every(row => Object.keys(row.dimensions).length === 0));
  const binding = draft?.business_semantics ?? (view?.preparation as unknown as { business_semantics?: Binding } | undefined)?.business_semantics;
  return <main className="ontology-page"><nav><a href="/ontology">业务本体</a> / 销售诊断</nav><header><p className="ontology-eyebrow">按已批准口径执行</p><h1>销售诊断</h1><p>确认业务定义与来源，再通过现有任务执行链计算并核验结果。</p><span className="ontology-badge">合成数据 · 观察性分析 · 业务结论待定</span></header><div role="status" aria-live="polite" className="ontology-message">{message}</div>
    <section><h2>1. 选择口径与执行方案</h2><p><strong>{definition?.name ?? "业务定义"}</strong> · 修订 {revision}</p>{definition && <p>口径：{definition.returns ? "销售冲减退货" : "仅统计销售发生额，退货不纳入金额"}；取消记录排除，各币种分别核算。</p>}<details><summary>查看业务定义标识</summary><p className="ontology-digest">{identity}</p></details><label className="ontology-file">导入执行方案包<span className="ontology-file-button">选择方案文件</span><span className="ontology-file-name">{fileName || "尚未选择文件（JSON）"}</span><input type="file" accept=".json" disabled={busy} onChange={async e => { try { const file = e.target.files?.[0]; if (!file) return; if (file.size > 98304) throw new Error("方案包过大"); const parsed: unknown = JSON.parse(await file.text()); validateDraftImport(parsed, identity, revision); const doc = parsed as Draft; setDraft(doc); setFileName(file.name); setPrepared(null); setMessage("方案包已载入，尚未确认或执行"); } catch (error) { setMessage(ontologyError(error)); } }} /></label>{binding && <><p>来源映射：{binding.mapping_code}</p><ul>{binding.queries.map((q, i) => <li key={i}>{metricNames[q.metric] ?? q.metric} · {q.dimensions.map(d=>dimensionName(d)).join(" / ") || "按币种汇总"}</li>)}</ul></>}<div className="ontology-actions"><button disabled={busy || !draft || !!prepared} onClick={() => action("prepare")}>核对并准备方案</button><button disabled={busy || !prepared || !!digest} onClick={() => action("confirm")}>确认口径与方案</button></div>{prepared && <details><summary>查看待确认的任务边界</summary><ul>{prepared.draft.semantics.boundaries.map((b, i) => <li key={i} className="ontology-digest">{b}</li>)}</ul></details>}{candidates.map(c => <p key={c.digest}><button disabled={busy} aria-pressed={digest === c.digest} onClick={() => { const next = new URLSearchParams(params); next.set("preparation", c.digest); setParams(next); }}>打开已准备方案 · 版本 {c.plan_version} · {c.digest.slice(0,8)}</button></p>)}</section>
    {digest && <section><h2>2. 执行与独立评估</h2><p>状态：{({PENDING:"待执行",RUNNING:"执行中",SUCCEEDED:"已完成",RECOVERY_REQUIRED:"需核对，已停止后续派发",FAILED:"执行失败",CANCELLED:"已取消"} as Record<string,string>)[view?.progress?.state ?? ""] ?? "尚未开始"}</p><div className="ontology-actions"><button disabled={busy || !view || !!view.executionStarted || view.admission.state !== "ADMITTED"} onClick={() => action("start")}>开始只读执行</button><button disabled={busy} onClick={() => action("refresh")}>刷新进度</button><button disabled={busy || view?.progress?.state !== "SUCCEEDED"} onClick={() => action("evaluate")}>按成功标准评估</button></div><ul>{view?.progress?.tasks.map(t => <li key={t.task_id}>{view?.preparation.semantics.tasks.find(task=>task.task_id===t.task_id)?.title ?? view?.taskTranslation?.tasks.find(task=>task.task_id===t.task_id)?.title ?? t.task_id} · {({WAITING:"等待前序任务",READY:"可执行",QUEUED:"已排队",RUNNING:"执行中",SUCCEEDED:"已完成",UNKNOWN:"结果待核对",FINAL_FAILED:"执行失败"} as Record<string,string>)[t.state] ?? t.state}</li>)}</ul>{view?.outcome && <><h3>验收结果</h3><ul>{view.outcome.evaluation.results.map((r, i) => <li key={i}>{({source:"来源一致性",totals:"金额核对",contributions:"变化贡献",exceptions:"异常与排除",claim_boundary:"结论边界"} as Record<string,string>)[r.check ?? ""] ?? "标准"}：{r.result==="SATISFIED"?"满足":r.result==="NOT_SATISFIED"?"不满足":"待核对"}<details><summary>查看评估依据</summary>{r.reason}</details></li>)}</ul><p>技术核验不等于真实经营问题解决，人工业务决定保持独立。</p></>}</section>}
    {report && <section><h2>3. 诊断结果与来源</h2><p>基期：{report.source.periods?.[0] ?? "见来源"}；本期：{report.source.periods?.[1] ?? "见来源"}。金额单位按各行币种，不作跨币种合计。</p>{overview && <div className="ontology-summary" aria-label="本期金额摘要">{overview.rows.map(row => <div key={row.currency}><span>{overview.metricName} · {row.currency}</span><strong>{row.current}</strong><span>基期 {row.baseline} · 变化 {row.delta}</span></div>)}</div>}{report.reports.map((r, i) => <div key={i}><h3>{reportTitle(r.metricName, r.rows[0]?.dimensions)}</h3><div className="ontology-table"><table><thead><tr><th>币种 / 分组</th><th>基期</th><th>本期</th><th>变化</th></tr></thead><tbody>{r.rows.map((row, j) => <tr key={j}><td>{row.currency} {Object.values(row.dimensions).join(" / ")}</td><td>{row.baseline}</td><td>{row.current}</td><td>{row.delta}</td></tr>)}</tbody></table></div><details><summary>查看来源行与排除项</summary>{r.rows.map((row, j) => <p key={j}>{row.currency}：{Object.values(row.sourceRows).flat().join("、")}</p>)}{r.excludedRows.map((row, j) => <p key={j}>{row.rowId} · {({CANCELLED:"取消记录，已排除",KIND_EXCLUDED_BY_ONTOLOGY:"当前口径不纳入此类记录",QUERY_FILTER:"不符合查询条件"} as Record<string,string>)[row.reason] ?? row.reason}</p>)}</details></div>)}<details><summary>查看原始来源明细</summary><div className="ontology-table"><table><thead><tr><th>记录</th><th>期间</th><th>币种</th><th>金额</th><th>记录类型 / 状态</th><th>来源行</th></tr></thead><tbody>{report.source.snapshot.rows.map(row => <tr key={row.values.rowId}><td>{row.values.rowId}</td><td>{row.values.period}</td><td>{row.values.currency}</td><td>{row.values.netSales}</td><td>{row.values.kind === "RETURN" ? "退货" : "销售"} / {row.values.status === "CANCELLED" ? "取消" : "已入账"}</td><td>{row.sourceLine}</td></tr>)}</tbody></table></div></details><details><summary>查看精确口径绑定</summary><p className="ontology-digest">{report.bindingDigest}</p></details></section>}
  </main>;
}
