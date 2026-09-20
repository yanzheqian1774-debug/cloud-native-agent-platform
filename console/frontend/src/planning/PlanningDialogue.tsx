import {useEffect, useRef, useState} from "react";
import {useNavigate, useSearchParams} from "react-router-dom";
import {ConversationComposer, SystemMessage, UserMessage} from "../problems/ProblemConversation";
import {formatTime} from "../journey/formatTime";
import type {PlanningPolicy, ProposalRead} from "./api";

import {planningRequest, type PlanningInput, type Invocation} from "./planningRequests";
const free: PlanningPolicy = {schema_version: "planning-policy.v2", mode: "FREE", template: null, required_operations: [], prohibited_operations: [], business_acceptance_as_task: false};

export function PlanningDialogue({problem, source, disabled=false}: {problem: string; source?: ProposalRead; disabled?: boolean}) {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [answer, setAnswer] = useState("");
  const [policy, setPolicy] = useState<PlanningPolicy>(source?.proposal.semantics.policy ?? free);
  const [result, setResult] = useState<Invocation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [unresolved, setUnresolved] = useState(false);
  const flight = useRef(false);
  const requestKey = params.get("request"), invocationId = params.get("invocation");
  useEffect(() => {
    let active = true;
    if (flight.current || (!requestKey && !invocationId)) return;
    setUnresolved(true);
    const path = requestKey ? `requests/${encodeURIComponent(requestKey)}` : `invocations/${encodeURIComponent(invocationId!)}`;
    planningRequest<Invocation>(`planning-v2/${path}`).then(value => {if (active) {setResult(value); setUnresolved(false);}}).catch(e => {if (active) setError(`${e.message}；保留原请求，尚未读回结果，不会重发。`);});
    return () => {active = false;};
  }, [requestKey, invocationId]);
  async function generate() {
    if (flight.current || unresolved) return;
    flight.current = true; setBusy(true); setError("");
    try {
      const input = await planningRequest<PlanningInput>(`planning-input/${encodeURIComponent(problem)}`);
      const prior = result?.invocation.request?.answers ?? [];
      const body = {target: input.target, policy, answers: [...prior, ...(answer.trim() ? [answer.trim()] : [])], idempotency_key: crypto.randomUUID(), ...(source ? {source_proposal: {resource_id: source.proposal.proposal_id, revision_id: String(source.proposal.revision), digest: source.digest}} : {}), ...(result ? {predecessor_invocation_id: result.invocation.target.invocation_id} : {})};
      await planningRequest("planning-v2/preflight", body);
      const next = new URLSearchParams(params); next.set("request", body.idempotency_key); next.delete("invocation");
      setUnresolved(true); setParams(next, {replace: true});
      const value = await planningRequest<Invocation>("planning-v2/invocations", body);
      setResult(value); setUnresolved(false); setAnswer("");
      next.delete("request"); next.set("invocation", value.invocation.target.invocation_id); setParams(next, {replace: true});
      if (value.result.proposal) navigate(`/work/planning/${encodeURIComponent(value.result.proposal.proposal_id)}?revision=${value.result.proposal.revision}`);
    } catch(e) {setError(e instanceof Error ? e.message : "请求结果未确认");}
    finally {flight.current = false; setBusy(false);}
  }
  const blocked = disabled || busy || unresolved || (!!result && (result.result.technical_status !== "SUCCEEDED" || result.result.kind !== "NEEDS_CLARIFICATION"));
  return <section className="planning-card" aria-label="持续规划对话">
    <details><summary>规划方式：{policy.mode === "FREE" ? "自由规划" : policy.mode === "TEMPLATE_ASSISTED" ? "模板辅助" : "强约束流程"} · 查看或调整</summary><label>规划方式<select aria-label="规划方式" value={policy.mode} disabled={busy || unresolved || !!result} onChange={e => {const mode=e.target.value as PlanningPolicy["mode"];setPolicy({...free, mode, template: mode === "FREE" ? null : "procurement-overdue.v1"});}}><option value="FREE">自由规划 · 不固定阶段和任务数</option><option value="TEMPLATE_ASSISTED">采购模板辅助 · 可调整结构</option><option value="STRICT_WORKFLOW">采购强约束 · 三阶段五项职责</option></select></label>
    <p>校验显式操作、输入输出依赖和标准引用覆盖；不能穷尽自然语言冲突，需要人工核对业务含义。</p></details>
    {result?.invocation.request?.answers.map((text,index)=><UserMessage key={index}>{text}</UserMessage>)}
    {result?.invocation.submitted_at && <p>消息提交时间：{formatTime(result.invocation.submitted_at)}</p>}
    {result?.result.questions?.length ? <section><h2>需要补充的信息</h2>{result.result.questions.map(q=><SystemMessage key={q}>{q}</SystemMessage>)}</section> : null}
    {result?.result.technical_status === "OUTCOME_UNKNOWN" && <p role="status">结果未知；保留原调用与预留，只读恢复，不自动再次调用。</p>}
    {result?.result.technical_status === "FAILED" && <p role="alert">失败阶段回执：{result.result.reason ?? "PLANNING_PROVIDER_FAILED"}。没有创建建议、批准或执行。</p>}
    {result?.result.proposal && <a href={`/work/planning/${result.result.proposal.proposal_id}?revision=${result.result.proposal.revision}`}>打开已持久化的建议</a>}
    {error && <p role="alert">{error}</p>}
    <ConversationComposer value={answer} onChange={setAnswer} onSend={()=>void generate()} onCancelEdit={()=>setAnswer("")} disabled={blocked} mode="PLANNING" maxLength={500}/>
    {!source && (!result || result.result.technical_status !== "SUCCEEDED") && <button type="button" disabled={blocked} onClick={()=>void generate()}>依据已确认目标生成建议</button>}
  </section>;
}
