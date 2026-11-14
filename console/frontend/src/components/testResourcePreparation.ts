import {readWorkbenchSession} from '../api/businessWorkspace';

export type ResourceAccessState={kind:'checking'|'recovering'|'ready'|'partial'|'unknown';detail?:string;renewal?:{marker:string;key:string};updated?:{pointer:string;original:string}};
type Receipt={policyDigest:string;selectionDigest?:string;items:{state:string}[]};
type Status={available:boolean;policyDigest?:string;selectionDigest?:string};
const pending=new Map<string,Promise<ResourceAccessState>>();
const prefix='/api/workbench/v1/test-resource-access';
export const resourceAccessChanged='conversation-resource-read-preparation';
async function json<T>(path:string,init?:RequestInit):Promise<T>{
 const response=await fetch(prefix+path,{credentials:'same-origin',signal:AbortSignal.timeout(init?.method==='POST'?60000:15000),...init});
 if(!response.ok)throw Object.assign(Error('RESOURCE_ACCESS_UNAVAILABLE'),{status:response.status});
 return (await response.json()).result as T;
}
async function successor(scope:string,key:string,policy:string,selection?:string){
 const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify([scope,key,policy,selection??null])));
 const suffix=Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');
 return (selection?'published:'+selection+':':'read-renewal:')+suffix;
}

async function prepare(scope:string):Promise<ResourceAccessState>{
 let checkingAvailability=true;
 const scopePointer='test-resource-read:'+scope+':pending-policy';
 try{
  const sameSession=async()=>{const value=await readWorkbenchSession();if(JSON.stringify(value.principal)!==scope)throw Error('IDENTITY_CHANGED');return value};
  const status=await json<Status>('/status');checkingAvailability=false;
  await sameSession();
  const pendingPolicy=sessionStorage.getItem(scopePointer);
  if(pendingPolicy&&(!status.available||JSON.parse(pendingPolicy).policyDigest!==status.policyDigest))throw Error('PENDING_POLICY_CHANGED');
  if(!status.available)return {kind:'ready'};
  if(!status.policyDigest)throw Error('POLICY_MISSING');
  const selection=status.selectionDigest;
  if(selection!==undefined&&!/^[a-f0-9]{64}$/.test(selection))throw Error('SELECTION_INVALID');
  const baseMarker='test-resource-read:'+scope+':'+status.policyDigest;
  const pointer=baseMarker+':unresolved',original=sessionStorage.getItem(pointer);
  if(original){const saved=JSON.parse(original) as {selectionDigest?:string;key?:string};
   if(!saved.selectionDigest||!saved.key)throw Error('PENDING_INVALID');
   if(saved.selectionDigest!==selection)return {kind:'partial',detail:'资料版本已更新。上次读取结果尚未核实，未重新提交；可继续使用已有权限，或读取新版资料。',updated:{pointer,original}};
  }
  const marker=baseMarker+(selection?':selection:'+selection:'');
  const automaticMarker=marker+':automatic-renewal';
  let key=sessionStorage.getItem(marker);
  if(!key){key=(selection?'published:'+selection+':':'')+crypto.randomUUID();sessionStorage.setItem(marker,key)}
  for(let attempt=0;attempt<2;attempt++){
   const current=await sameSession();
   if(selection){const unresolved=JSON.stringify({selectionDigest:selection,key});sessionStorage.setItem(pointer,unresolved);sessionStorage.setItem(marker+':unresolved',unresolved)}
   sessionStorage.setItem(scopePointer,JSON.stringify({policyDigest:status.policyDigest,key}));
   const result=await json<Receipt>('/prepare',{method:'POST',headers:{'Content-Type':'application/json','x-csrf-token':current.csrfToken},body:JSON.stringify({idempotencyKey:key,...(selection?{expectedSelectionDigest:selection}:{})})});
   await sameSession();
   if(result.policyDigest!==status.policyDigest||result.selectionDigest!==selection||!Array.isArray(result.items)||result.items.some(item=>!item||typeof item.state!=='string'))throw Error('RECEIPT_INVALID');
   if(selection&&result.items.every(item=>['APPROVED','EFFECTIVE','EXPIRED','REVOKED','DENIED'].includes(item.state))){const unresolved=JSON.stringify({selectionDigest:selection,key});if(sessionStorage.getItem(pointer)===unresolved)sessionStorage.removeItem(pointer);sessionStorage.removeItem(marker+':unresolved')}
   if(result.items.every(item=>['APPROVED','EFFECTIVE','EXPIRED','REVOKED','DENIED'].includes(item.state))&&sessionStorage.getItem(scopePointer)===JSON.stringify({policyDigest:status.policyDigest,key}))sessionStorage.removeItem(scopePointer);
   const unavailable=result.items.filter(item=>!['APPROVED','EFFECTIVE'].includes(item.state));
   if(!unavailable.length){sessionStorage.removeItem(automaticMarker);return {kind:'ready'}}
   // Only an exact completed EXPIRED receipt can open one successor. Unknown,
   // denial/revocation or another selection never become a new automatic request.
   if(attempt===0&&sessionStorage.getItem(automaticMarker)!==key&&unavailable.every(item=>item.state==='EXPIRED')){
    const observed=await json<Status>('/status');await sameSession();
    if(!observed.available||observed.policyDigest!==status.policyDigest||observed.selectionDigest!==selection)throw Error('SELECTION_CHANGED');
    const next=await successor(scope,key,status.policyDigest,selection);
    await sameSession();
    sessionStorage.setItem(automaticMarker,next);sessionStorage.setItem(marker,next);key=next;
    continue;
   }
   return {kind:'partial',detail:`有 ${unavailable.length} 项测试资源暂不可读取，其他页面可继续使用。`,...(result.items.some(item=>item.state==='EXPIRED')?{renewal:{marker,key}}:{})};
  }
  throw Error('READ_PREPARATION_UNRESOLVED');
 }catch(error){
  if(checkingAvailability&&!sessionStorage.getItem(scopePointer)&&(error as {status?:number}).status===404)return {kind:'ready'};
  return {kind:'unknown',detail:'测试资源准备结果尚未核实。可以核对原请求，或继续使用已有权限。'};
 }
}

/** Shared by shell and conversation. No model, work creation, or execution endpoint. */
export async function ensureTestResourceAccess(identity:string,expectedPrincipal?:unknown):Promise<ResourceAccessState>{
 const session=await readWorkbenchSession();
 const scope=JSON.stringify(session.principal);
 if(session.principal.principalId!==identity||(expectedPrincipal&&scope!==JSON.stringify(expectedPrincipal)))throw Error('IDENTITY_CHANGED');
 let request=pending.get(scope);
 if(!request){request=prepare(scope);pending.set(scope,request);void request.finally(()=>pending.delete(scope)).catch(()=>{})}
 const result=await request;
 window.dispatchEvent(new CustomEvent(resourceAccessChanged,{detail:{scope,state:result}}));
 return result;
}

export async function ensureConversationResourceReads(principal:{principalId:string}){
 if(import.meta.env.VITE_TEST_RESOURCE_READ_ENABLED!=='true')return;
 // Inventory preparation is advisory. Only the original exact work owner can
 // decide whether this work has every required current READ permission.
 return ensureTestResourceAccess(principal.principalId,principal);
}
