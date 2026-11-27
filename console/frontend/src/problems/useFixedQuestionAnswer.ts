import {useEffect,useEffectEvent,useLayoutEffect,useRef,useState} from 'react';
import {beginDraftAssistance,readConversationUnderstandingResult,readWorkbenchSession,type DraftAssistanceResult,type WorkbenchSession} from '../api/businessWorkspace';
import {conversationRequest,readConversationHead,type PrivateConversation} from '../api/privateConversation';
import {questionPath,readAnswer,readPresentation,sameQuestion,verifyPresentation,type AnswerResult,type FixedQuestionSelection,type PresentationResult,type QuestionIdentity} from '../api/fixedQuestionDelegation';
import {conversationScope} from './conversationViewState';

type Presented=Extract<PresentationResult,{state:'RECORDED'}>;
type Intent={selection:string;prepareCommand:string;prepareSent:boolean;presentation?:Presented;text?:string;messageKey?:string;messageId?:string;modelKey?:string;modelSent?:boolean;answerCommand?:string;answerSent?:boolean;invocationId?:string;done?:boolean};
const signature=(q:FixedQuestionSelection|null)=>q?JSON.stringify([q.bindingDigest,q.workDigest,q.eventId,q.receiptDigest,q.preparationDigest,q.runId,q.invocationId,q.questionKey,q.questionDigest,q.question,q.expiresAt]):'';
function load(key:string):Intent|null{try{const raw=sessionStorage.getItem(key);if(!raw||raw.length>24000)return null;const v=JSON.parse(raw);return typeof v.selection==='string'&&typeof v.prepareCommand==='string'&&typeof v.prepareSent==='boolean'?v:null}catch{return null}}
async function command(value:string){const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value));return 'question:'+Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('')}

/** Browser intents are recovery locators only. Every effect rechecks server facts. */
export function useFixedQuestionAnswer({enabled,conversation,session,question,onMessagesChanged}:{enabled:boolean;conversation:string|null;session:WorkbenchSession;question:FixedQuestionSelection|null;onMessagesChanged:()=>Promise<void>}){
 const identity=signature(question),scope=conversationScope(session),key='fixed-question.v1:'+JSON.stringify([session.principal,conversation,identity]);
 const [canContinue,setCanContinue]=useState(false);
 const [busy,setBusy]=useState(false),[ready,setReady]=useState(false),[notice,setNotice]=useState(''),[answerMode,setAnswerMode]=useState(true),[acceptedText,setAcceptedText]=useState(''),[acceptedKey,setAcceptedKey]=useState('');
 const current=useRef({enabled,identity,scope,key,conversation,question});useLayoutEffect(()=>{current.current={enabled,identity,scope,key,conversation,question}},[enabled,identity,scope,key,conversation,question]);
 const flight=useRef<string|null>(null),active=useRef(true),invalid=useRef(false),changed=useRef(onMessagesChanged);useEffect(()=>{changed.current=onMessagesChanged},[onMessagesChanged]);
 useEffect(()=>{active.current=true;invalid.current=false;const expire=()=>{invalid.current=true;setCanContinue(false);setReady(false);setNotice('登录已变化，原回答记录保留。')};window.addEventListener('workbench-session-expired',expire);return()=>{active.current=false;window.removeEventListener('workbench-session-expired',expire)}},[scope]);
 function persist(v:Intent){const raw=JSON.stringify(v);sessionStorage.setItem(key,raw);if(sessionStorage.getItem(key)!==raw)throw Error('无法保存本次处理记录，尚未提交。');return v}
 async function verify(){const s=await readWorkbenchSession();if(!active.current||invalid.current||!current.current.enabled||current.current.key!==key||current.current.identity!==identity||conversationScope(s)!==scope||s.csrfToken!==session.csrfToken||!question||Date.parse(question.expiresAt)<=Date.now())throw Error('当前问题或登录已变化，原输入保留。')}
 async function presented(v:Intent){await verify();if(!question||!conversation)throw Error('问题尚未核实。');const r=verifyPresentation(await readPresentation(conversation,v.prepareCommand),question,conversation,session,v.prepareCommand);await verify();persist({...v,presentation:r});return r}
 async function createPresentationOnSend(v:Intent){
  await verify();if(!question||!conversation)throw Error('问题尚未核实。');
  let result=await readPresentation(conversation,v.prepareCommand);await verify();
  if(result.state==='NOT_RECORDED'){
   if(result.conversationId!==conversation||result.commandId!==v.prepareCommand||v.prepareSent)throw Error('本题办理结果尚未核实，不会重复准备。');
   const observed=await conversationRequest<{identity:QuestionIdentity;question:{question:string}}>(questionPath(conversation)+'?'+new URLSearchParams({eventId:question.eventId,receiptDigest:question.receiptDigest,invocationId:question.invocationId,questionKey:question.questionKey}));
   await verify();if(!sameQuestion(observed.identity,question,conversation,session)||observed.question.question!==question.question)throw Error('本题与运行记录尚未一致。');
   const head=await readConversationHead(conversation);await verify();v=persist({...v,prepareSent:true});
   result=await conversationRequest<PresentationResult>(questionPath(conversation)+'/presentations',session.csrfToken,{identity:observed.identity,expectedConversationVersion:head.conversation.version,commandId:v.prepareCommand});
  }
  const p=verifyPresentation(result,question,conversation,session,v.prepareCommand);await verify();return {intent:persist({...v,presentation:p}),presentation:p};
 }
 async function prepare(){if(!enabled||!question||!conversation||flight.current===key)return;flight.current=key;setBusy(true);setReady(false);try{
  await verify();let v=load(key);if(!v){v=persist({selection:identity,prepareCommand:await command(key),prepareSent:false})}if(v.selection!==identity)throw Error('原问题身份不一致。');
  const result=await readPresentation(conversation,v.prepareCommand);await verify();
  if(result.state==='NOT_RECORDED'){
   if(result.conversationId!==conversation||result.commandId!==v.prepareCommand||v.prepareSent)throw Error('本题办理结果尚未核实，不会重复准备。');
   // Observation is not authorization: only an actual send may prepare presentation.
   setReady(true);setNotice('系统正在等待你的补充，回答只用于下方这条问题。');return;
  }
  const p=verifyPresentation(result,question,conversation,session,v.prepareCommand);await verify();persist({...v,presentation:p});setReady(!v.done);setNotice(v.done?'这条回答已保存，系统将按原任务继续。':v.messageKey?'已有回答处理记录，请先核查原状态。':'系统正在等待你的补充，回答只用于下方这条问题。');
 }catch{if(active.current&&current.current.key===key)setNotice('本题的回答条件尚未核实，输入可以保留；也可以另提问题。')}finally{if(flight.current===key)flight.current=null;if(active.current&&current.current.key===key)setBusy(false)}}
 const prepareEvent=useEffectEvent(prepare);const expiresAt=question?.expiresAt;
 useEffect(()=>{void Promise.resolve().then(()=>{if(current.current.key!==key)return;setAnswerMode(true);setCanContinue(false);setReady(false);setBusy(false);setNotice('');setAcceptedKey('');setAcceptedText('');void prepareEvent()});const timer=setInterval(()=>{if(expiresAt&&Date.parse(expiresAt)<=Date.now()){setReady(false);setNotice('本题等待已到期，原输入与记录保留。')}},1000);return()=>clearInterval(timer)},[key,enabled,expiresAt]); // Exact question change starts a new independent recovery slot.
 async function finish(v:Intent,r:AnswerResult,p:Presented){if(!conversation||r.state!=='RECORDED'||r.modelDispatched!==false||r.continuationDispatched!==false||r.receipt.presentationId!==p.presentation.presentationId||r.receipt.presentationDigest!==p.presentationDigest||r.receipt.actorId!==session.principal.principalId||r.receipt.executionSubject!==p.presentation.identity.executionSubject||r.receipt.commandId!==v.answerCommand||r.receipt.inputMessageId!==v.messageId||r.receipt.interpretationInvocationId!==v.invocationId)throw Error('回答接收状态尚未核实。');await verify();persist({...v,done:true});setCanContinue(false);setReady(false);setAcceptedText(v.text??'');setAcceptedKey(r.receiptDigest);setNotice('你的回答已保存；系统将继续原来的检查，不会新建或重跑任务。');await changed.current();return true}
 async function continueKnown(v:Intent,recovery:boolean){if(!conversation||!question)throw Error('问题尚未核实。');const p=await presented(v);
  const chat=await conversationRequest<PrivateConversation>('/'+encodeURIComponent(conversation));await verify();const messages=chat.messages.filter(m=>m.request_key===v.messageKey&&m.author_id===session.principal.principalId&&!m.kind);if(messages.length!==1||messages[0].content!==v.text||messages[0].focus_link_id!==p.presentation.focusLinkId)throw Error('原回复尚未核实，不会重复保存或理解。');v=persist({...v,messageId:messages[0].message_id});
  let result:DraftAssistanceResult;
  if(v.modelSent)result=await readConversationUnderstandingResult(conversation,v.messageId!,v.modelKey!);
  else{if(recovery){setCanContinue(true);setNotice('已核实原回复，可按原请求继续处理。');return false;}await presented(v);v=persist({...v,modelSent:true});result=await beginDraftAssistance(session.csrfToken,{idempotencyKey:v.modelKey!,content:v.text!,conversationId:conversation,conversationMessageId:v.messageId,conversationRouting:true})}
  await verify();if(result.state!=='SUCCEEDED'||result.resultKind!=='CURRENT_QUESTION_ANSWER'||result.conversationDelivery?.state!=='SAVED'||result.conversationRoute?.relation!=='CURRENT_QUESTION'||result.conversationRoute.currentQuestionToken!==p.presentation.currentQuestionToken)throw Error('这条回复尚未确认对应当前问题，未提交回答。');
  const route=await conversationRequest<{relation:string;messageId:string;originalText:string;target:{kind:string;delegationPresentationId?:string;invocationId:string;questionKey:string;questionDigest:string;executionDigest:string;runId:string}|null}>('/'+encodeURIComponent(conversation)+'/understanding-results/'+encodeURIComponent(v.messageId!)+'/route?'+new URLSearchParams({requestKey:v.modelKey!}));await verify();
  if(route.relation!=='CURRENT_QUESTION'||route.messageId!==v.messageId||route.originalText!==v.text||route.target?.kind!=='NATIVE'||route.target.delegationPresentationId!==p.presentation.presentationId||route.target.invocationId!==question.invocationId||route.target.questionKey!==question.questionKey||route.target.questionDigest!==question.questionDigest||route.target.executionDigest!==question.preparationDigest||route.target.runId!==question.runId)throw Error('原问题对应关系已变化，未提交回答。');
  v=persist({...v,invocationId:result.invocationId});await presented(v);
  if(v.answerSent)return finish(v,await readAnswer(conversation,p.presentation.presentationId,v.answerCommand!),p);
  if(recovery){setCanContinue(true);setNotice('已核实原回复与理解结果，可按原请求继续保存回答。');return false;}
  v=persist({...v,answerSent:true});const receipt=await conversationRequest<AnswerResult>(questionPath(conversation)+'/answers',session.csrfToken,{presentationId:p.presentation.presentationId,presentationDigest:p.presentationDigest,messageId:v.messageId,requestKey:v.modelKey,commandId:v.answerCommand});return finish(v,receipt,p);
 }
 async function send(text:string){if(flight.current||!ready||!answerMode||!question||!conversation)return false;flight.current=key;setBusy(true);try{let v=load(key);if(!v||v.messageKey)throw Error('已有回答处理记录，请核查原状态，不会再次提交。');const prepared=await createPresentationOnSend(v);v=prepared.intent;const p=prepared.presentation;const head=await readConversationHead(conversation);await verify();const request=crypto.randomUUID();v=persist({...v,text,messageKey:'question-message:'+request,modelKey:'question-c1:'+request,answerCommand:'question-answer:'+request});
  await conversationRequest('/'+encodeURIComponent(conversation)+'/messages',session.csrfToken,{content:text,expectedVersion:head.conversation.version,idempotencyKey:v.messageKey,focusLinkId:p.presentation.focusLinkId});await changed.current();return await continueKnown(v,false);
 }catch{if(active.current&&current.current.key===key)setNotice('原回答的处理状态尚未核实，输入和记录保留；不会再次提交或调用模型。');return false}finally{if(flight.current===key)flight.current=null;if(active.current&&current.current.key===key)setBusy(false)}}
 async function recover(){if(flight.current===key)return;const v=load(key);if(!v?.messageKey){await prepare();return}flight.current=key;setBusy(true);try{await continueKnown(v,true)}catch{if(active.current&&current.current.key===key)setNotice('尚未读回完整接收记录，原回答保留；本次仅核查，没有重发。')}finally{if(flight.current===key)flight.current=null;if(active.current&&current.current.key===key)setBusy(false)}}
 async function continueOriginal(){if(flight.current||!canContinue)return;const v=load(key);if(!v?.messageId||v.answerSent||v.done)return;flight.current=key;setBusy(true);setCanContinue(false);try{await continueKnown(v,false)}catch{if(active.current&&current.current.key===key)setNotice('原回答的处理状态尚未核实，输入和记录保留；不会再次提交或调用模型。')}finally{if(flight.current===key)flight.current=null;if(active.current&&current.current.key===key)setBusy(false)}}
 return {canContinue,continueOriginal,active:enabled&&!!question&&answerMode,question:question?.question??'',busy,ready,notice,send,recover,acceptedText,acceptedKey,anotherQuestion:()=>setAnswerMode(false),returnToQuestion:()=>setAnswerMode(true)};
}
