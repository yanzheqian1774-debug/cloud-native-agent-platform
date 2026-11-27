import {adoptIndependentResult,readIndependentAdoption,type IndependentAdoptionCommand,type IndependentAdoptionReceipt} from '../api/conversationGoalAdoption';
import {readConversationJournal,type GoalReference} from '../api/conversationGoals';
import {readFixedFocus,recordFixedFocus,type FixedCycleFocus,type FixedFocusCommand} from '../api/conversationFixedFocus';
import {routingReceiptNotice} from './conversationRoutingReceipt';
import {useCallback,useEffect,useEffectEvent,useMemo,useRef,useState} from 'react';
import {beginDraftAssistance,readConversationUnderstandingResult,readWorkbenchSession,WorkbenchRequestError,type DraftAssistanceResult,type WorkbenchSession} from '../api/businessWorkspace';
import {conversationRequest,readConversationHead,type PrivateConversation} from '../api/privateConversation';
import {conversationUnderstandingContent,type UserFactMessage} from './problemUnderstandingModel';
import {conversationScope} from './conversationViewState';
import {notifyConversationReply,notifyConversationSend} from './useConversationScroll';
import type {RoutedOwner,ConversationRoutingValue,RoutedOwnerTarget} from './ConversationRoutingContext';

type Phase='MESSAGE_PENDING'|'MODEL_PENDING'|'READY_TO_APPLY'|'APPLYING'|'DONE'|'REVIEW';
type Saved={independentResult?:{invocationId:string};goalAdoption?:IndependentAdoptionCommand;adoptedGoal?:GoalReference;naturalNeutral?:boolean;focusContentComplete?:boolean;fixedFocus?:FixedFocusCommand;focusLinkId?:string;messageSent?:boolean;key:string;messageKey:string;messageId?:string;text:string;phase:Phase;thread:UserFactMessage[];previousQuestion?:string;relation?:string;ownerTarget?:RoutedOwnerTarget;persistentRecovery?:boolean;observedOwner?:RoutedOwnerTarget;lastResult?:{state:string;reasonCode:string|null};unacceptedPreview?:string;failedRetryOf?:string;failureInvocationId?:string;routeRejected?:boolean};
type FailedItem={invocationId:string;messageId:string;originalText:string;state:string;reasonCode:string;target:RoutedOwnerTarget;continuationEligible:boolean;successorRequestKey:string;successor:DraftAssistanceResult|null};
type ExactRoute={relation:string;originalText:string;messageId:string;target:RoutedOwnerTarget|null};
function restored(key:string):Saved|null{try{const raw=sessionStorage.getItem(key);if(!raw||raw.length>64000)return null;const value=JSON.parse(raw);return typeof value?.key==='string'&&typeof value.messageKey==='string'&&typeof value.text==='string'&&Array.isArray(value.thread)&&['MESSAGE_PENDING','MODEL_PENDING','READY_TO_APPLY','APPLYING','DONE','REVIEW'].includes(value.phase)?value:null}catch{return null}}
function notDispatched(error:unknown){return error instanceof WorkbenchRequestError&&error.status===404&&error.reasonCode==='CONVERSATION_REQUEST_NOT_DISPATCHED'}
function failureNotice(error:unknown){if(notDispatched(error))return '问题已保存，但尚未开始处理。可在此继续处理这条问题，原任务不会重跑。';if(error instanceof WorkbenchRequestError&&error.reasonCode==='CONVERSATION_ROUTE_STALE')return '原工作已变化，这条回答未提交。请核对当前问题，输入已保留。';if(error instanceof WorkbenchRequestError&&error.reasonCode==='AUTHORIZATION_NOT_FOUND')return '暂时无法读取当前工作。问题和原任务均已保留，恢复读取后可在此继续。';return '暂未确认这条回复的处理结果。原问题已保留，请核查状态；不会自动重复提交。'}
function terminalNotice(state:string,reason:string|null){return state==='FAILED'?(reason==='OUTPUT_SCHEMA_INVALID'?'本次补充的回复格式校验未通过，生成文字未被采纳。原问题、输入与原任务均保留，不会自动重试。':'本次补充处理失败，生成文字未被采纳。原问题、输入与原任务均保留，不会自动重试。'):state==='CANCELLED'?'本次补充处理已取消，生成文字未被采纳。原问题和输入保留。':'本次补充未被接受，原问题和输入保留。'}
function sameTarget(expected:RoutedOwnerTarget,actual:RoutedOwnerTarget){
 if(expected.kind!==actual.kind||expected.invocationId!==actual.invocationId)return false;
 const fields: (keyof RoutedOwnerTarget)[]=expected.kind==='NATIVE'?['executionDigest','questionKey','questionDigest']:expected.kind==='UNDERSTANDING'?['journalVersion','journeyKey','contextId','turnId','turnVersion','aggregateVersion']:['journalVersion','journeyKey'];
 return fields.every(key=>expected[key]!==undefined&&expected[key]===actual[key])&&(expected.kind==='NATIVE'||expected.problemId===actual.problemId);
}
export function useConversationRouting({enabled,conversation,session,onMessagesChanged,onGoalRecorded,independentAdoptionReady=false,goal,naturalRouting=false,fixedMode=false,fixedFocus}:{onGoalRecorded?:(goal:GoalReference,messageId:string)=>Promise<void>;independentAdoptionReady?:boolean;naturalRouting?:boolean;goal?:GoalReference|null;fixedMode?:boolean;fixedFocus?:FixedCycleFocus|null;enabled:boolean;conversation:string|null;session:WorkbenchSession;onMessagesChanged:()=>Promise<void>}){
 const scope=conversationScope(session),storage='conversation-routing.v1:'+(fixedMode?JSON.stringify([session.principal.tenantId,session.principal.securityDomain,session.principal.principalId]):scope)+':'+conversation+(goal?':goal:'+goal.goalId+':'+goal.goalDigest:'');
 const [saved,setSaved]=useState<Saved|null>(()=>restored(storage)),[busy,setBusy]=useState(false),[notice,setNotice]=useState(()=>{const r=restored(storage)?.lastResult;return r?terminalNotice(r.state,r.reasonCode):''}),[preview,setPreview]=useState(()=>restored(storage)?.unacceptedPreview??''),[failedCandidate,setFailedCandidate]=useState<FailedItem|null>(null),[modelState,setModelState]=useState(saved?.lastResult?.state??'UNKNOWN'),[canResume,setCanResume]=useState(false),[ownerEpoch,setOwnerEpoch]=useState(0);
 const currentFocus=useRef({fixedMode,fixedFocus,naturalRouting});currentFocus.current={fixedMode,fixedFocus,naturalRouting};
 const liveStorage=useRef(storage),invalidated=useRef(false);liveStorage.current=storage;
 useEffect(()=>{invalidated.current=false;const invalidate=()=>{invalidated.current=true};window.addEventListener('workbench-session-expired',invalidate);return()=>window.removeEventListener('workbench-session-expired',invalidate)},[scope]);
 const previewRef=useRef(preview);
 const current=useRef(saved),flight=useRef(false),alive=useRef(true),owners=useRef(new Map<symbol,RoutedOwner>()),refresh=useRef(onMessagesChanged);useEffect(()=>{refresh.current=onMessagesChanged},[onMessagesChanged]);
 const persist=useCallback((value:Saved)=>{current.current=value;try{sessionStorage.setItem(storage,JSON.stringify(value))}catch{/* The server still owns the saved request. */}if(alive.current)setSaved(value)},[storage]);
 useEffect(()=>{let live=true;void Promise.resolve().then(()=>{if(!live||liveStorage.current!==storage)return;const value=restored(storage);current.current=value;setSaved(value);setCanResume(false);setPreview(value?.unacceptedPreview??'');});return()=>{live=false}},[storage]);
 const registerOwner=useCallback((owner:RoutedOwner)=>{const key=Symbol();owners.current.set(key,owner);setOwnerEpoch(n=>n+1);return()=>{owners.current.delete(key);setOwnerEpoch(n=>n+1)}},[]);
 const sendHandler=useRef<((text:string)=>Promise<boolean>)|null>(null);
 const context=useMemo<ConversationRoutingValue>(()=>({enabled,failure:saved?.lastResult&&saved.observedOwner?{target:saved.observedOwner,...saved.lastResult}:undefined,registerOwner,send:text=>sendHandler.current?sendHandler.current(text):Promise.resolve(false)}),[enabled,registerOwner,saved]);
 async function verify(){if(goal&&fixedMode)throw Error('CONVERSATION_GOAL_FOCUS_CONFLICT');const actual=await readWorkbenchSession();if(invalidated.current||!alive.current||liveStorage.current!==storage||conversationScope(actual)!==scope||actual.csrfToken!==session.csrfToken)throw Error('登录或会话已变化，原请求保留。')}
 // A durable answer is only a candidate: every exact owner GET must agree.
 const discoverPersisted=useEffectEvent(async(isLive:()=>boolean)=>{
  const before=current.current;
  if(fixedMode||!conversation||flight.current||before&&!['DONE','REVIEW'].includes(before.phase)||![...owners.current.values()].some(o=>o.target.kind==='UNDERSTANDING'))return;
  try{
   await verify();
   const record=await conversationRequest<PrivateConversation>('/'+encodeURIComponent(conversation));
   if(record.conversation.conversation_id!==conversation)return;
   const candidates:Saved[]=[];
   for(const message of record.messages){
    const f=message.facts;
    if(!f?.assistantResponse||f.invokedBy!==session.principal.principalId||f.state!=='SUCCEEDED'||f.source?.kind!=='DRAFT'||f.response?.conversationRoute?.relation!=='CURRENT_QUESTION'||!f.requestKey||!f.userMessageId)continue;
    const users=record.messages.filter(m=>m.message_id===f.userMessageId&&m.author_id===session.principal.principalId&&!m.facts?.assistantResponse);
    if(users.length!==1||!users[0].request_key)continue;
    const user=users[0],path='/'+encodeURIComponent(conversation)+'/understanding-results/'+encodeURIComponent(user.message_id),query='?'+new URLSearchParams({requestKey:f.requestKey});
    const result=await readConversationUnderstandingResult(conversation,user.message_id,f.requestKey);
    if(result.state!=='SUCCEEDED'||result.invocationId!==f.source.invocationId||result.conversationDelivery?.state!=='SAVED'||result.conversationRoute?.relation!=='CURRENT_QUESTION'||!['DRAFT_READY','NEEDS_DATA','NEEDS_CLARIFICATION'].includes(result.resultKind??''))continue;
    type Adoption={adoption:{target:{original_invocation_id:string;journal_version:number;journey_key:string;message_id:string};actualResult:{invocationId:string}};understanding:DraftAssistanceResult;modelDispatched:false};
    let adoption:Adoption|null=null;
    try{adoption=await conversationRequest<Adoption>(path+'/adoption'+query)}catch(e){if(!(e instanceof WorkbenchRequestError&&e.status===404&&e.reasonCode==='UNDERSTANDING_ADOPTION_NOT_FOUND'))throw e}
    if(adoption&&[...owners.current.values()].some(o=>o.target.kind==='UNDERSTANDING'&&o.target.invocationId===adoption.adoption.actualResult.invocationId))continue;
    let route:ExactRoute;
    try{route=await conversationRequest<ExactRoute>(path+'/route'+query)}catch(e){if(e instanceof WorkbenchRequestError&&['CONVERSATION_ROUTE_STALE','CONVERSATION_ROUTING_CONTEXT_CHANGED'].includes(e.reasonCode))continue;throw e}
    const target=route.target;
    if(route.relation!=='CURRENT_QUESTION'||route.messageId!==user.message_id||route.originalText!==user.content||target?.kind!=='UNDERSTANDING'||[...owners.current.values()].filter(o=>sameTarget(o.target,target)).length!==1)continue;
    if(adoption){const t=adoption.adoption.target;if(adoption.modelDispatched!==false||adoption.adoption.actualResult.invocationId!==result.invocationId||adoption.understanding.invocationId!==result.invocationId||t.original_invocation_id!==target.invocationId||t.journal_version!==target.journalVersion||t.journey_key!==target.journeyKey||t.message_id!==user.message_id)continue}
    candidates.push({key:f.requestKey,messageKey:user.request_key!,messageId:user.message_id,text:user.content,thread:[],phase:'READY_TO_APPLY',relation:'CURRENT_QUESTION',ownerTarget:target,persistentRecovery:true});
   }
   await verify();
   if(!isLive()||flight.current||current.current!==before)return;
   if(candidates.length===1&&[...owners.current.values()].filter(o=>sameTarget(o.target,candidates[0].ownerTarget!)).length===1){persist(candidates[0]);setNotice('已找到本问题保存的回答。核对并继续后，将接回原会话，不会重新调用模型。')}
   else if(candidates.length>1)setNotice('发现多条已保存回答，尚不能唯一对应。原记录已保留，未自动提交。');
  }catch{if(isLive()&&current.current===before)setNotice('暂时无法核对已保存回答。原记录已保留，未重新提交。')}
 });
 useEffect(()=>{if(!enabled)return;let live=true;const timer=setTimeout(()=>void discoverPersisted(()=>live),0);return()=>{live=false;clearTimeout(timer)}},[enabled,conversation,ownerEpoch]);
 async function accept(result:DraftAssistanceResult,request:Saved,apply:boolean){
  if(!alive.current)return false;
  setModelState(result.state);
  if(result.state!=='SUCCEEDED'){
   if(['FAILED','CANCELLED','REJECTED'].includes(result.state)){const lastResult={state:result.state,reasonCode:result.reasonCode??null};persist({...request,phase:'REVIEW',failureInvocationId:result.invocationId,lastResult,unacceptedPreview:previewRef.current});setNotice(terminalNotice(lastResult.state,lastResult.reasonCode));}
   else {persist({...request,unacceptedPreview:previewRef.current});setNotice(['RUNNING','ACCEPTED','DISPATCHING','DISPATCH_PREPARED'].includes(result.state)?'这条补充仍在处理，正在保留原请求；不会重复提交。':'这条补充的处理结果尚未核实，生成文字未被采纳。原请求保留，不会自动重复提交。');}
   return false;
  }
  if(result.conversationDelivery?.state!=='SAVED'||!result.conversationRoute)throw Error('本次回复尚未确认保存，不会提交给原任务。');
  setPreview('');const relation=result.conversationRoute.relation;
  await refresh.current();
  if((fixedMode||request.fixedFocus)&&relation==='CURRENT_QUESTION')throw Error('固定工作结果追问不能代替执行题回答。');
  if(relation==='CURRENT_QUESTION'&&['CURRENT_QUESTION_ANSWER','DRAFT_READY','NEEDS_DATA','NEEDS_CLARIFICATION'].includes(result.resultKind??'')){
   const ready={...request,relation,phase:'READY_TO_APPLY' as const};persist(ready);
   if(apply)return applyOwner(ready);
   setNotice('这条回复已保存。继续前将重新核对原任务的同一个问题。');return false;
  }
  if((['INDEPENDENT','CURRENT_WORK'].includes(relation)&&result.resultKind==='DIRECT_ANSWER')||(['AMBIGUOUS','CURRENT_WORK'].includes(relation)&&result.resultKind==='NEEDS_CLARIFICATION')||(relation==='INDEPENDENT'&&result.conversationRoute.intent==='ANSWER'&&['NEEDS_DATA','NEEDS_CLARIFICATION'].includes(result.resultKind??''))){
   persist({...request,relation,phase:'DONE',previousQuestion:result.clarificationQuestion??undefined});if(apply&&conversation&&result.conversationDelivery.messageId)notifyConversationReply(conversation,result.conversationDelivery.messageId);setPreview('');setNotice((result.resultKind==='DIRECT_ANSWER'?'回复已返回本会话，原任务保持不变。':'请回答会话中的必要确认，原任务保持不变。')+(request.focusContentComplete===false?'依据所选周期的结果节选回答，未包含全部正文。':''));return true;
  }
  if(fixedMode&&relation==='INDEPENDENT'&&result.conversationRoute?.intent==='TASK'&&['DRAFT_READY','NEEDS_DATA','NEEDS_CLARIFICATION'].includes(result.resultKind??'')){
   const held={...request,relation,phase:'REVIEW' as const,independentResult:{invocationId:result.invocationId}};persist(held);
   if(apply&&independentAdoptionReady)return prepareIndependent(held);
   setNotice('新的问题已理解，原固定工作保留。可沿用这次结果继续，不会再次调用理解。');return false;
  }
  persist({...request,phase:'REVIEW'});setNotice('这条补充尚不能安全关联到原工作，原任务保持不变。');return false;
 }
 async function finishIndependent(request:Saved,receipt:IndependentAdoptionReceipt){
  await verify();if(!request.independentResult||receipt.invocationId!==request.independentResult.invocationId)throw Error('CONVERSATION_GOAL_RESULT_MISMATCH');
  const adopted={goalId:receipt.goalId,goalDigest:receipt.goalDigest};persist({...request,phase:'DONE',adoptedGoal:adopted});
  setNotice('已沿用这次理解，另作一项工作处理，原固定工作继续保留。');
  await refresh.current();await verify();await onGoalRecorded?.(adopted,request.messageId!);return true;
 }
 async function prepareIndependent(request:Saved){
  if(!conversation||!request.messageId||!request.independentResult||!independentAdoptionReady||request.goalAdoption)return false;
  await verify();const head=await readConversationHead(conversation);await verify();
  const command={conversationId:conversation,commandId:request.key+':independent-goal',messageId:request.messageId,requestKey:request.key,expectedConversationVersion:head.conversation.version};
  const pending={...request,phase:'APPLYING' as const,goalAdoption:command};
  const serialized=JSON.stringify(pending);sessionStorage.setItem(storage,serialized);if(sessionStorage.getItem(storage)!==serialized)throw Error('CONVERSATION_GOAL_INTENT_NOT_SAVED');persist(pending);
  try{return await finishIndependent(pending,await adoptIndependentResult(command,session.csrfToken))}
  catch{if(alive.current)setNotice('理解结果已保存，独立工作的接收状态尚待核实；不会重发或再次理解。');return false}
 }
 async function continueIndependent(){const request=current.current;if(!request||flight.current)return;flight.current=true;setBusy(true);try{await prepareIndependent(request)}finally{flight.current=false;if(alive.current)setBusy(false)}}
 async function applyOwner(request:Saved){
  if(fixedMode||!conversation||!request.messageId||request.fixedFocus)return false;
  await verify();
  let route:ExactRoute;
  try{route=await conversationRequest<ExactRoute>('/'+encodeURIComponent(conversation)+'/understanding-results/'+encodeURIComponent(request.messageId)+'/route?'+new URLSearchParams({requestKey:request.key}));}
  catch(e){if(e instanceof WorkbenchRequestError&&[400,403,404,409,410,422].includes(e.status))persist({...request,phase:request.ownerTarget?.kind==='UNDERSTANDING'?'APPLYING':'REVIEW',routeRejected:true});throw e;}
  await verify();
  if(route.relation!=='CURRENT_QUESTION'||route.messageId!==request.messageId||route.originalText!==request.text||!route.target)throw Error('原问题对应关系已变化，未提交或改投其他任务。');
  const matches=[...owners.current.values()].filter(owner=>sameTarget(owner.target,route.target!));
  if(matches.length!==1)throw Error('原问题当前不可续接，已保留回复，不会提交给其他问题。');
  persist({...request,phase:'APPLYING',ownerTarget:route.target});
  const receipt=await matches[0].onAnswer(route.originalText,route.messageId,{requestKey:request.key});
  if(typeof receipt==='object'&&receipt.state==='REJECTED'){persist({...request,phase:'REVIEW'});setNotice(receipt.notice??'原问题未接受这条回答，输入已保留，请核对后修改；不会自动重发。');return false}
  if(receipt!==true&&!(typeof receipt==='object'&&receipt.state==='ACCEPTED')){setNotice(typeof receipt==='object'&&receipt.notice?receipt.notice:'原回答的接收状态尚待核实，请查看原工作进展；不会自动重发。');return false}
  persist({...request,phase:'DONE',ownerTarget:route.target});setNotice(routingReceiptNotice(request.text,route.target));await refresh.current();return true;
 }
 async function readSaved(){
  const request=current.current;if(!conversation||!request)return false;if(flight.current)return true;if(fixedMode&&!request.fixedFocus&&!(naturalRouting&&request.naturalNeutral)){setNotice('原补充记录保留，固定工作模式不续接原手动处理。');return false;}
  flight.current=true;setBusy(true);setPreview('');setCanResume(false);
  try{
   await verify();
   if(request.goalAdoption){const receipt=await readIndependentAdoption(request.goalAdoption);await verify();if(receipt.state==='RECORDED'){await finishIndependent(request,receipt);return false}setNotice('尚未读到独立工作的接收回执，原理解结果保留；不会重发或重新理解。');return false;}
   if(request.fixedFocus&&!request.messageSent&&!request.messageId){const observed=await readFixedFocus(request.fixedFocus);await verify();if(observed.state!=='RECORDED')throw Error('原结果焦点保存状态尚未核实，不会重复提交。');persist({...request,focusLinkId:observed.focusLinkId,focusContentComplete:observed.contentComplete});setCanResume(true);setNotice('已核对原结果焦点；问题尚未发送，可明确继续同一条问题。');return false;}
   if(!request.messageId){const record=await conversationRequest<PrivateConversation>('/'+encodeURIComponent(conversation));const message=record.messages.find(m=>m.request_key===request.messageKey);if(!message||message.content!==request.text||(request.fixedFocus&&message.focus_link_id!==request.focusLinkId)||(request.naturalNeutral&&(message.focus_link_id||message.goalId)))throw Error('尚未读到原消息的保存结果，输入保留；不会重新调用模型。');persist({...request,messageId:message.message_id,phase:'MODEL_PENDING',thread:[...request.thread,{id:'user:'+message.message_id,text:request.text}]});setNotice('原消息已保存，正在核查处理状态。原任务保持不变。');return true;}
   if(request.phase==='APPLYING'){
    if(request.ownerTarget?.kind==='NATIVE'&&request.ownerTarget.executionDigest){
     const target=request.ownerTarget;
     const response=await fetch('/api/workbench/v1/prepared-executions/'+encodeURIComponent(target.executionDigest!)+'/native-progress',{credentials:'same-origin',headers:{Accept:'application/json'}});const body=await response.json();if(!response.ok)throw new WorkbenchRequestError(body.reasonCode??'NATIVE_PROGRESS_UNAVAILABLE',response.status);await verify();
     const progress=body.result as {questions:{invocationId:string;questionKey:string;questionDigest:string;answer:string|null;expired:boolean}[]};
     const question=progress.questions?.find(q=>q.invocationId===target.invocationId&&q.questionKey===target.questionKey&&q.questionDigest===target.questionDigest);
     if(question?.answer===request.text){persist({...request,phase:'DONE'});await refresh.current();setNotice(routingReceiptNotice(request.text,target,true));return false;}
     setNotice('原回答的接收状态尚待核实，正在读取原记录；不会重发。');return Boolean(question&&!question.expired&&!question.answer);
    }
    if(request.ownerTarget?.kind==='UNDERSTANDING'){
     let receipt:{adoption:{actualResult:{invocationId:string}}};
     const path='/'+encodeURIComponent(conversation)+'/understanding-results/'+encodeURIComponent(request.messageId),query='?'+new URLSearchParams({requestKey:request.key});
     try{receipt=await conversationRequest<typeof receipt>(path+'/adoption'+query)}catch(e){
      if(!(e instanceof WorkbenchRequestError&&e.status===404&&e.reasonCode==='UNDERSTANDING_ADOPTION_NOT_FOUND'))throw e;
      const result=await readConversationUnderstandingResult(conversation,request.messageId,request.key);
      const route=await conversationRequest<ExactRoute>(path+'/route'+query);await verify();
      if(route.relation!=='CURRENT_QUESTION'||route.messageId!==request.messageId||route.originalText!==request.text||route.target?.kind!=='UNDERSTANDING'||!sameTarget(request.ownerTarget,route.target)||[...owners.current.values()].filter(o=>sameTarget(o.target,route.target!)).length!==1)throw Error('原问题对应关系尚未核实，未重复提交。',{cause:e});
      if(result.state!=='SUCCEEDED'||result.conversationDelivery?.state!=='SAVED'||result.conversationRoute?.relation!=='CURRENT_QUESTION'||!['DRAFT_READY','NEEDS_DATA','NEEDS_CLARIFICATION'].includes(result.resultKind??''))throw Error('原回答结果尚未核实，未重复提交。',{cause:e});
      persist({...request,phase:'READY_TO_APPLY',persistentRecovery:true});setNotice('已核对原回答与当前问题，尚未读到采用回执。可明确继续已有回答，不会重新调用模型。');return false;
     }
     const journal=await readConversationJournal<{draft?:{invocationId:string}}>(conversation,goal);await verify();
     if(journal.state?.draft?.invocationId===receipt.adoption.actualResult.invocationId){persist({...request,phase:'DONE'});setNotice(routingReceiptNotice(request.text,request.ownerTarget,true));await refresh.current();return false;}
     persist({...request,phase:'READY_TO_APPLY'});setNotice('理解结果已采用。可继续把已保存结果接回原会话，不会重新调用模型。');return false;
    }
    await refresh.current();setNotice('正在查看原回答对应的工作记录；接收状态未确认前不会重发。');return false;
   }
   const result=await readConversationUnderstandingResult(conversation,request.messageId,request.key);await verify();await accept(result,request,false);return ['RUNNING','ACCEPTED','DISPATCHING','DISPATCH_PREPARED'].includes(result.state);
  }catch(e){if(alive.current){setModelState('UNKNOWN');setCanResume(notDispatched(e)&&request.phase==='MODEL_PENDING');setNotice(failureNotice(e))}}
  finally{flight.current=false;if(alive.current)setBusy(false)}
 }
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[]);
 // Restoration is strictly read-only: never dispatch or apply a recovered answer.
 const readSavedEffect=useEffectEvent(readSaved),savedKey=saved?.key,savedPhase=saved?.phase;
 useEffect(()=>{
  if(!enabled||!savedKey||!savedPhase||(['DONE','READY_TO_APPLY'].includes(savedPhase)||savedPhase==='REVIEW'&&Boolean(current.current?.lastResult||current.current?.routeRejected)))return;
  let live=true,timer:ReturnType<typeof setTimeout>|undefined;
  const tick=async()=>{if(await readSavedEffect()&&live)timer=setTimeout(tick,3000)};void tick();
  return()=>{live=false;clearTimeout(timer)};
 },[enabled,savedKey,savedPhase]);
 async function send(text:string){
  if(!enabled||!conversation||(fixedMode&&!fixedFocus&&!naturalRouting)||flight.current||current.current&&!['DONE','REVIEW'].includes(current.current.phase))return false;
  flight.current=true;setBusy(true);setNotice('正在保存这条补充并核对与当前工作的关系…');setPreview('');previewRef.current='';
  const previous=current.current,continueThread=!fixedMode||Boolean(previous?.fixedFocus&&fixedFocus&&(['bindingDigest','workDigest','eventId','receiptDigest','preparationDigest','runId'] as const).every(k=>previous.fixedFocus![k]===fixedFocus[k])),request:Saved={...(fixedMode&&!fixedFocus&&naturalRouting?{naturalNeutral:true}:{}),key:'conversation-route:'+crypto.randomUUID(),messageKey:'conversation-route-message:'+crypto.randomUUID(),text,phase:'MESSAGE_PENDING',observedOwner:[...owners.current.values()].filter(o=>o.target.kind==='UNDERSTANDING').length===1?[...owners.current.values()].find(o=>o.target.kind==='UNDERSTANDING')!.target:undefined,thread:continueThread&&previous?.previousQuestion&&['AMBIGUOUS','CURRENT_WORK'].includes(previous.relation??'')?previous.thread:[],previousQuestion:continueThread&&previous?.previousQuestion&&['AMBIGUOUS','CURRENT_WORK'].includes(previous.relation??'')?previous.previousQuestion:undefined};if(!fixedMode||request.naturalNeutral)persist(request);
  try{
   await verify();let prepared=request;
   if(fixedMode&&fixedFocus){const head=await readConversationHead(conversation);await verify();const command={...fixedFocus,conversationId:conversation,commandId:request.key+':focus',expectedConversationVersion:head.conversation.version};prepared={...request,fixedFocus:command,messageSent:false};persist(prepared);const observed=await recordFixedFocus(command,session.csrfToken);await verify();prepared={...prepared,focusLinkId:observed.focusLinkId,focusContentComplete:observed.contentComplete};persist(prepared);}
   return await sendSavedMessage(prepared);
  }catch(e){if(alive.current){setModelState('UNKNOWN');setNotice(failureNotice(e))}return false}
  finally{flight.current=false;if(alive.current)setBusy(false)}
 }
 async function sendSavedMessage(request:Saved){
  if(!conversation||request.messageSent||request.messageId)throw Error('原消息状态尚未核实，不会重复发送。');
  await verify();const head=await readConversationHead(conversation);await verify();
  const pending={...request,messageSent:true};persist(pending);
  const sent=await conversationRequest<{identity:string}>('/'+encodeURIComponent(conversation)+'/messages',session.csrfToken,{expectedVersion:head.conversation.version,idempotencyKey:request.messageKey,content:request.text,...(goal?{goalId:goal.goalId}:{}),...(request.focusLinkId?{focusLinkId:request.focusLinkId}:{})});await verify();
  const active={...pending,messageId:sent.identity,phase:'MODEL_PENDING' as const,thread:[...request.thread,{id:'user:'+sent.identity,text:request.text}]};persist(active);notifyConversationSend(conversation);await refresh.current();return dispatchSaved(active);
 }
 async function dispatchSaved(request:Saved){
  if(!conversation||!request.messageId||(fixedMode&&!request.fixedFocus&&!(naturalRouting&&request.naturalNeutral)))return false;
  await verify();
  const focus=currentFocus.current;if(request.naturalNeutral&&(!focus.fixedMode||!focus.naturalRouting||focus.fixedFocus))throw Error('当前阅读上下文已变化，原问题保留，请核对后再继续。');if(focus.fixedMode&&!request.naturalNeutral&&(!request.fixedFocus||!focus.fixedFocus||(['bindingDigest','workDigest','eventId','receiptDigest','preparationDigest','runId'] as const).some(k=>request.fixedFocus![k]!==focus.fixedFocus![k])))throw Error('所选周期已变化，原问题保留；核对原周期后再明确继续。');
  setCanResume(false);setModelState('RUNNING');if(request.focusContentComplete===false)setNotice('依据所选周期的结果节选回答，未包含全部正文。');
  const content=conversationUnderstandingContent(request.thread,request.previousQuestion?{clarificationQuestion:request.previousQuestion} as DraftAssistanceResult:undefined);
  const result=await beginDraftAssistance(session.csrfToken,{idempotencyKey:request.key,content,conversationId:conversation,conversationMessageId:request.messageId,conversationRouting:true,...(request.failedRetryOf?{failedRetryOf:request.failedRetryOf}:{})},{},event=>{if(alive.current){setNotice('正在处理这条补充，原工作继续保留。');if(event.preview){previewRef.current=event.preview.slice(-600);setPreview(previewRef.current)}}});
  await verify();return await accept(result,request,true);
 }
 async function resumeUnstarted(){
  const request=current.current;if(!canResume||flight.current||!conversation||!request||(!request.messageId&&!(request.fixedFocus&&!request.messageSent))||(request.messageId&&request.phase!=='MODEL_PENDING'))return;
  flight.current=true;setBusy(true);setCanResume(false);
  try{
   await verify();
   if(request.fixedFocus&&!request.messageSent&&!request.messageId){const observed=await readFixedFocus(request.fixedFocus);await verify();if(observed.state!=='RECORDED')throw Error('原结果焦点尚未核实。');await sendSavedMessage({...request,focusLinkId:observed.focusLinkId,focusContentComplete:observed.contentComplete});return;}
   if(!request.messageId)return;
   try{const result=await readConversationUnderstandingResult(conversation,request.messageId,request.key);await verify();await accept(result,request,false);return;}
   catch(error){if(!notDispatched(error))throw error;}
   await verify();await dispatchSaved(request);
  }catch(error){if(alive.current){setModelState('UNKNOWN');setNotice(failureNotice(error))}}
  finally{flight.current=false;if(alive.current)setBusy(false)}
 }
 useEffect(()=>{sendHandler.current=send});
 async function failureCandidates(){if(!conversation)return [];await verify();const value=await conversationRequest<{items:FailedItem[]}>('/'+encodeURIComponent(conversation)+'/understanding-failures');await verify();if(!Array.isArray(value.items))throw Error('原理解失败记录尚未核实。');return value.items}
 const discoverFailure=useEffectEvent(async()=>{
  if(fixedMode||!enabled||flight.current||current.current&&!['DONE','REVIEW'].includes(current.current.phase))return;
  const before=current.current;
  try{const candidates=await failureCandidates();if(!alive.current||flight.current||current.current!==before)return;const exact=candidates.find(item=>item.target?.kind==='UNDERSTANDING'&&[...owners.current.values()].some(o=>sameTarget(item.target,o.target)));if(!alive.current)return;setFailedCandidate(exact??null);
   if(exact?.successor&&!current.current){const request:Saved={key:exact.successorRequestKey,messageKey:exact.messageId,messageId:exact.messageId,text:exact.originalText,thread:[{id:'user:'+exact.messageId,text:exact.originalText}],phase:'MODEL_PENDING',observedOwner:exact.target,failedRetryOf:exact.invocationId};persist(request);await accept(exact.successor,request,false);return}
   if(exact&&!exact.successor){const request=current.current;if(!request||request.phase==='REVIEW'){const lastResult={state:exact.state,reasonCode:exact.reasonCode};persist({key:exact.successorRequestKey+':failed',messageKey:exact.messageId,messageId:exact.messageId,text:exact.originalText,thread:[{id:'user:'+exact.messageId,text:exact.originalText}],phase:'REVIEW',observedOwner:exact.target,lastResult,failureInvocationId:exact.invocationId,unacceptedPreview:request?.failureInvocationId===exact.invocationId?request.unacceptedPreview:undefined});setNotice(terminalNotice(lastResult.state,lastResult.reasonCode))}}
  }catch{/* Failure discovery cannot authorize a retry; retain the original view. */}
 });
 useEffect(()=>{if(!enabled)return;const timer=setTimeout(()=>void discoverFailure(),0);return()=>clearTimeout(timer)},[enabled,ownerEpoch,saved?.failureInvocationId]);
 async function retryFailed(){
  if(fixedMode)return;const previous=failedCandidate;if(!previous||!previous.continuationEligible||flight.current)return;flight.current=true;setBusy(true);try{const candidates=await failureCandidates();if(!alive.current)return;const found=candidates.find(i=>i.invocationId===previous.invocationId);if(!found||!found.continuationEligible||found.successor||!sameTarget(previous.target,found.target)||![...owners.current.values()].some(o=>sameTarget(found.target,o.target)))throw Error('原问题或资料已变化，未重新调用模型。');
   const request:Saved={key:found.successorRequestKey,messageKey:found.messageId,messageId:found.messageId,text:found.originalText,phase:'MODEL_PENDING',thread:[{id:'user:'+found.messageId,text:found.originalText}],observedOwner:found.target,failedRetryOf:found.invocationId};persist(request);setFailedCandidate(null);setPreview('');previewRef.current='';await dispatchSaved(request);
  }catch(e){if(alive.current){setModelState('UNKNOWN');setNotice(failureNotice(e))}}finally{flight.current=false;if(alive.current)setBusy(false)}}
 async function continueAnswer(){if(flight.current||current.current?.phase!=='READY_TO_APPLY')return;flight.current=true;setBusy(true);try{await applyOwner(current.current)}catch(e){if(alive.current)setNotice(failureNotice(e))}finally{flight.current=false;if(alive.current)setBusy(false)}}
 const blocked=Boolean(saved&&!['DONE','REVIEW'].includes(saved.phase));
 return {context,send,busy,blocked,notice,preview,continueIndependent,canAdoptIndependent:independentAdoptionReady&&saved?.phase==='REVIEW'&&!!saved.independentResult&&!saved.goalAdoption,adoptedGoal:saved?.adoptedGoal,retryFailed,canRetryFailed:!fixedMode&&failedCandidate?.continuationEligible===true&&!failedCandidate.successor,previewLabel:saved?.lastResult?'本条回复未被采纳':['RUNNING','ACCEPTED','DISPATCHING','DISPATCH_PREPARED'].includes(modelState)?'本条回复生成中':'本条回复待核实',previewNotice:saved?.lastResult?'以下生成文字未被采纳，不作为处理结果：':['RUNNING','ACCEPTED','DISPATCHING','DISPATCH_PREPARED'].includes(modelState)?'正在生成回复，尚未核验：':'生成文字尚未核实，不作为处理结果：',readSaved,continueAnswer,canResume,resumeUnstarted,acceptedKey:saved?.phase==='DONE'?saved.key:undefined,acceptedText:saved?.phase==='DONE'?saved.text:undefined,persistentRecovery:saved?.persistentRecovery===true,readyToApply:!fixedMode&&saved?.phase==='READY_TO_APPLY'};
}
