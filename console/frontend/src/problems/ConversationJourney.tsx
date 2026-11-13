import {documentBusinessSummary} from './documentRuleSummary';
import {sameSelectedSource,sourceInputFeedback} from './sourceInputFeedback';
import type {SourceInputObservation} from '../api/draftAssistanceTypes';
import {adoptionFeedback,type AdoptionFeedback,type AdoptionStage} from './adoptionFeedback';
import {ConversationRoutingContext,useConversationRouteOwner,type RoutedOwner} from './ConversationRoutingContext';
import {ConversationPlanningRecovery,type PlanningStartStatus} from './ConversationPlanningRecovery';
import {notifyConversationSend} from './useConversationScroll';
import {retainPlanningQuestion} from './ConversationPlanningHistory';
import {ConversationTeamContext} from '../teams/ConversationTeamContext';
import {ConversationMessageIdentity} from './ConversationMessageIdentity';
import {ConversationElapsed} from './ConversationElapsed';
import {ConversationPlacement} from './ConversationPlacement';
import {ConversationAnswer} from './ConversationAnswer';
import {conversationScope} from './conversationViewState';
import type {ModelProgress} from '../api/modelStream';
import {ConversationProgress} from './ConversationProgress';
import {ConversationEvidenceRail} from './ConversationEvidenceRail';
import {NativeLiveProgress} from './NativeLiveProgress';
import {useCallback,useContext,useEffect,useEffectEvent,useRef,useState} from 'react';
import {WorkbenchRequestError,readConversationUnderstandingCapability,readConversationUnderstandingResult,beginDraftAssistance,readDraftAssistance,createBusinessProblem,linkDraftAssistanceProblem,readBusinessProblem,readWorkbenchSession,writeCriterion,writeCriteriaSet,transitionBusinessProblem,type WorkbenchSession,type DraftAssistanceResult,type BusinessProblemRevision} from '../api/businessWorkspace';
import {conversationRequest,readConversationHead,type PrivateConversation} from '../api/privateConversation';
import {planningRequest,type Invocation,type PlanningBody} from '../planning/planningRequests';
import {confirmPolicy,prepareResources,readResourcePreparation,readReadonlyContinuation,continueReadonlyWork,selectAutomaticResources,readResourceCoverage,type ExactRef,type Confirmation} from '../planning/api';
import {preparedRequest,type ExecutionView} from '../api/preparedExecution';
import {conversationUnderstandingContent,understandingContent,type UserFactMessage} from './problemUnderstandingModel';
import {PreparedExecutionPanel} from './PreparedExecutionPanel';

type Source={sourceContentDigest?:string;source:ExactRef;name:string;periods:string[];sourceSchema:string;synthetic:boolean;label?:string;completionCriteria?:string[];assessment?:{state:string;missingOperations:string[];limitations:string[]}};
const sameUsableSource=(a:Source,b:Source)=>a.source.resource_id===b.source.resource_id&&a.source.revision_id===b.source.revision_id&&a.source.digest===b.source.digest&&a.assessment?.state!=='MISSING_TOOLS';
type State={planningRequestKey?:string;planningAnswers?:string[];planningReply?:number;planningPredecessor?:string;understandingProtocol?:number;userMessageId?:string;understandingRetry?:number;selectionRetry?:number;resourceRetry?:number;cycle?:number;coverageFeedback?:string;expectedPlanVersion?:number;key:string;phase:string;question:string;messages:UserFactMessage[];sources?:Source[];source?:Source;draft?:DraftAssistanceResult;problem?:BusinessProblemRevision;criterion?:string;planning?:Invocation;confirmation?:Confirmation;execution?:string;error?:string;pending?:string;log:string[]};
type Journal={version:number;state:State|null};
const settledUnderstandingFailure=(draft?:DraftAssistanceResult)=>draft?.state==='FAILED'&&draft.reasonCode==='OUTPUT_SCHEMA_INVALID'&&draft.settlementStatus==='ESTIMATE_SETTLED'&&draft.localWorkerState==='REAPED';
const coverageFailure='Error: AUTOMATIC_SELECTION_COVERAGE_BLOCKED';
const canRepair=(s:State)=>s.phase==='SELECT_RESOURCES'&&s.pending==='select-resources'&&s.error===coverageFailure&&(s.cycle??0)<2;

export function ConversationJourney({initialAdoption=false,conversation,session,onActive,onCreatePaused,onExecutionContext,onProgressVisible,onRoutingWorkEligible,onMessagesChanged,composerTarget,railTarget,returnTarget,contentHidden=false,separatePreparation=false,composerEnabled=true,onFocusComposer}:{initialAdoption?:boolean;onCreatePaused?:(paused:boolean)=>void;contentHidden?:boolean;composerEnabled?:boolean;onFocusComposer?:()=>void;separatePreparation?:boolean;returnTarget?:HTMLElement|null;composerTarget?:HTMLElement|null;railTarget?:HTMLElement|null;conversation:string;session:WorkbenchSession;onActive:(active:boolean)=>void;onExecutionContext?:(value:ExecutionView|null)=>void;onProgressVisible?:(visible:boolean)=>void;onRoutingWorkEligible?:(eligible:boolean)=>void;onMessagesChanged?:()=>Promise<void>}){
 const routingContext=useContext(ConversationRoutingContext);
 const [journal,setJournal]=useState<Journal|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[execution,setExecution]=useState<ExecutionView|null>(null);
 const [recoveryObservation,setRecoveryObservation]=useState<{key:string;state:string}|null>(null);
 const [executionAbsent,setExecutionAbsent]=useState<string|null>(null);
 const [adoptionIssue,setAdoptionIssue]=useState<{invocationId:string;feedback:AdoptionFeedback}|null>(null);
 const [sourceInput,setSourceInput]=useState<{key:string;observation?:SourceInputObservation;capability?:string}|null>(null);
 const [createReadNotice,setCreateReadNotice]=useState('');
 const [stream,setStream]=useState<ModelProgress|null>(null);
 const [sourceRefreshMessage,setSourceRefreshMessage]=useState('');
 const sourceContext=conversationScope(session)+':'+conversation,sourceContextRef=useRef(sourceContext);sourceContextRef.current=sourceContext;
 const current=useRef<Journal|null>(null),flight=useRef(false),alive=useRef(true),recoveryAttempts=useRef(new Set<string>());
 const readSources=useCallback(async(protocol?:number)=>{
  try{return protocol===3?await conversationRequest<{items:Source[]}>('/'+conversation+'/sources'):await planningRequest<{items:Source[]}>('conversation-sources')}
  catch(e){throw Error('资料读取失败，原问题和已有处理记录已保存。可在本会话重新读取可用资料。'+String(e),{cause:e})}
 },[conversation]);
 useEffect(()=>{alive.current=true;let live=true;
  conversationRequest<Journal>('/'+conversation+'/journey').then(async j=>{
   if(live)setSourceRefreshMessage('');
   const s=j.state;
   // Saved work must remain available while the optional source list loads.
   if(live){current.current=j;setJournal(j);onActive(Boolean(j.state))}
   const loaded=j;
   if(s?.understandingProtocol===3&&s.phase==='CLARIFY'&&!s.pending&&!s.error&&['NEEDS_DATA','DRAFT_READY'].includes(s.draft?.resultKind??'')){
    try{const sources=(await readSources(s.understandingProtocol)).items;
     const source=s.source?sources.find(item=>sameUsableSource(item,s.source!)):undefined;
     j={...j,state:{...s,sources,source}};
     if(live&&s.source&&!source)setSourceRefreshMessage('原先选定的资料或执行能力当前不可用，请重新确认资料范围；尚未开始执行。');
    }catch{j={...j,state:{...s,sources:[],source:undefined}};if(live)setSourceRefreshMessage('暂时无法核对当前可用资料，请刷新后重试。原问题与补充说明已保留。')}
   }
   if(live&&!flight.current&&current.current===loaded){current.current=j;setJournal(j);onActive(Boolean(j.state))}
  }).catch(e=>{if(live)setError(String(e))});return()=>{live=false;alive.current=false}
 },[conversation,onActive,readSources]);
 async function reloadSources(){
  const s=current.current?.state;if(flight.current||!s||s.pending!=='source-discovery')return;
  flight.current=true;setBusy(true);setError('');const scope=sourceContext;
  try{await verify();const sources=(await readSources(s.understandingProtocol)).items;if(!alive.current||sourceContextRef.current!==scope||current.current?.state?.key!==s.key)return;const source=s.source?sources.find(item=>sameUsableSource(item,s.source!)):undefined;
   await save({...s,sources,source,pending:undefined,error:undefined,phase:'CLARIFY',log:[...s.log,'已重新读取可用资料；原理解结果保留，未重新调用模型。']});
  }catch(e){if(alive.current)setError(String(e))}finally{flight.current=false;setBusy(false)}
 }
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
 async function recoverExecution(resume=false){
  if(flight.current||!current.current?.state)return;
  const s=current.current.state,c=s.confirmation;
  if(s.phase!=='EXECUTE'||s.pending!=='execute'||!c)return;
  const token=JSON.stringify([s.key,c.plan.plan_id,c.plan.version,c.digest]);
  if(resume&&executionAbsent!==token)return;
  flight.current=true;setBusy(true);setExecutionAbsent(null);setError('');
  try{
   await verify();
   let result;
   try{result=await readReadonlyContinuation(c.plan.plan_id,c.plan.version)}catch(e){
    if(!(e instanceof WorkbenchRequestError)||e.status!==404||e.reasonCode!=='READONLY_CONTINUATION_NOT_FOUND')throw e;
   }
   await verify();
   if(!alive.current||current.current?.state!==s)throw Error('原会话状态已变化，请重新核对执行状态。');
   if(!result&&!resume){setExecutionAbsent(token);return;}
   if(!result){result=await continueReadonlyWork(c.plan.plan_id,c.plan.version,session.csrfToken);await verify();}
   const r=result.receipt;
   if(r.sourcePlanId!==c.plan.plan_id||r.sourcePlanVersion!==c.plan.version||r.sourcePlanDigest!==c.digest||r.subject!==session.principal.principalId||r.executionStarted!==true||!r.preparationDigest?.match(/^[a-f0-9]{64}$/))throw Error('READONLY_CONTINUATION_CONTEXT_MISMATCH');
   if(!alive.current||current.current?.state!==s)throw Error('原会话状态已变化，请重新核对执行状态。');
   await save({...s,pending:undefined,error:undefined,execution:r.preparationDigest,phase:'RUNNING',log:[...s.log,'已核实原执行回执，在本会话继续显示进展与结果。']});
  }catch(e){setError(String(e))}finally{flight.current=false;if(alive.current)setBusy(false)}
 }
 async function recheckSelection(){
  if(flight.current||!current.current?.state)return;flight.current=true;setBusy(true);
  try{await verify();const s=current.current.state,p=s.confirmation!.plan;
   const coverage=await readResourceCoverage(p.plan_id,p.version);
   if(coverage.planId!==p.plan_id||coverage.planVersion!==p.version||coverage.planDigest!==s.confirmation!.digest||coverage.subject!==session.principal.principalId)throw Error('RESOURCE_COVERAGE_CONTEXT_MISMATCH');
   await save({...s,pending:undefined,error:undefined,selectionRetry:(s.selectionRetry??0)+1,log:[...s.log,'已重新读取当前能力，继续核对原方案；不重发模型调用或执行任务。']});setError('');
  }catch(e){setError(String(e))}finally{flight.current=false;setBusy(false)}
 }
 function understandingKey(s:State){return s.key+':draft:'+s.messages.length+(s.understandingRetry?':retry:'+s.understandingRetry:'')}
 async function applyUnderstanding(s:State,draft:DraftAssistanceResult){
  if(settledUnderstandingFailure(draft))return save({...s,pending:undefined,error:undefined,draft,phase:'UNDERSTANDING_FAILED',log:[...s.log,'理解结果格式校验未通过，原问题已保留，尚未启动业务任务。']});
  if(draft.state!=='SUCCEEDED')throw Error('理解调用尚未成功：'+(draft.reasonCode??draft.state));
  if(draft.conversationDelivery?.state!=='SAVED')return save({...s,pending:undefined,draft,phase:'ANSWER_UNAVAILABLE',error:'本次调用已结束，但答复未能保存或正文不可恢复。不会自动重新调用模型。'});
  await onMessagesChanged?.();
  if(draft.resultKind==='DIRECT_ANSWER')return save({...s,pending:undefined,error:undefined,draft,phase:'DIRECT_DONE',log:[...s.log,'答复已保存到原会话。']});
  if(draft.resultKind==='NEEDS_CLARIFICATION')return save({...s,pending:undefined,error:undefined,draft,phase:'CLARIFY',log:[...s.log,'有一处会影响后续处理的信息需要确认。']});
  s=await pending({...s,draft},'source-discovery');
  const sources=(await readSources(s.understandingProtocol)).items;
  const source=s.source?sources.find(item=>sameUsableSource(item,s.source!)):undefined;
  return save({...s,pending:undefined,error:undefined,draft,sources,source,phase:draft.resultKind==='DRAFT_READY'&&source?'CREATE':'CLARIFY',log:[...s.log,'已核对当前可读资料，继续确定本次范围。']});
 }
 async function continueSavedCreate(){
  const j=current.current,s=j?.state,d=s?.draft;
  if(flight.current||!j||!s||s.phase!=='CREATE'||s.pending!=='create-problem'||d?.state!=='SUCCEEDED'||d.resultKind!=='DRAFT_READY'||!d.draft||!s.source)return;
  flight.current=true;setBusy(true);setCreateReadNotice('正在核对这份草案对应的原工作记录…');
  try{
   await verify();
   type CreationStatus={state:'NOT_CREATED'|'CREATED'|'UNKNOWN';draftInvocationId:string;requestKey:string;journeyKey:string;journalVersion:number;aggregateVersion:number;revision?:BusinessProblemRevision};
   const key=s.key+':problem',status=await conversationRequest<CreationStatus>('/'+encodeURIComponent(conversation)+'/create-status?'+new URLSearchParams({draftInvocationId:d.invocationId,requestKey:key}));
   await verify();
   if(current.current!==j||status.draftInvocationId!==d.invocationId||status.aggregateVersion!==d.aggregateVersion||status.requestKey!==key||status.journeyKey!==s.key||status.journalVersion!==j.version)throw Error('CREATE_BINDING_CHANGED');
   if(status.state==='UNKNOWN'){setCreateReadNotice('尚未核实原工作是否已经创建，已有草案保留；暂不重复提交。');return}
   let revision:BusinessProblemRevision;
   if(status.state==='CREATED'){
    if(!status.revision?.business_problem_id||!status.revision.revision_id||!status.revision.digest)throw Error('CREATE_RECEIPT_INCOMPLETE');revision=status.revision;
   }else if(status.state==='NOT_CREATED'){
    // Persist that a new same-key attempt is in progress before the owner POST.
    // A lost response must not leave the previous refusal as the latest fact.
    await save({...s,error:undefined,pending:'create-problem'});setError('');
    const created=await createBusinessProblem(session.csrfToken,{...d.draft,ownerId:session.principal.principalId,idempotencyKey:key,draftInvocationId:d.invocationId});revision=created.revision;
   }else throw Error('CREATE_STATUS_UNVERIFIED');
   if(!revision?.business_problem_id||!revision.revision_id||!revision.digest)throw Error('CREATE_RECEIPT_INCOMPLETE');
   await verify();
   await save({...s,error:undefined,pending:undefined,problem:revision,phase:'CRITERION',log:[...s.log,'已核对并续接这份草案对应的原工作，继续准备核对标准。']});setError('');setCreateReadNotice('已接回原工作，继续使用已保存草案。');
  }catch(e){
   if(e instanceof WorkbenchRequestError&&[401,403].includes(e.status))setCreateReadNotice('当前无法读取或继续这项工作。草案和输入均已保留，访问恢复后可再次核对。');
   else setCreateReadNotice('暂未确认本次接续状态。草案和输入均已保留；再次继续前会先读取原记录，不会重新理解问题。');
  }finally{flight.current=false;if(alive.current)setBusy(false)}
 }
 async function continueSavedCriterion(){
  const j=current.current,s=j?.state,d=s?.draft,p=s?.problem;
  if(flight.current||!j||!s||s.phase!=='CRITERION'||s.pending!=='criterion'||!p||!d||!s.source)return;
  flight.current=true;setBusy(true);setCreateReadNotice('正在核对当前工作的完成标准…');
  try{
   await verify();
   type CriterionStatus={state:'NOT_WRITTEN'|'WRITTEN'|'UNKNOWN';draftInvocationId:string;draftAggregateVersion:number;observedAggregateVersion:number;requestKey:string;journeyKey:string;journalVersion:number;problem:ExactRef;revision?:{revision_id:string;success_criterion_id:string;digest:string}};
   const key=s.key+':criterion',status=await conversationRequest<CriterionStatus>('/'+encodeURIComponent(conversation)+'/criterion-status?'+new URLSearchParams({draftInvocationId:d.invocationId,requestKey:key}));
   await verify();
   if(current.current!==j||status.draftInvocationId!==d.invocationId||status.draftAggregateVersion!==d.aggregateVersion||!Number.isInteger(status.observedAggregateVersion)||status.observedAggregateVersion<d.aggregateVersion||status.requestKey!==key||status.journeyKey!==s.key||status.journalVersion!==j.version||status.problem?.resource_id!==p.business_problem_id||status.problem.revision_id!==p.revision_id||status.problem.digest!==p.digest)throw Error('CRITERION_BINDING_CHANGED');
   if(status.state==='UNKNOWN'){setCreateReadNotice('暂未核实完成标准是否已保存，保留当前工作，暂不重复提交。');return}
   let revision=status.revision;
   if(status.state==='NOT_WRITTEN'){
    await save({...s,error:undefined,pending:'criterion'});setError('');
    await linkDraftAssistanceProblem(session.csrfToken,d.invocationId,{problemId:p.business_problem_id,problemRevisionId:p.revision_id,problemDigest:p.digest});
   const written=await writeCriterion(session.csrfToken,{problemId:p.business_problem_id,criterionType:'HUMAN_EVALUATED',measurement:{rubric:'回答已确认的用户目标：'+(p.description??s.question)+'。'+(s.source?.completionCriteria??['展示来源依据、异常与资料缺口；区分观察和推测。']).join('')+'仅作为测试资料分析，不代表真实业务问题已经解决。'},requiredEvidenceKinds:[],evaluatorType:'HUMAN',evaluatorVersion:'v1',applicability:{sourceReference:s.source!.source},idempotencyKey:key});
    revision=written.revision;
   }else if(status.state!=='WRITTEN')throw Error('CRITERION_STATUS_UNVERIFIED');
   if(!revision?.revision_id||!revision.success_criterion_id||!revision.digest)throw Error('CRITERION_RECEIPT_INCOMPLETE');
   await verify();
   await save({...s,error:undefined,pending:undefined,criterion:revision.revision_id,phase:'ACTIVATE',log:[...s.log,'已接回当前工作的完成标准，继续原工作。']});setError('');setCreateReadNotice('');
  }catch{setCreateReadNotice('暂未确认完成标准的接续状态。当前工作和输入已保留，再次继续时会先核对原记录，不会重新理解问题。')}
  finally{flight.current=false;if(alive.current)setBusy(false)}
 }
 async function preparePlanning(s:State){
    s=await pending({...s,planningRequestKey:s.key+':planning'+(s.cycle?':'+s.cycle:'')+(s.planningReply?':clarification:'+s.planningReply:'')},'planning');
    // The bounded routing question uses the current title; the exact problem
    // target supplies its complete description and criteria to planning.
    const routed=await planningRequest<{state:string;planningRequest:PlanningBody|null}>('question-activity-input',{question:s.problem!.title??s.question,problemId:s.problem!.business_problem_id,source:s.source!.source,idempotencyKey:s.key+':planning'+(s.cycle?':'+s.cycle:'')+(s.planningReply?':clarification:'+s.planningReply:'')});
    if(!routed.planningRequest)throw Error('暂不能根据所选资料开始分析：'+routed.state);
    if(s.coverageFeedback&&s.planning?.result.proposal){const old=s.planning.result.proposal;routed.planningRequest={...routed.planningRequest,source_proposal:{resource_id:old.proposal_id,revision_id:String(old.revision),digest:s.planning.result.proposal_digest!},answers:[...routed.planningRequest.answers,s.coverageFeedback]};}
    if(s.planningAnswers?.length)routed.planningRequest={...routed.planningRequest,answers:[...routed.planningRequest.answers,'用户对必要追问的补充：'+JSON.stringify(s.planningAnswers)]};
    if(s.planningPredecessor)routed.planningRequest={...routed.planningRequest,predecessor_invocation_id:s.planningPredecessor,source_proposal:s.planning?.invocation.request?.source_proposal as PlanningBody['source_proposal']};
    await planningRequest('planning-v2/preflight',routed.planningRequest);
    const planning=await planningRequest<Invocation>('planning-v2/invocations',routed.planningRequest,{},undefined,p=>{if(alive.current)setStream(previous=>p.kind==='stage'&&previous?.kind==='stream'?{...previous,stage:p.stage}:p)});
    if(planning.result.technical_status==='SUCCEEDED'&&planning.result.kind==='NEEDS_CLARIFICATION'&&planning.result.questions?.length){s=await save({...s,pending:undefined,error:undefined,planning,phase:'PLANNING_CLARIFY',log:[...s.log,'方案准备中有一处需要确认，补充后沿用本次问题继续。']});return s;}
    if(planning.result.technical_status!=='SUCCEEDED'||!planning.result.proposal)throw Error('分析方案尚未就绪：'+(planning.result.questions?.join('；')||planning.result.reason||planning.result.kind||planning.result.technical_status));
    s=await save({...s,pending:undefined,planning,planningPredecessor:undefined,phase:'CONFIRM',log:[...s.log,'分析方案已生成，正在核对并准备执行资源。']});
  return s;
 }
 function matchesPlanningStart(status:PlanningStartStatus){
  const j=current.current,s=j?.state,d=s?.draft,p=s?.problem;
  if(!j||!s||!d||!p||!s.source||s.phase!=='PLAN'||s.pending!=='planning')return false;
  const key=s.planningRequestKey??s.key+':planning'+(s.cycle?':'+s.cycle:'')+(s.planningReply?':clarification:'+s.planningReply:'');
  const selected=status.source as Pick<Source,'source'|'sourceContentDigest'|'sourceSchema'>;
  return status.journalVersion===j.version&&status.journeyKey===s.key&&status.requestKey===key&&status.draftInvocationId===d.invocationId&&status.draftAggregateVersion===d.aggregateVersion&&status.problem?.resource_id===p.business_problem_id&&status.problem.revision_id===p.revision_id&&status.problem.digest===p.digest&&Boolean(selected?.source)&&sameSelectedSource(selected,s.source);
 }
 async function continuePlanningPreparation(status:PlanningStartStatus){
  const j=current.current,s=j?.state;
  if(flight.current||!j||!s)return;
  if(status.state!=='NOT_STARTED'||!matchesPlanningStart(status))throw Error('PLANNING_START_TARGET_CHANGED');
  flight.current=true;setBusy(true);
  try{await verify();if(current.current!==j)throw Error('PLANNING_START_TARGET_CHANGED');await save({...s,error:undefined,pending:'planning'});setError('');await preparePlanning({...s,error:undefined});}
  catch(e){const latest=current.current?.state;if(latest)await save({...latest,error:String(e),pending:'planning'});setError(String(e));}
  finally{flight.current=false;if(alive.current)setBusy(false)}
 }
 async function run(){
  if(flight.current||!current.current?.state||(current.current.state.pending&&!canRepair(current.current.state)))return;
  flight.current=true;setBusy(true);setError('');let s=current.current.state;
  try{while(alive.current){await verify();
   if(canRepair(s)){s=await repairCoverage(s);continue;}
   if(s.phase==='UNDERSTAND'){
    if(!s.understandingProtocol){s=await pending(s,'understanding-capability');const capability=await readConversationUnderstandingCapability();s=await save({...s,pending:undefined,understandingProtocol:capability.conversationUnderstanding?3:2});}
    if(s.understandingProtocol!==3&&!s.source&&!s.sources){
     s=await pending(s,'source-discovery');
     const sources=(await readSources(s.understandingProtocol)).items;
     s=await save({...s,pending:undefined,sources,phase:'CLARIFY',log:[...s.log,'已核对可用资料，请确认本次分析范围。']});continue;
    }
    s=await pending(s,'understanding');const previous=s.draft?.state==='SUCCEEDED'?s.draft:undefined;
    if(s.understandingProtocol===3&&!s.userMessageId)throw Error('原请求与用户消息的关联尚未核实，未重新调用模型。');
    const content=s.understandingProtocol===3?conversationUnderstandingContent(s.messages,previous):understandingContent(s.messages,s.messages.length,previous?.draft??null,previous?.understanding??null,previous?.clarificationQuestion??null);
    const draft=await beginDraftAssistance(session.csrfToken,{idempotencyKey:understandingKey(s),content,...(s.understandingProtocol===3?{conversationId:conversation,conversationMessageId:s.userMessageId}:{}),...(previous&&!(s.understandingProtocol===3&&previous.resultKind==='DIRECT_ANSWER')?{parentContextId:previous.contextId,parentTurnId:previous.turnId,expectedParentVersion:previous.turnVersion,predecessorInvocationId:previous.invocationId}:{})},{},p=>{if(alive.current)setStream(previous=>p.kind==='stage'&&previous?.kind==='stream'?{...previous,stage:p.stage}:p)});
    setStream(null);if(s.understandingProtocol===3&&(draft.state==='SUCCEEDED'||settledUnderstandingFailure(draft))){s=await applyUnderstanding(s,draft);continue;}const recoverable=settledUnderstandingFailure(draft);
    if(draft.state!=='SUCCEEDED'&&!recoverable)throw Error('问题理解尚未完成：'+(draft.reasonCode??draft.state));
    const sources=s.sources??(await readSources(s.understandingProtocol)).items;
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
    // Use the created revision, including corrections made during clarification.
    // The original question stays in history; it must not redefine the goal.
    const criterion=await writeCriterion(session.csrfToken,{problemId:p.business_problem_id,criterionType:'HUMAN_EVALUATED',measurement:{rubric:'回答已确认的用户目标：'+(p.description??s.question)+'。'+(s.source?.completionCriteria??['展示来源依据、异常与资料缺口；区分观察和推测。']).join('')+'仅作为测试资料分析，不代表真实业务问题已经解决。'},requiredEvidenceKinds:[],evaluatorType:'HUMAN',evaluatorVersion:'v1',applicability:{sourceReference:s.source!.source},idempotencyKey:s.key+':criterion'});
    s=await save({...s,pending:undefined,criterion:criterion.revision.revision_id,phase:'ACTIVATE'});
   }else if(s.phase==='ACTIVATE'){
    s=await pending(s,'activate');const p=s.problem!,id=p.business_problem_id;let detail=await readBusinessProblem(id);
    await writeCriteriaSet(session.csrfToken,id,{problemRevisionId:p.revision_id,orderedCriterionRevisionIds:[s.criterion!],expectedVersion:detail.problem.aggregate_version,idempotencyKey:s.key+':criteria-set'});
    detail=await readBusinessProblem(id);await transitionBusinessProblem(session.csrfToken,id,{toState:'ACTIVE',expectedVersion:detail.problem.aggregate_version,idempotencyKey:s.key+':activate'});
    const c=await conversationRequest<PrivateConversation>('/'+conversation);await conversationRequest('/'+conversation+'/links',session.csrfToken,{expectedVersion:c.conversation.version,idempotencyKey:s.key+':link',target:{problemId:id,revisionId:p.revision_id,problemDigest:p.digest}});
    s=await save({...s,pending:undefined,phase:'PLAN',log:[...s.log,'正在结合资料和可用能力制定分析方案。']});
   }else if(s.phase==='PLAN'){
    s=await preparePlanning(s);if(s.phase==='PLANNING_CLARIFY')break;
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
 const preparationPaused=Boolean(state?.phase==='PLAN'&&state.pending==='planning'&&['QUESTION_INPUT_SERVICE_UNAVAILABLE','QUESTION_INPUT_SERVICE_ACCESS_DENIED'].some(reason=>(error||state.error||'').includes(reason)));
 const criterionPaused=Boolean(state?.phase==='CRITERION'&&state.pending==='criterion');
 const createPaused=Boolean(state?.phase==='CREATE'&&state.pending==='create-problem');
 useEffect(()=>{onCreatePaused?.(createPaused||criterionPaused||preparationPaused);return()=>onCreatePaused?.(false)},[createPaused,criterionPaused,preparationPaused,onCreatePaused]);
 const sourceInputKey=state?.draft?.state==='SUCCEEDED'&&state.source&&((state.phase==='CLARIFY'&&!state.pending&&!state.error&&!error&&state.draft.resultKind==='NEEDS_DATA')||(state.phase==='CREATE'&&state.draft.resultKind==='DRAFT_READY'))?JSON.stringify([state.draft.invocationId,state.draft.aggregateVersion,state.source.source,state.source.sourceContentDigest]):null;
 const readSourceInput=useEffectEvent(async(key:string,isLive:()=>boolean)=>{
  const s=current.current?.state,d=s?.draft;if(!s?.source||!d)return;
  let capability:string|undefined;
  try{
   const [result,cap]=await Promise.allSettled([readDraftAssistance(d.invocationId),readConversationUnderstandingCapability()]);
   await verify();if(!isLive())return;if(cap.status==='fulfilled')capability=cap.value.selectedSourceContext;
   const now=current.current?.state;
   if(now?.phase!==s.phase||now.draft?.invocationId!==d.invocationId||now.draft.aggregateVersion!==d.aggregateVersion||!sameSelectedSource(now.source,s.source))return;
   const value=result.status==='fulfilled'?result.value:undefined,o=value?.sourceInputObservation;
   const exact=value?.state==='SUCCEEDED'&&value.invocationId===d.invocationId&&value.contextId===d.contextId&&value.aggregateVersion===d.aggregateVersion&&o?.invocationId===d.invocationId&&o.aggregateVersion===d.aggregateVersion&&o.basis==='RECORDED_ADAPTER_CONTRACT'&&sameSelectedSource(value.inputSource,s.source)&&sameSelectedSource(o.source,s.source);
   setSourceInput({key,capability,observation:exact?o:undefined});
  }catch{if(isLive())setSourceInput({key,capability})}
 });
 useEffect(()=>{if(!sourceInputKey)return;let live=true;const timer=setTimeout(()=>void readSourceInput(sourceInputKey,()=>live),0);return()=>{live=false;clearTimeout(timer)}},[sourceInputKey]);

 const understandingFailed=Boolean(state&&['CLARIFY','UNDERSTANDING_FAILED'].includes(state.phase)&&settledUnderstandingFailure(state.draft));
 async function retryUnderstanding(){if(flight.current||!state||!understandingFailed)return;flight.current=true;setBusy(true);setStream(null);setError('');try{await verify();const receipt=await readDraftAssistance(state.draft!.invocationId);await verify();if(receipt.invocationId!==state.draft!.invocationId||!settledUnderstandingFailure(receipt))throw Error('原理解调用尚未核实为已结束，不会重新请求。');await save({...state,phase:'UNDERSTAND',pending:undefined,error:undefined,understandingRetry:(state.understandingRetry??0)+1,log:[...state.log,'已核实原理解失败且已结算；用户明确继续，按原问题发起新的受限理解请求。']});}catch(e){setError(String(e))}finally{flight.current=false;setBusy(false)}}
 useEffect(()=>{if(state&&(!state.pending||canRepair(state))&&!['CLARIFY','PLANNING_CLARIFY','UNDERSTANDING_FAILED','RUNNING','DONE','DIRECT_DONE','ANSWER_UNAVAILABLE'].includes(state.phase))void runEffect();},[state,busy]); // Each owner command is preceded by a durable CAS claim.
 useEffect(()=>{if(!state?.execution)return;let live=true;const refresh=async()=>{try{await verifyEffect();const v=await preparedRequest<ExecutionView>(state.execution!);await verifyEffect();if(live)setExecution(v)}catch(e){if(live){setExecution(null);setError(String(e))}}};void refresh();const timer=setInterval(()=>void refresh(),3000);return()=>{live=false;clearInterval(timer)}},[state?.execution]);
 async function answerPlanning(text:string,savedMessageId?:string){
  if(flight.current||!state||state.phase!=='PLANNING_CLARIFY'||!text.trim()||!state.planning)return false;
  flight.current=true;setBusy(true);setError('');
  try{await verify();const previous=state.planning.invocation.target.invocation_id;
   const c=await retainPlanningQuestion(conversation,session.csrfToken,state.key,state.planning,verify);
   await onMessagesChanged?.();
   const replyKey=state.key+':planning-answer:'+previous,known=c.messages.find(message=>message.request_key===replyKey);
   if(known&&(known.kind||known.content!==text.trim()))throw Error('上次补充已保存，请保留原补充内容继续，避免重复提交。');
   const saved=savedMessageId?c.messages.find(message=>message.message_id===savedMessageId):undefined;
   if(savedMessageId&&(!saved||saved.kind||saved.content!==text.trim()))throw Error('原补充消息核对不一致，未继续原任务。');
   const sent=saved?{identity:saved.message_id}:known?{identity:known.message_id}:await conversationRequest<{identity:string}>('/'+conversation+'/messages',session.csrfToken,{expectedVersion:c.conversation.version,idempotencyKey:replyKey,content:text.trim()});
   notifyConversationSend(conversation);
   await save({...state,pending:undefined,error:undefined,phase:'PLAN',planningPredecessor:previous,planningReply:(state.planningReply??0)+1,planningAnswers:[...(state.planningAnswers??[]),text.trim()],messages:[...state.messages,{id:'user:'+sent.identity,text:text.trim()}],log:[...state.log,'已收到补充，沿用原问题、资料和完成标准继续准备方案。']});
   await onMessagesChanged?.();return true;
  }catch(e){setError(String(e));return false}finally{flight.current=false;setBusy(false)}
 }
 async function selectSource(text:string,source:Source){
  if(initialAdoption&&routingContext.enabled&&current.current?.state?.phase==='CLARIFY'&&['NEEDS_DATA','DRAFT_READY'].includes(current.current.state.draft?.resultKind??'')&&!current.current.state.draft?.inputSource){
   if(flight.current)return false;try{await save({...current.current.state,source});return await routingContext.send?.(text)??false}catch(e){setError(String(e));return false}
  }
  return answer(text,source);
 }
 async function answer(text:string,source?:Source){if(flight.current||!state||!text.trim())return false;flight.current=true;setBusy(true);try{await verify();const c=await readConversationHead(conversation);const sent=await conversationRequest<{identity:string}>('/'+conversation+'/messages',session.csrfToken,{expectedVersion:c.conversation.version,idempotencyKey:state.key+':answer:'+(state.userMessageId??state.messages.length),content:text});notifyConversationSend(conversation);await save({...state,...(state.phase==='DIRECT_DONE'?{key:'question:'+sent.identity,question:text.trim(),planningAnswers:undefined,planningReply:undefined,planningPredecessor:undefined,sources:undefined,problem:undefined,criterion:undefined,planning:undefined,confirmation:undefined,execution:undefined,cycle:undefined,expectedPlanVersion:undefined,coverageFeedback:undefined,selectionRetry:undefined,resourceRetry:undefined,understandingRetry:undefined}:{}),userMessageId:sent.identity,source:source??(state.phase==='DIRECT_DONE'?undefined:state.source),phase:'UNDERSTAND',pending:undefined,error:undefined,messages:[...state.messages,{id:'user:'+sent.identity,text:text.trim()}],log:[...state.log,'已收到补充，继续理解并核对分析范围。']});if(state.understandingProtocol===3)await onMessagesChanged?.();return true}catch(e){setError(String(e));return false}finally{flight.current=false;setBusy(false)}}
 const planningAnswerHandler=useRef<typeof answerPlanning|null>(null);
 useEffect(()=>{planningAnswerHandler.current=answerPlanning});
 const routePlanning=useCallback(async(text:string,messageId:string)=>{if(!state?.planning?.invocation?.target?.invocation_id||current.current?.version!==journal?.version||current.current?.state?.planning?.invocation?.target?.invocation_id!==state.planning.invocation.target.invocation_id)return false;return planningAnswerHandler.current?planningAnswerHandler.current(text,messageId):false},[journal?.version,state?.planning?.invocation?.target?.invocation_id]);
 async function adoptAnswer(text:string,messageId:string,receipt?:{requestKey:string}){
  const j=current.current,s=j?.state;
  if(!initialAdoption||!j||!s||s.phase!=='CLARIFY'||!s.draft||!receipt||flight.current)return {state:'REJECTED' as const};
  flight.current=true;setBusy(true);setError('');setAdoptionIssue(null);let adoptionStage:AdoptionStage='READ';
  try{
   await verify();const path='/'+encodeURIComponent(conversation)+'/understanding-results/'+encodeURIComponent(messageId)+'/adoption';
   type Adoption={adoption:{target:{original_invocation_id:string;journal_version:number;journey_key:string;message_id:string};actualResult:{invocationId:string}};understanding:DraftAssistanceResult;modelDispatched:false};
   let saved:Adoption;
   try{saved=await conversationRequest<Adoption>(path+'?'+new URLSearchParams({requestKey:receipt.requestKey}));}
   catch(e){if(!(e instanceof WorkbenchRequestError)||e.status!==404||e.reasonCode!=='UNDERSTANDING_ADOPTION_NOT_FOUND')throw e;adoptionStage='SUBMIT';saved=await conversationRequest<Adoption>(path,session.csrfToken,{requestKey:receipt.requestKey});}
   adoptionStage='RECEIPT';await verify();const t=saved.adoption.target;
   if(current.current!==j||t.original_invocation_id!==s.draft.invocationId||t.journal_version!==j.version||t.journey_key!==s.key||t.message_id!==messageId||saved.modelDispatched!==false||saved.understanding.invocationId!==saved.adoption.actualResult.invocationId)throw Error('原问题已变化，已保存结果不会转交其他问题。');
   adoptionStage='JOURNAL';await applyUnderstanding({...s,userMessageId:messageId,messages:[...s.messages,{id:'user:'+messageId,text}]},saved.understanding);return true;
  }catch(e){const feedback=adoptionFeedback(e,adoptionStage);setAdoptionIssue({invocationId:s.draft.invocationId,feedback});return {state:'UNKNOWN' as const,notice:feedback.detail}}finally{flight.current=false;setBusy(false)}
 }
 const adoptionHandler=useRef<typeof adoptAnswer|null>(null);
 useEffect(()=>{adoptionHandler.current=adoptAnswer});
 const routeInitial=useCallback((text:string,messageId:string,receipt?:{requestKey:string})=>adoptionHandler.current?adoptionHandler.current(text,messageId,receipt):Promise.resolve(false),[]);
 const routeOwner:RoutedOwner|null=state?.phase==='PLANNING_CLARIFY'&&state.planning?{target:{kind:'PLANNING',journalVersion:journal!.version,journeyKey:state.key,problemId:state.problem?.business_problem_id,invocationId:state.planning.invocation.target.invocation_id},onAnswer:routePlanning}:initialAdoption&&state?.phase==='CLARIFY'&&!state.pending&&!state.error&&state.draft&&(['NEEDS_DATA','NEEDS_CLARIFICATION'].includes(state.draft.resultKind??'')||state.draft.resultKind==='DRAFT_READY'&&!state.draft.inputSource)?{target:{kind:'UNDERSTANDING',journalVersion:journal!.version,journeyKey:state.key,invocationId:state.draft.invocationId,contextId:state.draft.contextId,turnId:state.draft.turnId,turnVersion:state.draft.turnVersion,aggregateVersion:state.draft.aggregateVersion},onAnswer:routeInitial}:null;
 const routingEnabled=useConversationRouteOwner(routeOwner);
 useEffect(()=>{onRoutingWorkEligible?.(Boolean(state?.problem&&!['UNDERSTAND','CLARIFY'].includes(state.phase)||initialAdoption&&state?.phase==='CLARIFY'&&!state.pending&&!state.error&&(['NEEDS_DATA','NEEDS_CLARIFICATION'].includes(state.draft?.resultKind??'')||state.draft?.resultKind==='DRAFT_READY'&&!state.draft.inputSource)));return()=>onRoutingWorkEligible?.(false)},[state?.problem,state?.phase,state?.pending,state?.error,state?.draft?.resultKind,state?.draft?.inputSource,initialAdoption,onRoutingWorkEligible]);
 useEffect(()=>{const ref=execution?.preparation.semantics.target?.problem;const matches=execution&&execution.digest===state?.execution&&ref?.resource_id===state?.problem?.business_problem_id&&ref?.revision_id===state?.problem?.revision_id&&ref?.digest===state?.problem?.digest;onExecutionContext?.(matches?execution:null);return()=>onExecutionContext?.(null)},[execution,state?.execution,state?.problem,onExecutionContext]);
 useEffect(()=>{onProgressVisible?.(state?.phase!=='DIRECT_DONE')},[state?.phase,onProgressVisible]);
 const recoverEffect=useEffectEvent(async(s:State)=>{let result:DraftAssistanceResult;try{result=await readConversationUnderstandingResult(conversation,s.userMessageId!,understandingKey(s))}catch(error){if(String(error).includes('CONVERSATION_REQUEST_NOT_DISPATCHED')){if(s.error){if(alive.current)setError(s.error);return false;}await save({...s,pending:undefined,error:undefined,log:[...s.log,'已核实原请求尚未进入调用，沿用同一提问和请求记录继续处理。']});return false}if(s.error?.includes('CONVERSATION_REQUEST_CONTENT_INVALID')&&String(error).includes('CONVERSATION_RESULT_NOT_FOUND')){await save({...s,pending:undefined,error:undefined,log:[...s.log,'已核实原提问未进入模型调用，修正会话信息后继续处理。']});return false}throw error}if(result.state==='SUCCEEDED'||settledUnderstandingFailure(result)){await applyUnderstanding(s,result);return false}if(['RUNNING','ACCEPTED','DISPATCHING','DISPATCH_PREPARED'].includes(result.state))return true;if(alive.current)setError('原调用状态：'+result.state+'。未重新调用模型，原请求保留。');return false});
 useEffect(()=>{if(state?.understandingProtocol!==3||state.pending!=='understanding'||!state.userMessageId||flight.current||state.error?.includes('CONTEXT_ADMISSION_CONVERSATION_BINDING_REQUIRED'))return;const recoveryKey=state.userMessageId+':'+understandingKey(state);if(recoveryAttempts.current.has(recoveryKey))return;recoveryAttempts.current.add(recoveryKey);let live=true,timer:ReturnType<typeof setTimeout>|undefined;const tick=async()=>{if(flight.current||!live)return;try{if(await recoverEffect(state)&&live)timer=setTimeout(tick,3000)}catch(e){if(live)setError(String(e))}};timer=setTimeout(tick,0);return()=>{live=false;clearTimeout(timer)}},[state?.pending,state?.userMessageId,state?.understandingProtocol,state]);
 if(state?.phase==='DIRECT_DONE')return routingEnabled?null:<ConversationPlacement target={composerTarget}><ConversationAnswer storageKey={conversationScope(session)+':'+conversation+':'+state.key+':'+state.messages.length} id="journey-reply" label="继续提问" button="发送" disabled={busy} onAnswer={text=>answer(text)}/></ConversationPlacement>;
 if(!state)return error?<p role="alert">{error}</p>:null;
 const adoptionDisplay=adoptionIssue&&adoptionIssue.invocationId===state.draft?.invocationId?adoptionIssue.feedback:undefined;
 const sourceDisplay=state.phase==='CLARIFY'&&sourceInputKey?sourceInputFeedback(sourceInput?.key===sourceInputKey?sourceInput.observation:undefined,sourceInput?.key===sourceInputKey?sourceInput.capability:undefined):undefined;
 const createScopeDenied=createPaused&&state.draft?.state==='SUCCEEDED'&&state.draft.resultKind==='DRAFT_READY'&&(error||state.error)?.replace(/^Error: /,'')==='UNDERSTANDING_ADOPTION_BUSINESS_SCOPE_DENIED';
 const criterionDenied=criterionPaused&&(error||state.error)?.replace(/^Error: /,'')==='OWNED_BUSINESS_RESULT_CHANGED';
 const criterionDisplay=criterionDenied?{title:'草案已保存，完成标准暂未接续',detail:'当前工作已建立，完成标准在平台校验时暂停。理解结果和输入均已保留，核对后继续当前工作，无需重新提问。'}:undefined;
 const createDisplay=createScopeDenied?{title:'草案已保存，后续处理暂未获准',detail:(sourceInputKey&&sourceInput?.key===sourceInputKey&&sourceInput.observation?.state==='BODY_CONTEXT'?'资料正文已读取，草案已保存。':'本次草案和所选资料已保留。')+'后续处理的访问校验尚未通过。无需重新提问，恢复后沿用这份草案继续。'}:undefined;
 const sourceReadPending=state.pending==='source-discovery';
 const processingError=Boolean(error||state.error);
 const sourceMismatch=['CONTEXT_ADMISSION_SOURCE_MISMATCH','PLANNING_OUTPUT_SOURCE_MISMATCH'].some(code=>(error||state.error)?.includes(code));
 const preparationReadFailure=(error||state.error)?.includes('QUESTION_INPUT_SERVICE_UNAVAILABLE')?'后台准备服务暂不可用，原问题和已确认资料已保留。服务恢复后可在本会话继续，无需重新登录或重新提问。':(error||state.error)?.includes('QUESTION_INPUT_SERVICE_ACCESS_DENIED')?'后台准备服务的授权校验未通过，原问题和资料已保留。请在服务配置恢复后继续。':undefined;
 const inputReadFailure=sourceReadPending?'资料读取暂未完成，原问题和已有处理记录已保存。重新读取不会再次调用模型。':preparationReadFailure??((error||state.error)?.includes('CONVERSATION_INPUT_ACCESS_DENIED')?'当前访问校验未通过，原提问已保留。请在访问恢复后继续，无需重新描述问题。':(error||state.error)?.includes('CONVERSATION_INPUT_SERVICE_UNAVAILABLE')?'当前读取服务暂不可用，原提问已保留。请稍后在本会话重新核对。':state.phase==='UNDERSTAND'&&(error||state.error)?.includes('CONVERSATION_SOURCE_STALE_OR_UNREADABLE')?'本次所选资料的准确版本或内容未通过核对，原提问已保留。请重新核对资料后继续。':undefined);
 const conversationAdmissionBlocked=state.phase==='UNDERSTAND'&&Boolean(state.error?.includes('CONTEXT_ADMISSION_CONVERSATION_BINDING_REQUIRED'));
 const unknownUnderstanding=state.understandingProtocol===3&&!state.execution&&Boolean((error||state.error)?.includes('OUTCOME_UNKNOWN'));
 const unresolvedRequest=Boolean(state.pending&&!busy&&!processingError&&!state.execution);
 const recoveryKey=state.planningRequestKey??state.key+':planning'+(state.cycle?':'+state.cycle:'')+(state.planningReply?':clarification:'+state.planningReply:'');
 const recoveryState=state.phase==='PLAN'&&state.pending==='planning'&&recoveryObservation?.key===conversation+':'+recoveryKey?recoveryObservation.state:undefined;
 const recoveryWaiting=['OBSERVED','AUTHORIZATION_PENDING'].includes(recoveryState??'');
 const recoveryObserved=recoveryWaiting||['AUTHORIZED','DISPATCHED','CONTINUING'].includes(recoveryState??'');
 const recordedUpdate=execution?.events?.filter(event=>Number.isFinite(Date.parse(event.created_at))).reduce<string|undefined>((latest,event)=>!latest||Date.parse(event.created_at)>Date.parse(latest)?event.created_at:latest,undefined);
 return <section className="conversation-journey" hidden={contentHidden} aria-busy={busy}>{state.execution&&returnTarget&&<ConversationPlacement target={returnTarget}><ConversationTeamContext conversation={conversation} preparation={state.execution}/></ConversationPlacement>}<ConversationMessageIdentity statusPanel assistant timestamp={recordedUpdate} timeLabel={separatePreparation?"原有工作更新":"执行更新"}/><div className="conversation-assistant-bubble">{separatePreparation&&<header className="conversation-original-work"><h2>原有工作</h2><p>{state.question}</p><p>以下进展和成果属于原有工作，不是刚保存能力准备的执行结果。</p></header>}<h2>{preparationPaused?'方案准备暂时暂停':criterionDisplay?criterionDisplay.title:createDisplay?createDisplay.title:adoptionDisplay?adoptionDisplay.title:sourceDisplay?sourceDisplay.title:sourceReadPending?'正在核对可用资料':conversationAdmissionBlocked?'本次提问尚未开始处理':recoveryState==='CONTINUING'?'正在继续原问题':recoveryWaiting?'恢复申请已提交，等待核对':recoveryState==='AUTHORIZED'?'已可继续原问题':recoveryState==='DISPATCHED'?'本次处理已提交':execution?.progress?.state==='SUCCEEDED'?(separatePreparation?'原有工作的分析结果':'分析结果'):understandingFailed?'理解未成功':sourceMismatch?'已暂停：资料不一致':processingError?(state.execution?'本次工作需要核查':state.phase==='UNDERSTAND'?'理解进展待核实':'本次处理需要核查'):unresolvedRequest?'正在核对原请求':state.execution&&!execution?.progress?(separatePreparation?'正在读取原有工作':'正在读取本次工作'):state.phase==='PLANNING_CLARIFY'?'有一点需要确认':state.phase==='CLARIFY'?(state.draft?.resultKind==='NEEDS_CLARIFICATION'?'有一点需要确认':state.source?'还需要补充信息':'请确认一下资料范围'):['FAILED','RECOVERY_REQUIRED','CANCELLED','CANCELED','UNKNOWN'].includes(execution?.progress?.state||'')?'本次办理状态':'正在办理你的问题'}</h2>{state.understandingProtocol!==3&&state.messages.length>1&&<details><summary>本次补充说明</summary>{state.messages.slice(1).map(m=><blockquote key={m.id}>{m.text}</blockquote>)}</details>}<ConversationPlacement target={railTarget}><ConversationProgress feedback={preparationPaused?{title:'方案准备暂时暂停',detail:recoveryState==='PREPARATION_NOT_STARTED'?'尚未建立规划请求，等待服务恢复。':'后台准备服务校验未通过，正在核对原记录。'}:criterionDisplay?{title:criterionDisplay.title,detail:'等待核对完成标准，原工作保留。'}:createDisplay??adoptionDisplay??sourceDisplay} recoveryState={recoveryState} separatePreparation={separatePreparation} phase={understandingFailed?'UNDERSTANDING_FAILED':state.phase} pending={state.pending} busy={busy} error={error||state.error} execution={execution} hasExecution={Boolean(state.execution)}/>{busy&&<ConversationElapsed key={state.pending??state.phase}/>}</ConversationPlacement>{busy&&['understanding','planning'].includes(state.pending??'')&&stream&&!error&&<section aria-label="模型流式输出" className="journey-progress"><strong>{state.pending==='planning'?'正在准备分析方案':'正在理解你的问题'}</strong><p role="status">请求正在处理中，已有内容持续呈现，完成后继续原任务。</p><details><summary>查看传输信息</summary><p>已接收 {stream.characters??0} 个输出字符。</p></details>{stream.preview&&<p style={{whiteSpace:'pre-wrap'}}>{stream.preview}</p>}<small>生成中的内容尚未核验，不作为执行指令或最终结论。</small></section>}<details><summary>查看已完成的办理记录</summary><ol>{state.log.map((text,i)=><li key={i}>{text}</li>)}</ol></details>
 {sourceReadPending&&<section aria-label="资料读取恢复"><p>原问题和已有处理记录已保存。可以重新读取可用资料，或补充你的要求。</p><button type="button" disabled={busy} onClick={()=>void reloadSources()}>重新读取可用资料</button>{composerEnabled&&<ConversationPlacement target={composerTarget}><ConversationAnswer storageKey={conversationScope(session)+':'+conversation+':'+state.key+':source-reply'} id="source-reply" label="补充要求" button="发送补充" disabled={busy} onAnswer={text=>answer(text)}/></ConversationPlacement>}</section>}
 {understandingFailed&&<section role="alert" aria-label="理解结果未通过校验"><p>系统返回的理解结果格式不符合要求，本次理解未成功。这不是缺少资料，也不需要你重复描述问题。</p><p>原问题和已选资料已保留，尚未启动业务任务。不会自动重新调用模型；你可以沿用原问题明确继续。</p><button type="button" disabled={busy} onClick={()=>void retryUnderstanding()}>沿用原问题重新理解</button><small>将先核实原调用已结束，再发起一次新的理解请求，仍受授权与预算约束。</small></section>}
 {state.phase==='PLAN'&&state.pending==='planning'&&!busy&&<ConversationPlanningRecovery key={state.planning?.invocation?.target?.invocation_id??state.key} conversation={conversation} principal={JSON.stringify(session.principal)} requestKey={state.planningRequestKey??state.key+':planning'+(state.cycle?':'+state.cycle:'')+(state.planningReply?':clarification:'+state.planningReply:'')} preparation={preparationPaused&&state.draft?{invocationId:state.draft.invocationId,isCurrent:matchesPlanningStart,onContinue:continuePlanningPreparation}:undefined} onStatus={value=>setRecoveryObservation({key:conversation+':'+recoveryKey,state:value})} onProgress={setStream} onResult={async (planning,requestKey)=>{const s=current.current?.state;if(!s)return;await verify();if(planning.result.technical_status==='SUCCEEDED'&&planning.result.kind==='NEEDS_CLARIFICATION'&&planning.result.questions?.length){await save({...s,planning,pending:undefined,error:undefined,phase:'PLANNING_CLARIFY',log:[...s.log,'原问题的新一轮方案准备已返回，需要补充一处信息。']});setError('');}else if(planning.result.technical_status==='SUCCEEDED'&&planning.result.proposal){await save({...s,planning,planningPredecessor:undefined,pending:undefined,error:undefined,phase:'CONFIRM',log:[...s.log,'原问题的新方案已返回，继续核对执行资源；上次未确认记录保留。']});setError('');}else{await save({...s,planning,planningRequestKey:requestKey,pending:'planning',error:'本次处理尚未返回可用方案，原记录已保留。'});}}}/>}
 {state.phase==='PLANNING_CLARIFY'&&<section aria-label="方案补充确认"><p>补充以下信息后，会沿用原问题和资料继续准备方案。</p><ul>{state.planning?.result.questions?.map((question,index)=><li key={index}>{question}</li>)}</ul>{!routingEnabled&&(!composerEnabled?<button type="button" onClick={onFocusComposer}>补充原有工作</button>:<ConversationPlacement target={composerTarget}><ConversationAnswer key={state.key+':planning:'+(state.planningReply??0)} storageKey={conversationScope(session)+':'+conversation+':'+state.key+':planning:'+(state.planningReply??0)} id="planning-reply" label="补充说明" button="发送补充" disabled={busy} onAnswer={answerPlanning} question={state.planning?.result.questions?.join('；')}/></ConversationPlacement>)}</section>}
 {sourceDisplay&&<p role="status">{sourceDisplay.detail}</p>}
 {state.phase==='CLARIFY'&&!understandingFailed&&<div>{sourceRefreshMessage&&<p role="status">{sourceRefreshMessage}</p>}{state.draft?.clarificationQuestion?.trim()?<p>{state.draft.clarificationQuestion}</p>:state.draft?.dataNeeds?.some(item=>item.trim())?<ul aria-label={sourceDisplay?"本次回复提到的资料需求":"需要补充的资料"}>{state.draft.dataNeeds.filter(item=>item.trim()).map((item,index)=><li key={index}>{item}</li>)}</ul>:<p>{state.source?'请补充你最关注的问题，例如关注的指标、时间或对象。':'请选择本次要分析的资料范围。'}</p>}{!state.source&&(state.understandingProtocol!==3||state.draft?.resultKind!=='NEEDS_CLARIFICATION')&&<><p>系统可用资料如下。测试资料不代表真实经营数据；确认后将自动分析并把结果返回这里。</p>{state.sources?.filter(source=>source.assessment?.state==='MISSING_TOOLS').map(source=><p key={source.source.digest}>“{source.label??source.name}”可读取，但缺少兼容的执行工具，暂不能自动分析。</p>)}{state.sources?.map(source=><button key={source.source.digest} disabled={busy||source.assessment?.state==='MISSING_TOOLS'} onClick={()=>void selectSource('使用系统现有的'+source.name+'作为资料。继续按原问题和已确认的要求处理。',source)}>使用{source.periods.join('、')||'现有'}{source.label??(source.sourceSchema.startsWith('sales')?'销售':'交付')}{source.label?'':'测试资料'}</button>)}</>}{!routingEnabled&&(!composerEnabled?<button type="button" onClick={onFocusComposer}>补充原有工作</button>:<ConversationPlacement target={composerTarget}><ConversationAnswer key={state.key+':'+state.messages.length} storageKey={conversationScope(session)+':'+conversation+':'+state.key+':'+state.messages.length} id="journey-reply" label="补充说明" button="发送补充" disabled={busy} onAnswer={text=>answer(text)} question={state.draft?.clarificationQuestion??undefined}/></ConversationPlacement>)}</div>}
 {state.source&&<details><summary>本次能做什么与完成标准</summary>{state.execution&&<p>以下为执行前核对的范围与完成标准；当前进展见“本次工作”。</p>}<p>资料与已登记能力：{state.source.assessment?.state==='MISSING_TOOLS'?'尚缺执行工具':'可进入方案核验，尚不代表已经执行或解决问题'}</p><ul>{state.source.completionCriteria?.map((c,i)=><li key={i}>{c}</li>)}</ul>{state.source.assessment?.limitations.map((c,i)=><p key={i}>{c}</p>)}</details>}
 {state.draft?.draft&&<details><summary>查看已理解的目标</summary><p>{state.draft.draft.description}</p></details>}
 {sourceMismatch&&composerEnabled&&!routingEnabled&&<ConversationPlacement target={composerTarget}><ConversationAnswer storageKey={conversationScope(session)+':'+conversation+':'+state.key+':'+state.messages.length} id="source-mismatch-reply" label="暂存补充" button="暂不能发送" disabled={busy} blockedReason="资料一致性校验未通过，当前只能暂存补充，不能发送或继续执行。内容保存在本页，不会自动提交。" onAnswer={async()=>false}/></ConversationPlacement>}
 {unknownUnderstanding&&composerEnabled&&!routingEnabled&&<ConversationPlacement target={composerTarget}><ConversationAnswer storageKey={conversationScope(session)+':'+conversation+':'+state.key+':'+state.messages.length} id="journey-reply" label="暂存补充" button="等待结果核实" disabled={busy} blockedReason="原请求结果尚未确认，暂不能提交或继续执行；你输入的内容会保留。" onAnswer={async()=>false}/></ConversationPlacement>}
 {recoveryObserved&&(error||state.error)&&<details><summary>上次处理详情与错误记录</summary><p>{error||state.error}</p><p>原请求结果尚待核实，历史记录保留，不会自动重发。</p></details>}
 {adoptionDisplay&&<div role="alert"><p>{adoptionDisplay.title}</p><p>{adoptionDisplay.detail}</p><details><summary>技术详情</summary><p>{adoptionDisplay.technical}</p></details></div>}
 {(createDisplay||criterionDisplay)&&<div role="alert"><p>{(criterionDisplay??createDisplay)!.detail}</p><details><summary>技术详情</summary><p>{error||state.error}</p></details></div>}
 {state.phase==='CREATE'&&state.pending==='create-problem'&&state.draft?.state==='SUCCEEDED'&&state.draft.resultKind==='DRAFT_READY'&&<section aria-label="原草案接续"><button type="button" disabled={busy} onClick={()=>void continueSavedCreate()}>核对并继续当前工作</button>{createReadNotice&&<p role="status">{createReadNotice}</p>}</section>}
 {criterionPaused&&<section aria-label="完成标准接续"><button type="button" disabled={busy} onClick={()=>void continueSavedCriterion()}>核对并继续当前工作</button>{createReadNotice&&<p role="status">{createReadNotice}</p>}</section>}
 {!criterionDisplay&&!createDisplay&&!adoptionDisplay&&!recoveryObserved&&(error||state.error)&&<div role="alert"><p>{conversationAdmissionBlocked?'当前会话尚未启用提问处理。原提问已保留，完成会话接入后再继续；不会自动重发。':inputReadFailure??(sourceMismatch?'方案使用的资料与本次已确认的资料不一致，已停止继续处理。原问题、资料和调用记录均已保留，无需重新描述问题。':unknownUnderstanding?'暂时无法确认这次处理结果，已保留请求与已有回答。':'本次请求尚未完成或结果待核实，已有内容已保留。')}</p>{criterionPaused||conversationAdmissionBlocked||inputReadFailure||unknownUnderstanding||sourceMismatch?<details><summary>技术详情</summary><p>{error||state.error}</p></details>:<p>{error||state.error}</p>}<p>{conversationAdmissionBlocked?'本次请求在会话接入检查时停止，不会自动重发。原记录保留，后续仍在本会话处理。':sourceReadPending?'当前只需核对可用资料；已有处理记录保留，不会重复调用模型。':inputReadFailure?'本轮在输入读取阶段停止，未派发模型请求；不会自动重发，原消息保留。':sourceMismatch?((error||state.error)?.includes('CONTEXT_ADMISSION_SOURCE_MISMATCH')?'本轮规划请求在资料核对时被拒绝，尚未调用模型或启动执行。':'模型已返回方案，但资料核对未通过，尚未进入执行。'):'不会自动重发可能已执行的请求。恢复后仍在本会话继续。'}</p></div>}
 {state.phase==='EXECUTE'&&state.pending==='execute'&&state.confirmation&&<section aria-label="原执行状态核对"><p>先读取本次工作的执行记录；已启动的工作直接续接，不重复提交。</p><button disabled={busy} onClick={()=>void recoverExecution()}>核对执行状态</button>{executionAbsent===JSON.stringify([state.key,state.confirmation.plan.plan_id,state.confirmation.plan.version,state.confirmation.digest])&&<><p role="status">已核实原方案尚无已提交的执行记录。配置修复后，可继续同一项工作。</p><button disabled={busy} onClick={()=>void recoverExecution(true)}>继续原方案执行</button></>}</section>}
 {(state.phase==='PLAN'&&state.pending==='planning'&&state.error?.includes('（MODEL_AUTHORIZATION_INVALID）'))&&<button disabled={busy} onClick={()=>{setError('');void save({...state,pending:undefined,error:undefined})}}>配置修复后继续分析</button>}
 {state.phase==='SELECT_RESOURCES'&&state.pending==='select-resources'&&[coverageFailure,'Error: 现有能力仍不能完成该方案，已保留资料与方案缺口。'].includes(state.error??'')&&<button disabled={busy} onClick={()=>void recheckSelection()}>能力补齐后继续分析</button>}
 {state.phase==='RESOURCES'&&state.pending==='resources'&&state.error?.startsWith('Error: 分析所需能力尚未全部就绪：')&&<button disabled={busy} onClick={()=>void recheckResources()}>重新核对可用能力</button>}
 {!recoveryObserved&&state.pending&&!busy&&!state.error&&<p role="status">上次请求尚未核实，已保留原记录，暂不重复执行。</p>}
 {state.execution&&<><NativeLiveProgress composerEnabled={composerEnabled} onFocusComposer={onFocusComposer} key={conversationScope(session)+':'+conversation+':'+state.execution} digest={state.execution} conversation={conversation} csrf={session.csrfToken} executionState={execution?.progress?.state} composerTarget={composerTarget} railTarget={railTarget} viewScope={conversationScope(session)}/>{execution&&<ConversationEvidenceRail key={conversationScope(session)+':'+conversation+':'+execution.digest} view={execution} conversation={conversation} viewKey={conversationScope(session)+':'+conversation+':'+execution.digest} target={railTarget}/>}{execution?.progress?.state==='SUCCEEDED'&&documentBusinessSummary(execution)?<p className="document-lead">{documentBusinessSummary(execution)}</p>:<p>执行状态：{execution?.progress?.state??'正在读取'} · {execution?`已生成${execution.artifacts.length}份产物`:'产物数量待读取'}</p>}<PreparedExecutionPanel contextKey={'journey:'+conversation} digest={state.execution} problemId={state.problem!.business_problem_id} csrfToken={session.csrfToken} blocked={false} readOnly={true} onBusy={()=>{}} supplementConversation={conversation}/></>}
 </div></section>;
}
