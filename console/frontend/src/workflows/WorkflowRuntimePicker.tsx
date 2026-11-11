import {useEffect,useState} from 'react';
import {listReadableResources,type DirectoryItem} from '../api/resourceDirectory';
import type {ExactReference} from '../api/workflowDefinitions';

export function WorkflowRuntimePicker({value,onChange,locked}:{value:ExactReference;onChange:(value:ExactReference)=>void;locked:boolean}){
 const [rows,setRows]=useState<DirectoryItem[]>([]),[cursor,setCursor]=useState<string|null>(null),[error,setError]=useState(false),[loading,setLoading]=useState(true),[retry,setRetry]=useState(0);
 useEffect(()=>{const controller=new AbortController();void listReadableResources('runtime','','PUBLISHED',null,AbortSignal.any([controller.signal,AbortSignal.timeout(30_000)])).then(page=>{if(!controller.signal.aborted){setRows(page.items);setCursor(page.nextCursor);setError(false);setLoading(false)}}).catch(()=>{if(!controller.signal.aborted){setError(true);setLoading(false)}});return()=>controller.abort()},[retry]);
 const selected=rows.findIndex(row=>row.identity===value.resourceId&&row.revisionId===value.revisionId&&row.digest.replace(/^sha256:/,'')===value.digest?.replace(/^sha256:/,''));
 async function more(){setLoading(true);try{const page=await listReadableResources('runtime','','PUBLISHED',cursor,AbortSignal.timeout(30_000));setRows(old=>[...old,...page.items]);setCursor(page.nextCursor);setError(false)}catch{setError(true)}finally{setLoading(false)}}
 return <fieldset><legend>运行环境</legend><label>已发布运行环境<select aria-label="已发布运行环境" disabled={locked||loading||error} value={selected<0?'':String(selected)} onChange={event=>{const row=rows[Number(event.target.value)];if(event.target.value!==''&&row&&row.enabled&&row.isCurrentPublished)onChange({kind:'RUNTIME_PROFILE',resourceId:row.identity,revisionId:row.revisionId,digest:row.digest})}}><option value="">选择可读取的运行环境</option>{rows.map((row,i)=><option disabled={!row.enabled||!row.isCurrentPublished} key={row.identity+row.revisionId} value={String(i)}>{row.name} · {row.revisionId.slice(-8)}</option>)}</select></label>
 {loading&&<p role="status">正在读取运行环境…</p>}{error&&<><p role="alert">暂时无法读取运行环境，原引用保持不变。</p><button type="button" disabled={locked} onClick={()=>{setLoading(true);setRetry(n=>n+1)}}>重新读取运行环境</button></>}{cursor&&!error&&<button type="button" disabled={locked||loading} onClick={()=>void more()}>读取更多运行环境</button>}
 {value.resourceId&&<details><summary>查看固定运行环境版本</summary><p>{value.resourceId} · {value.revisionId}</p><p>{value.digest??'尚未核对内容标识，请选择已有运行环境。'}</p></details>}<p>此处固定运行配置；发布流程不会启动执行。</p></fieldset>;
}
