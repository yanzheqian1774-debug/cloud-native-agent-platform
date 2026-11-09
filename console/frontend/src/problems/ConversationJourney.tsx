import {useEffect,useEffectEvent,useRef,useState} from 'react';
import {beginDraftAssistance,createBusinessProblem,linkDraftAssistanceProblem,readBusinessProblem,readWorkbenchSession,writeCriterion,writeCriteriaSet,transitionBusinessProblem,type WorkbenchSession,type DraftAssistanceResult,type BusinessProblemRevision} from '../api/businessWorkspace';
import {conversationRequest,type PrivateConversation} from '../api/privateConversation';
import {planningRequest,type Invocation,type PlanningBody} from '../planning/planningRequests';
import {confirmPolicy,prepareResources,continueReadonlyWork,selectAutomaticResources,type ExactRef,type Confirmation} from '../planning/api';
import {preparedRequest,type ExecutionView} from '../api/preparedExecution';
import {understandingContent,appendUserMessage,type UserFactMessage} from './problemUnderstandingModel';
import {PreparedExecutionPanel} from './PreparedExecutionPanel';

type Source={source:ExactRef;name:string;periods:string[];sourceSchema:string;synthetic:boolean};
type State={key:string;phase:string;question:string;messages:UserFactMessage[];sources?:Source[];source?:Source;draft?:DraftAssistanceResult;problem?:BusinessProblemRevision;criterion?:string;planning?:Invocation;confirmation?:Confirmation;execution?:string;error?:string;pending?:string;log:string[]};
type Journal={version:number;state:State|null};
export function ConversationJourney({conversation,session,onActive}:{conversation:string;session:WorkbenchSession;onActive:(active:boolean)=>void}){
 const [journal,setJournal]=useState<Journal|null>(null),[busy,setBusy]=useState(false),[reply,setReply]=useState(''),[error,setError]=useState(''),[execution,setExecution]=useState<ExecutionView|null>(null);
 const current=useRef<Journal|null>(null),flight=useRef(false),alive=useRef(true);
 useEffect(()=>{alive.current=true;let live=true;conversationRequest<Journal>('/'+conversation+'/journey').then(j=>{if(live){current.current=j;setJournal(j);onActive(Boolean(j.state))}}).catch(e=>{if(live)setError(String(e))});return()=>{live=false;alive.current=false}},[conversation,onActive]);
 async function verify(){const actual=await readWorkbenchSession();if(JSON.stringify(actual.principal)!==JSON.stringify(session.principal))throw Error('登录身份已变化，请重新登录后继续。')}
 async function save(state:State){await verify();const j=await conversationRequest<Journal>('/'+conversation+'/journey',session.csrfToken,{expectedVersion:current.current!.version,state});current.current=j;if(alive.current)setJournal(j);return state}
 async function pending(s:State,name:string){return save({...s,pending:name,error:undefined})}
 async function run(){
  if(flight.current||!current.current?.state||current.current.state.pending)return;
  flight.current=true;setBusy(true);setError('');let s=current.current.state;
  try{while(alive.current){await verify();
   if(s.phase==='UNDERSTAND'){
    s=await pending(s,'understanding');const previous=s.draft;
    const content=understandingContent(s.messages,s.messages.length,previous?.draft??null,previous?.understanding??null,previous?.clarificationQuestion??null);
    const draft=await beginDraftAssistance(session.csrfToken,{idempotencyKey:s.key+':draft:'+s.messages.length,content,...(previous?{parentContextId:previous.contextId,parentTurnId:previous.turnId,expectedParentVersion:previous.turnVersion,predecessorInvocationId:previous.invocationId}:{})});
    if(draft.state!=='SUCCEEDED')throw Error('问题理解尚未完成：'+(draft.reasonCode??draft.state));
    const sources=s.sources??(await planningRequest<{items:Source[]}>('conversation-sources')).items;
    const next=draft.resultKind==='DRAFT_READY'&&s.source?'CREATE':'CLARIFY';
    s=await save({...s,pending:undefined,draft,sources,phase:next,log:[...s.log,next==='CLARIFY'?'问题理解已完成，请确认下方分析范围。':'已整理分析目标，正在核对资料与范围。']});
   }else if(s.phase==='CREATE'){
    if(!s.draft?.draft||!s.source)throw Error('需要先明确分析目标和资料范围。');
    s=await pending(s,'create-problem');
    const created=await createBusinessProblem(session.csrfToken,{...s.draft!.draft!,ownerId:session.principal.principalId,idempotencyKey:s.key+':problem',draftInvocationId:s.draft!.invocationId});
    s=await save({...s,pending:undefined,problem:created.revision,phase:'CRITERION',log:[...s.log,'分析目标已保存，正在准备核对标准。']});
   }else if(s.phase==='CRITERION'){
    s=await pending(s,'criterion');const p=s.problem!;
    await linkDraftAssistanceProblem(session.csrfToken,s.draft!.invocationId,{problemId:p.business_problem_id,problemRevisionId:p.revision_id,problemDigest:p.digest});
    const criterion=await writeCriterion(session.csrfToken,{problemId:p.business_problem_id,criterionType:'HUMAN_EVALUATED',measurement:{rubric:'依据所确认的合成测试资料，回答用户目标：'+s.question+'。展示按币种分别核算的汇总、异常和可复算依据；区分数据观察与原因推测，不声称真实经营改善。'},requiredEvidenceKinds:[],evaluatorType:'HUMAN',evaluatorVersion:'v1',applicability:{},idempotencyKey:s.key+':criterion'});
    s=await save({...s,pending:undefined,criterion:criterion.revision.revision_id,phase:'ACTIVATE'});
   }else if(s.phase==='ACTIVATE'){
    s=await pending(s,'activate');const p=s.problem!,id=p.business_problem_id;let detail=await readBusinessProblem(id);
    await writeCriteriaSet(session.csrfToken,id,{problemRevisionId:p.revision_id,orderedCriterionRevisionIds:[s.criterion!],expectedVersion:detail.problem.aggregate_version,idempotencyKey:s.key+':criteria-set'});
    detail=await readBusinessProblem(id);await transitionBusinessProblem(session.csrfToken,id,{toState:'ACTIVE',expectedVersion:detail.problem.aggregate_version,idempotencyKey:s.key+':activate'});
    const c=await conversationRequest<PrivateConversation>('/'+conversation);await conversationRequest('/'+conversation+'/links',session.csrfToken,{expectedVersion:c.conversation.version,idempotencyKey:s.key+':link',target:{problemId:id,revisionId:p.revision_id,problemDigest:p.digest}});
    s=await save({...s,pending:undefined,phase:'PLAN',log:[...s.log,'正在结合资料和可用能力制定分析方案。']});
   }else if(s.phase==='PLAN'){
    s=await pending(s,'planning');
    const routed=await planningRequest<{state:string;planningRequest:PlanningBody|null}>('question-activity-input',{question:s.question,problemId:s.problem!.business_problem_id,source:s.source!.source,idempotencyKey:s.key+':planning'});
    if(!routed.planningRequest)throw Error('暂不能根据所选资料开始分析：'+routed.state);
    await planningRequest('planning-v2/preflight',routed.planningRequest);
    const planning=await planningRequest<Invocation>('planning-v2/invocations',routed.planningRequest);
    if(planning.result.technical_status!=='SUCCEEDED'||!planning.result.proposal)throw Error('分析方案尚未就绪：'+(planning.result.questions?.join('；')||planning.result.reason||planning.result.kind||planning.result.technical_status));
    s=await save({...s,pending:undefined,planning,phase:'CONFIRM',log:[...s.log,'分析方案已生成，正在核对并准备执行资源。']});
   }else if(s.phase==='CONFIRM'){
    s=await pending(s,'confirm');const proposal=s.planning!.result.proposal!,digest=s.planning!.result.proposal_digest!;
    const {confirmation}=await confirmPolicy(proposal.proposal_id,proposal.revision,digest,proposal.semantics.target.problem,0,s.key+':confirm',session.csrfToken);
    s=await save({...s,pending:undefined,confirmation,phase:'SELECT_RESOURCES'});
   }else if(s.phase==='SELECT_RESOURCES'){
    const original=s.confirmation!;
    if(original.plan.semantics.requirements.filter(r=>r.kind==='EMPLOYEE').every(r=>r.selected)){
     s=await save({...s,phase:'RESOURCES'});
    }else{
     s=await pending(s,'select-resources');
     const selected=await selectAutomaticResources(original.plan.plan_id,original,s.key+':selection',session.csrfToken);
     s=await save({...s,pending:undefined,confirmation:selected.confirmation,phase:'RESOURCES'});
    }
   }else if(s.phase==='RESOURCES'){
    s=await pending(s,'resources');const plan=s.confirmation!.plan;
    const ready=await prepareResources(plan.plan_id,plan.version,s.key+':resources',session.csrfToken);
    if(ready.state!=='READY')throw Error('分析所需能力尚未全部就绪：'+ready.resources.filter(r=>r.reason).map(r=>r.reason).join('；'));
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
 useEffect(()=>{if(state&&!state.pending&&!['CLARIFY','RUNNING','DONE'].includes(state.phase))void runEffect();},[state,busy]); // Each owner command is preceded by a durable CAS claim.
 useEffect(()=>{if(!state?.execution)return;let live=true;const refresh=async()=>{try{await verifyEffect();const v=await preparedRequest<ExecutionView>(state.execution!);if(live)setExecution(v)}catch(e){if(live)setError(String(e))}};void refresh();const timer=setInterval(()=>void refresh(),3000);return()=>{live=false;clearInterval(timer)}},[state?.execution]);
 async function answer(text:string,source?:Source){if(flight.current||!state)return;flight.current=true;setBusy(true);try{await verify();const c=await conversationRequest<PrivateConversation>('/'+conversation);await conversationRequest('/'+conversation+'/messages',session.csrfToken,{expectedVersion:c.conversation.version,idempotencyKey:state.key+':answer:'+state.messages.length,content:text});await save({...state,source:source??state.source,phase:'UNDERSTAND',pending:undefined,error:undefined,messages:appendUserMessage(state.messages,text),log:[...state.log,'已收到补充，继续理解并核对分析范围。']});setReply('')}catch(e){setError(String(e))}finally{flight.current=false;setBusy(false)}}
 if(!state)return error?<p role="alert">{error}</p>:null;
 return <section className="conversation-journey" aria-busy={busy}><h2>{execution?.progress?.state==='SUCCEEDED'?'分析结果':state.phase==='CLARIFY'?'请确认一下分析范围':'正在办理你的问题'}</h2>{state.messages.slice(1).map(m=><blockquote key={m.id}>{m.text}</blockquote>)}<ol>{state.log.map((text,i)=><li key={i}>{text}</li>)}</ol>{busy&&<p role="status">正在处理，请稍候。进度会保存在本会话。</p>}
 {state.phase==='CLARIFY'&&<div><p>{state.draft?.clarificationQuestion??'请选择本次要分析的资料范围。'}</p>{!state.source&&<><p>系统可用资料如下。测试资料不代表真实经营数据；确认后将自动分析并把结果返回这里。</p>{state.sources?.map(source=><button key={source.source.digest} disabled={busy} onClick={()=>void answer('使用系统现有的'+source.name+'，时间范围为'+source.periods.join('、')+'。按资料的既有口径进行只读分析，展示汇总、变化贡献和异常明细，不修改原始数据。',source)}>使用{source.periods.join('、')||'现有'}{source.sourceSchema.startsWith('sales')?'销售':'交付'}测试资料</button>)}</>}<form onSubmit={e=>{e.preventDefault();void answer(reply)}}><label htmlFor="journey-reply">补充说明</label><textarea id="journey-reply" value={reply} onChange={e=>setReply(e.target.value)} maxLength={1800}/><button disabled={busy||!reply.trim()}>发送补充</button></form></div>}
 {state.draft?.draft&&<details><summary>查看已理解的目标</summary><p>{state.draft.draft.description}</p></details>}
 {(error||state.error)&&<div role="alert"><p>本次处理停在当前步骤，已有内容已保留。</p><p>{error||state.error}</p><p>不会自动重发可能已执行的请求。恢复后仍在本会话继续。</p></div>}
 {state.phase==='PLAN'&&state.pending==='planning'&&state.error?.includes('（MODEL_AUTHORIZATION_INVALID）')&&<button disabled={busy} onClick={()=>{setError('');void save({...state,pending:undefined,error:undefined})}}>配置修复后继续分析</button>}
 {state.pending&&!busy&&!state.error&&<p role="status">上次请求尚未核实，已保留原记录，暂不重复执行。</p>}
 {state.execution&&<><p>执行状态：{execution?.progress?.state??'正在读取'} · 已生成{execution?.artifacts.length??0}份产物</p><PreparedExecutionPanel contextKey={'journey:'+conversation} digest={state.execution} problemId={state.problem!.business_problem_id} csrfToken={session.csrfToken} blocked={true} onBusy={()=>{}} supplementConversation={conversation}/></>}
 </section>;
}
