import {useState} from 'react';
import {formatTime} from '../journey/formatTime';

type Delegation={delegation_id:string;issuer_id:string;created_at:string;revoked_at:string|null;development_stopped:boolean;original_digest:string;approval:{task_id:string;subject_id:string;expires_at?:string};development_revision?:{digest:string}|null;cases:{context_id:string;record:{case_label:string}}[]};
export function TaskDelegationPanel(){
 const [identity,setIdentity]=useState(new URLSearchParams(window.location.search).get('delegation')??'');
 const [value,setValue]=useState<Delegation|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function inspect(){setBusy(true);setError('');setValue(null);try{
  const response=await fetch(`/api/workbench/v1/authorization/task-delegations/${encodeURIComponent(identity)}`,{credentials:'same-origin'});
  if(!response.ok)throw new Error(response.status===401?'登录已失效，请重新登录。':'当前身份不能读取此精确委托，或该服务尚未配置。');
  setValue(await response.json() as Delegation);
 }catch(e){setError(e instanceof Error?e.message:'读取失败，未作任何授权或调用。')}finally{setBusy(false)}}
 return <section className="employee-authorization-request"><h2>已授权任务范围</h2><p>读取正式委托与追加修订，不依据本地缓存推断授权。任务授权不会扩展到未登记案例。</p><label>精确委托编号<input value={identity} onChange={e=>{setIdentity(e.target.value);setValue(null)}} disabled={busy}/></label><button disabled={busy||!identity.trim()} onClick={()=>void inspect()}>{busy?'正在读回…':'查看正式授权'}</button>{error&&<p role="alert">{error}</p>}{value&&<><dl><dt>任务</dt><dd>{value.approval.task_id}</dd><dt>被授权主体</dt><dd>{value.approval.subject_id}</dd><dt>独立签发人</dt><dd>{value.issuer_id}</dd><dt>签发时间</dt><dd>{formatTime(value.created_at)}</dd><dt>状态</dt><dd>{value.revoked_at?'已撤销':value.development_stopped?'已暂停或完成':value.development_revision?'持续开发修订已登记；每次操作仍核验有效性':'原有界委托；每次操作仍核验期限'}</dd></dl><h3>显式登记案例</h3><ul>{value.cases.map(item=><li key={item.context_id}>{item.record.case_label}<code>{item.context_id}</code></li>)}</ul><details><summary>原始委托与修订摘要</summary><code>{value.original_digest}</code><p>{value.development_revision?.digest}</p></details></>}<p>本页精确权限申请可由独立管理员审批。任务委托尚无正式“待审批申请”接口，因此不提供模拟的一键签发。</p></section>;
}
