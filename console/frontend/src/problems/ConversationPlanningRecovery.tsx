import {useEffect,useEffectEvent,useRef,useState} from 'react';
import {planningRequest,type Invocation} from '../planning/planningRequests';
import type {ModelProgress} from '../api/modelStream';

type Recovery={state:string;recovery_id?:string;new_request_key?:string;original_outcome:string};
/** All mount/refresh paths are reads. A new call needs a separate signed request. */
export function ConversationPlanningRecovery({conversation,requestKey,principal,onResult,onProgress}:{conversation:string;requestKey:string;principal:string;onResult:(value:Invocation)=>Promise<void>;onProgress:(value:ModelProgress)=>void}){
 const [status,setStatus]=useState<Recovery|null>(null),[old,setOld]=useState<Invocation|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[progress,setProgress]=useState<ModelProgress|null>(null);
 const flight=useRef(false),live=useRef(true);
 const expected=()=>({principal,isCurrent:()=>live.current});
 async function read(){
  const original=await planningRequest<Invocation>('planning-v2/requests/'+encodeURIComponent(requestKey)+'/read-only',undefined,{},expected());
  if(!live.current)return;
  if(!original?.result?.technical_status||!original.invocation?.target?.invocation_id)return;
  setOld(original);
  if(original.result.technical_status!=='OUTCOME_UNKNOWN')return;
  const value=await planningRequest<Recovery>('planning-v2/recoveries/for-invocation/'+encodeURIComponent(original.invocation.target.invocation_id)+'?conversation_id='+encodeURIComponent(conversation),undefined,{},expected());
  if(live.current)setStatus(value);
 }
 const readEffect=useEffectEvent(read);
 useEffect(()=>{live.current=true;Promise.resolve().then(readEffect).catch(e=>{if(live.current)setError(String(e))});return()=>{live.current=false}},[conversation,requestKey,principal]);
 async function act(kind:'read'|'prepare'|'continue'){
  if(flight.current||!old)return;flight.current=true;setBusy(true);setError('');
  try{
   if(kind==='read')await read();
   if(kind==='prepare'){
    const value=await planningRequest<Recovery>('planning-v2/recoveries',{conversation_id:conversation,invocation_id:old.invocation.target.invocation_id,idempotency_key:'recover:'+old.invocation.target.invocation_id},{},expected());
    if(live.current)setStatus(value);
   }
   if(kind==='continue'&&status?.recovery_id){
    const value=status.state==='DISPATCHED'
     ?await planningRequest<Invocation>('planning-v2/requests/'+encodeURIComponent(status.new_request_key!)+'/read-only',undefined,{},expected())
     :await planningRequest<Invocation>('planning-v2/recoveries/'+encodeURIComponent(status.recovery_id)+'/continue',{}, {},expected(),p=>{if(live.current){setProgress(p);onProgress(p)}});
    if(value.result.technical_status==='AUTHORIZATION_PENDING'){await read();return;}
    if(live.current)await onResult(value);
   }
  }catch(e){if(live.current)setError(String(e))}finally{flight.current=false;if(live.current)setBusy(false)}
 }
 if(!old||old.result.technical_status!=='OUTCOME_UNKNOWN')return error?<p role="status">暂时无法核对原请求，请稍后刷新。</p>:null;
 return <section aria-label="继续原问题" aria-busy={busy}><h3>原问题已保留</h3>{busy&&<p role="status">正在处理，请稍候。已有进展会持续呈现。</p>}{busy&&progress?.preview&&<p style={{whiteSpace:'pre-wrap'}}>{progress.preview}</p>}<p>上次方案准备的结果尚未确认。原记录和费用占用会保留，平台会核对是否可以单独安排一次新的处理。</p>{status?.state==='UNSUPPORTED'&&<p>本次属于已有方案的后继调整，暂不支持此恢复方式，已保留原记录供管理员核查。</p>}{status?.state==='NOT_REQUESTED'&&<button disabled={busy} onClick={()=>void act('prepare')}>申请继续原问题</button>}{['OBSERVED','AUTHORIZATION_PENDING'].includes(status?.state??'')&&<p role="status">已提交处理请求，正在等待管理员核对。不会自动重复执行。</p>}{status?.state==='AUTHORIZED'&&<button disabled={busy} onClick={()=>void act('continue')}>继续原问题</button>}{status?.state==='DISPATCHED'&&<button disabled={busy} onClick={()=>void act('continue')}>读取本次处理结果</button>}<button disabled={busy} onClick={()=>void act('read')}>读取处理进展</button>{error&&<p role="alert">{error}</p>}</section>;
}
