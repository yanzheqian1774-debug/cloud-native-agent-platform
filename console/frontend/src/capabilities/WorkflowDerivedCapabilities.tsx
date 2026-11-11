import {useEffect,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {workbenchPrincipalKey} from '../api/digitalEmployees';
import {capabilitySession,listWorkflowDerivedCapabilities,type CapabilityReference,type CapabilityItem} from '../api/businessCapabilities';

export function WorkflowDerivedCapabilities({reference,principal}:{reference:CapabilityReference;principal:string}){
 const [params]=useSearchParams(),[open,setOpen]=useState(false),[page,setPage]=useState<{cursor:string|null;attempt:number}>({cursor:null,attempt:0});
 const [result,setResult]=useState<{key:string;items:CapabilityItem[];next:string|null;error?:boolean}|null>(null);
 const {resource_id:id,revision_id:revision,digest}=reference;
 const key=JSON.stringify([id,revision,digest,principal,page]);
 useEffect(()=>{
  if(!open)return;
  const controller=new AbortController();
  void listWorkflowDerivedCapabilities({resource_id:id,revision_id:revision,digest},principal,page.cursor,controller.signal).then(value=>{
   if(!controller.signal.aborted)setResult({key,items:value.items,next:value.nextCursor});
  }).catch(()=>{if(!controller.signal.aborted)setResult({key,items:[],next:null,error:true})});
  return()=>controller.abort();
 },[open,id,revision,digest,principal,page,key]);
 const current=result?.key===key?result:null;
 const href=(item:CapabilityItem)=>'/capabilities?'+new URLSearchParams({capability:item.capabilityId,revision:item.revisionId,digest:item.digest,...(params.get('returnConversation')?{returnConversation:params.get('returnConversation')!}:{})});
 return <div className="capability-derived"><button aria-expanded={open} onClick={()=>{setResult(null);setOpen(value=>!value);setPage({cursor:null,attempt:0})}}>{open?'收起关联能力':'查看由此执行方案形成的能力'}</button>
  {open&&<><p>仅显示当前有权读取、且来源为这一固定执行方案版本的已发布能力和修改草稿，不代表执行调用记录。</p>
   {!current&&<p role="status">正在查询关联能力…</p>}
   {current?.error&&<div role="alert"><p>关联能力暂时无法核对。</p><button onClick={()=>setPage(value=>({...value,attempt:value.attempt+1}))}>重新读取关联能力</button></div>}
   {current&&!current.error&&<>{current.items.length?<ul>{current.items.map(item=><li key={item.capabilityId}><Link to={href(item)}>{item.title}</Link><span> · {item.state==='PUBLISHED'?'已发布':'修改草稿'}</span><p>{item.intent}</p>{item.currentDraft&&item.currentPublished&&<Link to={href({...item,...item.currentDraft})}>查看同源修改草稿</Link>}</li>)}</ul>:<p>此页没有可读取的同源能力。</p>}
    {current.next&&<button onClick={()=>setPage({cursor:current.next,attempt:0})}>下一页关联能力</button>}{page.cursor&&<button onClick={()=>setPage({cursor:null,attempt:0})}>返回关联能力首页</button>}
   </>}
  </>}
 </div>;
}

export function WorkflowCapabilityLookup({reference}:{reference:CapabilityReference}){
 const [principal,setPrincipal]=useState(''),[error,setError]=useState(false),[retry,setRetry]=useState(0);
 useEffect(()=>{
  const controller=new AbortController();
  void capabilitySession(controller.signal).then(value=>{if(!controller.signal.aborted){setPrincipal(workbenchPrincipalKey(value));setError(false)}}).catch(()=>{if(!controller.signal.aborted)setError(true)});
  return()=>controller.abort();
 },[retry]);
 return <section className="workbench-card"><h3>由此执行方案形成的业务能力</h3>{error?<><p role="alert">当前账号暂时无法核对。</p><button onClick={()=>setRetry(value=>value+1)}>重新核对账号</button></>:principal?<WorkflowDerivedCapabilities reference={reference} principal={principal}/>:<p role="status">正在核对账号…</p>}</section>;
}
