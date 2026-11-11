import {useEffect,useRef,useState} from 'react';
import {BusinessProcessRequestError,withdrawBusinessCapabilityRelation,readBusinessRelationWithdrawalReceipt,type BusinessRelationEntry,type BusinessRelationWithdrawalCommand} from '../api/businessProcesses';
import type {BusinessRelationAccess} from './useBusinessRelationAccess';
export function BusinessRelationWithdrawal({entry,access,onSaved,allowNew=true}:{allowNew?:boolean;entry:BusinessRelationEntry;access:BusinessRelationAccess;onSaved:()=>void}){
 const {principal,allowed,signal}=access;
 const [opened,setOpened]=useState(false),[reason,setReason]=useState(''),[pending,setPending]=useState<BusinessRelationWithdrawalCommand|null>(null),[retry,setRetry]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[invalid,setInvalid]=useState(false);
 const request=useRef<AbortController|null>(null),key=useRef(''),running=useRef(false);
 const {relationId,relationRevisionId,relationVersion,digest}=entry;
 useEffect(()=>{
  const controller=new AbortController();request.current=controller;let active=true;
  const expire=()=>{controller.abort();setOpened(false);setReason('');setPending(null);setError('')};
  if(signal?.aborted)controller.abort();else signal?.addEventListener('abort',expire,{once:true});
  void Promise.resolve().then(()=>{
   if(!active||!principal||controller.signal.aborted)return;
   try{key.current='business-relation-withdrawal:v1:'+JSON.stringify([principal,relationId,relationRevisionId]);const raw=sessionStorage.getItem(key.current),command=raw?JSON.parse(raw) as BusinessRelationWithdrawalCommand:null;
    if(command&&(command.relationId!==relationId||command.relationRevisionId!==relationRevisionId||command.expectedVersion!==relationVersion||command.digest!==digest||typeof command.reason!=='string'||!command.reason.trim()||command.reason.length>2000||typeof command.commandId!=='string'||!command.commandId))throw Error('INVALID_COMMAND');
    setPending(command);setRetry(false);if(command)setOpened(true);
   }catch{setInvalid(true);setError('原撤回记录无法核对，请保留原记录，不要重复提交。')}
  });
  return()=>{active=false;controller.abort();signal?.removeEventListener('abort',expire)};
 },[principal,signal,relationId,relationRevisionId,relationVersion,digest]);
 async function run(mode:'withdraw'|'read'|'retry'){
  const controller=request.current;if(!controller||controller.signal.aborted||running.current||!principal||invalid||(mode!=='read'&&!allowed))return;
  let command=pending;running.current=true;setBusy(true);setError('');
  try{
   if(!command){if(mode!=='withdraw'||!allowNew||entry.withdrawal||!reason.trim())return;command={relationId,relationRevisionId,expectedVersion:relationVersion,digest,reason:reason.trim(),commandId:'business-relation-withdraw:'+crypto.randomUUID()};sessionStorage.setItem(key.current,JSON.stringify(command));setPending(command)}
   const result=mode==='read'?await readBusinessRelationWithdrawalReceipt(command.commandId,principal,controller.signal):await withdrawBusinessCapabilityRelation(command,principal,controller.signal);
   if(controller.signal.aborted)return;
   if(result.relationId!==command.relationId||result.relationRevisionId!==command.relationRevisionId||result.relationVersion!==command.expectedVersion||result.digest!==command.digest||result.reason!==command.reason||result.state!=='WITHDRAWN'||result.executionAuthorized!==false)throw new BusinessProcessRequestError('INVALID_RECEIPT',503,true);
   sessionStorage.removeItem(key.current);setPending(null);setRetry(false);setReason('');setOpened(false);onSaved();
  }catch(cause){if(controller.signal.aborted)return;
   if(mode==='read'){setRetry(cause instanceof BusinessProcessRequestError&&cause.code==='BUSINESS_RELATION_WITHDRAWAL_NOT_FOUND');setError('原撤回结果尚未核实，不会自动再次提交。')}
   else if(mode==='withdraw'&&cause instanceof BusinessProcessRequestError&&!cause.outcomeUnknown){sessionStorage.removeItem(key.current);setPending(null);setError(cause.code==='BUSINESS_RELATION_VERSION_CONFLICT'?'关系已有新修订，请重新读取后再决定是否撤回。':'撤回未完成，请核对当前关系状态与维护权限。')}
   else setError('撤回结果尚未核实，已保留原提交。请先核实原撤回。');
  }finally{running.current=false;if(!controller.signal.aborted)setBusy(false)}
 }
 if(!principal||(!pending&&!invalid&&(entry.withdrawal||!allowed||!allowNew)))return null;
 return <section className="bp-relations" aria-label="撤回能力关联">
  {!opened&&!invalid?<button onClick={()=>setOpened(true)}>撤回此关联</button>:<><h3>撤回能力关联</h3><p>撤回后保留原关系版本供追溯，不能继续修订此关系；不会撤销已完成的工作。</p>
   {pending?<><p>原撤回原因：{pending.reason}</p><button disabled={busy} onClick={()=>void run('read')}>核实原撤回</button>{retry&&allowed&&<button disabled={busy} onClick={()=>void run('retry')}>重试同一份撤回</button>}</>:!invalid&&allowed&&<><label>撤回原因<textarea aria-label="撤回原因" maxLength={2000} value={reason} disabled={busy} onChange={event=>setReason(event.target.value)}/></label><button disabled={busy||!reason.trim()} onClick={()=>void run('withdraw')}>确认撤回关联</button><button disabled={busy} onClick={()=>setOpened(false)}>保留关联</button></>}
   {busy&&<p role="status">正在提交或核实撤回…</p>}{error&&<p role="alert">{error}</p>}
  </>}
 </section>;
}
