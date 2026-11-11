import {businessProcessHref,safeBusinessProcessReturn} from './businessRelationNavigation';
import {captureBusinessEditorPosition,restoreBusinessEditorPosition,type BusinessEditorPosition} from './businessEditorPosition';
import type {FixedBusinessReference} from '../api/businessProcesses';
import {BusinessReferencePicker} from './BusinessReferencePicker';
import {BusinessActivityMap} from "./BusinessActivityMap";
import {useEffect,useLayoutEffect,useId,useRef,useState} from 'react';
import {getWorkbenchSession,workbenchPrincipalKey} from '../api/digitalEmployees';
import {handoffIdentity,BusinessProcessRequestError,checkBusinessProcessEditorAccess,readBusinessArchitecture,readBusinessProcess,readBusinessProcessReceipt,saveBusinessProcess,type BusinessReferenceDetails,type BusinessArchitecture,type BusinessProcessCommand,type BusinessProcessContent,type BusinessProcessReceipt} from '../api/businessProcesses';

const withHandoffIds=(content:BusinessProcessContent):BusinessProcessContent=>({...content,handoffs:content.handoffs.map(item=>({...item,handoff_id:item.handoff_id??'business-handoff:'+crypto.randomUUID()}))});
const emptyProcess=():BusinessProcessContent=>({name:'',business_code:null,domain_id:'',group_id:'',owner_description:null,purpose:null,improvement_notes:null,activities:[],handoffs:[]});
const split=(value:string)=>value.split('\n').map(item=>item.trim()).filter(Boolean);
const optional=(value:string)=>value.trim()||null;
function message(error:unknown){
 if(error instanceof Error&&error.message==='LOCAL_DRAFT_NOT_AVAILABLE')return '当前账号下未找到这份未提交草稿，请返回原账号核对；不会创建替代草稿。';
 if(error instanceof BusinessProcessRequestError){
  if(error.outcomeUnknown)return '保存结果尚未核实。请先核实原提交；不会自动重复保存。';
  if(error.status===409)return '内容或登录身份已变化，当前输入已保留。请重新读取当前草稿后核对。';
  if(error.status===401||error.status===403||error.status===404)return '当前无法完成操作，请核对登录账号及使用范围。';
  if(error.status===422)return '部分内容暂不能保存，请检查领域、流程组和活动填写内容。';
 }
 return '暂时无法完成操作，当前输入已保留。';
}
export function BusinessProcessEditor({kind,processId,resumeDraftId='',onSaved,onCancel}:{resumeDraftId?:string;kind:'ARCHITECTURE'|'PROCESS';processId:string;onSaved:(value:BusinessProcessReceipt)=>void;onCancel:()=>void}){
 const [referenceDetails,setReferenceDetails]=useState<BusinessReferenceDetails>();
 const [architecture,setArchitecture]=useState<BusinessArchitecture>({domains:[],groups:[]});
 const [process,setProcess]=useState<BusinessProcessContent>(emptyProcess);
 const [version,setVersion]=useState(0),[objectId,setObjectId]=useState(''),[principal,setPrincipal]=useState('');
 const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [pending,setPending]=useState<BusinessProcessCommand|null>(null),[retryAllowed,setRetryAllowed]=useState(false);
 const controller=useRef<AbortController|null>(null),inFlight=useRef(false),storageKey=useRef(''),draftKey=useRef('');
 const [reload,setReload]=useState(0);
 const formId=useId(),formRef=useRef<HTMLFormElement>(null),restorePosition=useRef<BusinessEditorPosition|null>(null);
 const [baseReference,setBaseReference]=useState<FixedBusinessReference>();
 const [section,setSection]=useState<'basics'|'activity'|'handoff'>('basics'),[selectedActivity,setSelectedActivity]=useState(''),[selectedHandoff,setSelectedHandoff]=useState('');
 useEffect(()=>{
  const abort=new AbortController();controller.current=abort;let alive=true;
  let currentPrincipal='';
  const action=kind==='ARCHITECTURE'||processId?'REVISE':'CREATE';
  const target=kind==='ARCHITECTURE'?'architecture':processId;
  const access=async(key:string)=>{const result=await checkBusinessProcessEditorAccess(kind,target,action,key,abort.signal);if(result.allowed!==true||result.kind!==kind||result.objectId!==target||result.action!==action)throw new BusinessProcessRequestError('EDITOR_ACCESS_INVALID',403)};
  const load=async()=>{
   try{
    const session=await getWorkbenchSession(AbortSignal.any([abort.signal,AbortSignal.timeout(30_000)]));const key=workbenchPrincipalKey(session);currentPrincipal=key;await access(key);
    const storage='business-process-command:v1:'+JSON.stringify([key,kind,processId||'new']);
    const saved=sessionStorage.getItem(storage);const draftStorage=storage.replace('business-process-command:', 'business-process-draft:');const local=sessionStorage.getItem(draftStorage);
    if(resumeDraftId){const candidate=JSON.parse(saved??local??'null');if(kind!=='PROCESS'||processId||!candidate||candidate.objectId!==resumeDraftId)throw Error('LOCAL_DRAFT_NOT_AVAILABLE')}
    const arch=await readBusinessArchitecture(key,abort.signal);
    const current=kind==='PROCESS'&&processId?await readBusinessProcess(processId,'',key,abort.signal):null;
    if(!alive)return;
    storageKey.current=storage;draftKey.current=draftStorage;setPrincipal(key);setArchitecture(arch.record.content);setVersion(kind==='ARCHITECTURE'?arch.aggregateVersion:current?.aggregateVersion??0);
    setObjectId(kind==='ARCHITECTURE'?'architecture':current?.objectId??'business-process:'+crypto.randomUUID());
    if(current){if(current.revisionId&&current.digest)setBaseReference({resource_id:current.objectId,revision_id:current.revisionId,digest:current.digest});setProcess(withHandoffIds(current.record.content));setReferenceDetails(current.referenceDetails)}
    if(saved){
     const command=JSON.parse(saved) as BusinessProcessCommand;
     if(command.kind!==kind||!command.commandId||!command.objectId||!command.content||!Number.isInteger(command.expectedVersion))throw Error('INVALID_PENDING_COMMAND');
     setPending(command);setObjectId(command.objectId);setVersion(command.expectedVersion);
     if(kind==='ARCHITECTURE')setArchitecture(command.content as BusinessArchitecture);else setProcess(command.content as BusinessProcessContent);
     setError('发现尚未核实的保存记录。请先核实原提交，再继续修改。');
    }else if(local){
     const draft=JSON.parse(local) as {kind:string;objectId:string;version:number;content:BusinessArchitecture|BusinessProcessContent;section?:'basics'|'activity'|'handoff';selectedActivity?:string;selectedHandoff?:string;reference?:FixedBusinessReference;position?:BusinessEditorPosition};
     if(draft.kind!==kind||!draft.objectId||(processId&&draft.objectId!==processId)||!Number.isInteger(draft.version)||draft.version<0||!draft.content)throw Error('INVALID_LOCAL_DRAFT');
     setObjectId(draft.objectId);setVersion(draft.version);
     if(draft.reference?.resource_id===draft.objectId&&safeBusinessProcessReturn(businessProcessHref(draft.reference)))setBaseReference(draft.reference);
     restorePosition.current=draft.position??null;
     if(kind==='ARCHITECTURE'){setArchitecture(draft.content as BusinessArchitecture);setSection('basics')}
     else{
      const restored=withHandoffIds(draft.content as BusinessProcessContent);setProcess(restored);
      const activity=restored.activities.find(item=>item.activity_id===draft.selectedActivity);
      const handoff=restored.handoffs.find(item=>handoffIdentity(item)===draft.selectedHandoff);
      setSelectedActivity(activity?.activity_id??'');setSelectedHandoff(handoff?handoffIdentity(handoff):'');
      setSection(draft.section==='activity'&&activity?'activity':draft.section==='handoff'&&handoff?'handoff':'basics');
     }
     setError('已恢复当前账号未提交的草稿。保留原编辑版本，请核对后保存；不会自动覆盖更新的内容。');
    }
   }catch(cause){if(alive){setPrincipal('');setError(message(cause))}}finally{if(alive)setLoading(false)}
  };
  const expire=()=>{alive=false;abort.abort();setPrincipal('');setArchitecture({domains:[],groups:[]});setProcess(emptyProcess());setPending(null);setError('登录已失效，请重新登录。');setLoading(false);setBusy(false)};
  const recheck=()=>{if(!currentPrincipal||!alive)return;void access(currentPrincipal).catch(()=>{if(alive){expire();setError('当前身份或编辑权限已变化。内容已隐藏，原草稿与提交记录保留，需重新登录并核对权限。')}})};
  window.addEventListener('focus',recheck);window.addEventListener('workbench-session-expired',expire);void load();
  return()=>{alive=false;abort.abort();window.removeEventListener('workbench-session-expired',expire);window.removeEventListener('focus',recheck)};
 },[kind,processId,resumeDraftId,reload]);
 useLayoutEffect(()=>{if(!loading&&principal&&formRef.current&&restorePosition.current){restoreBusinessEditorPosition(formRef.current,restorePosition.current);restorePosition.current=null}},[loading,principal]);
 useEffect(()=>{
  if(loading||!principal||pending||!draftKey.current||!objectId)return;
  const key=draftKey.current,serialized=JSON.stringify({kind,objectId,version,content:kind==='ARCHITECTURE'?architecture:process,section,selectedActivity,selectedHandoff,reference:baseReference,position:formRef.current?captureBusinessEditorPosition(formRef.current):undefined});
  let active=true;
  void Promise.resolve().then(()=>{if(active)sessionStorage.setItem(key,serialized)}).catch(()=>{if(active)setError('本地草稿暂无法保留，请保持此页并保存，避免关闭后丢失输入。')});
  return()=>{active=false};
 },[loading,principal,pending,objectId,version,kind,architecture,process,section,selectedActivity,selectedHandoff,baseReference]);

 const returnTo=baseReference?businessProcessHref(baseReference,section==='activity'?selectedActivity:undefined)+'&edit=process':kind==='PROCESS'&&!processId&&objectId?'/business-processes?'+new URLSearchParams({edit:'process',draft:objectId}):undefined;
 const preserveBeforeNavigate=()=>{
  if(loading||busy||pending||!principal||!formRef.current||!draftKey.current||controller.current?.signal.aborted)return false;
  try{sessionStorage.setItem(draftKey.current,JSON.stringify({kind,objectId,version,content:kind==='ARCHITECTURE'?architecture:process,section,selectedActivity,selectedHandoff,reference:baseReference,position:captureBusinessEditorPosition(formRef.current)}));return true}
  catch{setError('本地草稿暂无法保留，请保持此页并保存，避免关闭后丢失输入。');return false}
 };

 const accepted=(receipt:BusinessProcessReceipt,command:BusinessProcessCommand)=>{
  if(receipt.objectId!==command.objectId||receipt.aggregateVersion!==command.expectedVersion+1||!receipt.revisionId||receipt.state!=='DRAFT'||receipt.executionAuthorized!==false)throw new BusinessProcessRequestError('INVALID_RECEIPT',503,true);
  sessionStorage.removeItem(storageKey.current);sessionStorage.removeItem(draftKey.current);setPending(null);onSaved(receipt);
 };
 const run=async(reconcile=false,replay=false,submittedContent?:BusinessProcessContent)=>{
  if(inFlight.current||!principal||!controller.current||controller.current.signal.aborted)return;
  inFlight.current=true;setBusy(true);setError('');const signal=controller.current.signal;
  let submitted=pending;
  try{
   if(reconcile){
    if(!submitted)return;
    const value=await readBusinessProcessReceipt(submitted.commandId,principal,signal);if(!signal.aborted)accepted(value,submitted);return;
   }
   if(pending&&!replay)return;
   if(!submitted){
    submitted={kind,objectId,expectedVersion:version,commandId:'business-process-save:'+crypto.randomUUID(),content:kind==='ARCHITECTURE'?architecture:submittedContent??process};
    sessionStorage.setItem(storageKey.current,JSON.stringify(submitted));setPending(submitted);
   }
   const value=await saveBusinessProcess(submitted,principal,signal);if(!signal.aborted)accepted(value,submitted);
  }catch(cause){
   if(signal.aborted)return;
   if(reconcile){setRetryAllowed(cause instanceof BusinessProcessRequestError&&cause.code==='BUSINESS_PROCESS_COMMAND_NOT_FOUND');setError('原提交尚未核实。未查到回执可能是仍在处理或当前不可读；保留原提交，不会新建第二份。')}
   else if(!replay&&cause instanceof BusinessProcessRequestError&&!cause.outcomeUnknown){sessionStorage.removeItem(storageKey.current);setPending(null);setRetryAllowed(false);setError(message(cause))}
   else setError(message(cause));
  }finally{inFlight.current=false;if(!signal.aborted)setBusy(false)}
 };
 const change=(field:keyof BusinessProcessContent,value:unknown)=>setProcess(old=>({...old,[field]:value}));
 const activity=(index:number,field:string,value:unknown)=>setProcess(old=>({...old,activities:old.activities.map((item,i)=>i===index?{...item,[field]:value}:item)}));
 const locked=loading||busy||!!pending||!principal;
 return <section className="bp-card bp-editor"><h2>{kind==='ARCHITECTURE'?'维护业务领域与流程组':processId?'修改当前业务流程草稿':'登记业务流程'}</h2><p>保存为登记草稿，尚不发布或执行。业务负责人描述不会授予账号权限。</p>
  {loading&&<p role="status">正在读取当前内容…</p>}{error&&<p role="alert">{error}</p>}
  <div className="bp-editor-toolbar"><button type="submit" form={formId} className="bp-primary" disabled={locked}>保存登记草稿</button><button disabled={busy} onClick={onCancel}>返回查看（保留草稿）</button></div>
  {!loading&&principal&&<form ref={formRef} id={formId} onInvalidCapture={event=>{event.preventDefault();const input=event.target as HTMLElement,block=input.closest<HTMLElement>('[data-edit-activity],[data-edit-handoff]');if(block?.dataset.editActivity){setSelectedActivity(block.dataset.editActivity);setSection('activity')}else if(block?.dataset.editHandoff!==undefined){setSelectedHandoff(block.dataset.editHandoff);setSection('handoff')}else setSection('basics');setError('请补齐标记的必要信息后保存。');requestAnimationFrame(()=>input.focus())}} onSubmit={event=>{event.preventDefault();const data=new FormData(event.currentTarget);const value=(key:string)=>String(data.get(key)??'');const content={...process,business_code:optional(value('business_code')),owner_description:optional(value('owner_description')),purpose:optional(value('purpose')),improvement_notes:optional(value('improvement_notes')),activities:process.activities.map(item=>({...item,responsible_role:optional(value(item.activity_id+':responsible_role')),inputs:split(value(item.activity_id+':inputs')),outputs:split(value(item.activity_id+':outputs')),completion_conditions:split(value(item.activity_id+':completion_conditions')),human_boundary:optional(value(item.activity_id+':human_boundary'))}))};void run(false,false,content)}}><fieldset disabled={locked}>
   {kind==='ARCHITECTURE'?<>
    {architecture.domains.map((domain,index)=><div className="bp-editor-section" key={domain.domain_id}><label>领域名称<input required maxLength={160} value={domain.name} onChange={event=>setArchitecture(old=>({...old,domains:old.domains.map((item,i)=>i===index?{...item,name:event.target.value}:item)}))}/></label><label>流程分类<select value={domain.band} onChange={event=>setArchitecture(old=>({...old,domains:old.domains.map((item,i)=>i===index?{...item,band:event.target.value as typeof domain.band}:item)}))}><option value="MANAGEMENT">管理流程</option><option value="CORE">核心流程</option><option value="SUPPORT">支持流程</option></select></label>
     {architecture.groups.filter(item=>item.domain_id===domain.domain_id).map(group=><label key={group.group_id}>流程组名称<input required maxLength={160} value={group.name} onChange={event=>setArchitecture(old=>({...old,groups:old.groups.map(item=>item.group_id===group.group_id?{...item,name:event.target.value}:item)}))}/></label>)}
     <button type="button" onClick={()=>setArchitecture(old=>({...old,groups:[...old.groups,{group_id:'business-group:'+crypto.randomUUID(),domain_id:domain.domain_id,name:''}]}))}>添加流程组</button></div>)}
    <button type="button" onClick={()=>setArchitecture(old=>({...old,domains:[...old.domains,{domain_id:'business-domain:'+crypto.randomUUID(),name:'',band:'CORE'}]}))}>添加业务领域</button>
   </>:<>
    <div className="bp-editor-tabs"><button type="button" aria-pressed={section==='basics'} onClick={()=>setSection('basics')}>基本信息</button><button type="button" onClick={()=>{const id='business-activity:'+crypto.randomUUID();change('activities',[...process.activities,{activity_id:id,name:'',responsible_role:null,inputs:[],outputs:[],completion_conditions:[],human_boundary:null}]);setSelectedActivity(id);setSection('activity')}}>添加业务活动</button><button type="button" disabled={!process.activities.length} onClick={()=>{const id='business-handoff:'+crypto.randomUUID();setSelectedHandoff(id);change('handoffs',[...process.handoffs,{handoff_id:id,from_activity_id:'',to_activity_id:'',event:'COMPLETED',explanation:'',responsible_role:null}]);setSection('handoff')}}>添加交接</button></div>
    <div className="bp-editor-local-layout"><BusinessActivityMap content={process} editing activeActivityId={section==='activity'?selectedActivity:null} activeHandoffId={section==='handoff'?selectedHandoff:null} onActivitySelect={id=>{setSelectedActivity(id);setSection('activity')}} onHandoffSelect={id=>{setSelectedHandoff(id);setSection('handoff')}}/>
    <div className="bp-editor-local-fields"><div hidden={section!=='basics'}><h3>基本信息</h3>
    <label>流程名称<input required maxLength={160} value={process.name} onChange={event=>change('name',event.target.value)}/></label>
    <div className="bp-grid"><label>业务领域<select required value={process.domain_id} onChange={event=>setProcess(old=>({...old,domain_id:event.target.value,group_id:''}))}><option value="">请选择</option>{architecture.domains.map(item=><option value={item.domain_id} key={item.domain_id}>{item.name}</option>)}</select></label><label>流程组<select required value={process.group_id} onChange={event=>change('group_id',event.target.value)}><option value="">请选择</option>{architecture.groups.filter(item=>item.domain_id===process.domain_id).map(item=><option value={item.group_id} key={item.group_id}>{item.name}</option>)}</select></label></div>
    {!architecture.groups.length&&<p>请先在业务架构全景中登记领域与流程组。</p>}
    <label>流程编号<input name="business_code" maxLength={160} defaultValue={process.business_code??''} onChange={event=>change('business_code',optional(event.target.value))}/></label>
    <label>业务负责人<input name="owner_description" maxLength={160} defaultValue={process.owner_description??''} onChange={event=>change('owner_description',optional(event.target.value))}/></label>
    <label>业务目的<textarea name="purpose" maxLength={2000} defaultValue={process.purpose??''} onChange={event=>change('purpose',optional(event.target.value))}/></label>
    <label>改善事项<textarea name="improvement_notes" maxLength={2000} defaultValue={process.improvement_notes??''} onChange={event=>change('improvement_notes',optional(event.target.value))}/></label>
    <BusinessReferencePicker kind="knowledge" returnTo={returnTo} onBeforeNavigate={preserveBeforeNavigate} selected={process.source_materials??[]} principal={principal} details={referenceDetails} disabled={busy||!!pending} onChange={value=>change('source_materials',value)}/>
    </div>{process.activities.map((item,index)=><div data-edit-activity={item.activity_id} hidden={section!=='activity'||selectedActivity!==item.activity_id} className="bp-editor-section" key={item.activity_id}><h3>编辑活动：{item.name||'新活动'}</h3><label>活动名称<input required maxLength={160} value={item.name} onChange={event=>activity(index,'name',event.target.value)}/></label><label>业务责任角色<input name={item.activity_id+':responsible_role'} maxLength={160} defaultValue={item.responsible_role??''} onChange={event=>activity(index,'responsible_role',optional(event.target.value))}/></label>
     <label>活动输入（每行一项）<textarea name={item.activity_id+':inputs'} defaultValue={item.inputs.join('\n')} onChange={event=>activity(index,'inputs',split(event.target.value))}/></label><label>活动输出（每行一项）<textarea name={item.activity_id+':outputs'} defaultValue={item.outputs.join('\n')} onChange={event=>activity(index,'outputs',split(event.target.value))}/></label><label>完成标准（每行一项）<textarea name={item.activity_id+':completion_conditions'} defaultValue={item.completion_conditions.join('\n')} onChange={event=>activity(index,'completion_conditions',split(event.target.value))}/></label><label>人工保留事项<textarea placeholder="哪些情况需要由谁核实或决定；确无此类事项时请明确说明" name={item.activity_id+':human_boundary'} maxLength={2000} defaultValue={item.human_boundary??''} onChange={event=>activity(index,'human_boundary',optional(event.target.value))}/></label>
     <BusinessReferencePicker kind="employee" returnTo={returnTo} onBeforeNavigate={preserveBeforeNavigate} selected={item.employee?[item.employee]:[]} principal={principal} details={referenceDetails} disabled={busy||!!pending} onChange={value=>activity(index,'employee',value[0]??null)}/>
     <button type="button" disabled={process.handoffs.some(edge=>edge.from_activity_id===item.activity_id||edge.to_activity_id===item.activity_id)} onClick={()=>{change('activities',process.activities.filter(value=>value.activity_id!==item.activity_id));setSelectedActivity('');setSection('basics')}}>移除活动</button></div>)}
    {process.handoffs.map((edge,index)=><div data-edit-handoff={handoffIdentity(edge)} hidden={section!=='handoff'||selectedHandoff!==handoffIdentity(edge)} className="bp-editor-section" key={handoffIdentity(edge)}><h3>编辑交接关系</h3>{(['from_activity_id','to_activity_id'] as const).map((field,i)=><label key={field}>{i?'接收活动':'发起活动'}<select required value={edge[field]} onChange={event=>change('handoffs',process.handoffs.map((item,n)=>n===index?{...item,[field]:event.target.value}:item))}><option value="">请选择</option>{process.activities.map(item=><option value={item.activity_id} key={item.activity_id}>{item.name||'未命名活动'}</option>)}</select></label>)}<label>交接类型<select value={edge.event} onChange={event=>change('handoffs',process.handoffs.map((item,n)=>n===index?{...item,event:event.target.value}:item))}><option value="COMPLETED">完成后交接</option><option value="RETURNED">退回处理</option><option value="NEEDS_INFORMATION">补充资料</option></select></label><label>交接说明<textarea required maxLength={2000} value={edge.explanation} onChange={event=>change('handoffs',process.handoffs.map((item,n)=>n===index?{...item,explanation:event.target.value}:item))}/></label><label>交接责任角色<input maxLength={160} value={edge.responsible_role??''} onChange={event=>change('handoffs',process.handoffs.map((item,n)=>n===index?{...item,responsible_role:event.target.value||null}:item))}/></label><button type="button" onClick={()=>{change('handoffs',process.handoffs.filter((_,n)=>n!==index));setSelectedHandoff('');setSection('basics')}}>移除交接</button></div>)}
    </div></div>
   </>}

  </fieldset></form>}
  {pending&&<div className="bp-actions"><button disabled={busy} onClick={()=>void run(true)}>核实原提交</button>{retryAllowed&&<button disabled={busy} onClick={()=>void run(false,true)}>重试同一份提交</button>}</div>}
  <div className="bp-actions">{!pending&&principal&&<button disabled={busy} onClick={()=>{sessionStorage.removeItem(draftKey.current);setLoading(true);setPrincipal('');setError('');setProcess(emptyProcess());setReload(value=>value+1)}}>放弃本地草稿，读取当前内容</button>}</div>
  {busy&&<p role="status">正在保存或核实记录，请稍候…</p>}
 </section>;
}
