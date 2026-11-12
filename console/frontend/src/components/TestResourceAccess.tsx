import {useEffect, useState, type ReactNode} from 'react';
import {readWorkbenchSession} from '../api/businessWorkspace';

type State = {kind:'checking'|'recovering'|'ready'|'partial'|'unknown'; detail?:string; renewal?:{marker:string;key:string}};
type Receipt = {policyDigest:string;items:{state:string}[]};
const pending = new Map<string, Promise<Receipt>>();
const prefix = '/api/workbench/v1/test-resource-access';
async function json<T>(path:string, init?:RequestInit):Promise<T> {
  const response = await fetch(prefix+path, {credentials:'same-origin', signal:AbortSignal.timeout(15000), ...init});
  if (!response.ok) throw Object.assign(new Error('RESOURCE_ACCESS_UNAVAILABLE'), {status:response.status});
  const value = await response.json();
  return value.result as T;
}

/** An interrupted request retains its original key; no execution or model calls. */
export function TestResourceAccess({identity, children}:{identity:string|null;children:ReactNode}) {
  const [state,setState] = useState<State>({kind:'checking'});
  const [retry,setRetry] = useState(0);
  useEffect(()=>{
    if(!identity)return;
    let active = true;
    let checkingAvailability = true;
    const run = async()=>{
      try {
        const session = await readWorkbenchSession();
        if(session.principal.principalId!==identity) throw Error('IDENTITY_CHANGED');
        const scope = JSON.stringify(session.principal);
        const status = await json<{available:boolean;policyDigest?:string}>('/status');
        checkingAvailability = false;
        if(!active) return;
        if(!status.available){setState({kind:'ready'});return;}
        if(!status.policyDigest) throw Error('POLICY_MISSING');
        const marker = 'test-resource-read:'+scope+':'+status.policyDigest;
        let key = sessionStorage.getItem(marker);
        if(!key){key=crypto.randomUUID();sessionStorage.setItem(marker,key);}
        let request = pending.get(marker);
        if(!request){
          request = (async()=>{
            const current = await readWorkbenchSession();
            if(JSON.stringify(current.principal)!==scope) throw Error('IDENTITY_CHANGED');
            return json<Receipt>('/prepare', {method:'POST',headers:{'Content-Type':'application/json','x-csrf-token':current.csrfToken},body:JSON.stringify({idempotencyKey:key})});
          })();
          pending.set(marker,request);
          void request.finally(()=>pending.delete(marker)).catch(()=>{});
        }
        const result = await request;
        const current = await readWorkbenchSession();
        if(JSON.stringify(current.principal)!==scope || result.policyDigest!==status.policyDigest) throw Error('IDENTITY_CHANGED');
        if(!active)return;
        const unavailable = result.items.filter(item=>!['APPROVED','EFFECTIVE'].includes(item.state)).length;
        setState(unavailable?{kind:'partial',detail:`有 ${unavailable} 项测试资源暂不可读取，其他页面可继续使用。`,...(result.items.some(item=>item.state==='EXPIRED')?{renewal:{marker,key}}:{})}:{kind:'ready'});
      } catch(error) {
        if(!active)return;
        // A missing optional server route means this deployment has no policy.
        if(checkingAvailability && (error as {status?:number}).status===404) setState({kind:'ready'});
        else setState({kind:'unknown',detail:'测试资源准备结果尚未核实。可以核对原请求，或继续使用已有权限。'});
      }
    };
    void run();
    return()=>{active=false;};
  },[identity,retry]);
  if(state.kind==='checking')return <p className="journey-test-source" role="status">{identity?'正在准备可用的测试资源…':'正在核对登录状态，请稍候或使用右上角登录入口。'}</p>;
  return <>{state.kind!=='ready'&&<div className="journey-test-source" role="status"><span>{state.detail}</span>{state.kind==='unknown'&&<button type="button" onClick={()=>{setState({kind:'recovering',detail:'正在核对原请求…'});setRetry(value=>value+1);}}>核对原请求</button>}{state.renewal&&<button type="button" onClick={()=>{const renewal=state.renewal;if(!renewal)return;if(sessionStorage.getItem(renewal.marker)===renewal.key)sessionStorage.removeItem(renewal.marker);setState({kind:'recovering',detail:'正在重新准备已过期的测试资源…'});setRetry(value=>value+1);}}>重新准备已过期资源</button>}</div>}{children}</>;
}
