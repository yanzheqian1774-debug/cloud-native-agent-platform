import {useCallback,useEffect,useRef,useState,type FormEvent} from 'react';
import {capabilitySession,CapabilityRequestError,readCapability,saveCapability,type CapabilityBinding,type CapabilityDetail,type CapabilityReference,type CapabilityRevision} from '../api/businessCapabilities';
import {getEmployeeDefinition,listEmployeeDefinitions,workbenchPrincipalKey} from '../api/digitalEmployees';
import {listReadableResources,type DirectoryKind} from '../api/resourceDirectory';

type Option={title:string;reference:CapabilityReference};
type PickKind=CapabilityBinding['kind']|'WORKFLOW';
const kinds:{kind:PickKind;title:string;directory?:DirectoryKind}[]=[{kind:'EMPLOYEE',title:'数字人'},{kind:'SKILL',title:'技能',directory:'skill'},{kind:'MCP',title:'MCP 服务',directory:'mcp'},{kind:'KNOWLEDGE',title:'知识',directory:'knowledge'},{kind:'RUNTIME_PROFILE',title:'运行环境',directory:'runtime'},{kind:'WORKFLOW',title:'来源流程',directory:'workflow'}];
const textFields=[['title','能力名称'],['intent','希望完成什么'],['inputs','需要提供哪些资料'],['outputs','将交付什么'],['business_scope','适用范围'],['exclusions','不包含哪些操作'],['manual_involvement','需要人工参与什么'],['known_limitations','当前已知限制']] as const;
type FormFields=Record<typeof textFields[number][0],string>;
export function CapabilityEditor({base,principal,fromWorkflow=false,onSaved,onCancel}:{base?:CapabilityDetail;principal:string;fromWorkflow?:boolean;onSaved:(value:CapabilityDetail)=>void;onCancel:()=>void}){
 const [fields,setFields]=useState<FormFields>(()=>Object.fromEntries(textFields.map(([key])=>[key,base?.revision[key]??''])) as FormFields);
 const [domain,setDomain]=useState(base?.revision.business_domain??'');
 const [criteria,setCriteria]=useState(base?.revision.acceptance_criteria.join('\n')??'');
 const [bindings,setBindings]=useState<CapabilityBinding[]>(base?.revision.bindings??[]);
 const [origin,setOrigin]=useState<CapabilityRevision['origin']>(base?.revision.origin??{kind:fromWorkflow?'WORKFLOW_REVISION':'INDEPENDENT',workflow:null,preparation_digest:null});
 const [kind,setKind]=useState<PickKind>(fromWorkflow?'WORKFLOW':'EMPLOYEE'),[options,setOptions]=useState<Option[]>([]),[selected,setSelected]=useState(''),[purpose,setPurpose]=useState('');
 const [cursor,setCursor]=useState<string|null>(null),[loading,setLoading]=useState(false),[pickerError,setPickerError]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[reload,setReload]=useState(0);
 const [submitted,setSubmitted]=useState<{revision:CapabilityRevision;expectedVersion:number;commandId:string}|null>(null);
 const [importNotice,setImportNotice]=useState('');
 const pending=useRef(false),alive=useRef(true),pickerEpoch=useRef(0);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[]);
 const readOptions=useCallback(async(type:PickKind,after:string|null,signal:AbortSignal)=>{
  const before=await capabilitySession(signal);
  if(workbenchPrincipalKey(before)!==principal)throw new Error('identity');
  let result:{items:Option[];cursor:string|null};
  if(type==='EMPLOYEE'){
   const page=await listEmployeeDefinitions(after??undefined,signal);
   result={items:page.items.filter(item=>item.publicationState==='PUBLISHED').map(item=>({title:item.role,reference:{resource_id:item.employeeDefinitionId,revision_id:item.employeeDefinitionRevisionId,digest:item.employeeDefinitionDigest}})),cursor:page.nextCursor??null};
  }else{
   const directory=kinds.find(item=>item.kind===type)!.directory!;
   const page=await listReadableResources(directory,'','PUBLISHED',after,signal);
   result={items:page.items.filter(item=>item.enabled&&item.isCurrentPublished).map(item=>({title:item.name,reference:{resource_id:item.identity,revision_id:item.revisionId,digest:item.digest}})),cursor:page.nextCursor};
  }
  const afterSession=await capabilitySession(signal);
  if(workbenchPrincipalKey(afterSession)!==principal)throw new Error('identity');
  return result;
 },[principal]);
 useEffect(()=>{
  const controller=new AbortController(),epoch=++pickerEpoch.current;
  const load=async()=>{
   setLoading(true);setOptions([]);setSelected('');setCursor(null);setPickerError('');
   try{const result=await readOptions(kind,null,AbortSignal.any([controller.signal,AbortSignal.timeout(30_000)]));if(epoch===pickerEpoch.current&&!controller.signal.aborted){setOptions(result.items);setCursor(result.cursor)}}
   catch{if(!controller.signal.aborted)setPickerError('暂时无法读取可选资源，请核对当前账号后重试。')}
   finally{if(!controller.signal.aborted)setLoading(false)}
  };void load();return()=>{controller.abort();pickerEpoch.current=epoch+1};
 },[kind,readOptions,reload]);
 const more=async()=>{
  const epoch=pickerEpoch.current;setLoading(true);setPickerError('');
  try{const result=await readOptions(kind,cursor,AbortSignal.timeout(30_000));if(alive.current&&epoch===pickerEpoch.current){setOptions(old=>[...old,...result.items]);setCursor(result.cursor)}}
  catch{if(alive.current&&epoch===pickerEpoch.current)setPickerError('读取下一页失败，可以重试。')}
  finally{if(alive.current&&epoch===pickerEpoch.current)setLoading(false)}
 };
 const add=()=>{
  const option=options[Number(selected)];if(selected===''||!option)return;
  if(kind==='WORKFLOW'){setOrigin({kind:'WORKFLOW_REVISION',workflow:option.reference,preparation_digest:null});return}
  const binding={kind,reference:option.reference,purpose:purpose.trim()};
  if(!binding.purpose)return;
  setBindings(old=>[...old.filter(item=>!(item.kind===kind&&item.reference.resource_id===option.reference.resource_id)),binding]);setPurpose('');
 };
 const importEmployee=async()=>{
  const option=options[Number(selected)];if(kind!=='EMPLOYEE'||selected===''||!option||pending.current)return;
  pending.current=true;setBusy(true);setError('');setImportNotice('');
  try{
   const signal=AbortSignal.timeout(30_000),before=await capabilitySession(signal);
   if(workbenchPrincipalKey(before)!==principal)throw Error('identity');
   const ref=option.reference,employee=await getEmployeeDefinition(ref.resource_id,ref.revision_id,signal),after=await capabilitySession(signal);
   if(workbenchPrincipalKey(after)!==principal||employee.employeeDefinitionId!==ref.resource_id||employee.employeeDefinitionRevisionId!==ref.revision_id||employee.employeeDefinitionDigest!==ref.digest||employee.publicationState!=='PUBLISHED')throw Error('reference');
   const responsibilities=employee.responsibilities.join('；'),supported=['SKILL','MCP','KNOWLEDGE','RUNTIME_PROFILE'];
   const imported:CapabilityBinding[]=[{kind:'EMPLOYEE',reference:ref,purpose:responsibilities||employee.role}];
   let unsupported=0;
   for(const member of employee.members){
    if(!supported.includes(member.kind)){unsupported++;continue}
    const duties=employee.responsibilityBindings?.filter(binding=>binding.member.kind===member.kind&&binding.member.resourceId===member.resourceId&&binding.member.revisionId===member.revisionId&&binding.member.digest===member.digest).map(binding=>binding.responsibility).join('；');
    imported.push({kind:member.kind as CapabilityBinding['kind'],reference:{resource_id:member.resourceId,revision_id:member.revisionId,digest:member.digest.replace(/^sha256:/,'')},purpose:duties||'数字人已绑定的'+(kinds.find(item=>item.kind===member.kind)?.title??member.kind)+'资源'});
   }
   if(imported.some(binding=>binding.purpose.length>1000)||responsibilities.length>2000||employee.role.length>120)throw Error('length');
   const additions=imported.filter(binding=>!bindings.some(existing=>existing.kind===binding.kind&&existing.reference.resource_id===binding.reference.resource_id));
   const conflicts=imported.filter(binding=>bindings.some(existing=>existing.kind===binding.kind&&existing.reference.resource_id===binding.reference.resource_id&&(existing.reference.revision_id!==binding.reference.revision_id||existing.reference.digest!==binding.reference.digest))).length;
   if(bindings.length+additions.length>64)throw Error('length');
   if(!alive.current)return;
   setFields(old=>({...old,title:old.title.trim()?old.title:employee.role,intent:old.intent.trim()?old.intent:responsibilities}));setBindings(old=>[...old,...additions]);
   setImportNotice('已从所选发布版本带入职责和 '+additions.length+' 项固定引用，保留已有填写与引用。'+(unsupported?unsupported+' 项内部依赖保留在数字人定义中，不单独加入能力。':'')+(conflicts?conflicts+' 项引用与已有版本不同，已保留原选择，请核对。':'')+'请补齐本次输入、交付和完成边界；保存时仍会核验资源。');
  }catch{if(alive.current)setError('未能带入所选数字人的完整发布信息。请核对版本、访问范围及内容长度；已有填写保持不变。')}
  finally{pending.current=false;if(alive.current)setBusy(false)}
 };
 const save=async(event:FormEvent)=>{
  event.preventDefault();if(pending.current)return;
  pending.current=true;setBusy(true);setError('');let accepted=false;
  try{
   let command=submitted;
   if(!command){
    if(!bindings.some(item=>item.kind==='EMPLOYEE'))throw new Error('employee');
    if(origin.kind==='WORKFLOW_REVISION'&&!origin.workflow)throw new Error('workflow');
    const session=await capabilitySession();if(workbenchPrincipalKey(session)!==principal)throw new Error('identity');
    const revision:CapabilityRevision={schemaVersion:'business-capability.v1',scope:{namespace:session.principal.tenantId,security_domain:session.principal.securityDomain},capability_id:base?.revision.capability_id??`capability:${crypto.randomUUID()}`,revision_id:`capability-revision:${crypto.randomUUID()}`,predecessor_revision_id:base?.revision.revision_id??null,...fields,...(domain.trim()?{business_domain:domain.trim()}:{}),acceptance_criteria:criteria.split('\n').map(item=>item.trim()).filter(Boolean),origin,bindings};
    command={revision,expectedVersion:base?.aggregateVersion??0,commandId:`capability-save:${crypto.randomUUID()}`};
    if(!alive.current)return;setSubmitted(command);
   }
   await saveCapability(command.revision,command.expectedVersion,command.commandId,principal);
   accepted=true;
   const result=await readCapability(command.revision.capability_id,command.revision.revision_id,principal);
   if(alive.current)onSaved(result);
  }catch(cause){if(alive.current){
   if(accepted||(cause instanceof CapabilityRequestError&&cause.outcomeUnknown))setError('保存结果尚未核实。再次核实会沿用同一份内容和提交记录。');
   else{setSubmitted(null);setError(cause instanceof CapabilityRequestError&&cause.status===409?'内容已经变化，请关闭编辑并重新读取当前草稿。':cause instanceof Error&&cause.message==='employee'?'请至少选择一位数字人并填写职责。':cause instanceof Error&&cause.message==='workflow'?'请选择真实的已发布来源流程。':'保存未完成，请检查内容、资源可读范围和当前账号后重试。')}
  }}finally{pending.current=false;if(alive.current)setBusy(false)}
 };
 return <form className="capability-panel capability-editor" onSubmit={save} aria-label="业务能力编辑">
  <h2>{base?'修改业务能力':'设计业务能力'}</h2><p>描述目标与交付，选择已有数字人及资料。保存为草稿后，再集中核对变更与发布影响。</p>
  {error&&<p role="alert">{error}</p>}{importNotice&&<p role="status">{importNotice}</p>}
  <fieldset disabled={busy||submitted!==null}><legend>目标与边界</legend><label>业务领域（可选）<input maxLength={80} value={domain} onChange={event=>setDomain(event.target.value)} placeholder="填写能力所属的业务领域"/></label><div className="capability-grid">{textFields.map(([key,title])=><label key={key}>{title}{key==='title'?<input aria-label={title} required maxLength={120} value={fields[key]} onChange={event=>setFields(old=>({...old,[key]:event.target.value}))}/>:<textarea aria-label={title} required maxLength={2000} value={fields[key]} onChange={event=>setFields(old=>({...old,[key]:event.target.value}))}/>}</label>)}</div><label>完成标准（每行一项）<textarea aria-label="完成标准（每行一项）" required value={criteria} onChange={event=>setCriteria(event.target.value)}/></label>
   <label>设计来源<select aria-label="设计来源" value={origin.kind} disabled={base!==undefined} onChange={event=>{const workflow=event.target.value==='WORKFLOW_REVISION';setOrigin({kind:workflow?'WORKFLOW_REVISION':'INDEPENDENT',workflow:null,preparation_digest:null});if(workflow)setKind('WORKFLOW')}}><option value="INDEPENDENT">独立设计</option><option value="WORKFLOW_REVISION">从业务流程设计</option>{origin.kind==='SAVED_PREPARATION'&&<option value="SAVED_PREPARATION">已保存的工作准备</option>}</select></label>
   {origin.workflow&&<p>已固定来源流程。更换流程需重新选择，既有工作不会随之改变。</p>}
   <h3>选择承担职责的数字人与资源</h3><label>资源类别<select aria-label="资源类别" value={kind} onChange={event=>setKind(event.target.value as PickKind)}>{kinds.filter(item=>item.kind!=='WORKFLOW'||origin.kind==='WORKFLOW_REVISION').map(item=><option key={item.kind} value={item.kind}>{item.title}</option>)}</select></label>
   {loading&&<p role="status">正在读取可选资源…</p>}{pickerError&&<p role="alert">{pickerError}<button type="button" onClick={()=>setReload(n=>n+1)}>重试读取</button></p>}
   <label>已发布资源<select aria-label="已发布资源" value={selected} onChange={event=>setSelected(event.target.value)} disabled={loading}><option value="">请选择</option>{options.map((option,index)=><option key={`${option.reference.resource_id}:${option.reference.revision_id}`} value={index}>{option.title}</option>)}</select></label>
   {kind==='EMPLOYEE'&&<button type="button" disabled={loading||selected===''} onClick={()=>void importEmployee()}>带入已保存职责与资源</button>}
   {!loading&&!pickerError&&!options.length&&<p>当前没有可选的已发布资源。</p>}{cursor&&<button type="button" disabled={loading} onClick={()=>void more()}>读取更多资源</button>}
   {kind!=='WORKFLOW'&&<label>本次承担什么职责<input maxLength={1000} value={purpose} onChange={event=>setPurpose(event.target.value)}/></label>}
   <button type="button" disabled={selected===''||(kind!=='WORKFLOW'&&!purpose.trim())} onClick={add}>{kind==='WORKFLOW'?'固定来源流程':'加入能力组成'}</button>
   <ul>{bindings.map(binding=><li key={`${binding.kind}:${binding.reference.resource_id}`}><strong>{kinds.find(item=>item.kind===binding.kind)?.title??binding.kind}</strong> · {binding.purpose} <button type="button" onClick={()=>setBindings(old=>old.filter(item=>item!==binding))}>移除</button></li>)}</ul>
  </fieldset>
  <div className="capability-actions"><button type="submit" disabled={busy}>{busy?'正在保存…':submitted?'核实并重试本次保存':'保存草稿'}</button><button type="button" disabled={busy} onClick={onCancel}>取消编辑</button></div>
 </form>;
}
