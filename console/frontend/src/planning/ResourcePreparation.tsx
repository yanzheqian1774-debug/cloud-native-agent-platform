import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {readWorkbenchSession} from '../api/businessWorkspace';
import {useAutomaticReadback} from '../journey/useAutomaticReadback';
import {formatTime} from '../journey/formatTime';
import * as api from './api';

const kinds:Record<string,string>={agent:'职责',runtime:'运行配置',skill:'技能',knowledge:'资料来源',mcp:'连接工具'};
const gaps:Record<string,string>={RESOURCE_SOURCE_OUTSIDE_WORK_SCOPE:'资料来源超出本次已授权范围',MCP_CREDENTIAL_AND_TOOL_VALIDATION_REQUIRED:'连接工具的凭据与操作尚未验证',NATIVE_RUNTIME_OR_CREDENTIAL_UNAVAILABLE:'运行环境或凭据暂不可用',RESOURCE_EXECUTOR_SOURCE_MISMATCH:'技能的数据契约与本次来源不匹配',RESOURCE_EXECUTOR_SCHEMA_MISMATCH:'技能输入输出契约不匹配',RESOURCE_PERMISSION_REVOKED:'本次必要权限已撤销',RESOURCE_TASK_OPERATION_GAPS:'必要操作仍有缺口',RESOURCE_VALIDATION_FAILED:'资源技术验证未通过',RESOURCE_EMPLOYEE_PUBLICATION_INCOMPLETE:'角色装配尚未发布完成'};
function message(reason?:string){return reason?gaps[reason]??'本次准备未通过核验，平台已保留缺口与原有结果':'仍有必要准备项待核验'}

export function ResourcePreparation({id,approved,enabled,onPrepared,policyStamp=""}:{id:string;approved:api.Confirmation;enabled:boolean;policyStamp?:string;onPrepared?:(snapshot:api.Snapshot)=>void}){
 const report=useRef(onPrepared);useLayoutEffect(()=>{report.current=onPrepared},[onPrepared]);
 const identity=JSON.stringify([id,approved.plan.version,approved.digest,policyStamp]);
 const [loaded,setLoaded]=useState<{identity:string;value:api.ResourcePreparation}|null>(null);
 const [issue,setIssue]=useState<{identity:string;text:string}|null>(null);
 const [pending,setPending]=useState(false);
 const locator=useRef<{identity:string;key:string;subject:string;scope:string}|null>(null),epoch=useRef(0),flight=useRef(false);
 const value=loaded?.identity===identity?loaded.value:null;
 const error=issue?.identity===identity?issue.text:null;
 function verify(result:api.ResourcePreparation,subject:string){if(result.planId!==id||result.planVersion!==approved.plan.version||result.planDigest!==approved.digest||result.subject!==subject)throw new Error('RESOURCE_PREPARATION_CONTEXT_MISMATCH')}
 useEffect(()=>{
  if(!enabled)return;
  const token=++epoch.current;let active=true;
  async function prepare(){
   setPending(true);
   try{
    const session=await readWorkbenchSession();if(!active)return;
    const p=session.principal;
    const storage='resource-preparation:'+JSON.stringify([p.principalId,p.tenantId,p.securityDomain,identity]);
    const saved=sessionStorage.getItem(storage),key=saved??crypto.randomUUID();
    sessionStorage.setItem(storage,key);locator.current={identity,key,subject:p.principalId,scope:JSON.stringify([p.tenantId,p.securityDomain])};
    let result:api.ResourcePreparation;
    if(saved){
     try{result=await api.readResourcePreparation(id,approved.plan.version,key)}
     catch(e){if(!(e&&typeof e==='object'&&'status'in e&&e.status===404))throw e;
      // Only this DB-only owner command is idempotently recovered after an
      // authenticated absence. It cannot call a model or dispatch a Run.
      result=await api.prepareResources(id,approved.plan.version,key,session.csrfToken)}
    }else result=await api.prepareResources(id,approved.plan.version,key,session.csrfToken);
    verify(result,p.principalId);
    const after=await readWorkbenchSession();if(after.principal.principalId!==p.principalId||after.principal.tenantId!==p.tenantId||after.principal.securityDomain!==p.securityDomain)throw new Error('RESOURCE_PREPARATION_IDENTITY_CHANGED');
    if(active&&token===epoch.current){setLoaded({identity,value:result});setIssue(null);setPending(false);if(result.resourceSnapshot)report.current?.(result.resourceSnapshot)}
   }catch(e){if(active&&token===epoch.current){setIssue({identity,text:e instanceof Error?e.message:'RESOURCE_PREPARATION_UNAVAILABLE'});setPending(Boolean(locator.current)&&!(e instanceof Error&&/IDENTITY_CHANGED|CONTEXT_MISMATCH/.test(e.message)))}}
  }
  void prepare();return()=>{active=false;if(epoch.current===token)epoch.current=token+1};
 // The immutable Plan digest binds the effect; refreshed parent objects do not resend.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[identity,enabled]);
 useAutomaticReadback({identity,enabled:enabled&&pending&&!value,read:async()=>{
  const saved=locator.current;if(!saved||saved.identity!==identity||flight.current)return false;
  flight.current=true;const token=epoch.current;
  try{const result=await api.readResourcePreparation(id,approved.plan.version,saved.key);verify(result,saved.subject);const session=await readWorkbenchSession();if(session.principal.principalId!==saved.subject||JSON.stringify([session.principal.tenantId,session.principal.securityDomain])!==saved.scope)throw new Error('RESOURCE_PREPARATION_IDENTITY_CHANGED');if(token!==epoch.current)return false;setLoaded({identity,value:result});setIssue(null);setPending(false);if(result.resourceSnapshot)report.current?.(result.resourceSnapshot);return false}
  catch(e){if(token!==epoch.current)return false;const status=e&&typeof e==='object'&&'status'in e?e.status:undefined;if(status===401||status===403||status===404||status===409||(e instanceof Error&&/IDENTITY_CHANGED|CONTEXT_MISMATCH/.test(e.message))){setPending(false);return false}throw e}
  finally{flight.current=false}
 }});
 if(!enabled)return null;
 return <section className="planning-card resource-auto-preparation" aria-label="平台自动准备资源" aria-live="polite">
  <h2>资源准备 · 平台核验，按需介入</h2>
  {!value&&!error&&<p role="status">{pending?'正在核对必要资源、验证发布与角色装配…':'正在读取本次准备记录…'}</p>}
  {error&&<div role="alert"><p>本次准备暂未完成。平台保留原请求并核实结果，不会重跑原任务。</p><details><summary>查看核查依据</summary><code>{error}</code></details></div>}
  {value&&<><p><strong>{value.state==='READY'?'资源已备齐，角色装配完成':value.state==='PARTIALLY_READY'?'部分资源已备齐，其余缺口已保留':'必要准备项尚未通过核验'}</strong></p><p>平台按本次已授权范围自动处理；资源负责人无需逐项确认。实际执行仍核验行动权限与预算。</p>
   <div className="planning-table-scroll"><table className="resource-auto-table"><caption>本次必要资源与核验结果</caption><thead><tr><th>资源类型</th><th>资源</th><th>技术核验</th><th>准备结果</th></tr></thead><tbody>{value.resources.map(r=><tr key={r.kind+':'+r.reference.resource_id+':'+r.reference.revision_id}><td>{kinds[r.kind]??'资源'}</td><td>{r.name??'本次必要资源'}</td><td>{r.state==='READY'?'通过':message(r.reason)}</td><td>{r.state==='READY'?(r.case==='EXISTING'?'复用已发布版本':'验证后已发布'):'保留缺口'}</td></tr>)}</tbody></table></div>
   {value.assembly.state!=='ASSEMBLED'&&<p role="status">角色装配：{message(value.assembly.reason)}。已通过项保留，不要求重复确认。</p>}
   <p className="journey-muted">核对时间：{formatTime(value.createdAt)} · {value.state==='READY'?'接续执行前的独立准入核验':'平台保留本次核验记录与后续处理依据'}</p>
   <details className="journey-technical"><summary>查看策略决定、精确版本与装配依据</summary><pre>{JSON.stringify({policy:value.policy,resources:value.resources,assembly:value.assembly,requestKey:value.requestKey},null,2)}</pre></details>
  </>}
 </section>;
}
