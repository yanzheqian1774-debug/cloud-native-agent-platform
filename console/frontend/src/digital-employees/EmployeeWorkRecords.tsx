import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {getEmployeeWorkRecords,getWorkbenchSession,workbenchPrincipalKey,type EmployeeDefinition,type EmployeeWorkRecords as Records} from '../api/digitalEmployees';

const labels:Record<string,string>={NOT_STARTED:'尚未开始',PENDING:'等待执行',RUNNING:'执行中',SUCCEEDED:'执行完成',FAILED:'执行失败',CANCELLED:'已取消',RECOVERY_REQUIRED:'需要核对执行结果'};
export function EmployeeWorkRecords({definition}:{definition:EmployeeDefinition}){
 const identity=JSON.stringify([definition.employeeDefinitionId,definition.employeeDefinitionRevisionId,definition.employeeDefinitionDigest]);
 const [state,setState]=useState<{identity:string;data?:Records;error?:string}|null>(null),[refresh,setRefresh]=useState(0);
 useEffect(()=>{
  let live=true;const controller=new AbortController();
  void (async()=>{
   try{
    const session=await getWorkbenchSession(controller.signal),actor=workbenchPrincipalKey(session);
    const value=await getEmployeeWorkRecords(definition,controller.signal);
    if(workbenchPrincipalKey(await getWorkbenchSession(controller.signal))!==actor||value.subject!==session.principal.principalId||value.scope.tenantId!==session.principal.tenantId||value.scope.securityDomain!==session.principal.securityDomain)throw Error('登录身份已变化，请重新进入员工管理。');
    const ref=value.employeeDefinition;
    if(value.schemaVersion!=='employee-work-records.v1'||value.visibility!=='AUTHORIZED_ONLY'||value.executionStarted!==false||ref.employeeDefinitionId!==definition.employeeDefinitionId||ref.employeeDefinitionRevisionId!==definition.employeeDefinitionRevisionId||ref.employeeDefinitionDigest!==definition.employeeDefinitionDigest||!Array.isArray(value.items)||typeof value.scanLimited!=='boolean'||value.items.some(w=>!/^[a-f0-9]{64}$/.test(w.executionDigest)||!w.title||(w.originConversationId!=null&&(typeof w.originConversationId!=='string'||!w.originConversationId))||(w.originVerified!==undefined&&typeof w.originVerified!=='boolean')||!['COORDINATION','TASK_EXECUTION'].includes(w.participation)||!Number.isInteger(w.planVersion)||!Array.isArray(w.tasks)||w.tasks.some(t=>!t.taskId||!t.title)))throw Error('工作记录与当前员工版本不一致。');
    if(new Set(value.items.map(w=>w.executionDigest)).size!==value.items.length)throw Error('工作记录重复，请重新读取。');
    if(live)setState({identity,data:value});
   }catch(error){if(live)setState({identity,error:error instanceof Error?error.message:'工作记录暂未读回。'})}
  })();
  const withdraw=()=>{live=false;controller.abort();setState({identity,error:'登录已失效，请重新进入员工管理。'})};
  const focus=()=>{setState(null);setRefresh(v=>v+1)};
  window.addEventListener('workbench-session-expired',withdraw);window.addEventListener('focus',focus);
  return()=>{live=false;controller.abort();window.removeEventListener('workbench-session-expired',withdraw);window.removeEventListener('focus',focus)};
 // Immutable definition is the read boundary; no work is inferred from names or latest versions.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[identity,refresh]);
 const current=state?.identity===identity?state:null;
 return <section className="employee-work-records" aria-label="员工工作记录"><header><div><h3>关联工作</h3></div><button onClick={()=>{setState(null);setRefresh(v=>v+1)}}>刷新工作记录</button></header>{!current&&<p role="status">正在核对任务参与记录…</p>}{current?.error&&<div role="alert"><p>工作记录暂不可读，不能据此判断没有任务。</p><details><summary>核查信息</summary>{current.error}</details></div>}{current?.data&&<>{current.data.items.length?<div className="employee-work-records-table"><table><thead><tr><th>目标 / 来源</th><th>承担者 / 固定版本</th><th>进度与阻塞</th><th>下一步</th><th>详情</th></tr></thead><tbody>{current.data.items.map(w=><tr key={w.executionDigest}><td><strong>{w.title}</strong><small>{w.participation==='COORDINATION'?'统筹工作':'参与执行'} · {w.tasks.length} 项任务</small>{w.tasks.map(t=><small key={t.taskId}>{t.title}</small>)}</td><td>{definition.role}<small>固定版本 · 方案 v{w.planVersion}</small></td><td><span className="employee-work-state">{labels[w.state]??'状态待核对'}</span></td><td>{w.state==='SUCCEEDED'?'查看已保存结果':w.state==='FAILED'||w.state==='RECOVERY_REQUIRED'?'核对失败或未确认结果':w.state==='NOT_STARTED'?'查看执行安排':'查看进展与阻塞'}</td><td><Link to={'/tasks?'+new URLSearchParams({work:w.executionDigest,...(w.originConversationId?{origin:w.originConversationId}:{}),...(w.state==='SUCCEEDED'?{workView:'result'}:{})})}>查看任务</Link></td></tr>)}</tbody></table></div>:<p>当前可读范围内未返回这个版本的工作记录。</p>}{current.data.scanLimited&&<p role="status">本次达到核对上限，列表可能不完整。</p>}<p className="employee-work-records-note">仅展示当前查看的固定版本参与记录。执行完成不代表业务验收通过；查看结果不会重新执行任务。</p></>}</section>;
}
