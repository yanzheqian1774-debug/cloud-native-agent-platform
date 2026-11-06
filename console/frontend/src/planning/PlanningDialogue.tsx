import {findReadRequestMarker} from './readRequestMarker';
import {conversationActionHeaders,continuationQuery} from "../api/conversationActions";
import {readWorkbenchSession} from "../api/businessWorkspace";
import {useEffect, useLayoutEffect, useRef, useState, type ReactNode} from "react";
import {Link, useNavigate, useSearchParams} from "react-router-dom";
import {ConversationFrame, ConversationComposer, SystemMessage, UserMessage} from "../problems/ProblemConversation";
import {clarificationChoices} from "./clarificationChoices";
import {formatTime} from "../journey/formatTime";
import {confirmPolicy,history,type Confirmation,type PlanningPolicy,type ProposalRead} from "./api";

import {rememberContinuous,rememberContinuousRequest,hasContinuousRequest} from "./continuousJourney";
import {PlanningRecoveryCard} from "./PlanningRecoveryCard";
import {planningRequest, type PlanningInput, type Invocation,type PlanningBody,type ActivityInput} from "./planningRequests";
const free: PlanningPolicy = {schema_version: "planning-policy.v2", mode: "FREE", template: null, required_operations: [], prohibited_operations: [], business_acceptance_as_task: false};

export function PlanningDialogue({problem, source, disabled=false, children, onStatus, suggestion,continuousEnabled=false}: {problem: string; source?: ProposalRead; disabled?: boolean; children?: ReactNode; onStatus?: (value:string)=>void; suggestion?:{key:string;text:string};continuousEnabled?:boolean}) {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [answer, setAnswer] = useState("");
  const [policy, setPolicy] = useState<PlanningPolicy>(source?.proposal.semantics.policy ?? free);
  const [response, setResponse] = useState<{key:string;value:Invocation} | null>(null);
  const [busy, setBusy] = useState(false),[reading,setReading]=useState(false);
  const [error, setError] = useState("");
  const [contextChoice,setContextChoice]=useState<{question:string;choices:{label:string;contextToken:string}[];selected:string}|null>(null);
  const [unresolvedState, setUnresolved] = useState(false);
  const flight = useRef(false);
  const receivedInvocation = useRef<string | null>(null);
  const consumedSuggestion=useRef<string|null>(null);
  useEffect(()=>{if(suggestion&&consumedSuggestion.current!==suggestion.key){consumedSuggestion.current=suggestion.key;setAnswer(current=>{const next=current.trim()?current+'\n'+suggestion.text:suggestion.text;if(next.length>500){setError('候选建议与已有输入超过500字，已保留原输入，请整理后再提交。');return current}return next})}},[suggestion]);
  const requestKey = params.get("request"), invocationId = params.get("invocation");
  const recordKey=requestKey?`request:${requestKey}`:invocationId?`invocation:${invocationId}`:"";
  const unresolved=Boolean(recordKey)&&unresolvedState;
  const locator=`${problem}\u0000${recordKey}`;
  const latestLocator=useRef<string|null>(locator),inFlightRequest=useRef<string|null>(null);
  useLayoutEffect(()=>{latestLocator.current=locator;return()=>{latestLocator.current=null}},[locator]);
  const readResult=response?.key===recordKey?response.value:null;
  const actualProblem=readResult?.invocation.target.problem?.problem?.resource_id;
  const mismatched=Boolean(actualProblem&&actualProblem!==problem);
  const result=mismatched?null:readResult;
  const waitingForRecord=Boolean(recordKey)&&response?.key!==recordKey;
  useEffect(() => {
    let active = true;
    // The POST already supplied this record. Resolving our own URL update would
    // briefly disable the composer again just as the next answer is being typed.
    if (invocationId && !requestKey && receivedInvocation.current === invocationId) return;
    receivedInvocation.current = null;
    if (!requestKey && !invocationId) return;
    if (flight.current&&inFlightRequest.current===recordKey) return;
    setUnresolved(true);
    const path = requestKey ? `requests/${encodeURIComponent(requestKey)}` : `invocations/${encodeURIComponent(invocationId!)}`;
    (async()=>{const before=await readWorkbenchSession();const access=findReadRequestMarker(before.principal,requestKey,invocationId);if(access){if(access.problemId!==problem)throw Error('原 READ 申请定位与页面尚未核实，不读取原调用。');if(!requestKey&&active)setParams(previous=>{const next=new URLSearchParams(previous);next.set('request',access.requestKey);return next},{replace:true});throw Error('已保留准确 READ 申请，仅核对申请状态；原调用需另行点击只读读取。');}const value=await planningRequest<Invocation>(`planning-v2/${path}`);if(JSON.stringify((await readWorkbenchSession()).principal)!==JSON.stringify(before.principal))throw Error("登录身份已变化，原记录需重新读取。");return value})().then(value => {if (active) {setResponse({key:recordKey,value}); setUnresolved(false);}}).catch(e => {if (active) setError(`${e.message}；保留原请求，尚未读回结果，不会重发。`);});
    return () => {active = false;};
  }, [requestKey, invocationId,recordKey,problem,setParams]);
  async function openProposal(value:Invocation,continuous:boolean,acceptedLocators=[locator],expectedPrincipal?:string){
    const currentView=()=>latestLocator.current!==null&&acceptedLocators.includes(latestLocator.current);
    if(!currentView())return;
    const proposal=value.result.proposal;if(!proposal)return;
    const session=await readWorkbenchSession(),principal=JSON.stringify(session.principal);
    if(!currentView())return;
    if(expectedPrincipal&&principal!==expectedPrincipal)throw Error('登录身份已变化，原请求保留，请重新读取。');
    if(continuous&&!source&&!value.invocation.request?.source_proposal){
      const digest=value.result.proposal_digest;
      if(value.result.technical_status!=="SUCCEEDED"||value.result.kind!=="VALID_SUGGESTION"||!digest||!/^[a-f0-9]{64}$/.test(digest)||proposal.semantics.target.problem.resource_id!==problem)throw Error('办理方案与当前目标不一致，已停止确认。');
      const key='continuous-confirm:'+value.invocation.target.invocation_id;
      const marker='continuous-confirm:'+JSON.stringify([principal,proposal.proposal_id,digest]);
      const matches=(c:Confirmation)=>c.plan.plan_id===proposal.proposal_id&&c.plan.source_proposal_revision===proposal.revision&&c.plan.source_proposal_digest===digest&&JSON.stringify(c.plan.semantics)===JSON.stringify(proposal.semantics);
      let confirmed:Confirmation|undefined;
      try{confirmed=(await history(proposal.proposal_id)).plans.find(matches)}catch(e){if(!(e&&typeof e==='object'&&'status'in e&&[403,404].includes(Number(e.status))))throw e;}
      if(!currentView())return;
      if(!confirmed){
        if(sessionStorage.getItem(marker))throw Error('尚未读回原确认记录，保留原请求，不会再次提交。');
        if(JSON.stringify((await readWorkbenchSession()).principal)!==principal)throw Error('登录身份已变化，已停止确认。');
        if(!currentView())return;
        sessionStorage.setItem(marker,key);
        try{confirmed=(await confirmPolicy(proposal.proposal_id,proposal.revision,digest,proposal.semantics.target.problem,0,key,session.csrfToken)).confirmation}
        catch(e){try{confirmed=(await history(proposal.proposal_id)).plans.find(matches)}catch{/* Unknown stays read-only. */}if(!confirmed)throw e;}
      }
      if(!matches(confirmed)||JSON.stringify((await readWorkbenchSession()).principal)!==principal)throw Error('确认回执或登录身份已变化，已停止接续。');
      if(!currentView())return;
      rememberContinuous(principal,proposal.proposal_id,confirmed.digest);
    }
    if(!currentView())return;
    navigate(`/work/planning/${encodeURIComponent(proposal.proposal_id)}?revision=${proposal.revision}${continuationQuery()}`);
  }
  async function generate(chosenContext?:string) {
    if (flight.current || blocked) return;
    flight.current = true; setBusy(true); setError(""); onStatus?.("处理中 · 正在生成与核验");
    try {
      const initialSession=await readWorkbenchSession();
      if(latestLocator.current!==locator)return;
      const input = await planningRequest<PlanningInput>(`planning-input/${encodeURIComponent(problem)}`);
      if(latestLocator.current!==locator)return;
      const prior = result?.invocation.request?.answers ?? [];
      let body:PlanningBody = {target: input.target, policy, output_language: "zh-CN", answers: [...prior, ...(answer.trim() ? [answer.trim()] : [])], idempotency_key: crypto.randomUUID(), ...(source ? {source_proposal: {resource_id: source.proposal.proposal_id, revision_id: String(source.proposal.revision), digest: source.digest}} : {}), ...(result ? {predecessor_invocation_id: result.invocation.target.invocation_id} : {})};
      const continuous=!source&&(continuousEnabled||params.get('continuous')==='1');
      if(!source&&!result&&continuous){
        if(!input.resourceAutomation?.enabled||!input.resourceAutomation.readonlyContinuationEnabled)throw Error('当前办理范围或资格未通过核验，未开始规划或执行。');
        const question=(answer.trim()||input.title+'：'+input.description).slice(0,500);
        const activity=await planningRequest<ActivityInput>('question-activity-input',{question,idempotencyKey:body.idempotency_key,...(chosenContext&&contextChoice?.question===question?{contextToken:chosenContext}:{})});
        if(latestLocator.current!==locator)return;
        if(activity.state==='NEEDS_BUSINESS_CONTEXT_CLARIFICATION'){setContextChoice({question,choices:activity.choices??[],selected:''});return;}
        if(activity.state!=='ACTIVITY_REQUEST_READY_FOR_GOVERNED_PLANNING'||!activity.planningRequest)throw Error(activity.state==='BLOCKED_ACTION_OUTSIDE_READONLY_CONTEXT'?'本次请求包含已授权只读分析之外的行动，未开始执行。':activity.state==='BLOCKED_PROCESS_CONTEXT_NOT_AVAILABLE'?'尚未取得业务流程实例，不能虚构当前活动。':'当前未取得可读、已授权的业务来源，未开始规划或执行。');
        if(activity.originalQuestion!==question||JSON.stringify(activity.planningRequest.target)!==JSON.stringify(input.target)||activity.planningRequest.idempotency_key!==body.idempotency_key)throw Error('本次提问与当前关注目标不一致，请先核对要办理的工作。');
        body={...Object.fromEntries(Object.entries(activity.planningRequest).filter(([,v])=>v!==null)),policy} as PlanningBody;
        setContextChoice(null);
      }
      await planningRequest("planning-v2/preflight", body);
      if(latestLocator.current!==locator)return;
      inFlightRequest.current=`request:${body.idempotency_key}`;
      const next = new URLSearchParams(params); next.set("request", body.idempotency_key); next.delete("invocation");
      if(continuous)next.set('continuous','1');
      setUnresolved(true); setParams(next, {replace: true});
      const session=await readWorkbenchSession();if(JSON.stringify(session.principal)!==JSON.stringify(initialSession.principal))throw Error('登录身份已变化，未派发本次请求。');if(latestLocator.current!==locator&&latestLocator.current!==`${problem}\u0000request:${body.idempotency_key}`)return;const target=input.target as {problem:{resource_id:string;revision_id:string;digest:string};expected_problem_version:number};const headers=await conversationActionHeaders(params.get("returnConversation"),session.csrfToken,"PLANNING",body,{kind:"PROBLEM",target:{problemId:target.problem.resource_id,revisionId:target.problem.revision_id,problemDigest:target.problem.digest}},target.expected_problem_version,continuous?body.answers[0]:undefined,()=>latestLocator.current===locator||latestLocator.current===`${problem}\u0000request:${body.idempotency_key}`);
      if(latestLocator.current!==locator&&latestLocator.current!==`${problem}\u0000request:${body.idempotency_key}`)return;
      if(JSON.stringify((await readWorkbenchSession()).principal)!==JSON.stringify(session.principal))throw Error("登录身份已变化，未派发本次请求。");
      if(continuous)rememberContinuousRequest(JSON.stringify(session.principal),problem,body.idempotency_key);
      const value = await planningRequest<Invocation>("planning-v2/invocations", body,headers,{principal:JSON.stringify(initialSession.principal),isCurrent:()=>latestLocator.current===locator||latestLocator.current===`${problem}\u0000request:${body.idempotency_key}`});
      if(latestLocator.current!==locator&&latestLocator.current!==`${problem}\u0000request:${body.idempotency_key}`)return;
      if(JSON.stringify((await readWorkbenchSession()).principal)!==JSON.stringify(session.principal))throw Error('登录身份已变化，原请求保留，请重新读取。');
      setResponse({key:value.admission?`request:${body.idempotency_key}`:`invocation:${value.invocation.target.invocation_id}`,value}); setUnresolved(false);
      // Clear only the submitted draft. A late response must preserve newer input.
      setAnswer(current => current === answer ? "" : current);
      if (!value.admission) {
        receivedInvocation.current =
          value.result.technical_status === "SUCCEEDED" && value.result.kind === "NEEDS_CLARIFICATION"
            ? value.invocation.target.invocation_id : null;
        next.delete("request");
        next.set("invocation", value.invocation.target.invocation_id);
        setParams(next, {replace: true});
      }
      if (value.result.proposal) await openProposal(value,continuous,[locator,`${problem}\u0000request:${body.idempotency_key}`,`${problem}\u0000invocation:${value.invocation.target.invocation_id}`],JSON.stringify(session.principal));
    } catch(e) {setError(e instanceof Error ? e.message : "请求结果未确认");}
    finally {flight.current = false; inFlightRequest.current=null;setBusy(false);}
  }
  async function preparedAction(continueCall=false) {
    if ((!requestKey&&!invocationId) || flight.current || (continueCall && (!requestKey||disabled||mismatched||waitingForRecord||unresolved||!result?.admission?.ready))) return;
    flight.current=true;setBusy(true);setReading(!continueCall);setError("");
    try {
      const originalSession=await readWorkbenchSession();
      if(latestLocator.current!==locator)return;
      const access=findReadRequestMarker(originalSession.principal,requestKey,invocationId);
      if(access&&access.problemId!==problem)throw Error('原 READ 申请定位与页面尚未核实，不读取原调用。');
      const path=!continueCall&&access?`planning-v2/requests/${encodeURIComponent(access.requestKey)}/read-only`:requestKey?`planning-v2/requests/${encodeURIComponent(requestKey)}`:`planning-v2/invocations/${encodeURIComponent(invocationId!)}`;
      let headers:Record<string,string>={};
      if(continueCall&&params.get("returnConversation")){
        const payload=Object.fromEntries(Object.entries(result!.invocation.request as unknown as Record<string,unknown>).filter(([k])=>["target","source_proposal","answers","idempotency_key","predecessor_invocation_id","policy","output_language"].includes(k))),target=payload.target as {problem:{resource_id:string;revision_id:string;digest:string};expected_problem_version:number};
        const session=await readWorkbenchSession();headers=await conversationActionHeaders(params.get("returnConversation"),session.csrfToken,"PLANNING_CONTINUE",payload,{kind:"PROBLEM",target:{problemId:target.problem.resource_id,revisionId:target.problem.revision_id,problemDigest:target.problem.digest}},target.expected_problem_version,params.get('continuous')==='1'&&hasContinuousRequest(JSON.stringify(originalSession.principal),problem,result?.invocation.request?.idempotency_key??requestKey)?result?.invocation.request?.answers[0]:undefined,()=>latestLocator.current===locator);
      }
      if(latestLocator.current!==locator)return;
      if(JSON.stringify((await readWorkbenchSession()).principal)!==JSON.stringify(originalSession.principal))throw Error("登录身份已变化，原请求保留。");
      const value=await planningRequest<Invocation>(continueCall?`${path}/continue`:path,continueCall?{}:undefined,headers,{principal:JSON.stringify(originalSession.principal),isCurrent:()=>latestLocator.current===locator});
      if(latestLocator.current!==locator)return;
      if(JSON.stringify((await readWorkbenchSession()).principal)!==JSON.stringify(originalSession.principal))throw Error('登录身份已变化，原请求保留，请重新读取。');
      setResponse({key:recordKey,value});setUnresolved(false);
      if(value.result.proposal) await openProposal(value,params.get('continuous')==='1'&&hasContinuousRequest(JSON.stringify(originalSession.principal),problem,value.invocation.request?.idempotency_key??requestKey),[locator],JSON.stringify(originalSession.principal));
    } catch(e) {setError(e instanceof Error?e.message:"状态尚未核实，原请求保留。");}
    finally {flight.current=false;setBusy(false);setReading(false);}
  }
  const state = busy ? (reading?"只读恢复 · 正在读取原记录":"处理中 · 正在生成与核验") : mismatched?"原调用与当前问题不一致 · 已停用写入":waitingForRecord||unresolved ? "请求待核实 · 只读恢复" : result?.admission ? (result.admission.ready?"准入已核验 · 等待显式继续":"等待精确规划准入 · 尚未派发") : result?.result.technical_status === "OUTCOME_UNKNOWN" ? "结果未知 · 原记录保留" : result?.result.technical_status === "FAILED" ? "调用已知失败" : result?.result.kind === "INVALID" ? "校验未通过 · 已停止" : result?.result.kind === "NEEDS_CLARIFICATION" ? "需要补充信息" : result?.result.proposal ? "建议已保存 · 等待确认" : source ? "可提出方案修订" : "等待显式生成";
  useEffect(()=>{onStatus?.(state)},[state,onStatus]);
  const singleCallUsed = result?.invocation.bounded_new_calls === 1 && !result.admission;
  const blocked = disabled || busy || unresolved || waitingForRecord || mismatched || singleCallUsed || (!!result && (result.result.technical_status !== "SUCCEEDED" || result.result.kind !== "NEEDS_CLARIFICATION"));
  return <ConversationFrame startAtTop newMessageKey={`${source?.proposal.revision ?? 0}:${result?.invocation.target.invocation_id ?? ""}`} composer={<section className="planning-composer" aria-label="持续规划对话">    <details><summary>规划方式：{policy.mode === "FREE" ? "自由规划" : policy.mode === "TEMPLATE_ASSISTED" ? "模板辅助" : "强约束流程"} · 查看或调整</summary><label>规划方式<select aria-label="规划方式" value={policy.mode} disabled={busy || unresolved || !!result} onChange={e => {const mode=e.target.value as PlanningPolicy["mode"];setPolicy({...free, mode, template: mode === "FREE" ? null : "procurement-overdue.v1"});}}><option value="FREE">自由规划 · 不固定阶段和任务数</option><option value="TEMPLATE_ASSISTED">采购模板辅助 · 可调整结构</option><option value="STRICT_WORKFLOW">采购强约束 · 三阶段五项职责</option></select></label>
    <p>校验显式操作、输入输出依赖和标准引用覆盖；不能穷尽自然语言冲突，需要人工核对业务含义。</p></details>
    <p className="planning-action-boundary">{continuousEnabled&&!source?'本次明确办理请求将生成方案，并在既有授权内确认、准备资源和接续只读执行；需要补充或独立准入时会停下。':'对话补充仅用于新建议，计划确认使用方案卡片中的独立按钮。'}<Link to={`/work?problem=${encodeURIComponent(problem)}${continuationQuery()}`}>正式修订目标与标准 →</Link></p>
    <ConversationComposer value={answer} onChange={setAnswer} onSend={()=>void generate()} onCancelEdit={()=>setAnswer("")} disabled={blocked} mode="PLANNING" continuousPlanning={continuousEnabled&&!source&&!result} maxLength={500}/>
    {!source && (!result || result.result.technical_status !== "SUCCEEDED") && <button type="button" disabled={blocked} onClick={()=>void generate()}>{continuousEnabled?'按已确认目标连续办理':'依据已确认目标生成建议'}</button>}
</section>}>
    {children}
    {contextChoice&&<section className="planning-card" aria-label="集中核对本次业务事项"><h2>本次要办理哪一项已授权分析？</h2><p>只核对当前事项，资料、角色和技术版本由平台继续检查。</p>{contextChoice.choices.map(c=><label key={c.contextToken}><input type="radio" name="analysis-context" checked={contextChoice.selected===c.contextToken} onChange={()=>setContextChoice({...contextChoice,selected:c.contextToken})}/>{c.label}</label>)}<button disabled={busy||!contextChoice.selected} onClick={()=>void generate(contextChoice.selected)}>按这个事项继续</button></section>}
    {(mismatched||waitingForRecord||unresolved||Boolean(error)||result?.result.kind==="INVALID"||result?.result.technical_status==="OUTCOME_UNKNOWN"||result?.result.technical_status==="FAILED")&&recordKey&&<PlanningRecoveryCard invocationId={readResult?.invocation.target.invocation_id??invocationId} requestKey={requestKey} status={mismatched?"MISMATCH":waitingForRecord||unresolved?"UNREAD":result?.result.kind==="INVALID"?"INVALID":result?.result.technical_status??"UNREAD"} remoteRecoveryUnavailable={result?.invocation.provider_configuration?.protocol==="KIMI_RESPONSES_V1"} diagnostic={result?.result.validation_diagnostic} reason={result?.result.reason} busy={busy||unresolved&&!error} onRead={()=>void preparedAction()} sourceProblem={problem}/>}
    {result?.admission && <section className="planning-card" aria-label="精确规划调用准入"><h2>{result.admission.ready?"等待继续":"等待独立规划准入"}</h2><p>本案目标、标准与规划请求已保存，尚未派发。仅本次最多一次，历史累计上限 {result.admission.cumulative_call_cap} 次；{result.admission.total_cost_cap_microusd?`本对象采用研发修订总额 USD ${result.admission.total_cost_cap_microusd/1000000}；全部历史费用和 UNKNOWN 预留继续计入。`:"原金额上限与 UNKNOWN 预留保持。"}登录、刷新和签发不会自动调用。</p>{result.admission.reasonCode&&<p role="alert">当前精确业务权限或会话条件未满足：{result.admission.reasonCode}。有效的独立决定仍保留，请先核对当前权限。</p>}<Link to={`/authorization-admin?context=${encodeURIComponent(result.admission.context_id)}`}>查看本次精确调用准入</Link><button disabled={busy} onClick={()=>void preparedAction()}>查看授权状态</button><button disabled={disabled||busy||unresolved||waitingForRecord||mismatched||!result.admission.ready} onClick={()=>void preparedAction(true)}>继续本次规划调用</button></section>}
    <p role="status" className="planning-dialogue-status">{state}</p>
    {(params.get('continuous')==='1'?result?.invocation.request?.answers.slice(0,1):result?.invocation.request?.answers)?.map((text,index)=><UserMessage key={index} occurredAt={result?.invocation.submitted_at}>{text}</UserMessage>)}
    {result?.invocation.submitted_at && <p>消息提交时间：{formatTime(result.invocation.submitted_at)}</p>}
    {result?.result.questions?.length ? <section><h2>需要补充的信息</h2>{result.result.questions.map(q=><SystemMessage label="数字员工" key={q} occurredAt={result.result.generated_at}><p style={{whiteSpace:"pre-wrap"}}>{q}</p>{clarificationChoices(q).map(option=><button type="button" key={option.label} disabled={blocked} onClick={()=>setAnswer(option.answer)}>{option.label}</button>)}</SystemMessage>)}</section> : null}
    {singleCallUsed && !result?.result.proposal && <p role="status">本次精确规划的一次调用已使用，原回复与问题保留；不能自动或普通重试追加调用。请先核对结果及正式修正路径。</p>}
    {result?.result.technical_status === "OUTCOME_UNKNOWN" && <p role="status">结果未知；保留原调用与预留，只读恢复，不自动再次调用。</p>}
    {result?.result.technical_status === "FAILED" && <p role="alert">失败阶段回执：{result.result.reason ?? "PLANNING_PROVIDER_FAILED"}。没有创建建议、批准或执行。</p>}
    {result?.result.proposal && <a href={`/work/planning/${result.result.proposal.proposal_id}?revision=${result.result.proposal.revision}`}>打开已持久化的建议</a>}
    {error && <p role="alert">{error}</p>}
    {result?.result.kind === "INVALID" && <section className="planning-card" role="alert"><h2>方案尚未通过校验</h2><p>{result.adaptive?.stop_reason === "NO_PROGRESS" ? "同类错误重复且没有进展，已停止自动修正。" : "本轮有界修正已停止；没有创建可确认方案。"}</p><p>原始目标、尝试及计量保留。请查看定位信息或修改目标后再开始新一轮。</p></section>}
    {result?.adaptive && <section className="planning-card" aria-label="本轮核对与修正"><h2>本轮核对与修正 · {result.adaptive.attempts.length} 次尝试</h2><p>服务端上限 {result.adaptive.limits.maximum_attempts} 次 / {result.adaptive.limits.total_seconds} 秒。成功后仍需确认，不启动执行。</p>{result.adaptive.attempts.map((a,index)=><div key={a.invocation_id}>尝试 {index+1}：{a.kind === "INVALID" ? "校验未通过" : a.kind === "VALID_SUGGESTION" ? "建议已保存" : "查看原尝试状态"}<details className="journey-technical"><summary>查看本次记录</summary><code>{a.invocation_id}</code></details></div>)}</section>}
  </ConversationFrame>;
}
