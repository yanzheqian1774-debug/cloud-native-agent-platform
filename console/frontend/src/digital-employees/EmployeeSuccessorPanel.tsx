import {useManagementActions} from '../management/useManagementActions';
import {EmployeeResponsibilityEditor} from './EmployeeResponsibilityEditor';
import {validResponsibilityBinding} from './employeeResponsibilityBindings';
import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {createEmployeeDefinition,getEmployeeDefinition,getWorkbenchSession,workbenchPrincipalKey,DigitalEmployeeRequestError,type EmployeeCreateCommand,type EmployeeDefinition,type EmployeeCommandResult,type EmployeeMember,type ResponsibilityBinding} from '../api/digitalEmployees';
import {EmployeeBoundResourceCard,EmployeeResourceComposition} from './EmployeeResourceComposition';
import {EmployeeResourcePicker} from './EmployeeResourcePicker';
import {successorDigest,verifySuccessor} from './employeeSuccessorState';

type Intent={command:EmployeeCreateCommand;digest:string;principal:string;state:'PREPARED'|'UNKNOWN'|'SAVED'};
const memberKey=(m:EmployeeMember)=>m.kind+'|'+m.resourceId;
function EmployeeSaveSummary({item,members}:{item:EmployeeDefinition;members:EmployeeMember[]}){
 const business=(m:EmployeeMember)=>['SKILL','MCP','KNOWLEDGE'].includes(m.kind);
 const selected=members.filter(business),removed=item.members.filter(business).filter(m=>!members.some(n=>memberKey(n)===memberKey(m)));
 const change=(m:EmployeeMember)=>{const before=item.members.find(n=>memberKey(n)===memberKey(m));return !before?'新增':before.revisionId===m.revisionId&&before.digest===m.digest?'保留':'替换版本'};
 return <section aria-label="本次保存的完整资源摘要"><h4>保存后共 {selected.length} 项业务资源</h4><p>另有 {members.length-selected.length} 项内部依赖，保留固定引用。</p>{selected.map(m=><div key={memberKey(m)}><strong>{change(m)}</strong><EmployeeBoundResourceCard member={m} item={item}/></div>)}{removed.map(m=><div key={memberKey(m)}><strong>移除</strong><EmployeeBoundResourceCard member={m} item={item}/></div>)}</section>;
}
export function EmployeeSuccessorPanel({item,onReadback,business=false,initialOpen=false}:{item:EmployeeDefinition;business?:boolean;initialOpen?:boolean;onReadback:(definition:EmployeeDefinition,result:EmployeeCommandResult)=>void}){
 const permissions=useManagementActions({kind:'employees',item});
 const identity=JSON.stringify([item.employeeDefinitionId,item.employeeDefinitionRevisionId,item.employeeDefinitionDigest]);
 const current=useRef(identity),epoch=useRef(0),flight=useRef(false);
 useLayoutEffect(()=>{const generation=epoch;current.current=identity;return()=>{current.current='';generation.current++}},[identity]);
 const [open,setOpen]=useState(initialOpen),[busy,setBusy]=useState(false),[responsibilities,setResponsibilities]=useState(item.responsibilities.join('\n')),[keep,setKeep]=useState(item.members.map(memberKey)),[added,setAdded]=useState<EmployeeMember[]>([]),[pickerPrincipal,setPickerPrincipal]=useState<string|null>(null),[intent,setIntent]=useState<Intent|null>(null),[actor,setActor]=useState(''),[message,setMessage]=useState('');
 const [bindings,setBindings]=useState<ResponsibilityBinding[]>(item.responsibilityBindings??[]);
 const storage=(principal:string)=>'employee-successor.v1:'+JSON.stringify([principal,identity]);
 useEffect(()=>{const token=++epoch.current;let live=true;void getWorkbenchSession().then(session=>{if(!live||token!==epoch.current)return;const principal=workbenchPrincipalKey(session),raw=sessionStorage.getItem(storage(principal));setActor(principal);if(raw){const old=JSON.parse(raw) as Intent;if(old.principal!==principal||old.command.employeeDefinitionId!==item.employeeDefinitionId||old.command.predecessorEmployeeRevisionId!==item.employeeDefinitionRevisionId||!['UNKNOWN','SAVED'].includes(old.state))throw Error('EMPLOYEE_SUCCESSOR_INTENT_INVALID');setIntent(old);setOpen(true)}}).catch(()=>{if(live)setMessage('原后继记录尚未核实；请核对当前账号与版本。')});return()=>{live=false};
 // Exact selected revision scopes its durable original intent.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[identity]);
 const members=[...new Map([...item.members.filter(m=>keep.includes(memberKey(m))&&(m.kind!=='AGENT'||!added.some(x=>x.kind==='AGENT'))),...added].map(m=>[memberKey(m),m])).values()];
 async function session(){const s=await getWorkbenchSession();if(!actor||workbenchPrincipalKey(s)!==actor)throw Error('登录身份已变化，请重新打开当前员工。');return s}
 async function readOriginal(value:Intent,valid:()=>boolean){
  await session();const definition=await getEmployeeDefinition(value.command.employeeDefinitionId,value.command.employeeDefinitionRevisionId);await session();verifySuccessor(definition,value.command,value.digest);if(!valid())return;
  const done={...value,state:'SAVED' as const};sessionStorage.setItem(storage(actor),JSON.stringify(done));setIntent(done);setMessage('已读回同一后继修订；没有再次提交。');
  onReadback(definition,{resourceKind:definition.resourceKind,employeeDefinitionId:definition.employeeDefinitionId,employeeDefinitionRevisionId:definition.employeeDefinitionRevisionId,employeeDefinitionDigest:definition.employeeDefinitionDigest,aggregateVersion:definition.aggregateVersion!,lifecycleState:definition.lifecycleState!});
 }
 async function act(kind:'prepare'|'submit'|'read'){
  if(flight.current)return;flight.current=true;setBusy(true);setMessage('');const context=current.current,token=epoch.current,valid=()=>context===current.current&&token===epoch.current;
  try{
   const s=await session();if(!valid())return;
   if(kind==='read'){if(intent)await readOriginal(intent,valid);return}
   const before=await getEmployeeDefinition(item.employeeDefinitionId,item.employeeDefinitionRevisionId);await session();if(!valid())return;
   if(before.employeeDefinitionDigest!==item.employeeDefinitionDigest||before.aggregateVersion!==item.aggregateVersion||!Number.isInteger(before.aggregateVersion))throw Error('原员工版本已变化，请重新读取后再准备。');
   if(!permissions.allows('CREATE',await permissions.refresh()))throw Error('当前账号暂不能保存修改；未保存内容仍保留。');
   if(kind==='prepare'){
    if(added.length&&pickerPrincipal!==actor)throw Error('资源选择身份已变化，请重新选择。');
    const duties=responsibilities.split('\n').map(x=>x.trim()).filter(Boolean);if(!duties.length||duties.length>32||duties.some(x=>x.length>500)||members.filter(x=>x.kind==='AGENT').length!==1)throw Error('请保留一个Agent并填写有效职责。');
    if(bindings.some(b=>!validResponsibilityBinding(b,duties,members)))throw Error('请先处理职责与资源的失效关联。');
    const command:EmployeeCreateCommand={employeeDefinitionId:item.employeeDefinitionId,employeeDefinitionRevisionId:'employee-revision:'+crypto.randomUUID(),predecessorEmployeeRevisionId:item.employeeDefinitionRevisionId,role:item.role,responsibilities:duties,responsibilityBindings:bindings.map(b=>({responsibility:b.responsibility,member:{...b.member}})),members:members.map(m=>({...m})),expectedVersion:before.aggregateVersion!,commandId:'employee-successor:'+crypto.randomUUID()};
    const digest=await successorDigest(s,command);if(valid())setIntent({command,digest,principal:actor,state:'PREPARED'});return;
   }
   if(!intent||intent.state!=='PREPARED')return;
   if(await successorDigest(s,intent.command)!==intent.digest)throw Error('后继内容与冻结摘要不符。');
   const marker:Intent={...intent,state:'UNKNOWN'};sessionStorage.setItem(storage(actor),JSON.stringify(marker));setIntent(marker);
   try{
    const response=await createEmployeeDefinition(marker.command,actor);await session();verifySuccessor(response,marker.command,marker.digest);if(!valid())return;
    const saved:Intent={...marker,state:'SAVED'};sessionStorage.setItem(storage(actor),JSON.stringify(saved));setIntent(saved);
    try{await readOriginal(saved,valid)}catch{if(valid())setMessage('后继保存回执已核对；详情读取尚未完成，请读取原后继修订。')}
   }catch(error){
    if(!valid())return;
    if(error instanceof DigitalEmployeeRequestError&&[400,403,404,409,422].includes(error.status)&&!error.unknownResult){sessionStorage.setItem(storage(actor)+':rejected:'+marker.command.commandId,JSON.stringify(marker));sessionStorage.removeItem(storage(actor));setIntent(null);throw error}
    try{await readOriginal(marker,valid)}catch{if(valid())setMessage('原提交结果尚未核实；保留同一修订，只读取原记录，不重复创建。')}
   }
  }catch(error){if(valid())setMessage(error instanceof DigitalEmployeeRequestError&&error.reasonCode==='EMPLOYEE_SUCCESSOR_ALREADY_EXISTS'?'该版本已有后继记录。请从员工版本记录打开已有后继后继续修改；本次没有保存新草稿。':error instanceof Error?error.message:'后继尚未核实；原版本保留。')}
  finally{flight.current=false;if(valid())setBusy(false)}
 }
 return <section className="employee-form-card" aria-label="同一员工后继维护"><h3>{business?(open?"编辑职责与资源":"已保存的职责与资源"):"维护后继版本"}</h3>{(!business||open)&&<p>保留当前修订和已有引用，准备同一员工的新职责与准确资源版本。保存草稿不代表发布或运行。</p>}{!permissions.allows('CREATE')&&<p role="status">{permissions.ready?'当前账号仅可查看，未保存内容仍保留。':'操作资格尚未核实，未保存内容仍保留。'}<button onClick={()=>void permissions.refresh()}>重新核对操作资格</button></p>}{business&&!open&&<EmployeeResourceComposition item={item} compact/>}<>{!open&&permissions.allows('CREATE')&&<button type="button" className="employee-secondary-button" disabled={busy||!actor} onClick={()=>setOpen(true)}>{business?"继续修改职责与资源":"准备员工后继"}</button>}</>{open&&<><label>{business?"职能职责（每行一项）":"后继职责（每行一项）"}<textarea aria-label={business?"职能职责":"后继职责"} rows={3} disabled={busy||!permissions.allows('CREATE')||Boolean(intent)} value={responsibilities} onChange={e=>setResponsibilities(e.target.value)}/></label>{business?<fieldset disabled={busy||!permissions.allows('CREATE')||Boolean(intent)}><legend>保留或替换已绑定资源</legend>{item.members.filter(m=>['SKILL','MCP','KNOWLEDGE'].includes(m.kind)).map((m,i)=><div key={memberKey(m)}><label><input type="checkbox" aria-label={'保留已绑定资源 '+(i+1)} checked={keep.includes(memberKey(m))} onChange={()=>setKeep(xs=>xs.includes(memberKey(m))?xs.filter(k=>k!==memberKey(m)):[...xs,memberKey(m)])}/>保留此资源</label><EmployeeBoundResourceCard member={m} item={item}/></div>)}<p>选择同一资源的新发布版本会替换草稿中的原绑定。内部依赖保持原引用，已有任务不变。</p></fieldset>:<><fieldset disabled={busy||!permissions.allows('CREATE')||Boolean(intent)}><legend>保留原成员</legend>{item.members.map(m=><label key={memberKey(m)}><input type="checkbox" aria-label={'保留 '+m.kind+' '+m.resourceId} checked={keep.includes(memberKey(m))&&(m.kind!=='AGENT'||!added.some(x=>x.kind==='AGENT'))} disabled={m.kind==='AGENT'} onChange={()=>setKeep(xs=>xs.includes(memberKey(m))?xs.filter(k=>k!==memberKey(m)):[...xs,memberKey(m)])}/>{m.kind} · {m.revisionId}</label>)}</fieldset><p>选择新的Agent职责会替换原主要Agent，原修订保留。同一资源的新发布修订替换其原版本；其他成员按上方选择保留。</p></>}<EmployeeResourcePicker allowAgent={!business} business={business} disabled={busy||!permissions.allows('CREATE')||Boolean(intent)} onChange={(xs,p)=>{setAdded(xs);setPickerPrincipal(p)}}/><EmployeeResponsibilityEditor item={item} duties={responsibilities.split('\n').map(x=>x.trim()).filter(Boolean)} members={members} value={bindings} onChange={setBindings} disabled={busy||!permissions.allows('CREATE')||Boolean(intent)}/>{!intent&&<button type="button" disabled={busy||!actor} hidden={!permissions.allows('CREATE')} style={!permissions.allows('CREATE')?{display:'none'}:undefined} onClick={()=>void act('prepare')}>{business?"核对修改":"核对后继草稿"}</button>}{intent?.state==='PREPARED'&&<section aria-label="员工后继确认"><p>同一员工 · {intent.command.members.length}项成员；原修订保留。</p><p>{business?"保存后形成独立草稿，原版本与任务引用保持不变。":""}</p><p>本次保存 {intent.command.responsibilityBindings?.length??0} 项职责资源关联。</p><>{business&&<EmployeeSaveSummary item={item} members={intent.command.members}/>}</><details open={!business}><summary>本次保存的准确资源依据</summary><ul>{intent.command.members.map(m=><li key={memberKey(m)}>{m.kind} · {m.revisionId}</li>)}</ul></details><button type="button" disabled={busy} onClick={()=>setIntent(null)}>{business?"返回修改":"返回修改后继"}</button><button type="button" disabled={busy} hidden={!permissions.allows('CREATE')} style={!permissions.allows('CREATE')?{display:'none'}:undefined} onClick={()=>void act('submit')}>{business?"保存修改草稿":"确认保存后继草稿"}</button></section>}{intent&&intent.state!=='PREPARED'&&<button type="button" disabled={busy} onClick={()=>void act('read')}>读取原后继修订</button>}</>}{busy&&<p role="status">正在核对同一员工与原操作…</p>}{message&&<p role="status">{message}</p>}</section>;
}
