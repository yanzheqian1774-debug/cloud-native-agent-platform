import {useRef,useState} from 'react';
import {getWorkbenchSession,workbenchPrincipalKey,type WorkbenchSession} from '../api/digitalEmployees';
import {formatTime} from '../journey/formatTime';

type Admission={budgetSummary?:{calls:number;charged_or_reserved_microusd:number};request:{context_id:string;subject_id:string;tenant_id:string;security_domain:string;account_revision:number;digest:string;record:{configuration:{profile_revision_id:string;profile_digest:string;configuration_digest:string;ledger_id:string;calls:number;cost_microusd:number;input_tokens:number;output_tokens:number}}};decision:{admission_id:string;issuer_id:string;expires_at:string}|null;status:string;reasonCode:string|null};
export function ContextAdmissionPanel({session}:{session:WorkbenchSession}){
 const [identity,setIdentity]=useState(new URLSearchParams(location.search).get('context')??'');
 const [value,setValue]=useState<Admission|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const command=useRef<{fingerprint:string;payload:{request_digest:string;expires_at:string;idempotency_key:string}}|null>(null);
 async function request(method:'GET'|'POST',body?:unknown){
  const current=await getWorkbenchSession();
  if(workbenchPrincipalKey(current)!==workbenchPrincipalKey(session))throw new Error('当前身份已变化，请重新登录并核对原对象。');
  const response=await fetch(`/api/workbench/v1/authorization/context-admissions/${encodeURIComponent(identity)}`,{method,credentials:'same-origin',headers:method==='POST'?{'Content-Type':'application/json','X-CSRF-Token':current.csrfToken}:{},...(body?{body:JSON.stringify(body)}:{})});
  const data=await response.json();
  if(!response.ok)throw new Error(response.status===401?'登录已失效；重新登录后返回本对象，不会自动提交。':`本次操作未完成：${data.reasonCode??'CONTEXT_ADMISSION_UNAVAILABLE'}。诊断：${data.requestId??'未提供'}。`);
  return data;
 }
 async function inspect(){setBusy(true);setError('');setValue(null);try{setValue(await request('GET'))}catch(e){setError(e instanceof Error?e.message:'读取失败')}finally{setBusy(false)}}
 async function approve(){if(!value)return;setBusy(true);setError('');try{
  const fingerprint=`${identity}:${value.request.digest}`;
  if(command.current?.fingerprint!==fingerprint)command.current={fingerprint,payload:{request_digest:value.request.digest,expires_at:new Date(Date.now()+60*60*1000).toISOString(),idempotency_key:`context-admission:${crypto.randomUUID()}`}};
  await request('POST',command.current.payload);setValue(await request('GET'));
 }catch(e){setError(e instanceof Error?e.message:'决定结果待核对；不要重复创建申请。')}finally{setBusy(false)}}
 return <section className="employee-authorization-request" aria-label="合成问题独立调用准入"><h2>合成问题 · 独立调用准入</h2><p>仅覆盖精确 context 的理解、补问与草稿。复用原模型和原账本；全部历史用量与 UNKNOWN 预留继续累计，不授予资源发布或 Native 执行。</p><label>实际 context 编号<input value={identity} disabled={busy} onChange={e=>{setIdentity(e.target.value);setValue(null)}}/></label><button disabled={busy||!identity.trim()} onClick={()=>void inspect()}>核对调用对象</button>{error&&<p role="alert">{error}</p>}{value&&<><dl><dt>状态</dt><dd>{value.status==='ACTIVE'?'当前准入有效；每次调用仍核验精确 Grant':'尚未取得当前有效准入'}</dd><dt>业务主体</dt><dd>{value.request.subject_id}</dd><dt>组织与隔离环境</dt><dd>{value.request.tenant_id} / {value.request.security_domain}</dd><dt>账号修订</dt><dd>{value.request.account_revision}</dd><dt>模型配置修订</dt><dd><code>{value.request.record.configuration.profile_revision_id}</code></dd><dt>原预算上限</dt><dd>{value.request.record.configuration.calls} 次 / USD {(value.request.record.configuration.cost_microusd/1000000).toFixed(6)}，不是剩余额度</dd><dt>单次 token 上限</dt><dd>输入 {value.request.record.configuration.input_tokens} / 输出 {value.request.record.configuration.output_tokens}</dd><dt>账本</dt><dd><code>{value.request.record.configuration.ledger_id}</code></dd><dt>请求摘要</dt><dd><code>{value.request.digest}</code></dd></dl>{value.budgetSummary&&<p>原账本已计 {value.budgetSummary.calls} 次；结算与未结算预留合计 USD {(value.budgetSummary.charged_or_reserved_microusd/1000000).toFixed(6)}。派发时重新原子核验剩余额度。</p>}{value.decision&&<p>最近签发：{value.decision.issuer_id}；截止 {formatTime(value.decision.expires_at)}。{value.reasonCode&&`当前检查：${value.reasonCode}`}</p>}<details><summary>精确配置与独立记录</summary><pre>{JSON.stringify(value,null,2)}</pre></details>{value.status!=='ACTIVE'&&<><p>本人确认此实际对象与合成范围后签发一小时准入。草稿辅助和模型 Grant 仍须分别审批；本操作不会自动调用模型。</p><button className="px-primary-button" disabled={busy||session.principal.principalId===value.request.subject_id} onClick={()=>void approve()}>本人独立签发此 context</button></>}</>}</section>
}
