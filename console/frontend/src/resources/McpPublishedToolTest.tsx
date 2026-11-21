import {useEffect,useRef,useState} from 'react';
import {readWorkbenchSession} from '../api/businessWorkspace';
import type {SkillMcpResource} from '../api/skillMcpResources';
type Option={bindingDigest:string;publishedReference:{resource_id:string;revision_id:string;digest:string};toolName:string;input:Record<string,unknown>};
type Receipt={commandKey:string;bindingDigest:string;publishedReference:Option['publishedReference'];state:string;result:unknown;retryPermitted:false};
type View={options:Option[];history:Receipt[];publishedOnly:true;automaticRetry:false};
const states:Record<string,string>={PREPARED:'测试请求已保存，尚未派发',UNKNOWN:'调用结果待核对，不会自动重发',SUCCEEDED:'工具调用已完成',TOOL_FAILED:'工具返回失败',NOT_DISPATCHED:'未派发'};
export function McpPublishedToolTest({resource,busy=false}:{resource:SkillMcpResource;busy?:boolean}){
 const [view,setView]=useState<View|null>(null),[error,setError]=useState(''),[working,setWorking]=useState(false),[pending,setPending]=useState<string|null>(null);
 const epoch=useRef(0),principal=useRef(''),flight=useRef(false);
 const root='/api/workbench/v1/resource-management/mcp/'+encodeURIComponent(resource.resourceId)+'/tool-tests';
 async function request<T>(suffix:string,body?:unknown,token=epoch.current):Promise<T>{
  const session=await readWorkbenchSession();if(token!==epoch.current)throw Error('STALE_VIEW');
  const who=JSON.stringify(session.principal);if(principal.current&&principal.current!==who)throw Error('IDENTITY_CHANGED');principal.current=who;
  const response=await fetch(root+suffix,{credentials:'same-origin',...(body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrfToken},body:JSON.stringify(body)})});
  const value=await response.json().catch(()=>null);if(token!==epoch.current)throw Error('STALE_VIEW');
  const after=await readWorkbenchSession();if(token!==epoch.current||JSON.stringify(after.principal)!==who)throw Error('IDENTITY_CHANGED');
  if(!response.ok||!value?.result)throw Error(response.status===404?'TOOL_TEST_NOT_ENABLED':'TOOL_TEST_READ_OR_OPERATION_UNCONFIRMED');return value.result;
 }
 async function refresh(){const token=epoch.current;try{const v=await request<View>('');if(token===epoch.current){setView(v);setError('')}}catch{if(token===epoch.current){setView(null);setError('工具测试暂不可用，或当前资格无法核对。')}}}
 useEffect(()=>{epoch.current++;principal.current='';const token=epoch.current;request<View>('').then(v=>{if(token===epoch.current)setView(v)}).catch(()=>{if(token===epoch.current)setError('工具测试暂不可用，或当前资格无法核对。')});const invalidate=()=>{epoch.current++;principal.current='';setView(null);setError('登录状态已变化，请重新进入本页核对。')};window.addEventListener('workbench-session-expired',invalidate);return()=>{epoch.current++;window.removeEventListener('workbench-session-expired',invalidate)}},[resource.resourceId,resource.publishedRevisionId]); // eslint-disable-line react-hooks/exhaustive-deps
 function exact(r:Receipt,o?:Option){return r.publishedReference?.resource_id===resource.resourceId&&r.retryPermitted===false&&(!o||r.bindingDigest===o.bindingDigest&&r.publishedReference.revision_id===o.publishedReference.revision_id&&r.publishedReference.digest===o.publishedReference.digest)}
 async function test(o:Option){
  if(flight.current||pending)return;flight.current=true;setWorking(true);const token=epoch.current;
  try{
   const fresh=await request<View>('');if(!fresh.options.some(x=>JSON.stringify(x)===JSON.stringify(o)))throw Error('OPTION_CHANGED');
   const key='mcp-tool-test:'+crypto.randomUUID();setPending(key);
   // Durable server history discovers the same key after reload; local storage is never authority.
   const prepared=await request<Receipt>('',{commandKey:key,bindingDigest:o.bindingDigest,input:o.input});if(!exact(prepared,o)||prepared.commandKey!==key||prepared.state!=='PREPARED')throw Error('RECEIPT_UNKNOWN');
   const done=await request<Receipt>('/'+encodeURIComponent(key)+'/dispatch',{});if(!exact(done,o)||done.commandKey!==key)throw Error('RECEIPT_UNKNOWN');
   if(done.state==='SUCCEEDED'||done.state==='TOOL_FAILED'||done.state==='NOT_DISPATCHED')setPending(null);
   await refresh();
  }catch{if(token===epoch.current)setError('测试结果尚未确认。请核对已有记录，不要重新发起。')}
  finally{flight.current=false;if(token===epoch.current)setWorking(false)}
 }
 async function continuePrepared(key:string){
  if(flight.current)return;flight.current=true;setWorking(true);const token=epoch.current;setPending(key);
  try{const saved=await request<Receipt>('/'+encodeURIComponent(key));if(!exact(saved)||saved.commandKey!==key||saved.state!=='PREPARED')throw Error('NOT_PREPARED');
   const done=await request<Receipt>('/'+encodeURIComponent(key)+'/dispatch',{});if(!exact(done)||done.commandKey!==key)throw Error('RECEIPT_UNKNOWN');if(['SUCCEEDED','TOOL_FAILED','NOT_DISPATCHED'].includes(done.state))setPending(null);await refresh();
  }catch{if(token===epoch.current)setError('当前测试暂不能继续，请核对已有记录。未创建新的测试。')}
  finally{flight.current=false;if(token===epoch.current)setWorking(false)}
 }
 async function readSaved(key:string){try{const r=await request<Receipt>('/'+encodeURIComponent(key));if(!exact(r)||r.commandKey!==key)throw Error('RECEIPT_UNKNOWN');if(r.state==='SUCCEEDED'||r.state==='TOOL_FAILED'||r.state==='NOT_DISPATCHED')setPending(null);await refresh()}catch{setError('已有测试记录暂不可读，未重新调用工具。')}}
 return <section className="rd-card" aria-label="已发布 MCP 工具测试"><h3>工具测试（已发布版本）</h3><p>真实调用已明确授权的只读工具。连接检查和工具发现不能替代本项；不作为草稿发布前测试。</p>{error&&<p role="status">{error}</p>}{!resource.publishedRevisionId?<p>发布连接配置后，才可准备准确版本的工具测试。</p>:view?.options.length?view.options.map(o=><div key={o.bindingDigest}><strong>{o.toolName}</strong><details><summary>本次准确版本与输入</summary><code>{o.publishedReference.revision_id}</code><pre>{JSON.stringify(o.input,null,2)}</pre></details><button disabled={busy||working||!!pending||view.history.some(r=>r.bindingDigest===o.bindingDigest&&!['SUCCEEDED','TOOL_FAILED','NOT_DISPATCHED'].includes(r.state))} onClick={()=>void test(o)}>运行一次工具测试</button></div>):<p>尚无当前可用的精确工具测试范围，不会调用工具。</p>}{pending&&<button disabled={working} onClick={()=>void readSaved(pending)}>核对本次测试状态</button>}<button disabled={working} onClick={()=>void refresh()}>刷新测试记录</button><ul>{view?.history.map(r=><li key={r.commandKey}><p>{states[r.state]??'状态待核对'}</p>{r.state==='PREPARED'&&<button disabled={working||busy} onClick={()=>void continuePrepared(r.commandKey)}>继续此测试</button>}<button disabled={working} onClick={()=>void readSaved(r.commandKey)}>核对测试状态</button><details><summary>测试依据</summary><pre>{JSON.stringify(r,null,2)}</pre></details></li>)}</ul></section>;
}
