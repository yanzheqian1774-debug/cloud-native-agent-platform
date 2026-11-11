import {Link,useNavigate} from 'react-router-dom';
import {businessProcessHref} from './businessRelationNavigation';
import {useEffect,useEffectEvent,useLayoutEffect,useRef,useState} from 'react';
import type {BusinessRelationAccess} from './useBusinessRelationAccess';
import {listCapabilities,readCapability,type CapabilityItem} from '../api/businessCapabilities';
import {BusinessProcessRequestError,readBusinessProcess,saveBusinessCapabilityRelation,readBusinessCapabilityRelationReceipt,type FixedBusinessReference,type BusinessRelationCommand,type BusinessRelationEntry} from '../api/businessProcesses';

type RelationDraft={description:string;kind:'SUPPORTS_ACTIVITY'|'DERIVED_FROM_PROCESS';adjusting:boolean;targetProcess:FixedBusinessReference;selected:FixedBusinessReference|null;coverage:string[]};

export function BusinessRelationEditor({reference,activityId,onSaved,base,access}:{access:BusinessRelationAccess;base?:BusinessRelationEntry;reference:FixedBusinessReference;activityId:string;onSaved:()=>void}){
 const {principal,allowed,signal:accessSignal}=access;
 const navigate=useNavigate();
 const [processTitle,setProcessTitle]=useState(base?.processName??'关联流程'),[processVersion,setProcessVersion]=useState<number|null>(null),[capabilityVersion,setCapabilityVersion]=useState<number|null>(null);
 const [adjusting,setAdjusting]=useState(false),[reviewed,setReviewed]=useState(false),[targetProcess,setTargetProcess]=useState(reference),[coverage,setCoverage]=useState(base?.record.activity_ids??[activityId]),[activities,setActivities]=useState(base?.activities??[]);
 const [opened,setOpened]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [items,setItems]=useState<CapabilityItem[]>([]),[cursor,setCursor]=useState<string|null>(null),[selected,setSelected]=useState<FixedBusinessReference|null>(base?.record.capability??null),[title,setTitle]=useState(base?.capabilityTitle??''),[description,setDescription]=useState(base?.record.coverage_description??''),[kind,setKind]=useState<'SUPPORTS_ACTIVITY'|'DERIVED_FROM_PROCESS'>(base?.record.relation_type??'SUPPORTS_ACTIVITY');
 const [pending,setPending]=useState<BusinessRelationCommand|null>(null),[retry,setRetry]=useState(false);
 const [draftReady,setDraftReady]=useState(false);
 const control=useRef<AbortController|null>(null),storage=useRef(''),hydrated=useRef(''),running=useRef(false);
 const {resource_id,revision_id,digest}=reference;
 const baseId=base?.relationId??'',baseRevision=base?.relationRevisionId??'',expectedVersion=base?.relationVersion??0;
 useEffect(()=>{
  const controller=new AbortController();control.current=controller;
  const expire=()=>{controller.abort();setOpened(false);setPending(null);setItems([]);setSelected(null);setDescription('');setDraftReady(false)};
  if(accessSignal?.aborted)controller.abort();else accessSignal?.addEventListener('abort',expire,{once:true});
  return()=>{controller.abort();accessSignal?.removeEventListener('abort',expire)};
 },[resource_id,revision_id,digest,activityId,baseId,baseRevision,expectedVersion,principal,accessSignal]);
 useEffect(()=>{
  const controller=control.current;if(!controller)return;let active=true;
  void Promise.resolve().then(async()=>{
   if(!active||!principal||controller.signal.aborted)return;
   setDraftReady(false);
   try{
    const localKey='business-relation-command:v1:'+JSON.stringify([principal,resource_id,revision_id,digest,activityId,...(baseId?[baseId,baseRevision]:[])]);
    const raw=sessionStorage.getItem(localKey),command=raw?JSON.parse(raw) as BusinessRelationCommand:null;
    if(command&&(command.relation.process.resource_id!==resource_id||(!baseId&&(command.relation.process.revision_id!==revision_id||command.relation.process.digest!==digest||!command.relation.activity_ids.includes(activityId)))||command.expectedVersion!==expectedVersion||(baseId&&(command.relation.relation_id!==baseId||command.relation.capability.resource_id!==base?.record.capability.resource_id||command.relation.relation_type!==base?.record.relation_type))||!command.commandId||!command.relation.relation_id||!command.relation.relation_revision_id))throw Error('INVALID_LOCAL_COMMAND');
    storage.current=localKey;setPending(command);setRetry(false);if(command)setOpened(true);
    const draftRaw=!command&&allowed&&hydrated.current!==localKey?sessionStorage.getItem(localKey+':draft'):null;
    if(draftRaw){
     const draft=JSON.parse(draftRaw) as RelationDraft;
     if(typeof draft.description!=='string'||draft.description.length>2000||typeof draft.adjusting!=='boolean'||!['SUPPORTS_ACTIVITY','DERIVED_FROM_PROCESS'].includes(draft.kind)||!Array.isArray(draft.coverage)||draft.coverage.some(id=>typeof id!=='string')||draft.targetProcess.resource_id!==resource_id||(baseId&&(draft.kind!==base?.record.relation_type||(draft.selected&&draft.selected.resource_id!==base?.record.capability.resource_id)))||(!baseId&&(draft.targetProcess.revision_id!==revision_id||draft.targetProcess.digest!==digest)))throw Error('INVALID_LOCAL_DRAFT');
     const process=await readBusinessProcess(resource_id,draft.targetProcess.revision_id,principal,controller.signal);
     if(process.revisionId!==draft.targetProcess.revision_id||process.digest!==draft.targetProcess.digest||draft.coverage.some(id=>!process.record.content.activities.some(a=>a.activity_id===id)))throw Error('DRAFT_REFERENCE_MISMATCH');
     const capability=draft.selected?await readCapability(draft.selected.resource_id,draft.selected.revision_id,principal,controller.signal):null;
     if(draft.selected&&(!capability||capability.revision.capability_id!==draft.selected.resource_id||capability.revision.revision_id!==draft.selected.revision_id||capability.digest!==draft.selected.digest))throw Error('DRAFT_REFERENCE_MISMATCH');
     if(!active||controller.signal.aborted)return;
     setDescription(draft.description);setKind(draft.kind);setAdjusting(draft.adjusting);setReviewed(false);setTargetProcess(draft.targetProcess);setProcessTitle(process.record.content.name);setCoverage(draft.coverage);setActivities(process.record.content.activities.map(a=>({activityId:a.activity_id,name:a.name})));setSelected(draft.selected);setTitle(capability?.revision.title??'');setOpened(true);
    }
    if(active&&!controller.signal.aborted){if(allowed||command)hydrated.current=localKey;setDraftReady(true)}
   }catch{if(!active||controller.signal.aborted)return;controller.abort();setError('编辑或原提交记录无法核对，请保留当前页面与记录，不要重复保存。')}
  });
  return()=>{active=false};
 },[resource_id,revision_id,digest,activityId,baseId,baseRevision,expectedVersion,principal,allowed,accessSignal,base?.record.capability.resource_id,base?.record.relation_type]);

 const retainDraft=useEffectEvent(()=>{
  if(!draftReady||!opened||pending||!allowed||control.current?.signal.aborted)return;
  try{sessionStorage.setItem(storage.current+':draft',JSON.stringify({description,kind,adjusting,targetProcess,selected,coverage} satisfies RelationDraft))}
  catch{queueMicrotask(()=>{if(!control.current?.signal.aborted)setError('编辑内容暂时无法保留，请留在此页并复制填写内容后再离开。')})}
 });
 useLayoutEffect(()=>{retainDraft()},[draftReady,opened,pending,allowed,description,kind,adjusting,targetProcess,selected,coverage]);
 function cancel(){try{sessionStorage.removeItem(storage.current+':draft');setOpened(false)}catch{setError('本地编辑记录暂时无法清除，请保留当前页面。')}}
 async function candidates(next=false){const controller=control.current;if(!controller||controller.signal.aborted||running.current||!principal||!allowed)return;running.current=true;setBusy(true);setError('');
  try{const page=await listCapabilities(principal,next?cursor:null,controller.signal);if(!controller.signal.aborted){setItems(old=>next?[...old,...page.items]:page.items);setCursor(page.nextCursor)}}catch{if(!controller.signal.aborted){setItems([]);setCursor(null);setError('能力目录暂时无法读取，请重试。')}}finally{running.current=false;if(!controller.signal.aborted)setBusy(false)}
 }
 async function currentProcess(){
  const controller=control.current;if(!base||!principal||!allowed||!controller||controller.signal.aborted||running.current)return;
  running.current=true;setBusy(true);setError('');setReviewed(false);
  try{const head=await readBusinessProcess(resource_id,'',principal,controller.signal),published=head.publicationState?.published;
   if(head.objectId!==resource_id||!head.publicationState?.currentStateAvailable||!published||published.objectId!==resource_id)throw Error('PUBLICATION_UNAVAILABLE');
   const value=await readBusinessProcess(resource_id,published.revisionId,principal,controller.signal);
   if(value.objectId!==resource_id||value.revisionId!==published.revisionId||value.digest!==published.digest)throw Error('REFERENCE_MISMATCH');
   if(controller.signal.aborted)return;setProcessTitle(value.record.content.name);setProcessVersion(published.contentVersion??null);setTargetProcess({resource_id,revision_id:published.revisionId,digest:published.digest});setActivities(value.record.content.activities.map(a=>({activityId:a.activity_id,name:a.name})));setCoverage(old=>old.filter(id=>value.record.content.activities.some(a=>a.activity_id===id)));
  }catch{if(!controller.signal.aborted)setError('当前发布流程版本暂未核实，保留原选择，不自动调整关联。')}
  finally{running.current=false;if(!controller.signal.aborted)setBusy(false)}
 }
 async function selectCapability(item:CapabilityItem){
  const fixed=item.currentPublished,controller=control.current;if(!fixed||!principal||!controller||controller.signal.aborted||running.current||!allowed)return;
  running.current=true;setBusy(true);setError('');setReviewed(false);
  try{const value=await readCapability(item.capabilityId,fixed.revisionId,principal,controller.signal);
   if(value.revision.capability_id!==item.capabilityId||value.revision.revision_id!==fixed.revisionId||value.digest!==fixed.digest||value.publishedRevisionId!==fixed.revisionId)throw Error('REFERENCE_MISMATCH');
   if(!controller.signal.aborted){setSelected({resource_id:item.capabilityId,revision_id:fixed.revisionId,digest:fixed.digest});setTitle(fixed.title);setCapabilityVersion(value.aggregateVersion??null)}
  }catch{if(!controller.signal.aborted)setError('所选能力的发布版本暂未核实，原选择保留。')}
  finally{running.current=false;if(!controller.signal.aborted)setBusy(false)}
 }
 async function submit(mode:'save'|'read'|'retry'){
  const controller=control.current;if(!controller||controller.signal.aborted||running.current||!principal||(mode!=='read'&&!allowed))return;
  let command=pending;running.current=true;setBusy(true);setError('');
  try{
   if(!command){if(mode!=='save'||!selected||!description.trim()||!coverage.length||(adjusting&&!reviewed))return;command={commandId:'business-relation-command:'+crypto.randomUUID(),expectedVersion,relation:{relation_id:baseId||'business-relation:'+crypto.randomUUID(),relation_revision_id:'business-relation-revision:'+crypto.randomUUID(),relation_type:kind,process:targetProcess,activity_ids:coverage,capability:selected,coverage_description:description.trim()}};sessionStorage.setItem(storage.current,JSON.stringify(command));setPending(command)}
   const receipt=mode==='read'?await readBusinessCapabilityRelationReceipt(command.commandId,principal,controller.signal):await saveBusinessCapabilityRelation(command,principal,controller.signal);
   if(controller.signal.aborted)return;
   if(receipt.relationId!==command.relation.relation_id||receipt.relationRevisionId!==command.relation.relation_revision_id||receipt.relationVersion!==command.expectedVersion+1||receipt.executionAuthorized!==false||!/^[a-f0-9]{64}$/.test(receipt.digest))throw new BusinessProcessRequestError('INVALID_RECEIPT',503,true);
   sessionStorage.removeItem(storage.current);sessionStorage.removeItem(storage.current+':draft');setPending(null);setRetry(false);setOpened(false);setSelected(null);setDescription('');if(command.relation.process.revision_id!==revision_id||command.relation.process.digest!==digest)navigate(businessProcessHref(command.relation.process,command.relation.activity_ids[0]));else onSaved();
  }catch(cause){if(controller.signal.aborted)return;
   if(mode==='read'){setRetry(cause instanceof BusinessProcessRequestError&&cause.code==='BUSINESS_RELATION_NOT_FOUND');setError('原关联提交尚未核实；不会自动再次保存。')}
   else if(mode==='save'&&cause instanceof BusinessProcessRequestError&&!cause.outcomeUnknown){sessionStorage.removeItem(storage.current);setPending(null);setError(cause.code==='BUSINESS_RELATION_VERSION_CONFLICT'?'关联已有更新，请重新读取后核对；原记录未被覆盖。':'关联未保存，请核对当前权限、固定版本与覆盖范围。设计来源另需能力维护权限。')}
   else setError('保存结果尚未核实，已保留原提交。请先核实原提交。');
  }finally{running.current=false;if(!controller.signal.aborted)setBusy(false)}
 }
 if(!principal||(!allowed&&!pending))return null;
 return <section className="bp-relations" aria-label="维护活动能力关联">
  {error&&<p role="alert">{error}</p>}
  {!opened?<button onClick={()=>setOpened(true)}>{base?'修订关联说明':'关联业务能力'}</button>:<><h3>{base?'修订关联说明':'关联业务能力'}</h3>{base&&<p>基于关系修订 {base.relationVersion} 保存新修订；保留原对象和关系类型，历史记录不被覆盖。</p>}<p>关联只说明活动与能力的关系，不授予执行权或改变业务责任人。</p>
   {pending?<><p>有一份关联提交待核实。</p><p>{pending.relation.coverage_description}</p><details><summary>原提交固定版本与覆盖</summary><p>流程：{pending.relation.process.revision_id}</p><p>能力：{pending.relation.capability.revision_id}</p><p>活动：{pending.relation.activity_ids.join('、')}</p></details><button disabled={busy} onClick={()=>void submit('read')}>核实原关联提交</button>{retry&&allowed&&<button disabled={busy} onClick={()=>void submit('retry')}>重试同一份关联</button>}</>:allowed&&<>
    {base&&<button disabled={busy} onClick={()=>{setAdjusting(!adjusting);setReviewed(false);setTargetProcess(reference);setProcessTitle(base.processName??'关联流程');setProcessVersion(null);setCapabilityVersion(null);setCoverage(base.record.activity_ids);setActivities(base.activities);setSelected(base.record.capability);setTitle(base.capabilityTitle)}}>{adjusting?'保留原关联版本与覆盖':'调整关联版本与覆盖'}</button>}
    {adjusting&&<><button disabled={busy} onClick={()=>void currentProcess()}>读取当前发布流程版本</button><fieldset disabled={busy}><legend>关联覆盖活动</legend>{activities.map(item=><label key={item.activityId}><input type="checkbox" checked={coverage.includes(item.activityId)} onChange={event=>{setReviewed(false);setCoverage(old=>event.target.checked?[...old,item.activityId]:old.filter(id=>id!==item.activityId))}}/>{item.name}</label>)}</fieldset></>}
    {(!base||adjusting)&&<button disabled={busy} onClick={()=>void candidates()}>选择已发布能力</button>}
    {(!base||adjusting)&&items.filter(item=>item.currentPublished&&(!base||item.capabilityId===base.record.capability.resource_id)).map(item=><button key={item.capabilityId} disabled={busy} onClick={()=>{if(base){void selectCapability(item);return}const fixed=item.currentPublished!;setSelected({resource_id:item.capabilityId,revision_id:fixed.revisionId,digest:fixed.digest});setTitle(fixed.title)}}>{item.currentPublished!.title}</button>)}
    {cursor&&(!base||adjusting)&&<button disabled={busy} onClick={()=>void candidates(true)}>加载更多能力</button>}
    {selected&&<p>已选择：{title}<small> · 固定版本 {selected.revision_id}</small></p>}
    <label>关系类型<select value={kind} disabled={busy||!!base} onChange={event=>setKind(event.target.value as typeof kind)}><option value="SUPPORTS_ACTIVITY">能力支撑活动</option><option value="DERIVED_FROM_PROCESS">能力来源于流程设计</option></select></label>
    <label>{kind==='SUPPORTS_ACTIVITY'?'支撑范围说明':'实际设计来源与活动覆盖说明'}<textarea aria-label={kind==='SUPPORTS_ACTIVITY'?'支撑范围说明':'实际设计来源与活动覆盖说明'} value={description} maxLength={2000} disabled={busy} onChange={event=>{setDescription(event.target.value);setReviewed(false)}}/></label>
    {adjusting&&base&&<section aria-label="关联版本调整差异"><h4>本次关联调整</h4>
     <p>仅核对引用版本与覆盖范围，未验证业务适配。保存关联不代表新版可执行或结果有效。</p>
     <dl><div><dt>流程</dt><dd>{base.processName??'关联流程'} · 原关联修订 {base.relationVersion} 所用版本 → {processTitle} · {targetProcess.revision_id===base.record.process.revision_id?'保留原固定版本':`已核对的当前发布版${processVersion!==null?'（内容修订 '+processVersion+'）':''}`}</dd></div>
     <div><dt>能力</dt><dd>{base.capabilityTitle} · 原关联修订 {base.relationVersion} 所用版本 → {title} · {selected?.revision_id===base.record.capability.revision_id?'保留原固定版本':'已核对的当前发布版'}</dd></div></dl>
     <p>覆盖未变：{base.activities.filter(a=>coverage.includes(a.activityId)).map(a=>{const name=activities.find(n=>n.activityId===a.activityId)?.name;return name&&name!==a.name?a.name+' → '+name+'（同一活动）':a.name}).join('、')||'无'}</p>
     <p>新增覆盖：{activities.filter(a=>coverage.includes(a.activityId)&&!base.record.activity_ids.includes(a.activityId)).map(a=>a.name).join('、')||'无'}</p>
     <p>移除覆盖：{base.activities.filter(a=>!coverage.includes(a.activityId)).map(a=>a.name).join('、')||'无'}</p>
     <p>原内容和拟用内容将在新标签页打开，当前填写保留。</p><div className="bp-actions">
      <Link target="_blank" rel="noopener noreferrer" to={businessProcessHref(base.record.process,base.record.activity_ids[0])}>查看原流程内容</Link>
      <Link target="_blank" rel="noopener noreferrer" to={businessProcessHref(targetProcess,coverage[0])}>查看拟用流程内容</Link>
      <Link target="_blank" rel="noopener noreferrer" to={'/capabilities?'+new URLSearchParams({capability:base.record.capability.resource_id,revision:base.record.capability.revision_id,digest:base.record.capability.digest})}>查看原能力内容</Link>
      {selected&&<Link target="_blank" rel="noopener noreferrer" to={'/capabilities?'+new URLSearchParams({capability:selected.resource_id,revision:selected.revision_id,digest:selected.digest})}>查看拟用能力内容</Link>}
     </div><details><summary>固定版本变化依据</summary><p>流程：{base.record.process.revision_id} → {targetProcess.revision_id}</p><p>能力：{base.record.capability.revision_id} → {selected?.revision_id}</p><p>拟用流程摘要：{targetProcess.digest}</p><p>拟用能力摘要：{selected?.digest}</p>{capabilityVersion!==null&&<p>读取拟用能力时的对象聚合版本：{capabilityVersion}（不作为内容修订号）</p>}</details>
     <p>仅保存关联新修订，不修改流程或能力定义，不更新其他任务绑定，不启动执行。历史修订保持原覆盖。</p><button disabled={busy||!coverage.length||!selected||!description.trim()} onClick={()=>setReviewed(true)}>{reviewed?'已核对引用与覆盖范围':'核对版本与覆盖调整'}</button></section>}
    <button disabled={busy||!selected||!description.trim()||!coverage.length||(adjusting&&!reviewed)} onClick={()=>void submit('save')}>保存能力关联</button><button disabled={busy} onClick={cancel}>{base?'取消修改':'取消'}</button>
   </>}{busy&&<p role="status">正在读取或核实关联…</p>}</>}
 </section>;
}
