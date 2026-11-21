import {useEffect,useRef,useState} from 'react';
import {readWorkbenchSession,type WorkbenchSession} from '../api/businessWorkspace';
import {conversationScope} from './conversationViewState';
import {preparedRequest,type ExecutionView} from '../api/preparedExecution';
import {readConversationCycles,readCycleAccessReceipt,prepareCycleRead,verifyCyclePage,verifyReadReceipt,type FixedCyclePage,type ExecutingCycleEvent,type CycleReadIdentity} from '../api/conversationFixedCycles';
import {readViewString,saveViewString} from './workViewState';
import {verifyCycleExecution} from './fixedCyclePresentation';

type Pending={identity:CycleReadIdentity;sent:boolean;previousCommandId?:string};
export function useFixedConversationCycles(conversation:string,session:WorkbenchSession){
 const scope=conversationScope(session),key=scope+':fixed-cycle:'+conversation;
 const durableKey=JSON.stringify([session.principal.principalId,session.principal.tenantId,session.principal.securityDomain,conversation]);
 const [page,setPage]=useState<FixedCyclePage|null>(null),[selected,setSelected]=useState(()=>readViewString(key,'event')),[view,setView]=useState<ExecutionView|null>(null),[error,setError]=useState(''),[readError,setReadError]=useState(''),[busy,setBusy]=useState(false),[readExpired,setReadExpired]=useState(false),[tick,setTick]=useState(0);
 const active=useRef(false),epoch=useRef(0),abort=useRef<AbortController|null>(null),flight=useRef<number|null>(null),selectedRef=useRef(selected),pageRef=useRef(page),prepared=useRef(new Set<string>()),bindingRef=useRef<string|null>(null);
 const verify=async(signal:AbortSignal)=>{if(conversationScope(await readWorkbenchSession(signal))!==scope)throw Error('FIXED_CYCLE_SESSION_CHANGED')};
 async function stableCommand(value:string){return 'fixed-cycle-read:'+Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value)))).map(x=>x.toString(16).padStart(2,'0')).join('')}
 async function access(p:FixedCyclePage,event:ExecutingCycleEvent,signal:AbortSignal,token:number){
  const store=durableKey+':'+p.bindingDigest+':'+p.work.digest+':'+event.eventId+':'+event.receiptDigest,preparedKey=store+':'+event.readTargetDigest;
  if(prepared.current.has(preparedKey))return;
  const root={conversationId:conversation,bindingDigest:p.bindingDigest,workDigest:p.work.digest,eventId:event.eventId,receiptDigest:event.receiptDigest,preparationDigest:event.preparationDigest,runId:event.runId};
  let pending:Pending;const saved=readViewString(store,'read');
  if(saved){pending=JSON.parse(saved) as Pending}else{pending={identity:{...root,readTargetDigest:event.readTargetDigest,commandId:await stableCommand(preparedKey)},sent:false};persist(pending)}
  function persist(value:Pending){saveViewString(store,'read',JSON.stringify(value));if(readViewString(store,'read')!==JSON.stringify(value))throw Error('FIXED_CYCLE_READ_INTENT_NOT_SAVED')}
  for(let step=0;step<2;step++){
   if(Object.entries(root).some(([k,v])=>pending.identity[k as keyof CycleReadIdentity]!==v))throw Error('FIXED_CYCLE_READ_INTENT_MISMATCH');
   const observed=verifyReadReceipt(await readCycleAccessReceipt(pending.identity,signal),pending.identity);
   if(observed.currentReadTargetDigest!==event.readTargetDigest)throw Error('FIXED_CYCLE_READ_TARGET_CHANGED');
   if(observed.state==='READ_READY'&&observed.readTargetRelation==='SAME'&&pending.identity.readTargetDigest===event.readTargetDigest){prepared.current.add(preparedKey);return}
   if(observed.state==='READ_READY'&&observed.readTargetRelation==='STRICT_SUPERSET'&&step===0){pending={identity:{...root,readTargetDigest:event.readTargetDigest,commandId:await stableCommand(preparedKey)},previousCommandId:pending.identity.commandId,sent:false};persist(pending);continue}
   if(observed.state==='EXPIRED'&&['SAME','STRICT_SUPERSET'].includes(observed.readTargetRelation)){if(active.current&&token===epoch.current&&selectedRef.current===event.eventId)setReadExpired(true);throw Error('FIXED_CYCLE_READ_EXPIRED')}
   if(observed.state!=='NOT_PREPARED'||pending.sent||pending.identity.readTargetDigest!==event.readTargetDigest)throw Error('FIXED_CYCLE_READ_UNCONFIRMED');
   await verify(signal);if(!active.current||token!==epoch.current||signal.aborted)throw Error('FIXED_CYCLE_STALE');
   pending={...pending,sent:true};persist(pending);
   const result=verifyReadReceipt(await prepareCycleRead(pending.identity,session.csrfToken,signal,pending.previousCommandId),pending.identity);
   if(result.state!=='READ_READY'||result.currentReadTargetDigest!==event.readTargetDigest||result.readTargetRelation!=='SAME')throw Error('FIXED_CYCLE_READ_UNCONFIRMED');prepared.current.add(preparedKey);return;
  }
  throw Error('FIXED_CYCLE_READ_UNCONFIRMED');
 }
 async function refresh(cursor?:string){
  if(flight.current===epoch.current||!active.current)return;const token=epoch.current;flight.current=token;setBusy(true);const controller=new AbortController();abort.current=controller;const signal=controller.signal;
  try{
   await verify(signal);let result=verifyCyclePage(await readConversationCycles(conversation,cursor,signal),conversation);await verify(signal);if(!active.current||token!==epoch.current)return;
   if(result.state==='BOUND'){const signature=JSON.stringify([result.bindingDigest,result.work.resource_id,result.work.revision_id,result.work.digest,result.problem.resource_id,result.problem.revision_id,result.problem.digest]);if(bindingRef.current&&bindingRef.current!==signature)throw Error('FIXED_CYCLE_BOUND_TARGET_CHANGED');bindingRef.current=signature}else if(bindingRef.current)throw Error('FIXED_CYCLE_BOUND_TARGET_UNVERIFIED');
   const old=pageRef.current;
   if(cursor){if(!old||old.bindingDigest!==result.bindingDigest||JSON.stringify(old.work)!==JSON.stringify(result.work)||JSON.stringify(old.problem)!==JSON.stringify(result.problem))throw Error('FIXED_CYCLE_PAGE_CHANGED');result={...result,items:[...old.items,...result.items.filter(x=>!old.items.some(y=>y.eventId===x.eventId))]}}
   else if(old?.bindingDigest===result.bindingDigest&&JSON.stringify(old.work)===JSON.stringify(result.work))result={...result,items:[...result.items,...old.items.filter(x=>!result.items.some(y=>y.eventId===x.eventId))]};
   pageRef.current=result;setPage(result);setError('');
   if(result.state!=='BOUND'){setView(null);return}
   const newest=result.items[0];
   if(!cursor&&newest&&newest.eventId!==selectedRef.current&&newest.phase==='EXECUTION'&&newest.readState==='READ_REQUIRED'){try{await access(result,newest,signal,token)}catch{/* No automatic retry; current selection remains independent. */}}
   let event=result.items.find(x=>x.eventId===selectedRef.current);
   if(!selectedRef.current){event=result.items.find(x=>x.phase==='PLANNING'||x.readState==='READABLE')??result.items.find(x=>x.readState==='READ_REQUIRED')}
   if(!event){setView(null);setReadError(selectedRef.current?'所选运行尚未读回；不会用另一周期替代。':'');return}
   if(!selectedRef.current){selectedRef.current=event.eventId;setSelected(event.eventId);saveViewString(key,'event',event.eventId)}
   if(event.phase==='PLANNING'){if(!selectedRef.current){selectedRef.current=event.eventId;setSelected(event.eventId);saveViewString(key,'event',event.eventId)}setView(null);setReadError('');return}
   if(event.readState==='UNVERIFIED'){setView(null);setReadError('本次运行的来源或计划时间待核实。');return}
   try{await access(result,event,signal,token)}catch{if(!active.current||token!==epoch.current)return;setReadError('本次结果读取准备尚未核实；不会重新执行，可再次只读核查。');if(event.readState!=='READABLE'){setView(null);return}}
   const actual=verifyCycleExecution(await preparedRequest<ExecutionView>(event.preparationDigest,undefined,undefined,undefined,signal),event,result.problem,event.sourceSnapshot);await verify(signal);
   if(!active.current||token!==epoch.current)return;
   if(selectedRef.current&&selectedRef.current!==event.eventId)return;
   if(!selectedRef.current){selectedRef.current=event.eventId;setSelected(event.eventId);saveViewString(key,'event',event.eventId)}
   setView(actual);if(prepared.current.has(durableKey+':'+result.bindingDigest+':'+result.work.digest+':'+event.eventId+':'+event.receiptDigest+':'+event.readTargetDigest)){setReadError('');setReadExpired(false)}
  }catch{if(active.current&&token===epoch.current){setView(null);setPage(null);pageRef.current=null;prepared.current.clear();setError('周期记录暂未读取成功，原运行与结果保留。')}}finally{if(flight.current===token)flight.current=null;if(active.current&&token===epoch.current)setBusy(false)}
 }
 function deactivate(){active.current=false;epoch.current++;abort.current?.abort()}
 useEffect(()=>{active.current=true;const expired=()=>{epoch.current++;abort.current?.abort();setPage(null);setView(null);setError('登录已失效，请重新登录后读取。');active.current=false};window.addEventListener('workbench-session-expired',expired);void refresh();const timer=window.setInterval(()=>void refresh(),15000);return()=>{deactivate();clearInterval(timer);window.removeEventListener('workbench-session-expired',expired)};
 // Exact identity is supplied by the keyed parent; refreshed functions use refs.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[key,tick]);
 function select(event:string){epoch.current++;abort.current?.abort();selectedRef.current=event;setSelected(event);saveViewString(key,'event',event);setView(null);setReadError('');setTick(x=>x+1)}
 async function renewRead(){
  const p=pageRef.current,event=p?.items.find(x=>x.eventId===selectedRef.current);if(!p||!event||event.phase!=='EXECUTION'||flight.current!==null||!active.current)return;
  const token=epoch.current,controller=new AbortController();flight.current=token;abort.current=controller;setBusy(true);
  try{await verify(controller.signal);const store=durableKey+':'+p.bindingDigest+':'+p.work.digest+':'+event.eventId+':'+event.receiptDigest;const saved=JSON.parse(readViewString(store,'read')) as Pending;const result=verifyReadReceipt(await readCycleAccessReceipt(saved.identity,controller.signal),saved.identity);await verify(controller.signal);if(result.state!=='EXPIRED'||!['SAME','STRICT_SUPERSET'].includes(result.readTargetRelation)||result.currentReadTargetDigest!==event.readTargetDigest||!active.current||token!==epoch.current)throw Error('FIXED_CYCLE_READ_NOT_EXPIRED');const nextCommand=await stableCommand('renew:'+saved.identity.commandId+':'+event.readTargetDigest);if(!active.current||token!==epoch.current||controller.signal.aborted)throw Error('FIXED_CYCLE_STALE');const next={identity:{...saved.identity,readTargetDigest:event.readTargetDigest,commandId:nextCommand},previousCommandId:saved.identity.commandId,sent:false};saveViewString(store,'read',JSON.stringify(next));prepared.current.delete(store+':'+event.readTargetDigest);setReadExpired(false);setTick(x=>x+1)}catch{if(active.current&&token===epoch.current)setReadError('读取资格尚未核实，保留原请求，不创建新的执行。')}finally{if(flight.current===token)flight.current=null;if(active.current&&token===epoch.current)setBusy(false)}
 }
 return {page,selected,view,error,readError,readExpired,renewRead,busy,select,refresh:()=>{setTick(x=>x+1)},more:()=>void refresh(page?.nextCursor??undefined)};
}
