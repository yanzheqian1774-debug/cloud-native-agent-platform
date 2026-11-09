import {useEffect,useEffectEvent,useRef,useState} from 'react';
import {beginDraftAssistance,createBusinessProblem,linkDraftAssistanceProblem,readBusinessProblem,readWorkbenchSession,writeCriterion,writeCriteriaSet,transitionBusinessProblem,type WorkbenchSession,type DraftAssistanceResult,type BusinessProblemRevision} from '../api/businessWorkspace';
import {conversationRequest,type PrivateConversation} from '../api/privateConversation';
import {planningRequest,type Invocation,type PlanningBody} from '../planning/planningRequests';
import {confirmPolicy,prepareResources,readResourcePreparation,continueReadonlyWork,selectAutomaticResources,readResourceCoverage,type ExactRef,type Confirmation} from '../planning/api';
import {preparedRequest,type ExecutionView} from '../api/preparedExecution';
import {understandingContent,appendUserMessage,type UserFactMessage} from './problemUnderstandingModel';
import {PreparedExecutionPanel} from './PreparedExecutionPanel';

type Source={source:ExactRef;name:string;periods:string[];sourceSchema:string;synthetic:boolean;label?:string;completionCriteria?:string[];assessment?:{state:string;missingOperations:string[];limitations:string[]}};
type State={resourceRetry?:number;cycle?:number;coverageFeedback?:string;expectedPlanVersion?:number;key:string;phase:string;question:string;messages:UserFactMessage[];sources?:Source[];source?:Source;draft?:DraftAssistanceResult;problem?:BusinessProblemRevision;criterion?:string;planning?:Invocation;confirmation?:Confirmation;execution?:string;error?:string;pending?:string;log:string[]};
type Journal={version:number;state:State|null};
const coverageFailure='Error: AUTOMATIC_SELECTION_COVERAGE_BLOCKED';
const canRepair=(s:State)=>s.phase==='SELECT_RESOURCES'&&s.pending==='select-resources'&&s.error===coverageFailure&&(s.cycle??0)<2;

export function ConversationJourney({conversation,session,onActive}:{conversation:string;session:WorkbenchSession;onActive:(active:boolean)=>void}){
 const [journal,setJournal]=useState<Journal|null>(null),[busy,setBusy]=useState(false),[reply,setReply]=useState(''),[error,setError]=useState(''),[execution,setExecution]=useState<ExecutionView|null>(null);
 const current=useRef<Journal|null>(null),flight=useRef(false),alive=useRef(true);
 useEffect(()=>{alive.current=true;let live=true;conversationRequest<Journal>('/'+conversation+'/journey').then(j=>{if(live){current.current=j;setJournal(j);onActive(Boolean(j.state))}}).catch(e=>{if(live)setError(String(e))});return()=>{live=false;alive.current=false}},[conversation,onActive]);
 async function verify(){const actual=await readWorkbenchSession();if(JSON.stringify(actual.principal)!==JSON.stringify(session.principal))throw Error('登录身份已变化，请重新登录后继续。')}
 async function save(state:State){await verify();const j=await conversationRequest<Journal>('/'+conversation+'/journey',session.csrfToken,{expectedVersion:current.current!.version,state});current.current=j;if(alive.current)setJournal(j);return state}
 async function pending(s:State,name:string){return save({...s,pending:name,error:undefined})}
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
 async function run(){
  if(flight.current||!current.current?.state||(current.current.state.pending&&!canRepair(current.current.state)))return;
  flight.current=true;setBusy(true);setError('');let s=current.current.state;
  try{while(alive.current){await verify();
   if(canRepair(s)){s=await repairCoverage(s);continue;}
   if(s.phase==='UNDERSTAND'){
    s=await pending(s,'understanding');const previous=s.draft?.state==='SUCCEEDED'?s.draft:undefined;
    const content=understandingContent(s.messages,s.messages.length,previous?.draft??null,previous?.understanding??null,previous?.clarificationQuestion??null);
    const draft=await beginDraftAssistance(session.csrfToken,{idempotencyKey:s.key+':draft:'+s.messages.length,content,...(previous?{parentContextId:previous.contextId,parentTurnId:previous.turnId,expectedParentVersion:previous.turnVersion,predecessorInvocationId:previous.invocationId}:{})});
    const recoverable=draft.state==='FAILED'&&draft.reasonCode==='OUTPUT_SCHEMA_INVALID'&&draft.settlementStatus==='ESTIMATE_SETTLED'&&draft.localWorkerState==='REAPED';
    if(draft.state!=='SUCCEEDED'&&!recoverable)throw Error('问题理解尚未完成：'+(draft.reasonCode??draft.state));
    const sources=s.sources??(await planningRequest<{items:Source[]}>('conversation-sources')).items;
    const next=draft.resultKind==='DRAFT_READY'&&s.source?'CREATE':'CLARIFY';
    s=await save({...s,pending:undefined,draft,sources,phase:next,log:[...s.log,recoverable?'目标整理暂未完成，原问题已保留。请先确认资料范围或补充关注点。':next==='CLARIFY'?'问题理解已完成，请确认下方分析范围。':'已整理分析目标，正在核对资料与范围。']});
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
    const planning=await planningRequest<Invocation>('planning-v2/invocations',routed.planningRequest);
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
     try{const selected=await selectAutomaticResources(original.plan.plan_id,original,s.key+':selection:'+(s.cycle??0),session.csrfToken);
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
 useEffect(()=>{if(state&&(!state.pending||canRepair(state))&&!['CLARIFY','RUNNING','DONE'].includes(state.phase))void runEffect();},[state,busy]); // Each owner command is preceded by a durable CAS claim.
 useEffect(()=>{if(!state?.execution)return;let live=true;const refresh=async()=>{try{await verifyEffect();const v=await preparedRequest<ExecutionView>(state.execution!);if(live)setExecution(v)}catch(e){if(live)setError(String(e))}};void refresh();const timer=setInterval(()=>void refresh(),3000);return()=>{live=false;clearInterval(timer)}},[state?.execution]);
 async function answer(text:string,source?:Source){if(flight.current||!state)return;flight.current=true;setBusy(true);try{await verify();const c=await conversationRequest<PrivateConversation>('/'+conversation);await conversationRequest('/'+conversation+'/messages',session.csrfToken,{expectedVersion:c.conversation.version,idempotencyKey:state.key+':answer:'+state.messages.length,content:text});await save({...state,source:source??state.source,phase:'UNDERSTAND',pending:undefined,error:undefined,messages:appendUserMessage(state.messages,text),log:[...state.log,'已收到补充，继续理解并核对分析范围。']});setReply('')}catch(e){setError(String(e))}finally{flight.current=false;setBusy(false)}}
 if(!state)return error?<p role="alert">{error}</p>:null;
 return <section className="conversation-journey" aria-busy={busy}><h2>{execution?.progress?.state==='SUCCEEDED'?'分析结果':state.phase==='CLARIFY'?'请确认一下分析范围':'正在办理你的问题'}</h2>{state.messages.slice(1).map(m=><blockquote key={m.id}>{m.text}</blockquote>)}<ol>{state.log.map((text,i)=><li key={i}>{text}</li>)}</ol>{busy&&<p role="status">正在处理，请稍候。进度会保存在本会话。</p>}
 {state.phase==='CLARIFY'&&<div><p>{state.draft?.clarificationQuestion??(state.source?'请补充你最关注的问题，例如关注的指标、时间或对象。':'请选择本次要分析的资料范围。')}</p>{!state.source&&<><p>系统可用资料如下。测试资料不代表真实经营数据；确认后将自动分析并把结果返回这里。</p>{state.sources?.filter(source=>source.assessment?.state==='MISSING_TOOLS').map(source=><p key={source.source.digest}>“{source.label??source.name}”可读取，但缺少兼容的执行工具，暂不能自动分析。</p>)}{state.sources?.map(source=><button key={source.source.digest} disabled={busy||source.assessment?.state==='MISSING_TOOLS'} onClick={()=>void answer('使用系统现有的'+source.name+'，时间范围为'+source.periods.join('、')+'。按资料的既有口径进行只读分析，展示汇总、变化贡献和异常明细，不修改原始数据。',source)}>使用{source.periods.join('、')||'现有'}{source.label??(source.sourceSchema.startsWith('sales')?'销售':'交付')}{source.label?'':'测试资料'}</button>)}</>}<form onSubmit={e=>{e.preventDefault();void answer(reply)}}><label htmlFor="journey-reply">补充说明</label><textarea id="journey-reply" value={reply} onChange={e=>setReply(e.target.value)} maxLength={1800}/><button disabled={busy||!reply.trim()}>发送补充</button></form></div>}
 {state.source&&<details open><summary>本次能做什么与完成标准</summary><p>资料与已登记能力：{state.source.assessment?.state==='MISSING_TOOLS'?'尚缺执行工具':'可进入方案核验，尚不代表已经执行或解决问题'}</p><ul>{state.source.completionCriteria?.map((c,i)=><li key={i}>{c}</li>)}</ul>{state.source.assessment?.limitations.map((c,i)=><p key={i}>{c}</p>)}</details>}
 {state.draft?.draft&&<details><summary>查看已理解的目标</summary><p>{state.draft.draft.description}</p></details>}
 {(error||state.error)&&<div role="alert"><p>本次处理停在当前步骤，已有内容已保留。</p><p>{error||state.error}</p><p>不会自动重发可能已执行的请求。恢复后仍在本会话继续。</p></div>}
 {((state.phase==='PLAN'&&state.pending==='planning'&&state.error?.includes('（MODEL_AUTHORIZATION_INVALID）'))||(state.phase==='EXECUTE'&&state.pending==='execute'&&['Error: READONLY_RESOURCE_PREPARATION_REQUIRED','Error: READONLY_CONTINUATION_VALIDATION_FAILED'].includes(state.error??'')))&&<button disabled={busy} onClick={()=>{setError('');void save({...state,pending:undefined,error:undefined})}}>配置修复后继续分析</button>}
 {state.phase==='RESOURCES'&&state.pending==='resources'&&state.error?.startsWith('Error: 分析所需能力尚未全部就绪：')&&<button disabled={busy} onClick={()=>void recheckResources()}>重新核对可用能力</button>}
 {state.pending&&!busy&&!state.error&&<p role="status">上次请求尚未核实，已保留原记录，暂不重复执行。</p>}
 {state.execution&&<><p>执行状态：{execution?.progress?.state??'正在读取'} · 已生成{execution?.artifacts.length??0}份产物</p><PreparedExecutionPanel contextKey={'journey:'+conversation} digest={state.execution} problemId={state.problem!.business_problem_id} csrfToken={session.csrfToken} blocked={false} readOnly={true} onBusy={()=>{}} supplementConversation={conversation}/></>}
 </section>;
}
