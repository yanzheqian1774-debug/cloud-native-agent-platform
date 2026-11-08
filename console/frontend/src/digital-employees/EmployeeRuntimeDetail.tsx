import {useEffect,useRef,useState} from 'react';
import {getWorkbenchSession,type EmployeeInstance,type EmployeeAssignment,type EmployeePlacement} from '../api/digitalEmployees';

type Binding={taskId:string;instanceId:string;assignmentId:string;attemptId:string|null;agentInstanceId:string;runtimeInstanceId:string;employee:{resource_id:string;revision_id:string;digest:string}};
type Detail={taskId:string;instance:EmployeeInstance;assignment:EmployeeAssignment;placement:EmployeePlacement|null;placementStatus:string;observedAt:string;freshUntil:string;providerHealth:string;executionStarted:false};
const lifecycle:Record<string,string>={ENABLED:'已启用',DISABLED:'已停用',RETIRED:'已退役',ACTIVE:'有效',ENDED:'已结束',REVOKED:'已撤销'};
const placementLabels:Record<string,string>={VERIFIED:'已核实准确放置',NOT_DISPATCHED:'尚无已派发记录',BINDING_UNAVAILABLE:'准确派发关联暂不可读',UNAVAILABLE:'放置记录暂不可读'};
const identity=(s:Awaited<ReturnType<typeof getWorkbenchSession>>)=>JSON.stringify(s.principal);
export function EmployeeRuntimeDetail({digest,task}:{digest:string;task:Binding}){
 const [detail,setDetail]=useState<Detail|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[now,setNow]=useState(Date.now),epoch=useRef(0),actor=useRef('');
 const key=JSON.stringify([digest,task]);
 const invalidate=()=>{epoch.current++};
 useEffect(()=>{const withdraw=()=>{epoch.current++;setDetail(null);setBusy(false);setError('登录状态已变化，请重新读取。')};const focus=()=>{if(actor.current)void getWorkbenchSession().then(s=>{if(identity(s)!==actor.current)withdraw()}).catch(withdraw)};window.addEventListener('workbench-session-expired',withdraw);window.addEventListener('focus',focus);const tick=window.setInterval(()=>setNow(Date.now()),1000);return()=>{invalidate();clearInterval(tick);window.removeEventListener('workbench-session-expired',withdraw);window.removeEventListener('focus',focus)}},[key]);
 async function load(){const token=++epoch.current;setBusy(true);setDetail(null);setError('');try{
  const session=await getWorkbenchSession(),pin=identity(session);actor.current=pin;
  const response=await fetch('/api/workbench/v1/prepared-executions/'+encodeURIComponent(digest)+'/runtime-details/'+encodeURIComponent(task.taskId),{credentials:'same-origin',signal:AbortSignal.timeout(10000),headers:{Accept:'application/json'}});
  if(response.status===401)window.dispatchEvent(new Event('workbench-session-expired'));
  if(!response.ok)throw Error('实例与放置详情暂不可读，原任务及结果保留。');
  const {result:r}=await response.json(),d:Detail=r?.detail,p=session.principal;
  if(identity(await getWorkbenchSession())!==pin||r.subject!==p.principalId||r.scope?.tenantId!==p.tenantId||r.scope?.securityDomain!==p.securityDomain)throw Error('身份或读取范围已变化。');
  if(r.schemaVersion!=='execution-runtime-review.v1'||r.executionDigest!==digest||r.executionStarted!==false||!d||d.taskId!==task.taskId||d.executionStarted!==false||d.providerHealth!=='NOT_OBSERVED'||d.instance?.instanceId!==task.instanceId||d.assignment?.assignmentId!==task.assignmentId||d.assignment.instanceId!==task.instanceId||d.instance.employeeDefinition?.employeeDefinitionId!==task.employee.resource_id||d.instance.employeeDefinition.employeeDefinitionRevisionId!==task.employee.revision_id||d.instance.employeeDefinition.digest!==task.employee.digest)throw Error('实例详情与原任务绑定不一致。');
  if(!Number.isFinite(Date.parse(d.observedAt))||!Number.isFinite(Date.parse(d.freshUntil))||Date.parse(d.freshUntil)<=Date.now())throw Error('详情已过期，请重新读取。');
  if(!Object.hasOwn(placementLabels,d.placementStatus)||(d.placementStatus==='VERIFIED')!==Boolean(d.placement))throw Error('放置状态尚未核实。');
  if(d.placement&&(d.placement.runtimeInstanceId!==task.runtimeInstanceId||d.placement.binding.instanceId!==task.instanceId||d.placement.binding.assignmentId!==task.assignmentId||d.placement.binding.attemptId!==task.attemptId||d.placement.binding.agentInstanceId!==task.agentInstanceId))throw Error('放置记录与原任务绑定不一致。');
  if(token===epoch.current){setNow(Date.now());setDetail(d)}
 }catch(e){if(token===epoch.current)setError(e instanceof Error?e.message:'详情暂不可读。')}finally{if(token===epoch.current)setBusy(false)}}
 const stale=detail&&now>=Date.parse(detail.freshUntil);
 return <section className="employee-runtime-detail" aria-label="实例与放置办理详情"><button disabled={busy} onClick={()=>void load()}>{busy?'正在核对实例与放置…':'查看实例状态与放置'}</button>{error&&<p role="alert">{error}</p>}{detail&&<div className={stale?'runtime-detail-stale':''}><h4>{stale?'详情快照已过期，请重新读取':'实例与放置详情'}</h4><p>读取于 {new Date(detail.observedAt).toLocaleString('zh-CN')}</p><dl><dt>实例生命周期</dt><dd>{lifecycle[detail.instance.lifecycle]??'状态待核实'}</dd><dt>工作分配状态</dt><dd>{lifecycle[detail.assignment.lifecycle]??'状态待核实'}</dd><dt>受派角色</dt><dd>{detail.assignment.businessRole}</dd><dt>放置核对</dt><dd>{placementLabels[detail.placementStatus]}</dd><dt>环境健康</dt><dd>未知 · 尚无可核实的环境健康观测</dd></dl>{detail.placement&&<><p>{detail.placement.decision==='PLACED'?'已分配运行位置；任务结果见上方任务状态。':'放置决定待核实'}</p><details><summary>查看正式放置记录</summary><dl><dt>放置标识</dt><dd>{detail.placement.placementId}</dd><dt>运行实例</dt><dd>{detail.placement.runtimeInstanceId}</dd><dt>决定时间</dt><dd>{detail.placement.decidedAt}</dd><dt>策略版本</dt><dd>{detail.placement.policyVersion}</dd><dt>记录摘要</dt><dd>{detail.placement.digest}</dd><dt>限制说明</dt><dd>{detail.placement.limitationCodes.join('、')||'未记录限制项'}</dd></dl></details></>}<p>实例启用表示可接受分工；执行进度与实时健康需分别核实。</p></div>}</section>
}
