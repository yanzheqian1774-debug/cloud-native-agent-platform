import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { readWorkbenchSession } from "../api/businessWorkspace";
import type { Proposal } from "./api";
import "./planning.css";

type Input = { target: Record<string, unknown>; title: string; description: string };
type Invocation = { invocation: { target: { invocation_id: string } }; result: { technical_status: string; kind: string | null; questions?: string[]; proposal?: Proposal | null }; facts_status: string };
async function invoke<T>(path: string, body?: object): Promise<T> {
  const session = await readWorkbenchSession();
  const response = await fetch(`/api/workbench/v1/${path}`, { method: body ? "POST" : "GET", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRF-Token": session.csrfToken }, ...(body ? { body: JSON.stringify(body) } : {}) });
  const value = await response.json();
  if (!response.ok) throw new Error(value.reasonCode ?? "PLANNING_UNAVAILABLE");
  return value.result as T;
}
export function PlanningEntry() {
  const [params, setParams] = useSearchParams();
  const problem = params.get("problem") ?? "";
  const invocationId = params.get("invocation");
  const navigate = useNavigate();
  const [input, setInput] = useState<Input | null>(null);
  const [result, setResult] = useState<Invocation | null>(null);
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const flight = useRef(false);
  const key = useRef<{ payload: string; key: string } | null>(null);
  useEffect(() => {
    let active = true;
    invoke<Input>(`planning-input/${encodeURIComponent(problem)}`).then(value => { if (active) setInput(value); }).catch(e => { if (active) setError(e.message); });
    if (invocationId) invoke<Invocation>(`planning-v2/invocations/${encodeURIComponent(invocationId)}`).then(value => { if (active) setResult(value); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [problem, invocationId]);
  async function generate() {
    if (!input || flight.current) return;
    flight.current = true; setBusy(true); setError("");
    const payload = { target: input.target, answers: answer.trim() ? [answer.trim()] : [], ...(invocationId ? { predecessor_invocation_id: invocationId } : {}) };
    const commitment = JSON.stringify(payload);
    if (key.current && key.current.payload !== commitment) {
      setError("上次请求结果尚未确认，请恢复原回答后重试");
      flight.current = false; setBusy(false); return;
    }
    if (!key.current) key.current = { payload: commitment, key: params.get("request") ?? crypto.randomUUID() };
    // Keep only the opaque retry identity in the URL, never the answer text.
    setParams({ problem, ...(invocationId ? { invocation: invocationId } : {}), request: key.current.key }, { replace: true });
    try {
      const value = await invoke<Invocation>("planning-v2/invocations", { ...payload, idempotency_key: key.current.key });
      setResult(value);
      key.current = null;
      setParams({ problem, invocation: value.invocation.target.invocation_id });
      if (value.result.proposal) navigate(`/work/planning/${encodeURIComponent(value.result.proposal.proposal_id)}?revision=${value.result.proposal.revision}`);
    } catch (e) { setError(e instanceof Error ? e.message : "生成请求未确认"); }
    finally { flight.current = false; setBusy(false); }
  }
  const unknown = result?.result.technical_status === "OUTCOME_UNKNOWN";
  return <section className="planning-page"><header className="planning-heading"><div><p>问题工作台 / 建议计划</p><h1>{input?.title ?? "读取已确认问题"}</h1></div><Link to={`/work?problem=${encodeURIComponent(problem)}`}>返回问题</Link></header><div className="planning-layout"><main><section className="planning-card"><h2>当前问题</h2><p>{input?.description ?? "正在读取问题及成功标准…"}</p><p>建议只用于规划；确认之后才保存正式计划，本轮不开始执行。</p></section>{result?.result.questions?.length ? <section className="planning-card"><h2>需要补充的信息</h2><ul>{result.result.questions.map(q => <li key={q}>{q}</li>)}</ul><label htmlFor="planning-answer">补充回答</label><textarea id="planning-answer" value={answer} maxLength={500} onChange={e => setAnswer(e.target.value)} style={{ width: "100%", minHeight: 110, marginTop: 12 }} /></section> : null}<section className="planning-card">{unknown ? <p role="status">调用结果未知。请读回原请求，不会自动再次调用模型。</p> : <button type="button" disabled={busy || !input || (!!result?.result.questions?.length && !answer.trim())} onClick={() => void generate()}>{busy ? "正在生成建议…" : result?.result.questions?.length ? "提交补充并生成建议" : "生成建议计划"}</button>}{result?.result.proposal && <Link to={`/work/planning/${encodeURIComponent(result.result.proposal.proposal_id)}?revision=${result.result.proposal.revision}`}>查看建议计划</Link>}{result?.result.kind === "INVALID" && <p>返回内容未通过结构校验，没有创建建议或批准。</p>}{result?.result.kind === "UNSUPPORTED" && <p>当前规划能力不支持此请求，没有创建计划。</p>}{result?.facts_status === "PENDING_RECONCILIATION" && <p>调用证据待补记；刷新不会重发模型请求。</p>}{error && <p role="alert">{error}。请求未完成；请保留原回答并重试，将复用原请求标识。</p>}</section></main><aside><section className="planning-card"><h2>执行边界</h2><p>只读分析，不修改订单、不发送通知。</p><p>资源缺口保留在建议中，不自动生产或发布资源。</p></section></aside></div></section>;
}
