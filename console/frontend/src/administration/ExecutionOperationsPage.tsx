import {useEffect,useRef,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {readWorkbenchSession,WorkbenchRequestError} from '../api/businessWorkspace';
import type {ExecutionView} from '../api/preparedExecution';
import type {PrivateConversation} from '../api/privateConversation';
import {PageHeader,StatusBadge} from '../components/WorkspacePrimitives';
import {ExecutionRuntimeSection} from '../digital-employees/EmployeeExecutionTrace';
import './ExecutionOperationsPage.css';

type Work={view:ExecutionView;conversation:string};
type Loaded={actor:string;items:Work[];limited:boolean;readAt:string};
class AccessChanged extends Error{}
const names:Record<string,string>={SUCCEEDED:'已完成',RUNNING:'执行中',QUEUED:'已排队',PENDING:'待执行',WAITING:'等待前序任务',NOT_STARTED:'尚未启动',FAILED:'执行失败',UNKNOWN:'结果待核实',OUTCOME_UNKNOWN:'结果待核实',RECOVERY_REQUIRED:'需要核查',CANCELLED:'已取消'};
const state=(v:ExecutionView)=>v.progress?.state??(v.executionStarted?'UNKNOWN':'NOT_STARTED');
const needsReview=(v:ExecutionView)=>['FAILED','UNKNOWN','OUTCOME_UNKNOWN','RECOVERY_REQUIRED'].includes(state(v))||v.progress?.tasks.some(t=>['FAILED','UNKNOWN','OUTCOME_UNKNOWN','RECOVERY_REQUIRED'].includes(t.state));
function tone(s:string):'neutral'|'success'|'danger'|'warning'|'info'{return s==='SUCCEEDED'?'success':s==='FAILED'?'danger':['UNKNOWN','OUTCOME_UNKNOWN','RECOVERY_REQUIRED'].includes(s)?'warning':['RUNNING','QUEUED','PENDING','WAITING'].includes(s)?'info':'neutral'}
const actorKey=(v:{principal:unknown})=>JSON.stringify(v.principal);
async function read<T>(path:string,actor:string,signal:AbortSignal):Promise<T>{
 if(actorKey(await readWorkbenchSession(signal))!==actor)throw new AccessChanged('当前登录身份已变化。');
 const r=await fetch('/api/workbench/v1/'+path,{credentials:'same-origin',headers:{Accept:'application/json'},signal}),body=await r.json().catch(()=>null);
 if(r.status===401){window.dispatchEvent(new Event('workbench-session-expired'));throw new AccessChanged('当前登录已失效。')}
 if(!r.ok)throw new WorkbenchRequestError(body?.reasonCode??'OPERATIONS_READ_UNAVAILABLE',r.status);
 if(actorKey(await readWorkbenchSession(signal))!==actor)throw new AccessChanged('当前登录身份已变化。');
 if(!body||!Object.hasOwn(body,'result'))throw Error('返回内容尚未核实。');
 return body.result as T;
}
function generated(view:ExecutionView){return (view.preparation as ExecutionView['preparation']&{synthetic?:boolean}).synthetic===true}
function verify(view:ExecutionView,digest:string,problemId:string,actor:string){
 const p=JSON.parse(actor),scope=view.preparation as ExecutionView['preparation']&{namespace?:string;security_domain?:string};
 if(view.digest!==digest||view.preparation?.semantics?.target?.problem?.resource_id!==problemId||scope.namespace&&scope.namespace!==p.tenantId||scope.security_domain&&scope.security_domain!==p.securityDomain||!Array.isArray(view.preparation?.semantics?.tasks)||!Array.isArray(view.artifacts)||!Array.isArray(view.resourceUses))throw Error('原执行身份、范围或内容尚未核实。');
 if(!Array.isArray(view.preparation.participants)||view.progress&&(!Array.isArray(view.progress.tasks)||view.progress.tasks.length!==view.preparation.semantics.tasks.length||new Set(view.progress.tasks.map(t=>t.task_id)).size!==view.progress.tasks.length||view.progress.tasks.some(t=>!view.preparation.semantics.tasks.some(s=>s.task_id===t.task_id))))throw Error('任务进度与原执行定义尚未核实。');
}
export function ExecutionOperationsPage(){
 const [params,setParams]=useSearchParams(),[data,setData]=useState<Loaded|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[version,setVersion]=useState(0);
 const epoch=useRef(0),pinned=useRef('');const invalidate=()=>{epoch.current++};
 useEffect(()=>{
  const token=++epoch.current,abort=new AbortController();let live=true;
  const withdraw=(message='当前读取依据已失效，请重新核对。')=>{epoch.current++;abort.abort();setData(null);setBusy(false);setError(message)};
  const expired=()=>withdraw('当前登录已失效，请重新登录后读取。');
  const focus=()=>{void readWorkbenchSession().then(s=>{if(pinned.current&&actorKey(s)!==pinned.current)withdraw('当前登录身份已变化。');else{setData(null);setVersion(v=>v+1)}}).catch(()=>withdraw('当前登录尚未核实。'))};
  async function load(){
   setBusy(true);setData(null);setError('');
   try{
    const actor=actorKey(await readWorkbenchSession(abort.signal));pinned.current=actor;
    const index=await read<{items:{conversation_id:string}[]}>('conversations',actor,abort.signal);
    if(!Array.isArray(index.items))throw Error('会话关联列表尚未核实。');
    let limited=index.items.length>20;const refs=new Map<string,{problemId:string;conversation:string}>();
    for(const item of index.items.slice(0,20)){
     try{const c=await read<PrivateConversation>('conversations/'+encodeURIComponent(item.conversation_id),actor,abort.signal);if(c.conversation.conversation_id!==item.conversation_id||!Array.isArray(c.links))throw Error('会话关联身份尚未核实。');for(const link of c.links){if(link.readable&&link.target?.executionDigest){if(!/^[a-f0-9]{64}$/.test(link.target.executionDigest))throw Error('执行关联标识尚未核实。');if(refs.size>=100&&!refs.has(link.target.executionDigest)){limited=true;continue}refs.set(link.target.executionDigest,{problemId:link.target.problemId,conversation:item.conversation_id})}else if(!link.readable)limited=true}}
     catch(e){if(e instanceof AccessChanged||abort.signal.aborted)throw e;limited=true}
    }
    const items:Work[]=[];
    for(const [digest,ref] of refs){
     try{const v=await read<ExecutionView>('prepared-executions/'+digest,actor,abort.signal);verify(v,digest,ref.problemId,actor);items.push({view:v,conversation:ref.conversation})}
     catch(e){if(e instanceof AccessChanged||abort.signal.aborted)throw e;limited=true}
    }
    if(actorKey(await readWorkbenchSession(abort.signal))!==actor)throw new AccessChanged('当前登录身份已变化。');
    if(live&&token===epoch.current)setData({actor,items,limited,readAt:new Date().toISOString()});
   }catch(e){if(live&&token===epoch.current){setData(null);setError(e instanceof Error?e.message:'执行记录尚未读回。')}}
   finally{if(live&&token===epoch.current)setBusy(false)}
  }
  void load();window.addEventListener('workbench-session-expired',expired);window.addEventListener('focus',focus);
  return()=>{live=false;invalidate();abort.abort();window.removeEventListener('workbench-session-expired',expired);window.removeEventListener('focus',focus)};
 },[version]);
 useEffect(()=>{if(!data)return;const token=epoch.current;const timer=window.setTimeout(()=>{if(epoch.current===token){setData(null);setError('本次读取快照已到期，请重新读取当前记录。')}},30000);return()=>window.clearTimeout(timer)},[data]);
 const query=params.get('q')??'',filter=params.get('state')??'ALL',selectedId=params.get('execution'),all=data?.items??[],visible=all.filter(w=>(filter==='ALL'||filter==='REVIEW'&&needsReview(w.view)||state(w.view)===filter)&&`${w.view.preparation.semantics.title} ${w.view.digest}`.toLowerCase().includes(query.toLowerCase())),selected=all.find(w=>w.view.digest===selectedId);
 function update(values:Record<string,string>){setParams(p=>{const next=new URLSearchParams(p);for(const [k,v]of Object.entries(values)){if(v)next.set(k,v);else next.delete(k)}return next})}
 function refresh(){setData(null);setVersion(v=>v+1)}
 const metric=(n:number)=>data&&(!data.limited||data.items.length)?n:'—';
 const e=selected?.view;
 return <main className="px-page execution-operations"><PageHeader eyebrow="运营与治理" title="执行与观测" description="查看本人会话已关联、当前可读的执行记录，继续核对任务、成果与运行绑定。" actions={<><button disabled={busy} onClick={refresh}>重新读取当前记录</button><Link to="/work">返回会话</Link></>}/><section className="operations-scope"><p>这里只统计本次成功读回的会话关联执行，最多核对20段会话和100项关联；不代表企业全部执行、实例群健康或账单。读取快照保留30秒，到期重新读取，不重试执行。数据性质按原任务来源核对，生成样本不代表真实经营效果。</p>{data&&<small>本次读取：{new Date(data.readAt).toLocaleString('zh-CN')}</small>}{data?.limited&&<p role="status">部分关联当前不可读或达到核对上限；已显示的记录不代表完整范围，未读回不计作零。</p>}{busy&&<p role="status">正在核对当前可读执行…</p>}{error&&<div role="alert">当前执行记录未能读回：{error}</div>}</section>
 <section className="operations-metrics" aria-label="当前已核实范围统计">{[['已核实执行',metric(all.length)],['已完成',metric(all.filter(w=>state(w.view)==='SUCCEEDED').length)],['进行中或排队',metric(all.filter(w=>['RUNNING','QUEUED','PENDING'].includes(state(w.view))).length)],['执行需核查',metric(all.filter(w=>needsReview(w.view)).length)]].map(([name,value])=><article key={name}><span>{name}</span><strong>{value}</strong></article>)}</section>
 <section className="operations-content"><div className="operations-filters"><label>查找执行<input aria-label="查找执行" value={query} maxLength={200} onChange={ev=>update({q:ev.target.value})} placeholder="工作名称或准确标识"/></label><label>执行状态<select aria-label="执行状态" value={filter} onChange={ev=>update({state:ev.target.value})}><option value="ALL">全部可读状态</option><option value="SUCCEEDED">已完成</option><option value="RUNNING">执行中</option><option value="NOT_STARTED">尚未启动</option><option value="REVIEW">需要核查</option></select></label></div>{data&&(!visible.length?<p role="status">当前返回范围内没有匹配的可核实执行；可调整筛选或回到原会话核对。</p>:<div className="operations-table"><table><thead><tr><th>工作与方案</th><th>正式执行状态</th><th>任务进度</th><th>可读成果</th><th>继续核对</th></tr></thead><tbody>{visible.map(w=><tr key={w.view.digest} className={selectedId===w.view.digest?'selected':''}><td><strong>{w.view.preparation.semantics.title}</strong><small>方案 v{w.view.preparation.plan_version} · {generated(w.view)?'项目生成验证资料':'来源性质见原任务'}</small></td><td><StatusBadge tone={tone(state(w.view))}>{names[state(w.view)]??'状态待核实'}</StatusBadge></td><td>{w.view.progress?`${w.view.progress.tasks.filter(t=>t.state==='SUCCEEDED').length}/${w.view.preparation.semantics.tasks.length}`:w.view.executionStarted?'进度待核实':`0/${w.view.preparation.semantics.tasks.length}`}</td><td>{w.view.artifacts.filter(a=>a.contentAccess==='AUTHORIZED').length}项正文可读</td><td><button onClick={()=>update({execution:w.view.digest,conversation:w.conversation})}>查看执行记录</button><Link to={'/work?'+new URLSearchParams({conversation:w.conversation})}>返回原会话</Link></td></tr>)}</tbody></table></div>)}</section>
 {selectedId&&data&&!e&&<section className="operations-content" role="status">所选执行当前未读回，不能据此判断原记录不存在。请在原会话核对当前读取资格。</section>}
 {e&&selected&&<section className="operations-content" aria-label="当前选择的原执行"><header className="operations-detail-header"><div><h2>{e.preparation.semantics.title}</h2><p>{generated(e)?'项目生成验证资料。':'数据性质以原任务来源为准。'}原任务状态与业务结果分别核对。</p></div><StatusBadge tone={tone(state(e))}>{names[state(e)]??'状态待核实'}</StatusBadge></header><div className="operations-detail-layout"><section aria-label="正式任务进度"><h3>正式任务进度</h3><ol>{e.preparation.semantics.tasks.map(t=>{const st=e.progress?.tasks.find(p=>p.task_id===t.task_id),taskState=st?.state??(e.executionStarted?'UNKNOWN':'NOT_STARTED');return <li key={t.task_id}><strong>{t.title}</strong><StatusBadge tone={tone(taskState)}>{names[taskState]??'状态待核实'}</StatusBadge></li>})}</ol><p>标准评价：{e.outcome?`${e.outcome.evaluation.results.filter(r=>r.result==='SATISFIED').length}/${e.outcome.evaluation.results.length}项满足`:'尚未读回'}</p><p>{e.outcome?.businessResolution==='UNDETERMINED'?'业务结果仍未判定。':'业务结果以原任务的正式确认记录为准。'}</p></section><section aria-label="成果与实际资源使用"><h3>成果与实际资源使用</h3><p>当前读取的成果记录：{e.artifacts.length}项；其中正文可读{e.artifacts.filter(a=>a.contentAccess==='AUTHORIZED').length}项。</p><p>当前可读成功资源使用记录：{e.resourceUses.filter(u=>u.state==='SUCCEEDED').length}条。</p>{e.resourceUses.some(u=>u.state==='READ_RESTRICTED')&&<p>部分资源使用记录当前不可读，不能据此认定没有使用。</p>}<Link to={'/work?'+new URLSearchParams({conversation:selected.conversation})}>在原会话查看完整结果与依据</Link><details><summary>准确执行与成果标识</summary><p>{e.digest}</p><ul>{e.artifacts.map(a=><li key={a.artifact_id}>{a.task_id} · {a.artifact_id} · {a.contentAccess==='AUTHORIZED'?'正文可读':'正文当前不可读'}</li>)}</ul></details></section></div><section aria-label="本次员工分工入口"><h3>员工分工与运行绑定</h3><div className="operations-employee-links">{e.preparation.participants.map(p=><Link key={p.task_id} to={'/employees?'+new URLSearchParams({employeeDefinitionId:p.definition.resource_id,employeeDefinitionRevisionId:p.definition.revision_id,detail:'1',section:'assignments',instanceId:p.instance_id,assignmentId:p.assignment_id,workExecution:e.digest,workTask:p.task_id,returnConversation:selected.conversation,observationReturn:e.digest})}>{e.preparation.semantics.tasks.find(t=>t.task_id===p.task_id)?.title??'查看准确分工'}</Link>)}</div></section>{e.executionStarted&&<ExecutionRuntimeSection key={e.digest} digest={e.digest} bindings={e.preparation.participants.map(p=>({taskId:p.task_id,instanceId:p.instance_id,assignmentId:p.assignment_id,runtimeInstanceId:p.runtime_instance_id??'',runtimeGeneration:p.runtime_generation??0}))}/>}</section>}
 </main>;
}
