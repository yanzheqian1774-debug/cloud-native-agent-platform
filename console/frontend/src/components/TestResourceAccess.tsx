import {useEffect, useState, type ReactNode} from 'react';
import {readWorkbenchSession} from '../api/businessWorkspace';

import {ensureTestResourceAccess,resourceAccessChanged,type ResourceAccessState as State} from './testResourcePreparation';

/** An interrupted request retains its original key; no execution or model calls. */
export function TestResourceAccess({identity, children}:{identity:string|null;children:ReactNode}) {
  const [state,setState] = useState<State>({kind:'checking'});
  const [retry,setRetry] = useState(0);
  useEffect(()=>{
    if(!identity)return;
    let active = true;
    const run=async()=>{try{const result=await ensureTestResourceAccess(identity);if(active)setState(result)}catch{if(active)setState({kind:'unknown',detail:'测试资源准备结果尚未核实。可以核对原请求，或继续使用已有权限。'})}};
    let observation=0;
    const observed=(event:Event)=>{const token=++observation;const value=(event as CustomEvent<{scope:string;state:State}>).detail;void readWorkbenchSession().then(session=>{if(active&&token===observation&&session.principal.principalId===identity&&JSON.stringify(session.principal)===value.scope)setState(value.state)}).catch(()=>{});};
    window.addEventListener(resourceAccessChanged,observed);
    void run();
    return()=>{active=false;window.removeEventListener(resourceAccessChanged,observed);};
  },[identity,retry]);
  if(state.kind==='checking')return <p className="journey-test-source" role="status">{identity?'正在准备可用的测试资源…':'正在核对登录状态，请稍候或使用右上角登录入口。'}</p>;
  return <>{state.kind!=='ready'&&<div className="journey-test-source" role="status"><span>{state.detail}</span>{state.kind==='unknown'&&<button type="button" onClick={()=>{setState({kind:'recovering',detail:'正在核对原请求…'});setRetry(value=>value+1);}}>核对原请求</button>}{state.updated&&<button type="button" onClick={()=>{const updated=state.updated;if(!updated)return;if(sessionStorage.getItem(updated.pointer)===updated.original)sessionStorage.removeItem(updated.pointer);setState({kind:'recovering',detail:'正在准备新版资料的读取权限…'});setRetry(value=>value+1);}}>读取新版资料</button>}{state.renewal&&<button type="button" onClick={()=>{const renewal=state.renewal;if(!renewal)return;if(sessionStorage.getItem(renewal.marker)===renewal.key)sessionStorage.removeItem(renewal.marker);setState({kind:'recovering',detail:'正在重新准备已过期的测试资源…'});setRetry(value=>value+1);}}>重新准备已过期资源</button>}</div>}{children}</>;
}
