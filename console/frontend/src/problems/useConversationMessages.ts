import {useCallback,useEffect,useRef,useState} from 'react';
import {readWorkbenchSession,type WorkbenchSession} from '../api/businessWorkspace';
import {conversationRequest,readCapabilityConversationContext,readConversationMessages,readConversationWorkLinks,type PrivateConversation,type PrivateMessage} from '../api/privateConversation';
import {conversationScope} from './conversationViewState';
import {clearMessagePosition,readMessagePosition,saveMessagePosition,type MessagePosition} from './conversationMessagePosition';

function ordered(messages:PrivateMessage[]){return [...new Map(messages.map(message=>[message.message_id,message])).values()].sort((a,b)=>a.sequence-b.sequence||a.message_id.localeCompare(b.message_id))}
export function useConversationMessages(id:string|null,session:WorkbenchSession,pagedHistory:boolean){
 const scope=conversationScope(session);
 const [data,setData]=useState<PrivateConversation|null>(null),[error,setError]=useState(''),[linksNotice,setLinksNotice]=useState(''),[linksReady,setLinksReady]=useState(false);
 const [page,setPage]=useState<{hasMore:boolean;nextCursor:string|null}>({hasMore:false,nextCursor:null}),[olderBusy,setOlderBusy]=useState(false),[olderError,setOlderError]=useState('');
 const [capabilityMessage,setCapabilityMessage]=useState<PrivateMessage|null>(null),[capabilityReady,setCapabilityReady]=useState(false),[capabilityNotice,setCapabilityNotice]=useState(''),[capabilityVersion,setCapabilityVersion]=useState<number|null>(null),[messageVersion,setMessageVersion]=useState<number|null>(null);
 const [restoredAnchor,setRestoredAnchor]=useState<MessagePosition|null>(null),[historicalPage,setHistoricalPage]=useState(false);
 const epoch=useRef(0),latest=useRef<AbortController|null>(null),links=useRef<AbortController|null>(null),older=useRef<AbortController|null>(null),invalid=useRef(false),mounted=useRef(false),messageCursors=useRef(new Map<string,string>()),capability=useRef<AbortController|null>(null);
 const clear=useCallback(()=>{epoch.current++;invalid.current=true;latest.current?.abort();links.current?.abort();older.current?.abort();capability.current?.abort();messageCursors.current.clear();setCapabilityMessage(null);setCapabilityReady(false);setCapabilityNotice('');setData(null);setPage({hasMore:false,nextCursor:null});setLinksReady(false);setOlderBusy(false);setLinksNotice('');setOlderError('');setRestoredAnchor(null)},[]);
 const verify=useCallback(async(signal?:AbortSignal)=>{if(!mounted.current||invalid.current)throw new DOMException('View changed','AbortError');const actual=await readWorkbenchSession(signal);if(!mounted.current||invalid.current)throw new DOMException('View changed','AbortError');if(conversationScope(actual)!==scope){clear();setError('登录身份已变化，请重新登录后读取。');window.dispatchEvent(new Event('workbench-session-expired'));throw Error('CONVERSATION_IDENTITY_CHANGED')}return actual},[scope,clear]);
 const reloadLinks=useCallback(async()=>{
  if(!id||invalid.current)return;
  links.current?.abort();const controller=new AbortController();links.current=controller;const token=epoch.current;setLinksReady(false);setLinksNotice('');
  try{
   const [value]=await Promise.all([readConversationWorkLinks(id,controller.signal),verify(controller.signal)]);await verify(controller.signal);
   if(!mounted.current||token!==epoch.current||controller.signal.aborted||invalid.current)return;
   if(value.conversation.conversation_id!==id)throw Error('CONVERSATION_RESPONSE_MISMATCH');
   setData(current=>current?{...current,conversation:value.conversation.version>current.conversation.version?value.conversation:current.conversation,links:value.links}:current);setLinksReady(true);
  }catch(reason){if(!controller.signal.aborted&&mounted.current&&token===epoch.current){if((reason as {status?:number}).status===401){clear();return}setLinksNotice('关联工作暂不可读，已读取的会话消息仍可查看。')}}
 },[id,verify,clear]);
 const reloadCapability=useCallback(async()=>{
  if(!id||invalid.current||!pagedHistory)return;
  capability.current?.abort();const controller=new AbortController();capability.current=controller;const token=epoch.current;setCapabilityReady(false);setCapabilityNotice('');
  try{const [value]=await Promise.all([readCapabilityConversationContext(id,controller.signal),verify(controller.signal)]);await verify(controller.signal);
   if(!mounted.current||token!==epoch.current||controller.signal.aborted||invalid.current)return;
   if(value.conversation?.conversation_id!==id||!Number.isSafeInteger(value.conversation.version)||!(value.message===null||value.message&&typeof value.message.message_id==='string'&&value.message.kind==='SOURCE'&&(value.message.facts?.readable===false||value.message.facts?.source?.kind==='CAPABILITY')))throw Error('CONVERSATION_CAPABILITY_CONTEXT_MISMATCH');
   setCapabilityMessage(value.message);setCapabilityVersion(value.conversation.version);setCapabilityReady(true);
  }catch(reason){if(!controller.signal.aborted&&mounted.current&&token===epoch.current){if((reason as {status?:number}).status===401){clear();return}setCapabilityMessage(null);setCapabilityNotice('原能力办理记录暂不可读，不能据此判断没有待接续工作。')}}
 },[id,pagedHistory,verify,clear]);
 const loadPage=useCallback(async(position:MessagePosition|null)=>{
  if(!id||invalid.current)return;
  const token=++epoch.current;latest.current?.abort();older.current?.abort();setOlderBusy(false);setOlderError('');const controller=new AbortController();latest.current=controller;setError('');
  try{
   const [result]=await Promise.all([pagedHistory?readConversationMessages(id,position?.cursor,controller.signal):conversationRequest<PrivateConversation>('/'+encodeURIComponent(id),undefined,undefined,controller.signal),verify(controller.signal)]);
   const value=pagedHistory?result as Awaited<ReturnType<typeof readConversationMessages>>:{...result,page:{hasMore:false,nextCursor:null}};await verify(controller.signal);
   if(!mounted.current||token!==epoch.current||controller.signal.aborted||invalid.current)return;
   if(value.conversation?.conversation_id!==id||!Array.isArray(value.messages)||typeof value.page?.hasMore!=='boolean'||value.page.hasMore&&!value.page.nextCursor)throw Error('CONVERSATION_RESPONSE_MISMATCH');
   messageCursors.current.clear();const resume=('resumeCursor' in value.page?value.page.resumeCursor:null)??position?.cursor;
   if(resume)for(const message of value.messages)messageCursors.current.set(message.message_id,String(resume));
   setData({conversation:value.conversation,messages:pagedHistory?ordered(value.messages):value.messages,links:pagedHistory?[]:(result as PrivateConversation).links});setMessageVersion(value.conversation.version);setPage(value.page);setRestoredAnchor(pagedHistory?position:null);setHistoricalPage(pagedHistory&&Boolean(position));
   if(pagedHistory){void reloadLinks();void reloadCapability()}else{setLinksReady(true);setCapabilityReady(true);setCapabilityVersion(value.conversation.version);setCapabilityMessage([...value.messages].reverse().find(message=>message.kind==='SOURCE'&&message.facts?.source?.kind==='CAPABILITY')??null)}
  }catch(reason){if(!controller.signal.aborted&&mounted.current&&token===epoch.current){if((reason as {status?:number}).status===401)clear();else setData(null);setError(String(reason))}}
 },[id,verify,reloadLinks,reloadCapability,clear,pagedHistory]);
 const load=useCallback(async()=>{if(id)clearMessagePosition(scope,id);setRestoredAnchor(null);setHistoricalPage(false);await loadPage(null)},[id,scope,loadPage]);
 const refreshCurrent=useCallback(async()=>{await loadPage(id&&pagedHistory?readMessagePosition(scope,id):null)},[id,scope,loadPage,pagedHistory]);
 const rememberAnchor=useCallback((messageId:string,offset:number)=>{if(!id||invalid.current)return;const cursor=messageCursors.current.get(messageId);if(cursor)saveMessagePosition(scope,id,{cursor,messageId,offset})},[id,scope]);
 const more=useCallback(async()=>{
  if(!id||invalid.current||older.current||!page.hasMore||!page.nextCursor)return;
  const token=epoch.current,controller=new AbortController();older.current=controller;setOlderBusy(true);setOlderError('');
  try{
   const before=page.nextCursor;
   const [value]=await Promise.all([readConversationMessages(id,before,controller.signal),verify(controller.signal)]);await verify(controller.signal);
   if(!mounted.current||token!==epoch.current||controller.signal.aborted||invalid.current)return;
   if(value.conversation.conversation_id!==id||value.page.hasMore&&(!value.page.nextCursor||value.page.nextCursor===before))throw Error('CONVERSATION_CURSOR_DID_NOT_ADVANCE');
   for(const message of value.messages)if(!messageCursors.current.has(message.message_id))messageCursors.current.set(message.message_id,value.page.resumeCursor??before);
   setData(current=>current?{...current,messages:ordered([...value.messages,...current.messages])}:current);setPage(value.page);
  }catch(reason){if(!controller.signal.aborted&&mounted.current&&token===epoch.current){if((reason as {status?:number}).status===401){clear();return}setOlderError('更早消息暂不可读，当前位置与未发送内容已保留。')}}finally{if(older.current===controller){older.current=null;if(mounted.current)setOlderBusy(false)}}
 },[id,page,verify,clear]);
 useEffect(()=>{
  const generation=epoch;mounted.current=true;invalid.current=false;const startingEpoch=epoch.current;
  const expired=()=>{clear();setError('登录状态已变化，请重新登录后读取。')};window.addEventListener('workbench-session-expired',expired);
  void Promise.resolve().then(()=>{if(mounted.current&&!invalid.current&&epoch.current===startingEpoch)return refreshCurrent()});
  return()=>{mounted.current=false;invalid.current=true;generation.current++;latest.current?.abort();links.current?.abort();older.current?.abort();capability.current?.abort();window.removeEventListener('workbench-session-expired',expired)};
 },[refreshCurrent,clear]);
 return {data,error,load,refreshCurrent,capabilityMessage,capabilityReady,capabilityNotice,reloadCapability,completeMessages:!historicalPage&&!page.hasMore&&messageVersion===capabilityVersion,more,reloadLinks,rememberAnchor,restoredAnchor,historicalPage,hasMore:page.hasMore,olderBusy,olderError,linksReady,linksNotice};
}
