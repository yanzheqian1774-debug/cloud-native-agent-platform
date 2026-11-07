import {useEffect,useRef,useState} from 'react';
import {getEmployeeRelations,getWorkbenchSession,workbenchPrincipalKey,DigitalEmployeeRequestError,type EmployeeDefinitionSummary,type EmployeeRelationMode,type EmployeeRelationPage,type EmployeeRelationItem} from '../api/digitalEmployees';
import './EmployeeRelations.css';

const titles={history:'已保存的员工版本',instances:'关联实例',assignments:'关联工作分配'};
const operations={history:'READ_EMPLOYEE_HISTORY',instances:'READ_EMPLOYEE_INSTANCES',assignments:'READ_INSTANCE_ASSIGNMENTS'};
const labels:Record<string,string>={PUBLISHED:'已发布',NOT_PUBLISHED:'未发布',DRAFT:'草稿',VALIDATED:'验证通过',APPROVED:'已批准',REJECTED:'已拒绝',DEPRECATED:'已弃用',ENABLED:'已启用',DISABLED:'已停用',ACTIVE:'生效中',INACTIVE:'未生效'};
const identityOf=(item:EmployeeRelationItem)=>'employeeDefinitionRevisionId' in item?item.employeeDefinitionRevisionId:'assignmentId' in item?item.assignmentId:item.instanceId;

function verify(value:EmployeeRelationPage,definition:EmployeeDefinitionSummary,mode:EmployeeRelationMode,instanceId?:string){
 const p=value.parent;
 if(value.relation!==operations[mode]||value.visibility!=='AUTHORIZED_ONLY'||value.executionStarted!==false||!Array.isArray(value.items)||!p)throw Error('关联返回内容尚未核实。');
 if(mode==='assignments'?p.instanceId!==instanceId:p.employeeDefinitionId!==definition.employeeDefinitionId||p.employeeDefinitionRevisionId!==definition.employeeDefinitionRevisionId||p.employeeDefinitionDigest!==definition.employeeDefinitionDigest)throw Error('关联返回内容与当前员工版本不一致。');
 for(const item of value.items){
  if(mode==='history'){
   if(!('employeeDefinitionId' in item)||item.employeeDefinitionId!==definition.employeeDefinitionId||!item.employeeDefinitionRevisionId||!/^[a-f0-9]{64}$/.test(item.employeeDefinitionDigest))throw Error('员工版本关联不一致。');
  }else if(mode==='instances'){
   if(!('instanceId' in item)||'assignmentId' in item||!item.employeeDefinition||item.employeeDefinition.employeeDefinitionId!==definition.employeeDefinitionId||item.employeeDefinition.employeeDefinitionRevisionId!==definition.employeeDefinitionRevisionId||item.employeeDefinition.digest!==definition.employeeDefinitionDigest)throw Error('实例与当前员工版本不一致。');
  }else if(!('assignmentId' in item)||item.instanceId!==instanceId)throw Error('工作分配与当前实例不一致。');
 }
}

export function EmployeeRelations({definition,mode,instanceId,onRevision,onInstance,onAssignment}:{definition:EmployeeDefinitionSummary;mode:EmployeeRelationMode;instanceId?:string;onRevision?:(item:EmployeeDefinitionSummary)=>void;onInstance?:(id:string)=>void;onAssignment?:(id:string)=>void}){
 const identity=JSON.stringify([mode,definition.employeeDefinitionId,definition.employeeDefinitionRevisionId,definition.employeeDefinitionDigest,instanceId??'']);
 const [loaded,setLoaded]=useState<{identity:string;value:EmployeeRelationPage}|null>(null),[issue,setIssue]=useState<{identity:string;text:string}|null>(null),[busy,setBusy]=useState(false);
 const epoch=useRef(0),controller=useRef<AbortController|null>(null),principal=useRef<string|null>(null),flight=useRef(false);
 const page=loaded?.identity===identity?loaded.value:null,error=issue?.identity===identity?issue.text:'';
 async function read(cursor?:string){
  if(flight.current||mode==='assignments'&&!instanceId)return;
  flight.current=true;const token=epoch.current,old=page;controller.current?.abort();const current=new AbortController();controller.current=current;setBusy(true);setLoaded(null);setIssue(null);
  try{
   const before=await getWorkbenchSession(current.signal),actor=workbenchPrincipalKey(before);
   if(principal.current&&principal.current!==actor)throw Error('登录身份已变化，请重新进入员工管理。');
   principal.current=actor;
   const value=await getEmployeeRelations(definition,mode,instanceId,cursor,current.signal);
   if(workbenchPrincipalKey(await getWorkbenchSession(current.signal))!==actor)throw Error('登录身份已变化，请重新进入员工管理。');
   verify(value,definition,mode,instanceId);if(token!==epoch.current)return;
   const items=cursor&&old?[...old.items,...value.items]:value.items,seen=new Set<string>();
   if(items.some(item=>{const id=identityOf(item);if(!id||seen.has(id))return true;seen.add(id);return false}))throw Error('关联分页内容重复或不完整，请重新读取。');
   setLoaded({identity,value:{...value,items}});
  }catch(e){if(token===epoch.current&&!(e instanceof DOMException&&e.name==='AbortError')){setLoaded(null);setIssue({identity,text:e instanceof Error?e.message:'当前关联暂不可读取。'});if(e instanceof DigitalEmployeeRequestError&&e.status===401)window.dispatchEvent(new Event('workbench-session-expired'))}}
  finally{if(token===epoch.current){flight.current=false;setBusy(false)}}
 }
 useEffect(()=>{
  const version=++epoch.current;flight.current=false;principal.current=null;queueMicrotask(()=>{if(epoch.current===version)void read()});
  const withdraw=()=>{epoch.current++;controller.current?.abort();flight.current=false;setLoaded(null);setBusy(false);setIssue({identity,text:'当前登录已失效，请重新进入员工管理。'})};
  const focus=()=>{void getWorkbenchSession().then(s=>{if(principal.current&&workbenchPrincipalKey(s)!==principal.current)withdraw()}).catch(withdraw)};
  window.addEventListener('workbench-session-expired',withdraw);window.addEventListener('focus',focus);
  return()=>{controller.current?.abort();epoch.current=version+1;flight.current=false;window.removeEventListener('workbench-session-expired',withdraw);window.removeEventListener('focus',focus)};
 // Immutable parent identity scopes every read; callbacks never dispatch writes.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[identity]);
 return <section className="employee-relations" aria-label={titles[mode]} aria-busy={busy}><header><div><h3>{titles[mode]}</h3><p>按当前可读范围显示；查看与选择不会创建实例或启动任务。</p></div><button type="button" disabled={busy||mode==='assignments'&&!instanceId} onClick={()=>void read()}>刷新列表</button></header>
 {mode==='assignments'&&!instanceId?<p>请先在实例页选择并核对一个关联实例。</p>:<>{busy&&<p role="status">正在读取当前关联…</p>}{error&&<div role="alert"><p>关联暂未读回，不能据此判断没有记录。</p><details><summary>核查信息</summary>{error}</details></div>}
 {page&&<>{page.items.length===0&&<p role="status">当前可读范围内未返回关联记录；不代表该员工在其他权限范围内没有关联。</p>}<ul>{page.items.map(item=>{
  if('employeeDefinitionId' in item)return <li key={identityOf(item)}><div><strong>{item.role}</strong><span>{labels[item.lifecycleState??item.publicationState]??'状态待核对'} · {item.employeeDefinitionRevisionId===definition.employeeDefinitionRevisionId?'当前查看版本':'已保存版本'}</span><details><summary>版本标识</summary><code>{item.employeeDefinitionRevisionId}</code><p>{item.employeeDefinitionDigest}</p></details></div><button type="button" disabled={item.employeeDefinitionRevisionId===definition.employeeDefinitionRevisionId} onClick={()=>onRevision?.(item)}>查看此版本</button></li>;
  if('assignmentId' in item)return <li key={identityOf(item)}><div><strong>{item.businessRole}</strong><span>{labels[item.lifecycle]??'状态待核对'} · 绑定情况以正式分配记录为准</span></div><button type="button" onClick={()=>onAssignment?.(item.assignmentId)}>查看工作分配</button></li>;
  return <li key={identityOf(item)}><div><strong>{item.ownerId}</strong><span>{labels[item.lifecycle]??'状态待核对'} · 启用不代表正在运行或健康</span><details><summary>实例标识</summary><code>{item.instanceId}</code></details></div><button type="button" onClick={()=>onInstance?.(item.instanceId)}>查看此实例</button></li>;
 })}</ul>{page.scanLimited&&<p role="status">已达本次核对上限，列表仍可能不完整；未核实的记录不会记为空。</p>}{page.nextCursor&&<button type="button" disabled={busy} onClick={()=>void read(page.nextCursor!)}>加载更多</button>}</>}
 </>}
 </section>;
}
