import {useEffect,useRef,useState} from 'react';
import {getWorkbenchSession,workbenchPrincipalKey,type WorkbenchSession} from '../api/digitalEmployees';
import {formatTime} from '../journey/formatTime';
import './bounded-task.css';

type Ref={resource_id:string;revision_id:string;digest:string};
type Task={request:{request_id:string;subject_id:string;tenant_id:string;security_domain:string;digest:string;record:{purpose:string;root:Ref;source_snapshot:Ref;determination_date:string;permissions:{owner:string;action:string;exact_resource:string}[];derived_permissions:{owner:string;action:string;phase:string}[];configuration:null|{revision_id:string;configuration_digest:string;read_seconds:number;total_seconds:number;cleanup_seconds:number;cumulative_call_cap:number};recovery_invocation_id:string|null}};status:string;reasonCode:string|null;decision:null|{decision_id:string;issuer_id:string;expires_at:string}};

export function BoundedTaskPanel({identity,session}:{identity:string;session:WorkbenchSession}){
 const [value,setValue]=useState<Task|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[confirmed,setConfirmed]=useState(false);
 const command=useRef<{request_digest:string;idempotency_key:string;not_before:string;expires_at:string}|null>(null);
 async function request(suffix='',body?:unknown){
  const current=await getWorkbenchSession();
  if(workbenchPrincipalKey(current)!==workbenchPrincipalKey(session))throw new Error('身份已变化，请重新登录并返回原事项。');
  const response=await fetch(`/api/workbench/v1/authorization/tasks/${encodeURIComponent(identity)}${suffix}`,{method:body?'POST':'GET',credentials:'same-origin',headers:body?{'Content-Type':'application/json','X-CSRF-Token':current.csrfToken}:{},...(body?{body:JSON.stringify(body)}:{})});
  const data=await response.json();
  if(!response.ok)throw new Error(response.status===401?'登录已失效；重新登录后返回本事项，不会自动提交。':`操作未完成：${data.reasonCode??'TASK_AUTHORIZATION_UNAVAILABLE'}；诊断编号：${data.requestId??'未提供'}。`);
  return data as Task;
 }
 useEffect(()=>{let active=true;getWorkbenchSession().then(async current=>{
  if(workbenchPrincipalKey(current)!==workbenchPrincipalKey(session))throw new Error('身份已变化，请重新登录。');
  const response=await fetch(`/api/workbench/v1/authorization/tasks/${encodeURIComponent(identity)}`,{credentials:'same-origin'});
  const data=await response.json();if(!response.ok)throw new Error(`无法读取此事项：${data.reasonCode??response.status}。请核对当前身份，不会自动办理。`);
  if(active)setValue(data);
 }).catch(e=>{if(active)setError(e instanceof Error?e.message:'读取失败')});return()=>{active=false};},[identity,session]);
 async function inspect(){setBusy(true);setError('');try{setValue(await request())}catch(e){setError(e instanceof Error?e.message:'读取失败')}finally{setBusy(false)}}
 async function decide(revoke=false){if(!value)return;setBusy(true);setError('');try{
  if(revoke&&value.decision){await request(`/decisions/${encodeURIComponent(value.decision.decision_id)}/revoke`,{});}
  else{command.current??={request_digest:value.request.digest,idempotency_key:crypto.randomUUID(),not_before:new Date().toISOString(),expires_at:new Date(Date.now()+4*3600*1000).toISOString()};await request('/approve',command.current);}
  setValue(await request());setConfirmed(false);
 }catch(e){setError(`${e instanceof Error?e.message:'决定结果未知'} 请先查询状态；不会自动重新签发。`)}finally{setBusy(false)}}
 const spec=value?.request.record;
 const self=value?.request.subject_id===session.principal.principalId;
 return <section aria-label="有界任务审核" className="bounded-task"><h2>审阅任务范围</h2><p>本次签发办理资格；模型准入、Plan确认、独立Run准入和成果接受分别保留正式记录。</p>{error&&<p role="alert">{error} <a href={`/api/workbench/v1/login?returnTo=${encodeURIComponent(location.pathname+location.search)}`}>重新登录并返回本事项</a></p>}<button disabled={busy} onClick={()=>void inspect()}>查询当前状态</button>{value&&spec&&<div className="bounded-task-columns"><div><section><h3>任务与合成数据</h3><dl><dt>验证路径</dt><dd>{spec.purpose==='SAME_CASE_DELIVERY'?'原供应商交付及时性案例':'独立隔离Native能力验证'}</dd><dt>精确根对象</dt><dd>{spec.root.resource_id}<br/>修订 {spec.root.revision_id}</dd><dt>数据快照</dt><dd>{spec.source_snapshot.resource_id} / {spec.source_snapshot.revision_id}</dd><dt>固定判定日期</dt><dd>{spec.determination_date}</dd><dt>组织与环境</dt><dd>{value.request.tenant_id} / {value.request.security_domain}</dd></dl><p>仅合成数据；不跨scope继承授权，不读取真实企业订单。</p></section><section><h3>授权范围</h3><ul>{spec.permissions.map(p=><li key={`${p.owner}:${p.action}:${p.exact_resource}`}>{p.owner} / {p.action}<br/><code>{p.exact_resource}</code></li>)}</ul><p>正式owner创建的范围内后继：{spec.derived_permissions.map(p=>`${p.owner}/${p.action}`).join('、')||'本申请未包含自动后继权限'}。</p>{spec.configuration&&<><h3>精确模型配置与原预算</h3><p>{spec.configuration.revision_id}；读取{spec.configuration.read_seconds}秒，受总期限{spec.configuration.total_seconds}秒约束；清理{spec.configuration.cleanup_seconds}秒不增加读取时间。</p><p>原policy为8；历史修订保留；本对象累计上限{spec.configuration.cumulative_call_cap}，不是新增{spec.configuration.cumulative_call_cap}次。全部历史费用及UNKNOWN预留计入原USD10上限。签发本任务不会调用模型。</p></>}</section></div><aside><section><h3>职责与当前状态</h3><dl><dt>申请人</dt><dd>{value.request.subject_id}</dd><dt>当前审批人</dt><dd>{session.principal.principalId}</dd><dt>状态</dt><dd>{value.status==='ACTIVE'?'当前任务授权有效':'尚无当前有效任务授权'}</dd></dl>{self&&<p>当前为申请人身份，不能独立签发。</p>}{value.reasonCode&&<p>{value.reasonCode}</p>}{value.decision&&<p>签发人 {value.decision.issuer_id}<br/>有效至 {formatTime(value.decision.expires_at)}</p>}</section><section><h3>决定影响</h3><p>本次签发有效4小时；登录、刷新不续期。撤销或到期后停止新的受控效应，保留已派发记录及UNKNOWN。</p><p>已有资源发布不重复办理；任务授权不自动确认计划、启动Run或接受成果。</p>{value.status!=='ACTIVE'?<><label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>本人已核对精确根对象、scope、范围与决定影响。</label><button className="px-primary-button" disabled={busy||self||!confirmed} onClick={()=>void decide()}>本人独立签发任务范围</button></>:<button disabled={busy||self} onClick={()=>void decide(true)}>撤销当前任务授权</button>}</section></aside><details><summary>完整精确修订与摘要</summary><pre>{JSON.stringify(value,null,2)}</pre></details></div>}</section>
}
