import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {createEmployeeDefinition,getEmployeeDefinition,getWorkbenchSession,workbenchPrincipalKey,DigitalEmployeeRequestError,type EmployeeCreateCommand,type EmployeeDefinition,type EmployeeCommandResult,type EmployeeMember} from '../api/digitalEmployees';
import {EmployeeResourcePicker} from './EmployeeResourcePicker';
import {successorDigest,verifySuccessor} from './employeeSuccessorState';

type Intent={command:EmployeeCreateCommand;digest:string;principal:string;state:'PREPARED'|'UNKNOWN'|'SAVED'};
const memberKey=(m:EmployeeMember)=>m.kind+'|'+m.resourceId;
export function EmployeeSuccessorPanel({item,onReadback}:{item:EmployeeDefinition;onReadback:(definition:EmployeeDefinition,result:EmployeeCommandResult)=>void}){
 const identity=JSON.stringify([item.employeeDefinitionId,item.employeeDefinitionRevisionId,item.employeeDefinitionDigest]);
 const current=useRef(identity),epoch=useRef(0),flight=useRef(false);
 useLayoutEffect(()=>{const generation=epoch;current.current=identity;return()=>{current.current='';generation.current++}},[identity]);
 const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[responsibilities,setResponsibilities]=useState(item.responsibilities.join('\n')),[keep,setKeep]=useState(item.members.map(memberKey)),[added,setAdded]=useState<EmployeeMember[]>([]),[pickerPrincipal,setPickerPrincipal]=useState<string|null>(null),[intent,setIntent]=useState<Intent|null>(null),[actor,setActor]=useState(''),[message,setMessage]=useState('');
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
   if(kind==='prepare'){
    if(added.length&&pickerPrincipal!==actor)throw Error('资源选择身份已变化，请重新选择。');
    const duties=responsibilities.split('\n').map(x=>x.trim()).filter(Boolean);if(!duties.length||duties.length>32||duties.some(x=>x.length>500)||members.filter(x=>x.kind==='AGENT').length!==1)throw Error('请保留一个Agent并填写有效职责。');
    const command:EmployeeCreateCommand={employeeDefinitionId:item.employeeDefinitionId,employeeDefinitionRevisionId:'employee-revision:'+crypto.randomUUID(),predecessorEmployeeRevisionId:item.employeeDefinitionRevisionId,role:item.role,responsibilities:duties,members:members.map(m=>({...m})),expectedVersion:before.aggregateVersion!,commandId:'employee-successor:'+crypto.randomUUID()};
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
  }catch(error){if(valid())setMessage(error instanceof Error?error.message:'后继尚未核实；原版本保留。')}
  finally{flight.current=false;if(valid())setBusy(false)}
 }
 return <section className="employee-form-card" aria-label="同一员工后继维护"><h3>维护后继版本</h3><p>保留当前修订和已有引用，准备同一员工的新职责与准确资源版本。保存草稿不代表发布或运行。</p>{!open&&<button type="button" disabled={busy||!actor} onClick={()=>setOpen(true)}>准备员工后继</button>}{open&&<><label>后继职责（每行一项）<textarea aria-label="后继职责" rows={3} disabled={busy||Boolean(intent)} value={responsibilities} onChange={e=>setResponsibilities(e.target.value)}/></label><fieldset disabled={busy||Boolean(intent)}><legend>保留原成员</legend>{item.members.map(m=><label key={memberKey(m)}><input type="checkbox" aria-label={'保留 '+m.kind+' '+m.resourceId} checked={keep.includes(memberKey(m))&&(m.kind!=='AGENT'||!added.some(x=>x.kind==='AGENT'))} disabled={m.kind==='AGENT'} onChange={()=>setKeep(xs=>xs.includes(memberKey(m))?xs.filter(k=>k!==memberKey(m)):[...xs,memberKey(m)])}/>{m.kind} · {m.revisionId}</label>)}</fieldset><p>选择新的Agent职责会替换原主要Agent，原修订保留。同一资源的新发布修订替换其原版本；其他成员按上方选择保留。</p><EmployeeResourcePicker allowAgent disabled={busy||Boolean(intent)} onChange={(xs,p)=>{setAdded(xs);setPickerPrincipal(p)}}/>{!intent&&<button type="button" disabled={busy||!actor} onClick={()=>void act('prepare')}>核对后继草稿</button>}{intent?.state==='PREPARED'&&<section aria-label="员工后继确认"><p>同一员工 · {intent.command.members.length}项成员；原修订保留。</p><ul>{intent.command.members.map(m=><li key={memberKey(m)}>{m.kind} · {m.revisionId}</li>)}</ul><button type="button" disabled={busy} onClick={()=>setIntent(null)}>返回修改后继</button><button type="button" disabled={busy} onClick={()=>void act('submit')}>确认保存后继草稿</button></section>}{intent&&intent.state!=='PREPARED'&&<button type="button" disabled={busy} onClick={()=>void act('read')}>读取原后继修订</button>}</>}{busy&&<p role="status">正在核对同一员工与原操作…</p>}{message&&<p role="status">{message}</p>}</section>;
}
