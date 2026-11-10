import {ConversationMessageIdentity} from './ConversationMessageIdentity';
import {ConversationElapsed} from './ConversationElapsed';
import {ConversationPlacement} from './ConversationPlacement';
import {ConversationAnswer} from './ConversationAnswer';
import {conversationScope} from './conversationViewState';
import type {ModelProgress} from '../api/modelStream';
import {ConversationProgress} from './ConversationProgress';
import {ConversationEvidenceRail} from './ConversationEvidenceRail';
import {NativeLiveProgress} from './NativeLiveProgress';
import {useEffect,useEffectEvent,useRef,useState} from 'react';
import {beginDraftAssistance,readDraftAssistance,createBusinessProblem,linkDraftAssistanceProblem,readBusinessProblem,readWorkbenchSession,writeCriterion,writeCriteriaSet,transitionBusinessProblem,type WorkbenchSession,type DraftAssistanceResult,type BusinessProblemRevision} from '../api/businessWorkspace';
import {conversationRequest,type PrivateConversation} from '../api/privateConversation';
import {planningRequest,type Invocation,type PlanningBody} from '../planning/planningRequests';
import {confirmPolicy,prepareResources,readResourcePreparation,continueReadonlyWork,selectAutomaticResources,readResourceCoverage,type ExactRef,type Confirmation} from '../planning/api';
import {preparedRequest,type ExecutionView} from '../api/preparedExecution';
import {understandingContent,appendUserMessage,type UserFactMessage} from './problemUnderstandingModel';
import {PreparedExecutionPanel} from './PreparedExecutionPanel';

type Source={source:ExactRef;name:string;periods:string[];sourceSchema:string;synthetic:boolean;label?:string;completionCriteria?:string[];assessment?:{state:string;missingOperations:string[];limitations:string[]}};
type State={understandingRetry?:number;selectionRetry?:number;resourceRetry?:number;cycle?:number;coverageFeedback?:string;expectedPlanVersion?:number;key:string;phase:string;question:string;messages:UserFactMessage[];sources?:Source[];source?:Source;draft?:DraftAssistanceResult;problem?:BusinessProblemRevision;criterion?:string;planning?:Invocation;confirmation?:Confirmation;execution?:string;error?:string;pending?:string;log:string[]};
type Journal={version:number;state:State|null};
const settledUnderstandingFailure=(draft?:DraftAssistanceResult)=>draft?.state==='FAILED'&&draft.reasonCode==='OUTPUT_SCHEMA_INVALID'&&draft.settlementStatus==='ESTIMATE_SETTLED'&&draft.localWorkerState==='REAPED';
const coverageFailure='Error: AUTOMATIC_SELECTION_COVERAGE_BLOCKED';
const canRepair=(s:State)=>s.phase==='SELECT_RESOURCES'&&s.pending==='select-resources'&&s.error===coverageFailure&&(s.cycle??0)<2;

export function ConversationJourney({conversation,session,onActive,composerTarget,railTarget}:{composerTarget?:HTMLElement|null;railTarget?:HTMLElement|null;conversation:string;session:WorkbenchSession;onActive:(active:boolean)=>void}){
 const [journal,setJournal]=useState<Journal|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[execution,setExecution]=useState<ExecutionView|null>(null);
 const [stream,setStream]=useState<ModelProgress|null>(null);
 const current=useRef<Journal|null>(null),flight=useRef(false),alive=useRef(true);
 useEffect(()=>{alive.current=true;let live=true;conversationRequest<Journal>('/'+conversation+'/journey').then(j=>{if(live){current.current=j;setJournal(j);onActive(Boolean(j.state))}}).catch(e=>{if(live)setError(String(e))});return()=>{live=false;alive.current=false}},[conversation,onActive]);
 async function verify(){const actual=await readWorkbenchSession();if(JSON.stringify(actual.principal)!==JSON.stringify(session.principal))throw Error('登录身份已变化，请重新登录后继续。')}
 async function save(state:State){await verify();const j=await conversationRequest<Journal>('/'+conversation+'/journey',session.csrfToken,{expectedVersion:current.current!.version,state});current.current=j;if(alive.current)setJournal(j);return state}
 async function pending(s:State,name:string){setStream(null);return save({...s,pending:name,error:undefined})}
 async function repairCoverage(s:State){
  if((s.cycle??0)>=2)throw Error('现有能力仍不能完成该方案，已保留资料与方案缺口。');
  s=await pending(s,'coverage-repair');const p=s.confirmation!.plan;
  const coverage=await readResourceCoverage(p.plan_id,p.version);
  if(coverage.planId!==p.plan_id||coverage.planVersion!==p.version||coverage.planDigest!==s.confirmation!.digest||coverage.subject!==session.principal.principalId)throw Error('RESOURCE_COVERAGE_CONTEXT_MISMATCH');
  const reasons=[...new Set(coverage.candidates.map(c=>c.reason).filter(Boolean))].slice(0,8);
  return save({...s,pending:undefined,error:undefined,cycle:(s.cycle??0)+1,expectedPlanVersion:p.version,phase:'PLAN',coverageFeedback:('现有资源对前版方案的实际核验未通过，原因：'+reasons.join('、')+'。请形成保留原目标、范围、标准与来源的后继方案。已发布Knowledge来源可由观察到的READ_DATA技能读取；不要为了读取该内部快照额外虚构MCP依赖。仅在真实需要外部接口时保留该缺口；不得伪称能力已具备。').slice(0,500),log:[...s.log,'正在根据实际可用能力调整方案，无需补充技术描述。']});
 }
 function resourceKey(s:State){return s.key+':resources:'+(s.cycle??0)+(s.resourceRetry?':recheck:'+s.resourceRetry:'')}
 async function recheckResources(){
  if(flight.current||!current.current?.state)return;flight.current=true;setBusy(true);
  try{const s=current.current.state;await verify();const p=s.confirmation!.plan;
   const receipt=await readResourcePreparation(p.plan_id,p.version,resourceKey(s));
   if(receipt.planId!==p.plan_id||receipt.planVersion!==p.version||receipt.planDigest!==s.confirmation!.digest||receipt.subject!==session.principal.principalId||receipt.executionStarted!==false)throw Error('RESOURCE_PREPARATION_CONTEXT_MISMATCH');
   if(!['READY','PARTIALLY_READY','BLOCKED'].includes(receipt.state))throw Error('RESOURCE_PREPARATION_OUTCOME_UNKNOWN');
   await save({...s,pending:undefined,error:undefined,phase:receipt.state==='READY'?'EXECUTE':'RESOURCES',resourceRetry:receipt.state==='READY'?s.resourceRetry:(s.resourceRetry??0)+1,log:[...s.log,'已核实上次准备结果且尚未启动执行，继续核对资源。']});setError('');
  }catch(e){setError(String(e))}finally{flight.current=false;setBusy(false)}
 }
 async function recheckSelection(){
  if(flight.current||!current.current?.state)return;flight.current=true;setBusy(true);
  try{await verify();const s=current.current.state,p=s.confirmation!.plan;
   const coverage=await readResourceCoverage(p.plan_id,p.version);
   if(coverage.planId!==p.plan_id||coverage.planVersion!==p.version||coverage.planDigest!==s.confirmation!.digest||coverage.subject!==session.principal.principalId)throw Error('RESOURCE_COVERAGE_CONTEXT_MISMATCH');
   await save({...s,pending:undefined,error:undefined,selectionRetry:(s.selectionRetry??0)+1,log:[...s.log,'已重新读取当前能力，继续核对原方案；不重发模型调用或执行任务。']});setError('');
  }catch(e){setError(String(e))}finally{flight.current=false;setBusy(false)}
 }
 async function run(){
  if(flight.current||!current.current?.state||(current.current.state.pending&&!canRepair(current.current.state)))return;
  flight.current=true;setBusy(true);setError('');let s=current.current.state;
  try{while(alive.current){await verify();
   if(canRepair(s)){s=await repairCoverage(s);continue;}
   if(s.phase==='UNDERSTAND'){
    if(!s.source&&!s.sources){
     s=await pending(s,'source-discovery');
     const sources=(await planningRequest<{items:Source[]}>('conversation-sources')).items;
     s=await save({...s,pending:undefined,sources,phase:'CLARIFY',log:[...s.log,'已核对可用资料，请确认本次分析范围。']});continue;
    }
    s=await pending(s,'understanding');const previous=s.draft?.state==='SUCCEEDED'?s.draft:undefined;
    const content=understandingContent(s.messages,s.messages.length,previous?.draft??null,previous?.understanding??null,previous?.clarificationQuestion??null);
    const draft=await beginDraftAssistance(session.csrfToken,{idempotencyKey:s.key+':draft:'+s.messages.length+(s.understandingRetry?':retry:'+s.understandingRetry:''),content,...(previous?{parentContextId:previous.contextId,parentTurnId:previous.turnId,expectedParentVersion:previous.turnVersion,predecessorInvocationId:previous.invocationId}:{})},{},p=>{if(alive.current)setStream(previous=>p.kind==='stage'&&previous?.kind==='stream'?{...previous,stage:p.stage}:p)});
    setStream(null);const recoverable=settledUnderstandingFailure(draft);
    if(draft.state!=='SUCCEEDED'&&!recoverable)throw Error('问题理解尚未完成：'+(draft.reasonCode??draft.state));
    const sources=s.sources??(await planningRequest<{items:Source[]}>('conversation-sources')).items;
    const next=recoverable?'UNDERSTANDING_FAILED':draft.resultKind==='DRAFT_READY'&&s.source?'CREATE':'CLARIFY';
    s=await save({...s,pending:undefined,draft,sources,phase:next,log:[...s.log,recoverable?'理解结果格式校验未通过，原问题与资料已保留；没有启动业务任务，等待明确继续。':next==='CLARIFY'?'问题理解已完成，请确认下方分析范围。':'已整理分析目标，正在核对资料与范围。']});
   }else if(s.phase==='CREATE'){
    if(!s.draft?.draft||!s.source)throw Error('需要先明确分析目标和资料范围。');
    s=await pending(s,'create-problem');
    const created=await createBusinessProblem(session.csrfToken,{...s.draft!.draft!,ownerId:session.principal.principalId,idempotencyKey:s.key+':problem',draftInvocationId:s.draft!.invocationId});
    s=await save({...s,pending:undefined,problem:created.revision,phase:'CRITERION',log:[...s.log,'分析目标已保存，正在准备核对标准。']});
   }else if(s.phase==='CRITERION'){
    s=await pending(s,'criterion');const p=s.problem!;
    await linkDraftAssistanceProblem(session.csrfToken,s.draft!.invocationId,{problemId:p.business_problem_id,problemRevisionId:p.revision_id,problemDigest:p.digest});
    const criterion=await writeCriterion(session.csrfToken,{problemId:p.business_problem_id,criterionType:'HUMAN_EVALUATED',measurement:{rubric:'回答已确认的用户目标：'+s.question+'。'+(s.source?.completionCriteria??['展示来源依据、异常与资料缺口；区分观察和推测。']).join('')+'仅作为测试资料分析，不代表真实业务问题已经解决。'},requiredEvidenceKinds:[],evaluatorType:'HUMAN',evaluatorVersion:'v1',applicability:{sourceReference:s.source!.source},idempotencyKey:s.key+':criterion'});
    s=await save({...s,pending:undefined,criterion:criterion.revision.revision_id,phase:'ACTIVATE'});
   }else if(s.phase==='ACTIVATE'){
    s=await pending(s,'activate');const p=s.problem!,id=p.business_problem_id;let detail=await readBusinessProblem(id);
    await writeCriteriaSet(session.csrfToken,id,{problemRevisionId:p.revision_id,orderedCriterionRevisionIds:[s.criterion!],expectedVersion:detail.problem.aggregate_version,idempotencyKey:s.key+':criteria-set'});
    detail=await readBusinessProblem(id);await transitionBusinessProblem(session.csrfToken,id,{toState:'ACTIVE',expectedVersion:detail.problem.aggregate_version,idempotencyKey:s.key+':activate'});
    const c=await conversationRequest<PrivateConversation>('/'+conversation);await conversationRequest('/'+conversation+'/links',session.csrfToken,{expectedVersion:c.conversation.version,idempotencyKey:s.key+':link',target:{problemId:id,revisionId:p.revision_id,problemDigest:p.digest}});
    s=await save({...s,pending:undefined,phase:'PLAN',log:[...s.log,'正在结合资料和可用能力制定分析方案。']});
   }else if(s.phase==='PLAN'){
    s=await pending(s,'planning');
    const routed=await planningRequest<{state:string;planningRequest:PlanningBody|null}>('question-activity-input',{question:s.question,problemId:s.problem!.business_problem_id,source:s.source!.source,idempotencyKey:s.key+':planning'+(s.cycle?':'+s.cycle:'')});
    if(!routed.planningRequest)throw Error('暂不能根据所选资料开始分析：'+routed.state);
    if(s.coverageFeedback&&s.planning?.result.proposal){const old=s.planning.result.proposal;routed.planningRequest={...routed.planningRequest,source_proposal:{resource_id:old.proposal_id,revision_id:String(old.revision),digest:s.planning.result.proposal_digest!},answers:[...routed.planningRequest.answers,s.coverageFeedback]};}
    await planningRequest('planning-v2/preflight',routed.planningRequest);
    const planning=await planningRequest<Invocation>('planning-v2/invocations',routed.planningRequest,{},undefined,p=>{if(alive.current)setStream(previous=>p.kind==='stage'&&previous?.kind==='stream'?{...previous,stage:p.stage}:p)});
    if(planning.result.technical_status!=='SUCCEEDED'||!planning.result.proposal)throw Error('分析方案尚未就绪：'+(planning.result.questions?.join('；')||planning.result.reason||planning.result.kind||planning.result.technical_status));
    s=await save({...s,pending:undefined,planning,phase:'CONFIRM',log:[...s.log,'分析方案已生成，正在核对并准备执行资源。']});
   }else if(s.phase==='CONFIRM'){
    s=await pending(s,'confirm');const proposal=s.planning!.result.proposal!,digest=s.planning!.result.proposal_digest!;
    const {confirmation}=await confirmPolicy(proposal.proposal_id,proposal.revision,digest,proposal.semantics.target.problem,s.expectedPlanVersion??0,s.key+':confirm:'+(s.cycle??0),session.csrfToken);
    s=await save({...s,pending:undefined,confirmation,phase:'SELECT_RESOURCES'});
   }else if(s.phase==='SELECT_RESOURCES'){
    const original=s.confirmation!;
    if(original.plan.semantics.requirements.filter(r=>r.kind==='EMPLOYEE').every(r=>r.selected)){
     s=await save({...s,phase:'RESOURCES'});
    }else{
     s=await pending(s,'select-resources');
     try{const selected=await selectAutomaticResources(original.plan.plan_id,original,s.key+':selection:'+(s.cycle??0)+(s.selectionRetry?':recheck:'+s.selectionRetry:''),session.csrfToken);
     s=await save({...s,pending:undefined,confirmation:selected.confirmation,phase:'RESOURCES'});}
     catch(e){if(String(e)!==coverageFailure)throw e;s=await repairCoverage(s);}
    }
   }else if(s.phase==='RESOURCES'){
    s=await pending(s,'resources');const plan=s.confirmation!.plan;
    const ready=await prepareResources(plan.plan_id,plan.version,resourceKey(s),session.csrfToken);
    if(ready.state!=='READY')throw Error('分析所需能力尚未全部就绪：'+[ready.assembly?.reason,...ready.resources.map(r=>r.reason)].filter(Boolean).join('；'));
    s=await save({...s,pending:undefined,phase:'EXECUTE',log:[...s.log,'资源核验完成，正在执行分析并生成结果。']});
   }else if(s.phase==='EXECUTE'){
    s=await pending(s,'execute');const plan=s.confirmation!.plan;
    const result=await continueReadonlyWork(plan.plan_id,plan.version,session.csrfToken);
    s=await save({...s,pending:undefined,execution:result.receipt.preparationDigest,phase:'RUNNING'});
   }else break;
  }}catch(e){const message=String(e);setError(message);if(current.current?.state){try{await save({...current.current.state,error:message})}catch{/* Keep the original pending journal on conflicts. */}}}finally{flight.current=false;if(alive.current)setBusy(false)}
 }
 const runEffect=useEffectEvent(run),verifyEffect=useEffectEvent(verify);
 const state=journal?.state;
 const understandingFailed=Boolean(state&&['CLARIFY','UNDERSTANDING_FAILED'].includes(state.phase)&&settledUnderstandingFailure(state.draft));
 async function retryUnderstanding(){if(flight.current||!state||!understandingFailed)return;flight.current=true;setBusy(true);setStream(null);setError('');try{await verify();const receipt=await readDraftAssistance(state.draft!.invocationId);await verify();if(receipt.invocationId!==state.draft!.invocationId||!settledUnderstandingFailure(receipt))throw Error('原理解调用尚未核实为已结束，不会重新请求。');await save({...state,phase:'UNDERSTAND',pending:undefined,error:undefined,understandingRetry:(state.understandingRetry??0)+1,log:[...state.log,'已核实原理解失败且已结算；用户明确继续，按原问题发起新的受限理解请求。']});}catch(e){setError(String(e))}finally{flight.current=false;setBusy(false)}}
 useEffect(()=>{if(state&&(!state.pending||canRepair(state))&&!['CLARIFY','UNDERSTANDING_FAILED','RUNNING','DONE'].includes(state.phase))void runEffect();},[state,busy]); // Each owner command is preceded by a durable CAS claim.
 useEffect(()=>{if(!state?.execution)return;let live=true;const refresh=async()=>{try{await verifyEffect();const v=await preparedRequest<ExecutionView>(state.execution!);if(live)setExecution(v)}catch(e){if(live)setError(String(e))}};void refresh();const timer=setInterval(()=>void refresh(),3000);return()=>{live=false;clearInterval(timer)}},[state?.execution]);
 async function answer(text:string,source?:Source){if(flight.current||!state||!text.trim())return false;flight.current=true;setBusy(true);try{await verify();const c=await conversationRequest<PrivateConversation>('/'+conversation);await conversationRequest('/'+conversation+'/messages',session.csrfToken,{expectedVersion:c.conversation.version,idempotencyKey:state.key+':answer:'+state.messages.length,content:text});await save({...state,source:source??state.source,phase:'UNDERSTAND',pending:undefined,error:undefined,messages:appendUserMessage(state.messages,text),log:[...state.log,'已收到补充，继续理解并核对分析范围。']});return true}catch(e){setError(String(e));return false}finally{flight.current=false;setBusy(false)}}
 if(!state)return error?<p role="alert">{error}</p>:null;
 const recordedUpdate=execution?.events?.filter(event=>Number.isFinite(Date.parse(event.created_at))).reduce<string|undefined>((latest,event)=>!latest||Date.parse(event.created_at)>Date.parse(latest)?event.created_at:latest,undefined);
 return <section className="conversation-journey" aria-busy={busy}><ConversationMessageIdentity assistant timestamp={recordedUpdate} timeLabel="执行更新"/><div className="conversation-assistant-bubble"><h2>{execution?.progress?.state==='SUCCEEDED'?'分析结果':understandingFailed?'理解未成功':state.execution&&!execution?.progress?'正在读取本次工作':state.phase==='CLARIFY'?'请确认一下分析范围':['FAILED','RECOVERY_REQUIRED','CANCELLED','CANCELED','UNKNOWN'].includes(execution?.progress?.state||'')?'本次办理状态':'正在办理你的问题'}</h2>{state.messages.length>1&&<details open={execution?.progress?.state!=='SUCCEEDED'}><summary>本次补充说明</summary>{state.messages.slice(1).map(m=><blockquote key={m.id}>{m.text}</blockquote>)}</details>}<ConversationPlacement target={railTarget}><ConversationProgress phase={understandingFailed?'UNDERSTANDING_FAILED':state.phase} pending={state.pending} busy={busy} error={error||state.error} execution={execution} hasExecution={Boolean(state.execution)}/>{busy&&<ConversationElapsed key={state.pending??state.phase}/>}</ConversationPlacement>{busy&&['understanding','planning'].includes(state.pending??'')&&stream&&!error&&<section aria-label="模型流式输出" className="journey-progress"><strong>{state.pending==='planning'?'正在准备分析方案':'正在理解你的问题'}</strong><p role="status">请求正在处理中，已有内容持续呈现，完成后继续原任务。</p><details><summary>查看传输信息</summary><p>已接收 {stream.characters??0} 个输出字符。</p></details>{stream.preview&&<p style={{whiteSpace:'pre-wrap'}}>{stream.preview}</p>}<small>生成中的内容尚未核验，不作为执行指令或最终结论。</small></section>}<details><summary>查看已完成的办理记录</summary><ol>{state.log.map((text,i)=><li key={i}>{text}</li>)}</ol></details>
 {understandingFailed&&<section role="alert" aria-label="理解结果未通过校验"><p>系统返回的理解结果格式不符合要求，本次理解未成功。这不是缺少资料，也不需要你重复描述问题。</p><p>原问题和已选资料已保留，尚未启动业务任务。不会自动重新调用模型；你可以沿用原问题明确继续。</p><button type="button" disabled={busy} onClick={()=>void retryUnderstanding()}>沿用原问题重新理解</button><small>将先核实原调用已结束，再发起一次新的理解请求，仍受授权与预算约束。</small></section>}
 {state.phase==='CLARIFY'&&!understandingFailed&&<div><p>{state.draft?.clarificationQuestion??(state.source?'请补充你最关注的问题，例如关注的指标、时间或对象。':'请选择本次要分析的资料范围。')}</p>{!state.source&&<><p>系统可用资料如下。测试资料不代表真实经营数据；确认后将自动分析并把结果返回这里。</p>{state.sources?.filter(source=>source.assessment?.state==='MISSING_TOOLS').map(source=><p key={source.source.digest}>“{source.label??source.name}”可读取，但缺少兼容的执行工具，暂不能自动分析。</p>)}{state.sources?.map(source=><button key={source.source.digest} disabled={busy||source.assessment?.state==='MISSING_TOOLS'} onClick={()=>void answer('使用系统现有的'+source.name+(source.periods.length?'，时间范围为'+source.periods.join('、'):'，分析范围为该资料包含的全部记录')+(source.sourceSchema==='document-review-source.v1'?'。检查材料的完整性，引用原文；如适用规范不明确，请在执行中向我确认。不执行上线操作。':'。按资料的既有口径进行只读分析，展示汇总、变化贡献和异常明细，不修改原始数据。'),source)}>使用{source.periods.join('、')||'现有'}{source.label??(source.sourceSchema.startsWith('sales')?'销售':'交付')}{source.label?'':'测试资料'}</button>)}</>}<ConversationPlacement target={composerTarget}><ConversationAnswer key={state.key+':'+state.messages.length} storageKey={conversationScope(session)+':'+conversation+':'+state.key+':'+state.messages.length} id="journey-reply" label="补充说明" button="发送补充" disabled={busy} onAnswer={text=>answer(text)} question={state.draft?.clarificationQuestion??undefined}/></ConversationPlacement></div>}
 {state.source&&<details open={!state.execution}><summary>本次能做什么与完成标准</summary>{state.execution&&<p>以下为执行前核对的范围与完成标准；当前进展见“本次工作”。</p>}<p>资料与已登记能力：{state.source.assessment?.state==='MISSING_TOOLS'?'尚缺执行工具':'可进入方案核验，尚不代表已经执行或解决问题'}</p><ul>{state.source.completionCriteria?.map((c,i)=><li key={i}>{c}</li>)}</ul>{state.source.assessment?.limitations.map((c,i)=><p key={i}>{c}</p>)}</details>}
 {state.draft?.draft&&<details><summary>查看已理解的目标</summary><p>{state.draft.draft.description}</p></details>}
 {(error||state.error)&&<div role="alert"><p>本次处理停在当前步骤，已有内容已保留。</p><p>{error||state.error}</p><p>不会自动重发可能已执行的请求。恢复后仍在本会话继续。</p></div>}
 {((state.phase==='PLAN'&&state.pending==='planning'&&state.error?.includes('（MODEL_AUTHORIZATION_INVALID）'))||(state.phase==='EXECUTE'&&state.pending==='execute'&&['Error: READONLY_RESOURCE_PREPARATION_REQUIRED','Error: READONLY_CONTINUATION_VALIDATION_FAILED'].includes(state.error??'')))&&<button disabled={busy} onClick={()=>{setError('');void save({...state,pending:undefined,error:undefined})}}>配置修复后继续分析</button>}
 {state.phase==='SELECT_RESOURCES'&&state.pending==='select-resources'&&[coverageFailure,'Error: 现有能力仍不能完成该方案，已保留资料与方案缺口。'].includes(state.error??'')&&<button disabled={busy} onClick={()=>void recheckSelection()}>能力补齐后继续分析</button>}
 {state.phase==='RESOURCES'&&state.pending==='resources'&&state.error?.startsWith('Error: 分析所需能力尚未全部就绪：')&&<button disabled={busy} onClick={()=>void recheckResources()}>重新核对可用能力</button>}
 {state.pending&&!busy&&!state.error&&<p role="status">上次请求尚未核实，已保留原记录，暂不重复执行。</p>}
 {state.execution&&<><NativeLiveProgress key={conversationScope(session)+':'+conversation+':'+state.execution} digest={state.execution} conversation={conversation} csrf={session.csrfToken} executionState={execution?.progress?.state} composerTarget={composerTarget} railTarget={railTarget} viewScope={conversationScope(session)}/>{execution&&<ConversationEvidenceRail key={conversationScope(session)+':'+conversation+':'+execution.digest} view={execution} conversation={conversation} viewKey={conversationScope(session)+':'+conversation+':'+execution.digest} target={railTarget}/>}<p>执行状态：{execution?.progress?.state??'正在读取'} · 已生成{execution?.artifacts.length??0}份产物</p><PreparedExecutionPanel contextKey={'journey:'+conversation} digest={state.execution} problemId={state.problem!.business_problem_id} csrfToken={session.csrfToken} blocked={false} readOnly={true} onBusy={()=>{}} supplementConversation={conversation}/></>}
 </div></section>;
}
