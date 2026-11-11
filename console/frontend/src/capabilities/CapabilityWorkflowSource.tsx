import {useEffect,useState} from 'react';
import {WorkflowDerivedCapabilities} from './WorkflowDerivedCapabilities';
import {readCapabilityWorkflowSource,type CapabilityWorkflowSourceDetail,type CapabilityReference} from '../api/businessCapabilities';

const strings=(value:unknown)=>Array.isArray(value)?value.filter((item):item is string=>typeof item==='string'):[];
const record=(value:unknown):value is Record<string,unknown>=>!!value&&typeof value==='object'&&!Array.isArray(value);

/** Provenance is a fixed source revision, not evidence of execution or a caller. */
export function CapabilityWorkflowSource({reference,principal}:{reference:CapabilityReference;principal:string}){
 const [open,setOpen]=useState(false),[retry,setRetry]=useState(0);
 const [result,setResult]=useState<{key:string;value?:CapabilityWorkflowSourceDetail;error?:boolean}|null>(null);
 const {resource_id:id,revision_id:revision,digest}=reference;
 const key=JSON.stringify([principal,id,revision,digest,retry]);
 useEffect(()=>{
  if(!open)return;
  const controller=new AbortController();
  const signal=AbortSignal.any([controller.signal,AbortSignal.timeout(30_000)]);
  void (async()=>{
   try{
    const value=await readCapabilityWorkflowSource({resource_id:id,revision_id:revision,digest},principal,signal);
    if(!controller.signal.aborted)setResult({key,value});
   }catch{if(!controller.signal.aborted)setResult({key,error:true})}
  })();
  return()=>controller.abort();
 },[open,retry,principal,id,revision,digest,key]);
 const current=result?.key===key?result:null;
 const value=current?.value,content=value?.revision?.content;
 const tasks=Array.isArray(content?.tasks)?content.tasks.filter(record):[];
 return <section className="capability-panel" aria-label="来源执行方案">
  <h2>来源执行方案</h2><p>查看设计此能力时固定的执行方案版本。来源关联不代表该执行方案已经调用或执行本能力。</p>
  <button aria-expanded={open} onClick={()=>{setResult(null);setOpen(value=>!value)}}>{open?'收起来源执行方案':'查看来源执行方案'}</button>
  {open&&<>{!current&&<p role="status">正在核对来源执行方案与固定版本…</p>}
   {current?.error&&<div role="alert"><p>来源执行方案暂时无法读取，或当前账号无权查看此版本。未展示未经核对的内容。</p><button onClick={()=>setRetry(value=>value+1)}>重新读取来源执行方案</button></div>}
   {value&&<><h3>{value.definition.name}</h3>{typeof content?.description==='string'&&<p>{content.description}</p>}
    <dl><div><dt>方案输入</dt><dd>{strings(content?.inputs).join('；')||'该版本未声明'}</dd></div><div><dt>方案产出</dt><dd>{strings(content?.outputs).join('；')||'该版本未声明'}</dd></div></dl>
    <h3>已保存的执行步骤</h3>{tasks.length?<ol>{tasks.map((task,index)=><li key={`${String(task.taskId)}:${index}`}><strong>{typeof task.name==='string'?task.name:'未命名步骤'}</strong><p>输入：{strings(task.inputs).join('；')||'未声明'}；产出：{strings(task.outputs).join('；')||'未声明'}</p></li>)}</ol>:<p>该版本未提供可展示的步骤。</p>}
    <WorkflowDerivedCapabilities reference={reference} principal={principal}/>
    <details><summary>查看来源固定版本</summary><dl><div><dt>执行方案</dt><dd>{id}</dd></div><div><dt>版本</dt><dd>{revision}</dd></div><div><dt>内容标识</dt><dd>{digest}</dd></div></dl></details>
   </>}
  </>}
 </section>;
}
