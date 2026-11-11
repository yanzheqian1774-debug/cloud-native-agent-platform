import {useCapabilityAdvance} from './useCapabilityAdvance';
import {useContext,useEffect,useEffectEvent,useRef,useState} from 'react';
import {capabilitySession} from '../api/businessCapabilities';
import {workbenchPrincipalKey} from '../api/digitalEmployees';
import {conversationRequest} from '../api/privateConversation';
import type {ExecutionView} from '../api/preparedExecution';
import {planningRequest} from '../planning/planningRequests';
import {useAutomaticReadback} from '../journey/useAutomaticReadback';
import {PreparedDeliverySummary} from '../problems/PreparedDeliverySummary';
import {ExecutionWorkView} from '../problems/ExecutionWorkView';
import {ConversationPlacement} from '../problems/ConversationPlacement';
import {CapabilityComposerContext} from './CapabilityComposerContext';
import {capabilityJournalPath,readCapabilityJournal,type CapabilityJournal} from './capabilityWorkJournal';

type Continuation={receipt:{subject:string;sourcePlanId:string;sourcePlanVersion:number;sourcePlanDigest:string;preparationDigest:string;executionStarted:boolean;capabilitySource:{conversationId:string;sourceMessageId:string;contractDigest:string}};execution:ExecutionView};
const labels:Record<string,string>={PENDING:'等待执行',QUEUED:'已排队',RUNNING:'执行中',SUCCEEDED:'执行已完成',FAILED:'执行失败',CANCELLED:'已取消',UNKNOWN:'结果待核实'};
export function CapabilityExecution({conversation,messageId,principal,journal,onRefresh,autoContinue=false,onStop}:{conversation:string;messageId:string;principal:string;journal:CapabilityJournal;onRefresh:()=>void;autoContinue?:boolean;onStop?:()=>void}){
 const composer=useContext(CapabilityComposerContext),alive=useRef(true),flight=useRef(false);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[view,setView]=useState<ExecutionView|null>(null),[poll,setPoll]=useState(false),[artifact,setArtifact]=useState('');
 const evaluation=useRef<HTMLDivElement>(null);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[]);
 const identity=JSON.stringify([principal,conversation,messageId,journal.contractDigest,journal.state?.selectedPlan]);
 async function session(){const s=await capabilitySession();if(!alive.current||workbenchPrincipalKey(s)!==principal)throw Error('登录身份或当前工作已变化，停止读取。');return s}
 async function read(){
  const s=await session(),plan=journal.state?.selectedPlan;
  if(!plan)throw Error('本次资源方案尚未核实。');
  const query=new URLSearchParams({version:String(plan.version),capabilityConversationId:conversation,capabilityMessageId:messageId,capabilityContractDigest:journal.contractDigest});
  const value=await planningRequest<Continuation>('planning-v2/'+encodeURIComponent(plan.id)+'/readonly-continuation?'+query,undefined,{}, {principal:JSON.stringify(s.principal),isCurrent:()=>alive.current});
  await session();const r=value.receipt,v=value.execution,source=r.capabilitySource;
  if(r.subject!==s.principal.principalId||r.sourcePlanId!==plan.id||r.sourcePlanVersion!==plan.version||r.sourcePlanDigest!==plan.digest||r.preparationDigest!==v.digest||!r.executionStarted||!v.executionStarted||!source||source.conversationId!==conversation||source.sourceMessageId!==messageId||source.contractDigest!==journal.contractDigest||v.preparation.semantics.target.problem.resource_id!==journal.state?.problemId||journal.state?.executionDigest&&journal.state.executionDigest!==v.digest)throw Error('执行结果与本次会话来源不一致，停止展示。');
  return v;
 }
 function accept(value:ExecutionView){setView(value);setError('');const terminal=['SUCCEEDED','FAILED','CANCELLED'].includes(value.progress?.state??'');setPoll(!terminal||Boolean(!value.outcome&&value.automation?.evaluation==='AUTOMATIC'&&Date.parse(value.automation.authorizationExpiresAt)>Date.now()))}
 async function act(start:boolean){
  if(flight.current)return;flight.current=true;setBusy(true);setError('');composer?.selectWork(messageId);
  try{
   const s=await session();let current=await readCapabilityJournal(conversation,messageId,principal,AbortSignal.timeout(30_000));
   if(current.contractDigest!==journal.contractDigest||current.state?.problemId!==journal.state?.problemId||current.version!==journal.version)throw Error('当前执行进展已变化，请重新读取。');
   async function save(phase:string,extra:Partial<NonNullable<CapabilityJournal['state']>>={}){
    const auth=await session();await conversationRequest(capabilityJournalPath(conversation,messageId),auth.csrfToken,{expectedVersion:current.version,idempotencyKey:'capability:'+journal.contractDigest+':journal:'+current.version,contractDigest:journal.contractDigest,state:{...current.state,phase,...extra}});
    current=await readCapabilityJournal(conversation,messageId,principal,AbortSignal.timeout(30_000));
    if(current.contractDigest!==journal.contractDigest||current.state?.problemId!==journal.state?.problemId||current.state?.phase!==phase)throw Error('执行记录尚未读回，请核对原记录。');onRefresh();
   }
   if(start){
    if(current.state?.phase!=='RESOURCES_READY'||!current.state.selectedPlan)throw Error('固定资源尚未核实为就绪，不能启动执行。');
    const plan=current.state.selectedPlan;
    await save('EXECUTION_PENDING');
    await planningRequest('planning-v2/'+encodeURIComponent(plan.id)+'/readonly-continuation',{version:plan.version,capabilityConversationId:conversation,capabilityMessageId:messageId,capabilityContractDigest:journal.contractDigest},{}, {principal:JSON.stringify(s.principal),isCurrent:()=>alive.current});
   }
   const value=await read();
   if(current.state?.executionDigest&&current.state.executionDigest!==value.digest)throw Error('已保存的执行关联不一致。');
   if(current.state?.phase!=='EXECUTION_BOUND')await save('EXECUTION_BOUND',{executionDigest:value.digest});
   await session();accept(value);
  }catch(cause){onStop?.();if(alive.current){setView(null);setPoll(false);setError(cause instanceof Error&&/[\u4e00-\u9fff]/.test(cause.message)?cause.message:'执行状态尚未核实，请读取原执行记录；不会自动重试。')}}
  finally{flight.current=false;if(alive.current)setBusy(false)}
 }
 useCapabilityAdvance(autoContinue&&journal.state?.phase==='RESOURCES_READY',JSON.stringify([principal,conversation,messageId,journal.contractDigest,'RESOURCES_READY']),()=>act(true));
 const readSaved=useEffectEvent(async()=>{if(flight.current)return;flight.current=true;try{accept(await read())}catch{if(alive.current){setView(null);setPoll(false);setError('原执行状态尚未核实，请读取原执行记录；不会自动重试。')}}finally{flight.current=false}});
 const bound=['EXECUTION_PENDING','EXECUTION_BOUND'].includes(journal.state?.phase??'');
 useEffect(()=>{if(!bound)return;const timer=setTimeout(()=>void readSaved(),0);return()=>clearTimeout(timer)},[identity,bound]);
 useAutomaticReadback({identity,enabled:poll,read:async()=>{if(flight.current)return true;flight.current=true;try{const value=await read();accept(value);return !['SUCCEEDED','FAILED','CANCELLED'].includes(value.progress?.state??'')||Boolean(!value.outcome&&value.automation?.evaluation==='AUTOMATIC'&&Date.parse(value.automation.authorizationExpiresAt)>Date.now())}catch{if(alive.current){setView(null);setPoll(false);setError('执行进展暂未读回，原任务保留，请读取原记录。')}return false}finally{flight.current=false}}});
 if(!['RESOURCES_READY','EXECUTION_PENDING','EXECUTION_BOUND'].includes(journal.state?.phase??''))return null;
 const state=view?.progress?.state??'UNKNOWN',title=view?(labels[state]??'等待处理'):bound?'执行状态待核实':'资源已备齐';
 return <section aria-label="本次执行与结果">{bound&&composer?.work===messageId&&composer.rail&&<ConversationPlacement target={composer.rail}><section className="capability-live-status journey-progress" aria-label="当前工作执行进展"><h2>当前工作 · {title}</h2><p role="status">{error||(view?`已完成 ${view.progress?.tasks.filter(t=>t.state==='SUCCEEDED').length??0} 项，共 ${view.preparation.semantics.tasks.length} 项；已保存 ${view.artifacts.length} 份产物。`:'正在核对原执行记录，不会重复启动。')}</p><small>执行完成与业务目标达成分别核对。</small></section></ConversationPlacement>}<button type="button" disabled={busy} onClick={()=>void act(!bound)}>{busy?'正在核对执行…':bound?'读取原执行记录':'继续执行本次工作'}</button>{error&&<p role="alert">{error}</p>}{view&&<><p role="status">{title}。结果保留在当前会话。</p><PreparedDeliverySummary view={view} viewKey={identity} selectedArtifact={artifact} onArtifact={setArtifact} onCloseArtifact={()=>setArtifact('')} query="" onReview={()=>evaluation.current?.scrollIntoView({block:'nearest'})}/><details><summary>查看本次执行过程</summary><ExecutionWorkView view={view} viewKey={identity} onArtifact={setArtifact}/></details><div ref={evaluation}><h3>完成标准核对</h3>{view.outcome?<><p>{view.outcome.businessResolution==='CONFIRMED_SOLVED'?'业务结果已确认':'业务结果尚未确认解决'}</p><ul>{view.outcome.evaluation.results.map(r=><li key={r.criterionRevisionId}>{r.result==='SATISFIED'?'符合标准':r.result==='NOT_SATISFIED'?'未符合标准':'仍需核实'}：{r.reason}</li>)}</ul></>:<p>尚未返回完成标准的评价，不能据此认定业务问题已解决。</p>}</div></>}</section>;
}
