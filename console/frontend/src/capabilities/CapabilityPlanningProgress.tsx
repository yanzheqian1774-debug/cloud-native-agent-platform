import {CapabilityExecution} from './CapabilityExecution';
import {CapabilityResourcePreparation} from './CapabilityResourcePreparation';
import {CapabilityPlanConfirmation} from './CapabilityPlanConfirmation';
import {CapabilityPlanningRail} from './CapabilityPlanningRail';
import {CapabilityComposerContext} from './CapabilityComposerContext';
import {ConversationPlacement} from '../problems/ConversationPlacement';
import {useViewString} from '../problems/workViewState';
import {useContext,useEffect,useEffectEvent,useRef,useState} from 'react';
import {capabilitySession} from '../api/businessCapabilities';
import {workbenchPrincipalKey} from '../api/digitalEmployees';
import {conversationRequest,type PrivateConversation} from '../api/privateConversation';
import type {ModelProgress} from '../api/modelStream';
import {planningRequest,type Invocation,type PlanningBody} from '../planning/planningRequests';
import {capabilityJournalPath,readCapabilityJournal,type CapabilityJournal} from './capabilityWorkJournal';

type PlanningChain={rootRequestKey:string;rootInvocationId:string;value:Invocation};
type PlanningInput={state:string;planningRequest:PlanningBody|null;capabilitySource:{conversationId:string;sourceMessageId:string;contractDigest:string}};
export function CapabilityPlanningProgress({conversation,messageId,principal,journal,onRefresh,objective}:{objective:string;conversation:string;messageId:string;principal:string;journal:CapabilityJournal;onRefresh:()=>void}){
 const composer=useContext(CapabilityComposerContext);
 const [autoContinue,setAutoContinue]=useState(false);
 const requestKey=journal.state?.planningRequestKey??'capability:'+journal.contractDigest+':planning';
 const [answer,setAnswer]=useViewString(JSON.stringify([principal,conversation,messageId,requestKey]),'clarification-answer');
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[stage,setStage]=useState(''),[stream,setStream]=useState<ModelProgress|null>(null),[result,setResult]=useState<Invocation|null>(null);
 const flight=useRef(false),alive=useRef(true),queued=useRef<string|null>(null);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[]);
 async function verify(){const s=await capabilitySession();if(!alive.current||workbenchPrincipalKey(s)!==principal)throw Error('登录身份或当前工作已变化，原记录保留。');return s}
 async function save(current:CapabilityJournal,phase:string,invocationId?:string,extra:Partial<NonNullable<CapabilityJournal['state']>>={}){
  const session=await verify();await conversationRequest(capabilityJournalPath(conversation,messageId),session.csrfToken,{expectedVersion:current.version,idempotencyKey:'capability:'+journal.contractDigest+':journal:'+current.version,contractDigest:current.contractDigest,state:{...current.state,phase,planningRequestKey:requestKey,...(invocationId?{invocationId}:{}),...extra}});await verify();
 }
 function validate(chain:PlanningChain,expectedKey=requestKey){
  const value=chain.value,attempts=value.adaptive?.attempts;
  if(chain.rootRequestKey!==expectedKey||!chain.rootInvocationId||value.invocation.target.problem?.problem?.resource_id!==journal.state?.problemId||(attempts?(attempts.length<1||attempts.length>4||attempts[0].invocation_id!==chain.rootInvocationId||attempts.at(-1)?.invocation_id!==value.invocation.target.invocation_id):(value.invocation.target.invocation_id!==chain.rootInvocationId||value.invocation.request?.idempotency_key!==expectedKey)))throw Error('方案调用与当前工作未能核对，停止后续办理。');
 }
 async function run(readOnly:boolean){
  if(flight.current)return;if(!readOnly)setAutoContinue(true);flight.current=true;composer?.selectWork(messageId);setBusy(true);setError('');setStream(null);setStage(readOnly?'正在读取原方案调用':'正在核对目标、固定资源和方案权限');
  try{
   const session=await verify(),signal=AbortSignal.timeout(30_000);
   const current=await readCapabilityJournal(conversation,messageId,principal,signal);
   if(current.contractDigest!==journal.contractDigest||current.state?.problemId!==journal.state?.problemId)throw Error('当前工作已变化，请重新读取。');
   const expected={principal:JSON.stringify(session.principal),isCurrent:()=>alive.current};
   const readOriginal=()=>planningRequest<PlanningChain>('planning-v2/requests/'+encodeURIComponent(requestKey)+'/read-only-chain',undefined,{},expected);
   let chain:PlanningChain;
   if(readOnly){
    if(!current.state||current.state.phase==='PREPARE_PLAN')throw Error('尚无已提交的方案请求。');
    chain=await readOriginal();
   }else{
    if(current.version!==journal.version||current.state?.phase!=='PREPARE_PLAN')throw Error('方案可能已由其他页面提交，请读取原调用，不会重复派发。');
    const input=await planningRequest<PlanningInput>('capability-planning-input',{conversationId:conversation,sourceMessageId:messageId,contractDigest:journal.contractDigest,problemId:current.state.problemId,idempotencyKey:requestKey},{},expected);
    if(!input.planningRequest||input.state!=='CAPABILITY_READY_FOR_GOVERNED_PLANNING')throw Error('当前固定能力尚不能生成方案，请补齐已登记的资料与工具。');
    const source=input.capabilitySource;
    if(source.conversationId!==conversation||source.sourceMessageId!==messageId||source.contractDigest!==journal.contractDigest||input.planningRequest.idempotency_key!==requestKey)throw Error('方案输入归属未能核对，未派发模型请求。');
    if(current.state.predecessorInvocationId){
     if(!current.state.predecessorRequestKey||!current.state.clarificationAnswers?.length)throw Error('补充信息的原调用未能核对。');
     const previous=await planningRequest<PlanningChain>('planning-v2/requests/'+encodeURIComponent(current.state.predecessorRequestKey)+'/read-only-chain',undefined,{},expected);
     validate(previous,current.state.predecessorRequestKey);
     if(previous.value.invocation.target.invocation_id!==current.state.predecessorInvocationId||previous.value.result.technical_status!=='SUCCEEDED'||previous.value.result.kind!=='NEEDS_CLARIFICATION')throw Error('原调用不再处于待补充状态，停止新请求。');
     input.planningRequest={...input.planningRequest,predecessor_invocation_id:current.state.predecessorInvocationId,answers:[...input.planningRequest.answers,...current.state.clarificationAnswers]};
    }
    await planningRequest('planning-v2/preflight',input.planningRequest,{},expected);
    await save(current,'PLANNING_PENDING');onRefresh();
    await verify();setStage('正在生成方案，完成后会返回当前会话');
    await planningRequest<Invocation>('planning-v2/invocations',input.planningRequest,{},expected,p=>{if(alive.current)setStream(p)});
    chain=await readOriginal();
   }
   await verify();validate(chain);const value=chain.value;setResult(value);setStream(null);if(value.result.kind==='NEEDS_CLARIFICATION')composer?.select(messageId);
   const latest=await readCapabilityJournal(conversation,messageId,principal,AbortSignal.timeout(30_000));
   if(latest.contractDigest!==journal.contractDigest||latest.state?.problemId!==journal.state?.problemId)throw Error('方案记录归属已变化，停止更新进度。');
   if(latest.state?.phase==='PLANNING_PENDING'&&value.result.technical_status==='SUCCEEDED')await save(latest,value.result.kind==='NEEDS_CLARIFICATION'?'PLANNING_CLARIFICATION':value.result.proposal?'PLAN_READY':'PLANNING_STOPPED',value.invocation.target.invocation_id);
   onRefresh();
  }catch(cause){setAutoContinue(false);if(alive.current)setError(cause instanceof Error&&cause.message.includes('PLANNING_NOT_CONFIGURED')?'当前环境的模型服务尚未接通，目标和资料已保留，待服务就绪后可继续。':cause instanceof Error&&/[\u4e00-\u9fff]/.test(cause.message)?cause.message:'方案响应尚未核实，请读取原方案调用。')}
  finally{flight.current=false;if(alive.current){setBusy(false);setStage('')}}
 }
 async function answerQuestion(){
  if(flight.current||!answer.trim()||answer.trim().length>500)return;
  flight.current=true;setBusy(true);setError('');setStage('正在保存补充说明，沿用原目标与完成标准');
  try{
   const session=await verify(),current=await readCapabilityJournal(conversation,messageId,principal,AbortSignal.timeout(30_000));
   if(current.contractDigest!==journal.contractDigest||current.version!==journal.version||current.state?.phase!=='PLANNING_CLARIFICATION'||!current.state.invocationId)throw Error('待补充的问题已变化，请读取原方案调用。');
   const chain=await planningRequest<PlanningChain>('planning-v2/requests/'+encodeURIComponent(requestKey)+'/read-only-chain',undefined,{}, {principal:JSON.stringify(session.principal),isCurrent:()=>alive.current});
   validate(chain);
   const invocation=chain.value.invocation.target.invocation_id;
   if(chain.value.result.technical_status!=='SUCCEEDED'||chain.value.result.kind!=='NEEDS_CLARIFICATION'||invocation!==current.state.invocationId)throw Error('原调用尚未核实为待补充，不会发起后续请求。');
   const token=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify([journal.contractDigest,invocation]))))).map(byte=>byte.toString(16).padStart(2,'0')).join('');
   const nextKey='capability-followup:'+token,route='/'+encodeURIComponent(conversation),messageKey='capability-answer:'+token,text=answer.trim();
   const data=await conversationRequest<PrivateConversation>(route),existing=data.messages.find(message=>message.request_key===messageKey);
   if(existing&&existing.content!==text)throw Error('本轮已保存不同的补充说明，请读取原记录。');
   await verify();
   if(!existing)await conversationRequest(route+'/messages',session.csrfToken,{expectedVersion:data.conversation.version,idempotencyKey:messageKey,content:text});
   const confirmed=await conversationRequest<PrivateConversation>(route);
   if(!confirmed.messages.some(message=>message.request_key===messageKey&&message.content===text))throw Error('补充说明尚未读回，原记录保留。');
   await save(current,'PREPARE_PLAN',undefined,{planningRequestKey:nextKey,predecessorInvocationId:invocation,predecessorRequestKey:requestKey,clarificationAnswers:[...(current.state.clarificationAnswers??[]),text]});
   queued.current=nextKey;setAnswer('');setResult(null);composer?.select(null);onRefresh();
  }catch(cause){setAutoContinue(false);if(alive.current)setError(cause instanceof Error&&/[\u4e00-\u9fff]/.test(cause.message)?cause.message:'补充信息保存状态尚未核实，请沿用原记录继续。')}
  finally{flight.current=false;if(alive.current){setBusy(false);setStage('')}}
 }
 const runEffect=useEffectEvent(run);
 useEffect(()=>{if(!busy&&!flight.current&&queued.current===requestKey&&journal.state?.phase==='PREPARE_PLAN'){queued.current=null;void runEffect(false)}},[busy,requestKey,journal.version,journal.state?.phase]);
 if(!journal.state)return null;
 const pending=journal.state.phase!=='PREPARE_PLAN';
 return <section aria-label="本次方案进展">{!['EXECUTION_PENDING','EXECUTION_BOUND'].includes(journal.state.phase)&&composer?.work===messageId&&composer.rail&&<ConversationPlacement target={composer.rail}><CapabilityPlanningRail journal={journal} busy={busy} stage={stage} error={error} stream={stream} result={result}/></ConversationPlacement>}<button type="button" disabled={busy} onClick={()=>void run(pending)}>{busy?'正在处理方案…':pending?'读取原方案调用':'继续准备方案'}</button>{busy&&<p role="status">{stage}</p>}{stream?.preview&&<div className="journey-progress"><p style={{whiteSpace:'pre-wrap'}}>{stream.preview}</p><small>生成中的内容尚未核验，不是执行结果。</small></div>}{error&&<p role="alert">{error} 原工作保留；不会自动重发模型请求。</p>}{result&&<div><p>{result.result.proposal?(autoContinue?'方案已返回，正在继续核对资源并办理。':'方案已返回，可沿用原记录继续办理。'):result.result.kind==='NEEDS_CLARIFICATION'?'方案准备需要补充信息。':'原调用已读回，尚未获得可执行方案。'}</p>{result.result.questions?.map((question,index)=><p key={index}>{question}</p>)}{result.result.kind==='NEEDS_CLARIFICATION'&&journal.state.phase==='PLANNING_CLARIFICATION'&&(composer&&composer.active!==messageId?<button type="button" onClick={()=>composer.select(messageId)}>补充这项工作</button>:<ConversationPlacement target={composer?.target}><form className="private-composer f3-answer capability-answer" onSubmit={event=>{event.preventDefault();void answerQuestion()}}><p className="f3-composer-question">{result.result.questions?.join('；')}</p><label>补充当前工作 · {objective}<textarea aria-label="方案补充说明" maxLength={500} required disabled={busy} value={answer} onChange={event=>setAnswer(event.target.value)}/></label><button type="submit" disabled={busy||!answer.trim()}>保存补充并继续</button><small>补充保留在原会话；保存后沿用原目标继续准备方案。</small></form></ConversationPlacement>)}{result.result.proposal&&<details open><summary>查看返回的方案</summary><p>{result.result.proposal.semantics.title}</p><ol>{result.result.proposal.semantics.tasks.map(task=><li key={task.task_id}>{task.title}：{task.responsibility}</li>)}</ol></details>}</div>}<CapabilityPlanConfirmation conversation={conversation} messageId={messageId} principal={principal} journal={journal} result={result} onRefresh={onRefresh} autoContinue={autoContinue&&!busy} onStop={()=>setAutoContinue(false)}/><CapabilityResourcePreparation conversation={conversation} messageId={messageId} principal={principal} journal={journal} onRefresh={onRefresh} autoContinue={autoContinue&&!busy} onStop={()=>setAutoContinue(false)}/><CapabilityExecution conversation={conversation} messageId={messageId} principal={principal} journal={journal} onRefresh={onRefresh} autoContinue={autoContinue&&!busy} onStop={()=>setAutoContinue(false)}/></section>;
}
