import {acceptedDelivery,readableDeliveryPackage} from './deliveryAcceptanceState';
import {useEffect,useRef,useState} from 'react';
import {readWorkbenchSession,WorkbenchRequestError} from '../api/businessWorkspace';
import {preparedRequest,type ExecutionView,type DeliveryDecision} from '../api/preparedExecution';

type Command={idempotencyKey:string;action:'ACCEPT_DELIVERY'|'RETRACT_DELIVERY';packageDigest:string;expectedVersion:number;targetEventId:string|null;reason:string};
type Pending={subject:string;digest:string;command:Command};
export function DeliveryAcceptancePanel({view}:{view:ExecutionView}){
 const [verifiedView,setVerifiedView]=useState<ExecutionView|null>(null);
 const [current,setCurrent]=useState(view),[pending,setPending]=useState<Pending|null>(null),[reason,setReason]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[subject,setSubject]=useState('');
 const epoch=useRef(0),running=useRef(false),storage=useRef('');
 useEffect(()=>{
  if(!view.deliveryAcceptance)return;
  const token=++epoch.current;let live=true;
  const expired=()=>{++epoch.current;setSubject('');setCurrent({...view,deliveryAcceptance:{status:'UNAVAILABLE'}});setError('登录已失效，请重新登录后核对原记录。')};
  window.addEventListener('workbench-session-expired',expired);
  void readWorkbenchSession().then(session=>{if(!live||token!==epoch.current)return;const p=session.principal;const identity=JSON.stringify([p.tenantId,p.securityDomain,p.principalId]);storage.current='delivery-acceptance:'+identity+':'+view.digest;setSubject(identity);setCurrent(view);setVerifiedView(view);setPending(null);try{const saved=localStorage.getItem(storage.current);if(saved){const value=JSON.parse(saved) as Pending;if(value.subject!==identity||value.digest!==view.digest||typeof value.command?.idempotencyKey!=='string')throw Error();setPending(value)}}catch{setError('原提交记录暂不可核对；请保留当前页面，不要重复提交。');setSubject('')}}).catch(()=>{if(live&&token===epoch.current)setError('当前身份暂不可核对。')});
  return()=>{live=false;epoch.current=token+1;window.removeEventListener('workbench-session-expired',expired)};
 },[view]);
 async function resolve(p:Pending,receipt:{event:DeliveryDecision}){
  const session=await readWorkbenchSession();const principal=session.principal;
  if(JSON.stringify([principal.tenantId,principal.securityDomain,principal.principalId])!==p.subject)throw Error('当前身份已变化。');
  if(receipt.event.commandKey!==p.command.idempotencyKey||!/^[a-f0-9]{64}$/.test(receipt.event.commandDigest)||receipt.event.preparationDigest!==p.digest||receipt.event.packageDigest!==p.command.packageDigest||receipt.event.action!==p.command.action||receipt.event.actorId!==JSON.parse(p.subject)[2]||receipt.event.version!==p.command.expectedVersion+1||receipt.event.targetEventId!==p.command.targetEventId)throw Error('返回记录与本次提交不一致。');
  const fresh=await preparedRequest<ExecutionView>(view.digest);
  if(fresh.digest!==p.digest)throw Error('交付版本已变化。');
  return fresh;
 }
 async function act(action:Command['action']){
  const a=current.deliveryAcceptance;if(!a||a.status==='UNAVAILABLE'||!readableDeliveryPackage(current)||running.current||pending||!subject)return;
  if(action==='RETRACT_DELIVERY'&&!reason.trim())return;
  const token=epoch.current;running.current=true;setBusy(true);setError('');
  const record:Pending={subject,digest:view.digest,command:{idempotencyKey:'delivery:'+crypto.randomUUID(),action,packageDigest:a.packageDigest,expectedVersion:a.version,targetEventId:action==='RETRACT_DELIVERY'?a.event?.eventId??null:null,reason:action==='RETRACT_DELIVERY'?reason.trim():''}};
  try{
   const session=await readWorkbenchSession();const p=session.principal;if(JSON.stringify([p.tenantId,p.securityDomain,p.principalId])!==subject||epoch.current!==token)throw Error('当前身份已变化。');
   localStorage.setItem(storage.current,JSON.stringify(record));setPending(record);
   const receipt=await preparedRequest<{event:DeliveryDecision}>(view.digest,'delivery-acceptance',session.csrfToken,record.command);
   const fresh=await resolve(record,receipt);if(epoch.current!==token)return;
   setCurrent(fresh);setPending(null);localStorage.removeItem(storage.current);setReason('');
  }catch(e){
   if(epoch.current!==token)return;
   if(e instanceof WorkbenchRequestError&&e.status===409&&['DELIVERY_TARGET_CHANGED','DELIVERY_ALREADY_ACCEPTED','DELIVERY_RETRACTION_NOT_ALLOWED'].includes(e.reasonCode)){
    try{const fresh=await preparedRequest<ExecutionView>(view.digest);if(epoch.current!==token)return;if(fresh.digest!==record.digest)throw Error('返回交付版本不一致。',{cause:e});setCurrent(fresh);setPending(null);localStorage.removeItem(storage.current);setError('本次提交未生效，交付内容或接受记录已变化。已重新读取，请核对后再决定。')}catch{if(epoch.current===token)setError('本次提交未生效，当前记录仍不可读取；请先核对原记录。')}
   }else setError('提交结果暂不可核对，请读取原记录，不要重复提交。');
  }
  finally{running.current=false;if(epoch.current===token)setBusy(false)}
 }
 async function recover(){
  if(!pending||running.current||!subject)return;const token=epoch.current;running.current=true;setBusy(true);setError('');
  try{
   const response=await fetch(`/api/workbench/v1/prepared-executions/${encodeURIComponent(view.digest)}/delivery-acceptance/commands/${encodeURIComponent(pending.command.idempotencyKey)}`,{credentials:'same-origin',headers:{Accept:'application/json'}});const body=await response.json();if(!response.ok)throw Error('原提交结果仍不可核对，请勿重复提交。');
   const fresh=await resolve(pending,body.result);if(epoch.current!==token)return;setCurrent(fresh);setPending(null);localStorage.removeItem(storage.current);
  }catch{if(epoch.current===token)setError('原提交结果仍不可核对，请勿重复提交。')}
  finally{running.current=false;if(epoch.current===token)setBusy(false)}
 }
 if(!view.deliveryAcceptance)return null;
 if(verifiedView!==view)return <section className="f3-work-card" aria-label="本次交付接受"><p>{error||'正在核对交付接受状态…'}</p></section>;
 const projected=current.deliveryAcceptance;if(!projected)return null;
 const a=projected.status==='UNAVAILABLE'||!readableDeliveryPackage(current)||(projected.status==='ACCEPTED'&&!acceptedDelivery(current))?{status:'UNAVAILABLE' as const}:projected;
 return <section className="f3-work-card" aria-label="本次交付接受"><h3>本次交付接受</h3><p>接受这份交付内容及已列明限制，不代表业务问题已解决或批准上线。</p>{a.status==='UNAVAILABLE'?<p>接受状态暂不可读取，不能据此判断是否已接受。</p>:<><p>{acceptedDelivery(current)?'已接受本次交付':a.status==='RETRACTED'?'已撤回接受；阶段记录仍保留。':a.status==='SUPERSEDED'?'交付内容已变化，旧接受不适用于本次交付。':'本次交付尚未接受；无需确认也可阅读和保存结果。'}</p><p>本次包含 {a.package.snapshot.artifacts.length} 份已保存产物。</p><p>适用限制：合成资料，不证明真实业务问题已解决。{current.progress?.state!=='SUCCEEDED'?'本次执行未成功完成，仅接受当前已保存的阶段内容。':''}</p><details><summary>本包全部已列明限制</summary>{a.package.limitations.map(x=><p key={x}>{({SYNTHETIC_ONLY:'仅合成资料',REAL_BUSINESS_OUTCOME_UNPROVEN:'不证明真实业务结果',RESOURCE_USE_SNAPSHOT_MISSING:'缺少资源使用快照',EXECUTION_FAILED:'执行失败，仅包含已保存的阶段内容',EXECUTION_CANCELLED:'执行已取消，仅包含已保存的阶段内容'} as Record<string,string>)[x]??x}</p>)}</details>{!pending&&subject&&a.canAccept===true&&<button disabled={busy} onClick={()=>void act('ACCEPT_DELIVERY')}>接受本次交付</button>}{!pending&&subject&&a.canRetract===true&&<details><summary>撤回本次接受</summary><label>撤回理由<textarea value={reason} onChange={e=>setReason(e.target.value)} maxLength={1000}/></label><button disabled={busy||!reason.trim()} onClick={()=>void act('RETRACT_DELIVERY')}>撤回接受</button></details>}{a.event&&<details><summary>查看接受记录</summary><p>{a.event.actorId} · {a.event.createdAt}</p><p>{a.event.reason}</p><code>{a.event.eventId}</code></details>}</>}{pending&&<><p>本次提交结果尚待核对；只读取原结果，不会再次提交。</p><button disabled={busy||!subject} onClick={()=>void recover()}>读取原接受结果</button></>}{error&&<p role="alert">{error}</p>}</section>;
}
