import {useEffect,useRef,useState} from 'react';
import {capabilitySession,readCapability,saveCapability,CapabilityRequestError,type CapabilityRevision,type CapabilityBinding,type CapabilityDetail,type CapabilityReference} from '../api/businessCapabilities';
import {getEmployeeDefinition,getEmployeeAuthoring,workbenchPrincipalKey} from '../api/digitalEmployees';
import {listReadableResources,readExactDirectoryResource,type DirectoryKind} from '../api/resourceDirectory';

type Update={binding:CapabilityBinding;name:string;next?:CapabilityReference;before:string;after?:string;status:string};
const directories:Partial<Record<CapabilityBinding['kind'],DirectoryKind>>={SKILL:'skill',MCP:'mcp',KNOWLEDGE:'knowledge',RUNTIME_PROFILE:'runtime'};
const canonical=(digest:string)=>/^(?:sha256:)?([a-f0-9]{64})$/.exec(digest)?.[1];
const key=(binding:CapabilityBinding)=>binding.kind+':'+binding.reference.resource_id;

type Scan={references:CapabilityReference[];complete:boolean};
async function scan(type:CapabilityBinding['kind'],signal:AbortSignal):Promise<Scan>{
 const kind=directories[type],found:CapabilityReference[]=[];let cursor:string|null=null;const seen=new Set<string>();let pages=0;
  do{
   const page=await listReadableResources(kind!,'','PUBLISHED',cursor,signal);
   for(const item of page.items)if(item.enabled&&item.isCurrentPublished&&canonical(item.digest))found.push({resource_id:item.identity,revision_id:item.revisionId,digest:canonical(item.digest)!});
   cursor=page.nextCursor;
   if(cursor&&seen.has(cursor))throw Error('Repeated page');if(cursor)seen.add(cursor);pages++;
  }while(cursor&&pages<20);
 return {references:found,complete:!cursor};
}

async function inspect(binding:CapabilityBinding,name:string,signal:AbortSignal,cache:Map<string,Promise<Scan>>):Promise<Update>{
 const ref=binding.reference,kind=directories[binding.kind];
 if(binding.kind!=='EMPLOYEE'&&!kind)return {binding,name,before:binding.purpose,status:'此类资源尚不支持自动核对，请通过资源详情核实。'};
 const exact=async(reference:CapabilityReference,candidate=false)=>{
  if(binding.kind==='EMPLOYEE'){
   const value=await getEmployeeDefinition(reference.resource_id,reference.revision_id,signal);
   if(value.employeeDefinitionId!==reference.resource_id||value.employeeDefinitionRevisionId!==reference.revision_id||value.employeeDefinitionDigest!==reference.digest||(candidate&&value.publicationState!=='PUBLISHED'))throw Error('Unverified employee');
   return value.responsibilities.join('；')+'\n固定资源：'+value.members.map(member=>member.kind+' · '+member.resourceId+' · '+member.revisionId).join('；');
  }
  const value=await readExactDirectoryResource(kind!,reference.resource_id,reference.revision_id,reference.digest,signal);
  if(!value.revision||(candidate&&value.revision.state!=='PUBLISHED'))throw Error('Unpublished resource');
  return value.name+'\n'+JSON.stringify(value.revision.content,null,2);
 };
 try{
  const before=await exact(ref);
  let found:CapabilityReference[];
  if(binding.kind==='EMPLOYEE'){
   const owner=await getEmployeeAuthoring({employeeDefinitionId:ref.resource_id,employeeDefinitionRevisionId:ref.revision_id,employeeDefinitionDigest:ref.digest,role:name,publicationState:'PUBLISHED'},signal);
   if(owner.basis!=='OWNER_FACT_ORDER'||owner.parent.employeeDefinitionId!==ref.resource_id||owner.parent.employeeDefinitionRevisionId!==ref.revision_id||owner.parent.employeeDefinitionDigest!==ref.digest)throw Error('Authoring identity mismatch');
   if(owner.publication.status!=='AVAILABLE')return {binding,name,before,status:'当前发布版本暂不可核实；保留原有引用。'};
   const published=owner.publication.definition;
   if(published.employeeDefinitionId!==ref.resource_id||published.publicationState!=='PUBLISHED')throw Error('Published identity mismatch');
   found=[{resource_id:published.employeeDefinitionId,revision_id:published.employeeDefinitionRevisionId,digest:published.employeeDefinitionDigest}];
  }else{
   if(!cache.has(binding.kind))cache.set(binding.kind,scan(binding.kind,signal));
   const listing=await cache.get(binding.kind)!;
   if(!listing.complete)return {binding,name,before,status:'目录尚未读取完整，暂不能确认最新发布版本。'};
   found=listing.references.filter(value=>value.resource_id===ref.resource_id);
  }
  const choices=found.filter((value,index)=>found.findIndex(other=>JSON.stringify(other)===JSON.stringify(value))===index);
  if(choices.length!==1)return {binding,name,before,status:choices.length?'有多个发布候选，请先在资源管理中核实。':'未找到当前可读的发布候选；不代表已有引用已失效。'};
  const next=choices[0];if(!canonical(next.digest))throw Error('Invalid digest');
  if(next.revision_id===ref.revision_id){if(next.digest!==ref.digest)throw Error('Same revision digest differs');return {binding,name,before,status:'当前引用与可读的发布版本一致。'}}
  const after=await exact(next,true);return {binding,name,before,after,next,status:'可选择新的发布版本'};
 }catch{if(signal.aborted)throw Error('Aborted');return {binding,name,before:binding.purpose,status:'当前或候选版本未能核实，请检查资源可读性后重新核对。'}}
}

function ComparedContent({value}:{value:string}){
 const [summary,...evidence]=value.split('\n');
 return <><p>{summary}</p>{evidence.length>0&&<details><summary>查看完整资源定义与引用</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{evidence.join('\n')}</pre></details>}</>;
}

const typeNames:Record<CapabilityBinding['kind'],string>={EMPLOYEE:'数字人',SKILL:'技能',MCP:'MCP 服务',KNOWLEDGE:'知识',RUNTIME_PROFILE:'运行环境',ONTOLOGY:'本体',TOOL:'工具'};
function ChangeSummary({before,after}:{before:string;after:string}){
 const sentences=(value:string)=>value.split('\n')[0].split('；').filter(Boolean);
 const difference=(left:string[],right:string[])=>{const remaining=[...right];return left.filter(text=>{const index=remaining.indexOf(text);if(index<0)return true;remaining.splice(index,1);return false})};
 const added=difference(sentences(after),sentences(before)),removed=difference(sentences(before),sentences(after));
 return <div aria-label="本次内容差异">{added.map((text,index)=><p key={'add'+index}><strong>新增：</strong><mark style={{background:'#e7f6ee',color:'#18865d'}}>{text}</mark></p>)}{removed.map((text,index)=><p key={'remove'+index}><strong>移除：</strong><del>{text}</del></p>)}{!added.length&&!removed.length&&<p>职责摘要相同，固定定义或资源引用有变化，请展开核对完整内容。</p>}</div>;
}

export function CapabilityResourceUpdates({detail,principal,onSaved,onCancel}:{detail:CapabilityDetail;principal:string;onSaved:(detail:CapabilityDetail)=>void;onCancel:()=>void}){
 const [rows,setRows]=useState<Update[]>([]),[selected,setSelected]=useState<string[]>([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[retry,setRetry]=useState(0);
 const [busy,setBusy]=useState(false),[command,setCommand]=useState<{revision:CapabilityRevision;expectedVersion:number;commandId:string}|null>(null);
 const alive=useRef(true),pending=useRef(false);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[]);
 const stable=(value:unknown):string=>JSON.stringify(value,(_key,item)=>item&&typeof item==='object'&&!Array.isArray(item)?Object.fromEntries(Object.entries(item).sort(([a],[b])=>a.localeCompare(b))):item);
 async function createDraft(){
  if(pending.current)return;pending.current=true;setBusy(true);setError('');let dispatched=false;
  try{
   const signal=AbortSignal.timeout(30_000);let frozen=command;
   if(!frozen){
    if(!selected.length||detail.headRevisionId!==detail.revision.revision_id)throw Error('selection');
    const current=await readCapability(detail.revision.capability_id,detail.revision.revision_id,principal,signal);
    if(current.headRevisionId!==detail.revision.revision_id||current.aggregateVersion!==detail.aggregateVersion||current.digest!==detail.digest)throw Error('changed');
    const cache=new Map<string,Promise<Scan>>();
    const checked=await Promise.all(rows.filter(row=>selected.includes(key(row.binding))).map(async row=>{
     const fresh=await inspect(row.binding,row.name,signal,cache);
     if(!fresh.next||stable(fresh.next)!==stable(row.next))throw Error('resource-changed');
     return fresh;
    }));
    if(checked.length!==selected.length)throw Error('selection');
    const session=await capabilitySession(signal);if(workbenchPrincipalKey(session)!==principal)throw Error('identity');
    frozen={revision:{...detail.revision,revision_id:'capability-revision:'+crypto.randomUUID(),predecessor_revision_id:detail.revision.revision_id,bindings:detail.revision.bindings.map(binding=>{const row=checked.find(item=>key(item.binding)===key(binding));return row?.next?{...binding,reference:row.next}:binding})},expectedVersion:detail.aggregateVersion,commandId:'capability-upgrade:'+crypto.randomUUID()};
    if(!alive.current)return;setCommand(frozen);dispatched=true;
    await saveCapability(frozen.revision,frozen.expectedVersion,frozen.commandId,principal,signal);
   }
   const result=await readCapability(frozen.revision.capability_id,frozen.revision.revision_id,principal,signal);
   if(stable(result.revision)!==stable(frozen.revision))throw Error('readback');
   if(alive.current)onSaved(result);
  }catch(cause){if(alive.current){
   const rejected=cause instanceof CapabilityRequestError&&!cause.outcomeUnknown&&[400,403,404,409,422].includes(cause.status);
   if(dispatched&&rejected)setCommand(null);
   setError(command||dispatched&&!rejected?'草稿结果尚未核实。请读取原草稿，保持同一修订，不再次提交。':'当前能力、资源或权限已变化，未能创建草稿。请重新核对更新后再选择。');
  }}finally{pending.current=false;if(alive.current)setBusy(false)}
 }
 useEffect(()=>{
  const controller=new AbortController();let active=true;
  const load=async()=>{
   setLoading(true);setRows([]);setSelected([]);setError('');
   try{
    const signal=AbortSignal.any([controller.signal,AbortSignal.timeout(30_000)]),before=await capabilitySession(signal);
    if(workbenchPrincipalKey(before)!==principal)throw Error('identity');
    const cache=new Map<string,Promise<Scan>>();
    const values=await Promise.all(detail.revision.bindings.map(binding=>inspect(binding,detail.members?.find(member=>member.kind===binding.kind&&member.resourceId===binding.reference.resource_id&&member.revisionId===binding.reference.revision_id)?.name??binding.purpose,signal,cache)));
    const after=await capabilitySession(signal);if(workbenchPrincipalKey(after)!==principal)throw Error('identity');
    if(active)setRows(values);
   }catch{if(active)setError('资源更新暂未核对完成，请重新读取；本次没有修改任何引用。')}
   finally{if(active)setLoading(false)}
  };void load();return()=>{active=false;controller.abort()};
 },[detail,principal,retry]);
 const changed=rows.filter(row=>row.next),same=rows.filter(row=>row.status==='当前引用与可读的发布版本一致。'),unverified=rows.filter(row=>!row.next&&!same.includes(row));
 const historical=detail.headRevisionId!==detail.revision.revision_id;
 return <section className="capability-panel" aria-label="资源版本升级"><h2>核对资源版本更新</h2><p>只替换所选资源的固定版本，保留其他分工、业务规则和完成标准。既有会话、任务与流程调用不自动更新。</p>
 {historical&&<p className="capability-notice" role="status">正在比较历史版本，仅供查看。请回到当前版本准备修改；此处不能改写后续版本。</p>}
 {loading&&<p role="status">正在核对当前引用与可读的发布版本…</p>}{error&&<p role="alert">{error}</p>}
 {!loading&&!error&&<p role="status">已核对 {rows.length} 项：{changed.length} 项可更新，{same.length} 项引用一致，{unverified.length} 项待核实。</p>}
 {!loading&&!changed.length&&!unverified.length&&!error&&<p>当前引用已一致，无需创建升级草稿。</p>}
 {changed.map(row=><article className="capability-change" key={key(row.binding)}><h3>{row.name}</h3><p>本次职责保持：{row.binding.purpose}</p><ChangeSummary before={row.before} after={row.after??''}/><details><summary>核对完整内容与固定版本</summary><div className="capability-grid"><div><h4>当前固定内容</h4><ComparedContent value={row.before}/><p>{row.binding.reference.revision_id}</p><p>{row.binding.reference.digest}</p></div><div><h4>拟采用内容</h4><ComparedContent value={row.after??''}/><p>{row.next!.revision_id}</p><p>{row.next!.digest}</p></div></div></details>
 {!historical&&<label style={{display:'flex',alignItems:'center',gap:8}}><input style={{width:'auto'}} type="checkbox" disabled={busy||command!==null} checked={selected.includes(key(row.binding))} onChange={event=>setSelected(old=>event.target.checked?[...old,key(row.binding)]:old.filter(value=>value!==key(row.binding)))}/>采用 {row.name} 的新发布版本</label>}</article>)}
 {!!same.length&&<details><summary>其余 {same.length} 项保持当前引用</summary>{same.map(row=><details key={key(row.binding)}><summary>{typeNames[row.binding.kind]} · {row.name} · 引用一致</summary><ComparedContent value={row.before}/><p>{row.binding.reference.revision_id}</p></details>)}</details>}
 {unverified.map(row=><article key={key(row.binding)}><h3>{typeNames[row.binding.kind]} · {row.name}</h3><p>{row.status}</p></article>)}
 <div className="capability-actions">{!historical&&(!!changed.length||command)&&<button disabled={loading||busy||(!command&&!selected.length)} onClick={()=>void createDraft()}>{busy?'正在核实草稿…':command?'读取原草稿':'创建能力新版本草稿'}</button>}<button disabled={loading||busy||command!==null} onClick={()=>setRetry(value=>value+1)}>重新核对资源更新</button><button disabled={busy} onClick={onCancel}>返回能力</button></div><p>创建后仍需核对变更并发布能力，才会供新的工作选择；现有工作不自动更新。</p></section>;
}
