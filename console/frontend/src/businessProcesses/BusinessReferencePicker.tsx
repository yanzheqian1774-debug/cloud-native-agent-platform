import {Link} from 'react-router-dom';
import {businessReferenceHref} from './businessRelationNavigation';
import {useEffect,useRef,useState} from 'react';
import {getEmployeeAuthoring,getEmployeeDefinition,getWorkbenchSession,listEmployeeDefinitions,workbenchPrincipalKey} from '../api/digitalEmployees';
import {listReadableResources,readExactDirectoryResource} from '../api/resourceDirectory';
import type {FixedBusinessReference,BusinessReferenceDetails} from '../api/businessProcesses';

type Choice=FixedBusinessReference&{name:string;current?:boolean};
const identity=(item:FixedBusinessReference)=>JSON.stringify([item.resource_id,item.revision_id,item.digest]);
export function BusinessReferencePicker({kind,selected,principal,details,disabled=false,onChange,returnTo,onBeforeNavigate}:{onBeforeNavigate?:()=>boolean;returnTo?:string;kind:'knowledge'|'employee';selected:FixedBusinessReference[];principal?:string;details?:BusinessReferenceDetails;disabled?:boolean;onChange?:(value:FixedBusinessReference[])=>void}){
 const [items,setItems]=useState<Choice[]>([]),[names,setNames]=useState<Record<string,string>>({}),[cursor,setCursor]=useState<string|null>(null),[loaded,setLoaded]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [projectionVisible,setProjectionVisible]=useState(true);
 const projected=Object.fromEntries((details?.items??[]).filter(item=>item.kind===kind&&item.status==='AVAILABLE'&&item.name).map(item=>[identity(item.reference),item.name!]));
 const known={...(projectionVisible?projected:{}),...names};
 const missing=selected.some(item=>!known[identity(item)]);
 const unavailable=selected.some(item=>details?.items.some(value=>value.kind===kind&&identity(value.reference)===identity(item)&&value.status==='UNAVAILABLE')&&!known[identity(item)]);
 const groups=[...new Set(items.map(item=>item.resource_id))].map(id=>({id,versions:items.filter(item=>item.resource_id===id)}));
 const abort=useRef<AbortController|null>(null),subject=useRef(principal??''),running=useRef(false);
 const label=kind==='knowledge'?'流程资料':'支撑数字人';
 const unresolved=JSON.stringify(selected.filter(item=>!known[identity(item)]));
 useEffect(()=>{
  if(!principal||disabled||unresolved==='[]')return;
  const controller=new AbortController(),signal=AbortSignal.any([controller.signal,AbortSignal.timeout(30_000)]);
  const expire=()=>controller.abort();window.addEventListener('workbench-session-expired',expire);
  void(async()=>{
   const before=workbenchPrincipalKey(await getWorkbenchSession(signal));if(before!==principal)throw Error('IDENTITY_CHANGED');
   const references=JSON.parse(unresolved) as FixedBusinessReference[];
   const resolved=await Promise.all(references.map(async item=>{
    if(kind==='knowledge'){const value=await readExactDirectoryResource('knowledge',item.resource_id,item.revision_id,item.digest,signal);return [identity(item),value.name]}
    const value=await getEmployeeDefinition(item.resource_id,item.revision_id,signal);if(value.employeeDefinitionId!==item.resource_id||value.employeeDefinitionRevisionId!==item.revision_id||value.employeeDefinitionDigest!==item.digest)throw Error('REFERENCE_CHANGED');return [identity(item),value.role];
   }));
   if(workbenchPrincipalKey(await getWorkbenchSession(signal))!==before)throw Error('IDENTITY_CHANGED');
   if(!signal.aborted)setNames(old=>({...old,...Object.fromEntries(resolved)}));
  })().catch(()=>{if(!signal.aborted)setError('关联内容暂未核实，请核对访问范围后重试。原关联不会自动替换。')});
  return()=>{controller.abort();window.removeEventListener('workbench-session-expired',expire)};
 },[principal,kind,unresolved,disabled]);

 useEffect(()=>{const controller=new AbortController();abort.current=controller;subject.current=principal??'';const expire=()=>{controller.abort();setItems([]);setNames({});setProjectionVisible(false);setLoaded(false);setCursor(null);setError('登录已变化，请重新读取业务定义。')};window.addEventListener('workbench-session-expired',expire);return()=>{controller.abort();window.removeEventListener('workbench-session-expired',expire)}},[principal]);
 async function perform(action:(signal:AbortSignal)=>Promise<()=>void>){
  if(running.current||disabled||!abort.current||abort.current.signal.aborted)return;
  running.current=true;setBusy(true);setError('');const signal=AbortSignal.any([abort.current.signal,AbortSignal.timeout(30_000)]);
  try{const before=workbenchPrincipalKey(await getWorkbenchSession(signal));if(subject.current&&before!==subject.current)throw Error('IDENTITY_CHANGED');subject.current=before;const apply=await action(signal);const after=workbenchPrincipalKey(await getWorkbenchSession(signal));if(signal.aborted)return;if(after!==before)throw Error('IDENTITY_CHANGED');apply()}
  catch{if(!abort.current?.signal.aborted){setItems([]);setNames({});setProjectionVisible(false);setLoaded(false);setCursor(null);setError('关联内容暂未核实，请核对访问范围后重试。原关联不会自动替换。')}}finally{running.current=false;if(!abort.current?.signal.aborted)setBusy(false)}
 }
 function load(more=false){void perform(async signal=>{
  let choices:Choice[],next:string|null;
  if(kind==='knowledge'){const page=await listReadableResources('knowledge','','PUBLISHED',more?cursor:null,signal);choices=page.items.filter(item=>item.enabled&&item.isCurrentPublished).map(item=>({resource_id:item.identity,revision_id:item.revisionId,digest:item.digest,name:item.name}));next=page.nextCursor}
  else{const page=await listEmployeeDefinitions(more?cursor??undefined:undefined,signal);const parents=[...new Map(page.items.map(item=>[item.employeeDefinitionId,item])).values()];const heads=new Map<string,string>();const current:Choice[]=[];
   for(let offset=0;offset<parents.length;offset+=4)await Promise.all(parents.slice(offset,offset+4).map(async parent=>{try{const view=await getEmployeeAuthoring(parent,signal);if(view.publication.status==='AVAILABLE'){const item=view.publication.definition;heads.set(item.employeeDefinitionId,item.employeeDefinitionRevisionId);current.push({resource_id:item.employeeDefinitionId,revision_id:item.employeeDefinitionRevisionId,digest:item.employeeDefinitionDigest,name:item.role,current:true})}}catch{/* Keep historical candidates separate; never infer the current version. */}}));
   choices=[...page.items.filter(item=>item.publicationState==='PUBLISHED').map(item=>({resource_id:item.employeeDefinitionId,revision_id:item.employeeDefinitionRevisionId,digest:item.employeeDefinitionDigest,name:item.role,current:heads.has(item.employeeDefinitionId)?heads.get(item.employeeDefinitionId)===item.employeeDefinitionRevisionId:undefined})),...current];next=page.nextCursor??null}
  return()=>{setItems(old=>[...new Map([...(more?old:[]),...choices].map(item=>[identity(item),item])).values()]);setNames(old=>({...old,...Object.fromEntries(choices.map(item=>[identity(item),item.name]))}));setCursor(next);setLoaded(true)}
 })}
 function verify(){void perform(async signal=>{
  const resolved=await Promise.all(selected.map(async item=>{
   if(kind==='knowledge'){const value=await readExactDirectoryResource('knowledge',item.resource_id,item.revision_id,item.digest,signal);return [identity(item),value.name]}
   const value=await getEmployeeDefinition(item.resource_id,item.revision_id,signal);if(value.employeeDefinitionId!==item.resource_id||value.employeeDefinitionRevisionId!==item.revision_id||value.employeeDefinitionDigest!==item.digest)throw Error('REFERENCE_CHANGED');return [identity(item),value.role];
  }));return()=>setNames(old=>({...old,...Object.fromEntries(resolved)}));
 })}
 function choose(item:FixedBusinessReference,remove=false){void perform(async()=>()=>{if(!onChange)return;const key=identity(item);if(remove){onChange(selected.filter(value=>identity(value)!==key));return}if(selected.some(value=>identity(value)===key))return;if(kind==='knowledge'&&selected.length>=64){setError('流程资料最多关联64项。');return}const fixed={resource_id:item.resource_id,revision_id:item.revision_id,digest:item.digest};onChange(kind==='employee'?[fixed]:[...selected,fixed])})}
 function renderChoice(item:Choice){return <div key={identity(item)}><button type="button" disabled={disabled||busy||selected.some(value=>identity(value)===identity(item))} onClick={()=>choose(item)}>{item.name}{selected.some(value=>identity(value)===identity(item))?' · 已选择':''}</button><details><summary>候选版本依据</summary><p>{item.revision_id}</p><p>{item.digest}</p></details></div>}
 return <section className="bp-reference-picker" aria-label={label}><h4>{label}</h4><p>{kind==='knowledge'?'资料用于说明业务依据。':'数字人支撑此活动，业务责任角色保持独立。'}关联固定版本不代表可执行。</p>
 {selected.length>0?<><ul>{selected.map((item,index)=><li key={identity(item)}><strong>{known[identity(item)]??`${kind==='knowledge'?'资料':'数字人'} ${index+1} · 名称待核对`}</strong>{returnTo&&businessReferenceHref(kind,item,returnTo)&&<Link onClick={event=>{if(disabled||onBeforeNavigate?.()===false)event.preventDefault()}} to={businessReferenceHref(kind,item,returnTo)!}>查看固定版本详情</Link>}<details data-bp-state-key={kind+':'+identity(item)}><summary>版本依据</summary><p>{item.resource_id}</p><p>{item.revision_id}</p><p>{item.digest}</p></details>{kind==='employee'&&items.some(value=>identity(value)===identity(item)&&value.current===false)&&<small>已关联历史版本，保持原版本</small>}{onChange&&<button type="button" disabled={disabled||busy} onClick={()=>choose(item,true)}>移除此关联</button>}</li>)}</ul>{missing&&<button type="button" disabled={disabled||busy} onClick={verify}>重新读取关联</button>}</>:<p>尚未关联{kind==='knowledge'?'资料':'数字人'}。</p>}
 {unavailable&&<p>部分关联当前不可读或暂不可用，原固定引用仍保留。</p>}
 {onChange&&<button type="button" disabled={disabled||busy} onClick={()=>load()}>选择{kind==='knowledge'?'流程资料':'支撑数字人'}</button>}
 {busy&&<p role="status">正在核对可读版本…</p>}{error&&<p role="alert">{error}</p>}
 {loaded&&onChange&&<div><p>可选择已发布的固定版本</p>{kind==='knowledge'?items.map(renderChoice):groups.map(group=>{const current=group.versions.find(item=>item.current);const historical=group.versions.filter(item=>!item.current);return <div className="bp-reference-object" key={group.id}><h5>{current?.name??group.versions[0].name}</h5>{current?renderChoice(current):<p>当前发布版暂不可读或未发布。</p>}{historical.length>0&&<details><summary>查看历史版本（{historical.length}）</summary>{historical.map(renderChoice)}</details>}</div>})}{!items.length&&<p>当前页暂无可选版本。</p>}{cursor&&<button type="button" disabled={disabled||busy} onClick={()=>load(true)}>加载更多候选</button>}</div>}
 </section>;
}
