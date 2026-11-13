import {useCallback,useEffect,useEffectEvent,useMemo,useRef,useState} from 'react';
import {beginDraftAssistance,readConversationUnderstandingResult,readWorkbenchSession,WorkbenchRequestError,type DraftAssistanceResult,type WorkbenchSession} from '../api/businessWorkspace';
import {conversationRequest,readConversationHead,type PrivateConversation} from '../api/privateConversation';
import {conversationUnderstandingContent,type UserFactMessage} from './problemUnderstandingModel';
import {conversationScope} from './conversationViewState';
import {notifyConversationReply,notifyConversationSend} from './useConversationScroll';
import type {RoutedOwner,ConversationRoutingValue,RoutedOwnerTarget} from './ConversationRoutingContext';

type Phase='MESSAGE_PENDING'|'MODEL_PENDING'|'READY_TO_APPLY'|'APPLYING'|'DONE'|'REVIEW';
type Saved={key:string;messageKey:string;messageId?:string;text:string;phase:Phase;thread:UserFactMessage[];previousQuestion?:string;relation?:string;ownerTarget?:RoutedOwnerTarget;persistentRecovery?:boolean};
type ExactRoute={relation:string;originalText:string;messageId:string;target:RoutedOwnerTarget|null};
function restored(key:string):Saved|null{try{const raw=sessionStorage.getItem(key);if(!raw||raw.length>64000)return null;const value=JSON.parse(raw);return typeof value?.key==='string'&&typeof value.messageKey==='string'&&typeof value.text==='string'&&Array.isArray(value.thread)&&['MESSAGE_PENDING','MODEL_PENDING','READY_TO_APPLY','APPLYING','DONE','REVIEW'].includes(value.phase)?value:null}catch{return null}}
function notDispatched(error:unknown){return error instanceof WorkbenchRequestError&&error.status===404&&error.reasonCode==='CONVERSATION_REQUEST_NOT_DISPATCHED'}
function failureNotice(error:unknown){if(notDispatched(error))return '问题已保存，但尚未开始处理。可在此继续处理这条问题，原任务不会重跑。';if(error instanceof WorkbenchRequestError&&error.reasonCode==='CONVERSATION_ROUTE_STALE')return '原工作已变化，这条回答未提交。请核对当前问题，输入已保留。';if(error instanceof WorkbenchRequestError&&error.reasonCode==='AUTHORIZATION_NOT_FOUND')return '暂时无法读取当前工作。问题和原任务均已保留，恢复读取后可在此继续。';return '暂未确认这条回复的处理结果。原问题已保留，请核查状态；不会自动重复提交。'}
function sameTarget(expected:RoutedOwnerTarget,actual:RoutedOwnerTarget){
 if(expected.kind!==actual.kind||expected.invocationId!==actual.invocationId)return false;
 const fields: (keyof RoutedOwnerTarget)[]=expected.kind==='NATIVE'?['executionDigest','questionKey','questionDigest']:expected.kind==='UNDERSTANDING'?['journalVersion','journeyKey','contextId','turnId','turnVersion','aggregateVersion']:['journalVersion','journeyKey'];
 return fields.every(key=>expected[key]!==undefined&&expected[key]===actual[key])&&(expected.kind==='NATIVE'||expected.problemId===actual.problemId);
}
export function useConversationRouting({enabled,conversation,session,onMessagesChanged}:{enabled:boolean;conversation:string|null;session:WorkbenchSession;onMessagesChanged:()=>Promise<void>}){
 const scope=conversationScope(session),storage='conversation-routing.v1:'+scope+':'+conversation;
 const [saved,setSaved]=useState<Saved|null>(()=>restored(storage)),[busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[preview,setPreview]=useState(''),[canResume,setCanResume]=useState(false),[ownerEpoch,setOwnerEpoch]=useState(0);
 const current=useRef(saved),flight=useRef(false),alive=useRef(true),owners=useRef(new Map<symbol,RoutedOwner>()),refresh=useRef(onMessagesChanged);useEffect(()=>{refresh.current=onMessagesChanged},[onMessagesChanged]);
 const persist=useCallback((value:Saved)=>{current.current=value;try{sessionStorage.setItem(storage,JSON.stringify(value))}catch{/* The server still owns the saved request. */}if(alive.current)setSaved(value)},[storage]);
 const registerOwner=useCallback((owner:RoutedOwner)=>{const key=Symbol();owners.current.set(key,owner);setOwnerEpoch(n=>n+1);return()=>{owners.current.delete(key);setOwnerEpoch(n=>n+1)}},[]);
 const sendHandler=useRef<((text:string)=>Promise<boolean>)|null>(null);
 const context=useMemo<ConversationRoutingValue>(()=>({enabled,registerOwner,send:text=>sendHandler.current?sendHandler.current(text):Promise.resolve(false)}),[enabled,registerOwner]);
 async function verify(){const actual=await readWorkbenchSession();if(!alive.current||conversationScope(actual)!==scope)throw Error('登录或会话已变化，原请求保留。')}
 // A durable answer is only a candidate: every exact owner GET must agree.
 const discoverPersisted=useEffectEvent(async(isLive:()=>boolean)=>{
  const before=current.current;
  if(!conversation||flight.current||before&&!['DONE','REVIEW'].includes(before.phase)||![...owners.current.values()].some(o=>o.target.kind==='UNDERSTANDING'))return;
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
  if(result.state!=='SUCCEEDED'){
   if(['FAILED','CANCELLED','REJECTED'].includes(result.state)){persist({...request,phase:'REVIEW'});setNotice('这条补充未完成处理，原任务和输入均保留。');}
   else setNotice('这条补充仍在处理，正在保留原请求；不会重复提交。');
   return false;
  }
  if(result.conversationDelivery?.state!=='SAVED'||!result.conversationRoute)throw Error('本次回复尚未确认保存，不会提交给原任务。');
  setPreview('');const relation=result.conversationRoute.relation;
  await refresh.current();
  if(relation==='CURRENT_QUESTION'&&['CURRENT_QUESTION_ANSWER','DRAFT_READY','NEEDS_DATA','NEEDS_CLARIFICATION'].includes(result.resultKind??'')){
   const ready={...request,relation,phase:'READY_TO_APPLY' as const};persist(ready);
   if(apply)return applyOwner(ready);
   setNotice('这条回复已保存。继续前将重新核对原任务的同一个问题。');return false;
  }
  if((['INDEPENDENT','CURRENT_WORK'].includes(relation)&&result.resultKind==='DIRECT_ANSWER')||(['AMBIGUOUS','CURRENT_WORK'].includes(relation)&&result.resultKind==='NEEDS_CLARIFICATION')){
   persist({...request,relation,phase:'DONE',previousQuestion:result.clarificationQuestion??undefined});if(apply&&conversation&&result.conversationDelivery.messageId)notifyConversationReply(conversation,result.conversationDelivery.messageId);setPreview('');setNotice(result.resultKind==='DIRECT_ANSWER'?'回复已返回本会话，原任务保持不变。':'请回答会话中的必要确认，原任务保持不变。');return true;
  }
  persist({...request,phase:'REVIEW'});setNotice('这条补充尚不能安全关联到原工作，原任务保持不变。');return false;
 }
 async function applyOwner(request:Saved){
  if(!conversation||!request.messageId)return false;
  await verify();
  let route:ExactRoute;
  try{route=await conversationRequest<ExactRoute>('/'+encodeURIComponent(conversation)+'/understanding-results/'+encodeURIComponent(request.messageId)+'/route?'+new URLSearchParams({requestKey:request.key}));}
  catch(e){if(e instanceof WorkbenchRequestError&&[400,403,404,409,410,422].includes(e.status))persist({...request,phase:'REVIEW'});throw e;}
  await verify();
  if(route.relation!=='CURRENT_QUESTION'||route.messageId!==request.messageId||route.originalText!==request.text||!route.target)throw Error('原问题对应关系已变化，未提交或改投其他任务。');
  const matches=[...owners.current.values()].filter(owner=>sameTarget(owner.target,route.target!));
  if(matches.length!==1)throw Error('原问题当前不可续接，已保留回复，不会提交给其他问题。');
  persist({...request,phase:'APPLYING',ownerTarget:route.target});
  const receipt=await matches[0].onAnswer(route.originalText,route.messageId,{requestKey:request.key});
  if(typeof receipt==='object'&&receipt.state==='REJECTED'){persist({...request,phase:'REVIEW'});setNotice('原问题未接受这条回答，输入已保留，请核对后修改；不会自动重发。');return false}
  if(receipt!==true&&!(typeof receipt==='object'&&receipt.state==='ACCEPTED')){setNotice('原回答的接收状态尚待核实，请查看原工作进展；不会自动重发。');return false}
  persist({...request,phase:'DONE'});setNotice('回答已提交到原问题，后续进展继续在本会话显示。');await refresh.current();return true;
 }
 async function readSaved(){
  const request=current.current;if(!conversation||!request)return false;if(flight.current)return true;
  flight.current=true;setBusy(true);setPreview('');setCanResume(false);
  try{
   await verify();
   if(!request.messageId){const record=await conversationRequest<PrivateConversation>('/'+encodeURIComponent(conversation));const message=record.messages.find(m=>m.request_key===request.messageKey);if(!message||message.content!==request.text)throw Error('尚未读到原消息的保存结果，输入保留；不会重新调用模型。');persist({...request,messageId:message.message_id,phase:'MODEL_PENDING',thread:[...request.thread,{id:'user:'+message.message_id,text:request.text}]});setNotice('原消息已保存，正在核查处理状态。原任务保持不变。');return true;}
   if(request.phase==='APPLYING'){
    if(request.ownerTarget?.kind==='NATIVE'&&request.ownerTarget.executionDigest){
     const target=request.ownerTarget;
     const response=await fetch('/api/workbench/v1/prepared-executions/'+encodeURIComponent(target.executionDigest!)+'/native-progress',{credentials:'same-origin',headers:{Accept:'application/json'}});const body=await response.json();if(!response.ok)throw new WorkbenchRequestError(body.reasonCode??'NATIVE_PROGRESS_UNAVAILABLE',response.status);await verify();
     const progress=body.result as {questions:{invocationId:string;questionKey:string;questionDigest:string;answer:string|null;expired:boolean}[]};
     const question=progress.questions?.find(q=>q.invocationId===target.invocationId&&q.questionKey===target.questionKey&&q.questionDigest===target.questionDigest);
     if(question?.answer===request.text){persist({...request,phase:'DONE'});await refresh.current();setNotice('已从原问题记录核实回答已保存，没有再次提交。');return false;}
     setNotice('原回答的接收状态尚待核实，正在读取原记录；不会重发。');return Boolean(question&&!question.expired&&!question.answer);
    }
    if(request.ownerTarget?.kind==='UNDERSTANDING'){
     const receipt=await conversationRequest<{adoption:{actualResult:{invocationId:string}}}>('/'+encodeURIComponent(conversation)+'/understanding-results/'+encodeURIComponent(request.messageId)+'/adoption?'+new URLSearchParams({requestKey:request.key}));
     const journal=await conversationRequest<{state:{draft?:{invocationId:string}}|null}>('/'+encodeURIComponent(conversation)+'/journey');await verify();
     if(journal.state?.draft?.invocationId===receipt.adoption.actualResult.invocationId){persist({...request,phase:'DONE'});setNotice('已核实原会话接续记录，没有重复理解。');await refresh.current();return false;}
     persist({...request,phase:'READY_TO_APPLY'});setNotice('理解结果已采用。可继续把已保存结果接回原会话，不会重新调用模型。');return false;
    }
    await refresh.current();setNotice('正在查看原回答对应的工作记录；接收状态未确认前不会重发。');return false;
   }
   const result=await readConversationUnderstandingResult(conversation,request.messageId,request.key);await verify();await accept(result,request,false);return ['RUNNING','ACCEPTED','DISPATCHING','DISPATCH_PREPARED'].includes(result.state);
  }catch(e){if(alive.current){setCanResume(notDispatched(e)&&request.phase==='MODEL_PENDING');setNotice(failureNotice(e))}}
  finally{flight.current=false;if(alive.current)setBusy(false)}
 }
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[]);
 // Restoration is strictly read-only: never dispatch or apply a recovered answer.
 const readSavedEffect=useEffectEvent(readSaved),savedKey=saved?.key,savedPhase=saved?.phase;
 useEffect(()=>{
  if(!enabled||!savedKey||!savedPhase||['DONE','REVIEW','READY_TO_APPLY'].includes(savedPhase))return;
  let live=true,timer:ReturnType<typeof setTimeout>|undefined;
  const tick=async()=>{if(await readSavedEffect()&&live)timer=setTimeout(tick,3000)};void tick();
  return()=>{live=false;clearTimeout(timer)};
 },[enabled,savedKey,savedPhase]);
 async function send(text:string){
  if(!enabled||!conversation||flight.current||current.current&&!['DONE','REVIEW'].includes(current.current.phase))return false;
  flight.current=true;setBusy(true);setNotice('正在保存这条补充并核对与当前工作的关系…');setPreview('');
  const previous=current.current,request:Saved={key:'conversation-route:'+crypto.randomUUID(),messageKey:'conversation-route-message:'+crypto.randomUUID(),text,phase:'MESSAGE_PENDING',thread:previous?.previousQuestion&&['AMBIGUOUS','CURRENT_WORK'].includes(previous.relation??'')?previous.thread:[],previousQuestion:previous?.previousQuestion&&['AMBIGUOUS','CURRENT_WORK'].includes(previous.relation??'')?previous.previousQuestion:undefined};persist(request);
  try{
   await verify();const head=await readConversationHead(conversation);
   const sent=await conversationRequest<{identity:string}>('/'+encodeURIComponent(conversation)+'/messages',session.csrfToken,{expectedVersion:head.conversation.version,idempotencyKey:request.messageKey,content:text});await verify();
   const active={...request,messageId:sent.identity,phase:'MODEL_PENDING' as const,thread:[...request.thread,{id:'user:'+sent.identity,text}]};persist(active);notifyConversationSend(conversation);await refresh.current();
   return await dispatchSaved(active);
  }catch(e){if(alive.current)setNotice(failureNotice(e));return false}
  finally{flight.current=false;if(alive.current)setBusy(false)}
 }
 async function dispatchSaved(request:Saved){
  if(!conversation||!request.messageId)return false;
  setCanResume(false);
  const content=conversationUnderstandingContent(request.thread,request.previousQuestion?{clarificationQuestion:request.previousQuestion} as DraftAssistanceResult:undefined);
  const result=await beginDraftAssistance(session.csrfToken,{idempotencyKey:request.key,content,conversationId:conversation,conversationMessageId:request.messageId,conversationRouting:true},{},event=>{if(alive.current){setNotice('正在处理这条补充，原工作继续保留。');if(event.preview)setPreview(event.preview.slice(-600))}});
  await verify();return await accept(result,request,true);
 }
 async function resumeUnstarted(){
  const request=current.current;if(!canResume||flight.current||!conversation||!request?.messageId||request.phase!=='MODEL_PENDING')return;
  flight.current=true;setBusy(true);setCanResume(false);
  try{
   await verify();
   try{const result=await readConversationUnderstandingResult(conversation,request.messageId,request.key);await verify();await accept(result,request,false);return;}
   catch(error){if(!notDispatched(error))throw error;}
   await verify();await dispatchSaved(request);
  }catch(error){if(alive.current)setNotice(failureNotice(error))}
  finally{flight.current=false;if(alive.current)setBusy(false)}
 }
 useEffect(()=>{sendHandler.current=send});
 async function continueAnswer(){if(flight.current||current.current?.phase!=='READY_TO_APPLY')return;flight.current=true;setBusy(true);try{await applyOwner(current.current)}catch(e){if(alive.current)setNotice(String(e))}finally{flight.current=false;if(alive.current)setBusy(false)}}
 const blocked=Boolean(saved&&!['DONE','REVIEW'].includes(saved.phase));
 return {context,send,busy,blocked,notice,preview,readSaved,continueAnswer,canResume,resumeUnstarted,acceptedKey:saved?.phase==='DONE'?saved.key:undefined,acceptedText:saved?.phase==='DONE'?saved.text:undefined,persistentRecovery:saved?.persistentRecovery===true,readyToApply:saved?.phase==='READY_TO_APPLY'};
}
