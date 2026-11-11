import {CapabilityPlanningProgress} from './CapabilityPlanningProgress';
import {readCapabilityJournal,type CapabilityJournal} from './capabilityWorkJournal';
import {useEffect,useRef,useState} from 'react';
import {capabilitySession,type CapabilityExecutionContract} from '../api/businessCapabilities';
import type {CapabilityConversationSource} from '../api/conversationActions';
import {conversationRequest} from '../api/privateConversation';
import {workbenchPrincipalKey} from '../api/digitalEmployees';
import {prepareCapabilityWork} from './prepareCapabilityWork';

export function CapabilityWorkResume({conversation,messageId,source,principal,onRefresh}:{conversation:string;messageId:string;source:CapabilityConversationSource;principal:string;onRefresh:()=>Promise<void>}){
 const [saved,setSaved]=useState<(CapabilityJournal&{viewContext:string;readContext:string})|null>(null),[refresh,setRefresh]=useState(0);
 const [readFailure,setReadFailure]=useState<string|null>(null);
 const viewContext=JSON.stringify([conversation,messageId,principal]);
 const readContext=JSON.stringify([conversation,messageId,principal,refresh]);
 const verified=saved?.readContext===readContext,failed=readFailure===readContext;
 const [busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[error,setError]=useState('');
 const flight=useRef(false),alive=useRef(true),controller=useRef<AbortController|null>(null);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;controller.current?.abort()}},[]);
 useEffect(()=>{
  const request=new AbortController();let live=true;
  void readCapabilityJournal(conversation,messageId,principal,AbortSignal.any([request.signal,AbortSignal.timeout(30_000)])).then(value=>{if(live)setSaved({...value,viewContext:JSON.stringify([conversation,messageId,principal]),readContext:JSON.stringify([conversation,messageId,principal,refresh])})}).catch(()=>{if(live){setSaved(null);setReadFailure(JSON.stringify([conversation,messageId,principal,refresh]))}});
  return()=>{live=false;request.abort()};
 },[conversation,messageId,principal,refresh]);
 async function resume(){
  if(flight.current||!verified)return;flight.current=true;setBusy(true);setNotice('');setError('');controller.current=new AbortController();
  try{
   const signal=AbortSignal.any([controller.current.signal,AbortSignal.timeout(30_000)]),session=await capabilitySession(signal);
   if(workbenchPrincipalKey(session)!==principal)throw Error('登录身份已变化，请重新读取原会话。');
   const resolved=await conversationRequest<CapabilityExecutionContract>('/'+encodeURIComponent(conversation)+'/sources/'+encodeURIComponent(messageId)+'/execution-contract',undefined,undefined,signal);
   if(resolved.contract.conversationId!==conversation||resolved.contract.sourceMessageId!==messageId||resolved.contract.scope.tenantId!==session.principal.tenantId||resolved.contract.scope.securityDomain!==session.principal.securityDomain)throw Error('本次准备的归属未能核对。');
   await prepareCapabilityWork(resolved,source,principal,signal);
   if(!alive.current)return;await onRefresh();if(alive.current){setRefresh(value=>value+1);setNotice('已核实目标和完成标准。本次核验没有调用模型或启动执行。');}
  }catch(cause){if(alive.current)setError(cause instanceof Error&&/[\u4e00-\u9fff]/.test(cause.message)?cause.message:'准备结果尚未核实，已保存记录保留。再次核验时会先读取原动作结果。')}
  finally{flight.current=false;if(alive.current)setBusy(false)}
 }
 return <div className="capability-work-resume">{!verified&&!failed&&<p role="status">正在读取已保存进展…</p>}{failed&&<p role="alert">已保存进展暂未核实，不代表工作未开始或记录丢失。请先重新读取，再继续办理。<button type="button" disabled={busy} onClick={()=>setRefresh(value=>value+1)}>重新读取已保存进展</button></p>}{saved?.state&&saved.viewContext===viewContext&&!failed&&<section aria-label="已保存的工作进度"><strong>已保存进展</strong><p>{saved.state.phase==='PREPARE_PLAN'?'目标与完成标准已保存，等待方案准备。':'后续办理记录已保留，继续前将核验实际状态。'}</p><small>这是续接记录，实际执行状态和结果以办理回执为准。</small><CapabilityPlanningProgress objective={source.target.objective} key={JSON.stringify([conversation,messageId,principal])} conversation={conversation} messageId={messageId} principal={principal} journal={saved} onRefresh={()=>{setRefresh(value=>value+1);void onRefresh().catch(()=>{if(alive.current)setError('会话消息尚未读回，已保存的工作保留。')})}}/></section>}<details key={viewContext} className="capability-preparation-recovery"><summary>准备遇到问题？</summary><p>核对已保存的目标与完成标准，不启动方案生成。需要时补齐原准备记录，不会另建一项工作。</p><button type="button" disabled={busy||!verified} onClick={()=>void resume()}>{busy?'正在核对准备记录…':'核对准备记录'}</button></details>{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}</div>;
}
