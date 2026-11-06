import {useEffect,useRef,useState} from 'react';
import {readWorkbenchSession,WorkbenchRequestError} from '../api/businessWorkspace';

type Usage={schemaVersion:string;measurement?:{usage?:{input_tokens?:number;output_tokens?:number}};settlement?:{status?:string;reservation_retained?:boolean}|null;localCleanup?:{stage?:string;reaped?:boolean;decision_seconds?:number};remoteCancellation?:string;providerInvoice?:string};
const stages:Record<string,string>={WAIT_HEADERS:'等待响应头',READ_BODY:'读取响应',VALIDATE_RESPONSE:'核验响应',PREPARE:'准备请求',CONNECT:'连接',SEND_REQUEST:'发送请求'};
export function PlanningCallEvidence({invocationId}:{invocationId:string}){
 const [value,setValue]=useState<Usage|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const mounted=useRef(false),epoch=useRef(0),scope=useRef<string|null>(null),abort=useRef<AbortController|null>(null);
 useEffect(()=>{let active=true;mounted.current=true;epoch.current++;const withdraw=()=>{scope.current=null;abort.current?.abort();epoch.current++;setValue(null);setBusy(false);setError('登录状态已变化，请核对原账号后读取。')};
  const verify=()=>{if(!scope.current)return;const expected=scope.current;void readWorkbenchSession(AbortSignal.timeout(8000)).then(s=>{if(active&&JSON.stringify(s.principal)!==expected)withdraw()}).catch(()=>{if(active)withdraw()})};
  window.addEventListener('workbench-session-expired',withdraw);window.addEventListener('focus',verify);
  return()=>{active=false;mounted.current=false;abort.current?.abort();window.removeEventListener('workbench-session-expired',withdraw);window.removeEventListener('focus',verify)};
 },[invocationId]);
 async function read(){
  if(busy)return;const token=++epoch.current;setBusy(true);setError('');setValue(null);
  const controller=new AbortController();abort.current=controller;const timer=window.setTimeout(()=>controller.abort(),8000);
  try{
   const before=await readWorkbenchSession(controller.signal),expected=JSON.stringify(before.principal);scope.current=expected;
   if(!mounted.current||token!==epoch.current)return;
   const response=await fetch('/api/workbench/v1/planning-v2/invocations/'+encodeURIComponent(invocationId)+'/usage',{credentials:'same-origin',headers:{Accept:'application/json'},signal:controller.signal});
   const body=await response.json();if(response.status===401)window.dispatchEvent(new Event('workbench-session-expired'));if(!response.ok)throw new WorkbenchRequestError(body.reasonCode??'PROVIDER_USAGE_NOT_FOUND',response.status);
   const after=await readWorkbenchSession(controller.signal);if(JSON.stringify(after.principal)!==expected)throw Error('CALL_EVIDENCE_IDENTITY_CHANGED');
   if(!mounted.current||token!==epoch.current)return;
   if(body.result?.schemaVersion!=='provider-usage-read.v1')throw Error('CALL_EVIDENCE_UNVERIFIED');setValue(body.result);
  }catch(e){if(mounted.current&&token===epoch.current)setError(e instanceof WorkbenchRequestError&&[403,404].includes(e.status)?'当前未取得这次本地回执的读取权限或可读记录；原调用与预留仍保留，不能认定零费用。':e instanceof Error&&e.message==='CALL_EVIDENCE_IDENTITY_CHANGED'?'登录身份已变化，已撤下原回执，请核对原账号。':'本地回执尚未读回；保留原调用，不会重新派发。')}
  finally{window.clearTimeout(timer);if(mounted.current&&token===epoch.current)setBusy(false)}
 }
 const settled=value?.settlement?.status==='ESTIMATE_SETTLED'&&value.settlement.reservation_retained===false;
 const pending=value?.settlement?.status==='PENDING_RECONCILIATION'&&value.settlement.reservation_retained===true;
 return <section aria-label="原调用本地回执与计量"><h3>本次调用依据</h3><p>按独立读取权限核对平台保存的回执；不发起模型调用。</p><button disabled={busy} onClick={()=>void read()}>{busy?'正在读取本地回执…':'读取本地回执与计量'}</button>{error&&<p role="status">{error}</p>}{value&&<>
  <p>本地进程：{value.localCleanup?.reaped===true?'已回收':'当前未取得已回收证明'}。{value.localCleanup?.stage&&`回执阶段：${stages[value.localCleanup.stage]??'见原回执'}。`}{typeof value.localCleanup?.decision_seconds==='number'&&`原判定耗时约${value.localCleanup.decision_seconds.toFixed(2)}秒。`}</p>
  {settled?<p>本地估算结算记录已保存{typeof value.measurement?.usage?.input_tokens==='number'&&`；输入 ${value.measurement.usage.input_tokens} Token`}{typeof value.measurement?.usage?.output_tokens==='number'&&`，输出 ${value.measurement.usage.output_tokens} Token`}。有效计量不代表方案有效或业务通过。</p>:pending?<p>尚未取得可结算计量，原预算预留保持。不能认定远端未处理或零费用。</p>:<p>计量结算状态尚未核实，不能认定已结算、预留已释放或零费用。</p>}
  <p>本地回收不能证明远端取消；供应商账单尚未核实。</p>
 </>}</section>;
}
