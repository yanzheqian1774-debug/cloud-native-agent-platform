import {useEffect,useEffectEvent,useRef,useState} from 'react';
import {planningRequest,type Invocation} from '../planning/planningRequests';
import type {ModelProgress} from '../api/modelStream';

type Recovery={state:string;recovery_id?:string;new_request_key?:string;original_outcome:string};
/** All mount/refresh paths are reads. A new call needs a separate signed request. */
export function ConversationPlanningRecovery({conversation,requestKey,principal,onResult,onProgress,onStatus}:{conversation:string;requestKey:string;principal:string;onResult:(value:Invocation,requestKey:string)=>Promise<void>;onProgress:(value:ModelProgress)=>void;onStatus:(state:string)=>void}){
 const [status,setStatus]=useState<Recovery|null>(null),[old,setOld]=useState<Invocation|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[progress,setProgress]=useState<ModelProgress|null>(null);
 const flight=useRef(false),live=useRef(true);
 const publish=(value:Recovery)=>{setStatus(value);onStatus(value.state)};
 const expected=()=>({principal,isCurrent:()=>live.current});
 async function read(){
  const original=await planningRequest<Invocation>('planning-v2/requests/'+encodeURIComponent(requestKey)+'/read-only',undefined,{},expected());
  if(!live.current)return;
  if(!original?.result?.technical_status||!original.invocation?.target?.invocation_id)return;
  setOld(original);
  if(original.result.technical_status!=='OUTCOME_UNKNOWN')return;
  const value=await planningRequest<Recovery>('planning-v2/recoveries/for-invocation/'+encodeURIComponent(original.invocation.target.invocation_id)+'?conversation_id='+encodeURIComponent(conversation),undefined,{},expected());
  if(live.current)publish(value);
 }
 const readEffect=useEffectEvent(read);
 useEffect(()=>{live.current=true;Promise.resolve().then(readEffect).catch(e=>{if(live.current)setError(String(e))});return()=>{live.current=false}},[conversation,requestKey,principal]);
 const refreshEffect=useEffectEvent(async()=>{if(flight.current)return;try{await read()}catch(e){if(live.current){setError(String(e));onStatus('READ_UNAVAILABLE')}}});
 useEffect(()=>{if(!['OBSERVED','AUTHORIZATION_PENDING'].includes(status?.state??''))return;let active=true;let timer:ReturnType<typeof setTimeout>;const tick=async()=>{await refreshEffect();if(active)timer=setTimeout(tick,5000)};timer=setTimeout(tick,5000);return()=>{active=false;clearTimeout(timer)}},[status?.state]);
 async function act(kind:'read'|'prepare'|'continue'){
  if(flight.current||!old)return;flight.current=true;setBusy(true);setError('');
  try{
   if(kind==='read')await read();
   if(kind==='prepare'){
    const value=await planningRequest<Recovery>('planning-v2/recoveries',{conversation_id:conversation,invocation_id:old.invocation.target.invocation_id,idempotency_key:'recover:'+old.invocation.target.invocation_id},{},expected());
    if(live.current)publish(value);
   }
   if(kind==='continue'&&status?.recovery_id){
    onStatus('CONTINUING');
    const value=status.state==='DISPATCHED'
     ?await planningRequest<Invocation>('planning-v2/requests/'+encodeURIComponent(status.new_request_key!)+'/read-only',undefined,{},expected())
     :await planningRequest<Invocation>('planning-v2/recoveries/'+encodeURIComponent(status.recovery_id)+'/continue',{}, {},expected(),p=>{if(live.current){setProgress(p);onProgress(p)}});
    if(value.result.technical_status==='AUTHORIZATION_PENDING'){await read();return;}
    if(!status.new_request_key)throw Error('本次处理的记录尚未核实，请重新读取处理进展。');
    if(live.current)await onResult(value,status.new_request_key);
   }
  }catch(e){if(live.current){setError(String(e));onStatus('READ_UNAVAILABLE')}}finally{flight.current=false;if(live.current)setBusy(false)}
 }
 if(!old||old.result.technical_status!=='OUTCOME_UNKNOWN')return error?<p role="status">暂时无法核对原请求，请稍后刷新。</p>:null;
 return <section aria-label="继续原问题" aria-busy={busy}><h3>{busy?'正在处理恢复请求':['OBSERVED','AUTHORIZATION_PENDING'].includes(status?.state??'')?'恢复申请已提交':status?.state==='AUTHORIZED'?'已可继续原问题':'原问题已保留'}</h3>{busy&&<p role="status">正在处理，请稍候。已有进展会持续呈现。</p>}{busy&&progress?.preview&&<p style={{whiteSpace:'pre-wrap'}}>{progress.preview}</p>}<details><summary>上次处理详情</summary><p>上次方案准备的结果尚未确认。原记录和费用占用会保留，不会自动重发。</p></details>{status?.state==='UNSUPPORTED'&&<p>本次属于已有方案的后继调整，暂不支持此恢复方式，已保留原记录供管理员核查。</p>}{status?.state==='NOT_REQUESTED'&&<button disabled={busy} onClick={()=>void act('prepare')}>申请继续原问题</button>}{['OBSERVED','AUTHORIZATION_PENDING'].includes(status?.state??'')&&<p role="status">恢复申请已提交，等待核对；当前无需操作。</p>}{status?.state==='AUTHORIZED'&&<button disabled={busy} onClick={()=>void act('continue')}>继续原问题</button>}{status?.state==='DISPATCHED'&&<button disabled={busy} onClick={()=>void act('continue')}>读取本次处理结果</button>}<button className="secondary" disabled={busy} onClick={()=>void act('read')}>读取处理进展</button>{error&&<p role="alert">{error}</p>}</section>;
}
