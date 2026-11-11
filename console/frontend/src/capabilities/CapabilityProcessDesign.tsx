import {useEffect,useMemo,useRef,useState} from 'react';
import {Link} from 'react-router-dom';
import {CapabilityEditor,type CapabilityEditorDraft,type CapabilitySeed,type CapabilitySaveDraft} from './CapabilityEditor';
import {readCapability,type CapabilityDetail} from '../api/businessCapabilities';
import {BusinessProcessRequestError,readBusinessProcess,saveBusinessCapabilityRelation,readBusinessCapabilityRelationReceipt,type BusinessRelationCommand,type BusinessProcessContent} from '../api/businessProcesses';
import {safeBusinessProcessReturn} from '../businessProcesses/businessRelationNavigation';

type Progress={draft?:CapabilityEditorDraft;command?:CapabilitySaveDraft;saved?:{id:string;revision:string;digest:string};relation?:BusinessRelationCommand;complete?:boolean};
export function CapabilityProcessDesign({source,principal}:{source:string;principal:string}){
 const safe=safeBusinessProcessReturn(source),query=useMemo(()=>safe?new URL(safe,window.location.origin).searchParams:null,[safe]);
 const valid=!!query?.get('activity')&&!query?.has('edit')&&!query?.has('draft');
 const storage='capability-process-design:v1:'+JSON.stringify([principal,safe]);
 const latest=useRef<Progress>({});
 const [draftError,setDraftError]=useState('');
 const [content,setContent]=useState<BusinessProcessContent|null>(null),[state,setState]=useState<Progress|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[reload,setReload]=useState(0),[retryAllowed,setRetryAllowed]=useState(false);
 useEffect(()=>{const controller=new AbortController();let active=true;
  void (async()=>{try{
   if(!valid||!query)throw Error('来源地址不完整，请返回原活动重新进入。');
   const record=await readBusinessProcess(query.get('process')!,query.get('revision')!,principal,controller.signal);
   if(record.objectId!==query.get('process')||record.revisionId!==query.get('revision')||record.digest!==query.get('digest')||!record.record.content.activities.some(a=>a.activity_id===query.get('activity')))throw Error('原流程版本或活动无法核实。');
   const raw=sessionStorage.getItem(storage),progress:Progress=raw?JSON.parse(raw):{};
   if(progress.draft&&(!progress.draft.fields||!Object.values(progress.draft.fields).every(v=>typeof v==='string')||typeof progress.draft.criteria!=='string'||typeof progress.draft.domain!=='string'||typeof progress.draft.purpose!=='string'||!Array.isArray(progress.draft.bindings)||!['INDEPENDENT','WORKFLOW_REVISION','SAVED_PREPARATION'].includes(progress.draft.origin?.kind)))throw Error('本地编辑记录无法核实，请保留记录。');
   if(progress.command&&(!progress.command.commandId||progress.command.expectedVersion!==0||progress.command.revision.predecessor_revision_id!==null))throw Error('原保存记录无法核实，请保留记录，不要重复创建。');
   if(progress.relation&&(!progress.saved||progress.relation.expectedVersion!==0||progress.relation.relation.relation_type!=='DERIVED_FROM_PROCESS'||progress.relation.relation.process.resource_id!==query.get('process')||progress.relation.relation.process.revision_id!==query.get('revision')||progress.relation.relation.process.digest!==query.get('digest')||JSON.stringify(progress.relation.relation.activity_ids)!==JSON.stringify([query.get('activity')])||progress.relation.relation.capability.resource_id!==progress.saved.id||progress.relation.relation.capability.revision_id!==progress.saved.revision||progress.relation.relation.capability.digest!==progress.saved.digest))throw Error('来源续接记录不匹配，请保留原记录。');
   if(progress.complete){if(!progress.relation)throw Error('来源回执缺失');const receipt=await readBusinessCapabilityRelationReceipt(progress.relation.commandId,principal,controller.signal);if(receipt.relationId!==progress.relation.relation.relation_id||receipt.relationRevisionId!==progress.relation.relation.relation_revision_id||receipt.executionAuthorized!==false)throw Error('来源回执无法核实')}
   if(progress.saved){const saved=await readCapability(progress.saved.id,progress.saved.revision,principal,controller.signal);if(saved.digest!==progress.saved.digest)throw Error('已保存能力版本无法核实。')}
   if(active){setContent(record.record.content);latest.current=progress;setState(progress);setError('')}
  }catch(e){if(active){setContent(null);setState(null);setError(e instanceof Error?e.message:'来源暂不可读')}}})();
  return()=>{active=false;controller.abort()};
 },[source,principal,storage,valid,reload,query]);
 const persist=(next:Progress)=>{sessionStorage.setItem(storage,JSON.stringify(next));latest.current=next;setState(next)};
 const activity=content?.activities.find(a=>a.activity_id===query?.get('activity'));
 const register=async(progress:Progress,readOnly=false)=>{
  if(!query||!progress.saved||busy)return;setBusy(true);setError('');setRetryAllowed(false);
  try{
   let next=progress;
   if(!next.relation){
    next={...next,relation:{commandId:'business-relation-command:'+crypto.randomUUID(),expectedVersion:0,relation:{relation_id:'business-relation:'+crypto.randomUUID(),relation_revision_id:'business-relation-revision:'+crypto.randomUUID(),relation_type:'DERIVED_FROM_PROCESS',process:{resource_id:query.get('process')!,revision_id:query.get('revision')!,digest:query.get('digest')!},activity_ids:[query.get('activity')!],capability:{resource_id:progress.saved.id,revision_id:progress.saved.revision,digest:progress.saved.digest},coverage_description:'基于活动“'+activity!.name+'”创建能力草稿；输入、交付、人工边界和完成标准来自此固定活动，资源适用性与执行效果尚未验证。'}}};persist(next);
   }
   const command=next.relation!;
   const result=readOnly?await readBusinessCapabilityRelationReceipt(command.commandId,principal,new AbortController().signal):await saveBusinessCapabilityRelation(command,principal,new AbortController().signal);
   if(result.relationId!==command.relation.relation_id||result.relationRevisionId!==command.relation.relation_revision_id||result.relationVersion!==1||result.executionAuthorized!==false)throw Error('来源回执不匹配');
   persist({...next,complete:true});
  }catch(cause){setRetryAllowed(readOnly&&cause instanceof BusinessProcessRequestError&&cause.code==='BUSINESS_RELATION_NOT_FOUND');setError('能力草稿已保存，来源登记未完成或结果尚未核实。请先核实原提交，不会自动再次写入。')}
  finally{setBusy(false)}
 };
 const saved=async(value:CapabilityDetail)=>{
  const next={...latest.current,draft:undefined,saved:{id:value.revision.capability_id,revision:value.revision.revision_id,digest:value.digest}};
  try{persist(next);await register(next)}catch{setError('能力已保存，但本地续接记录保存失败。请保留当前页面，不要重复创建。')}
 };
 const seed:CapabilitySeed=activity&&content?{title:activity.name+'能力',intent:content.purpose??'',inputs:activity.inputs.join('；'),outputs:activity.outputs.join('；'),manual_involvement:activity.human_boundary??'',acceptance_criteria:activity.completion_conditions,bindings:[...(activity.employee?[{kind:'EMPLOYEE' as const,reference:activity.employee,purpose:activity.name}]:[]),...(content.source_materials??[]).map(reference=>({kind:'KNOWLEDGE' as const,reference,purpose:'流程资料候选依据，适用性待核对'}))]}:{};
 return <main className="f3-capabilities"><header><h1>基于活动创建能力草稿</h1></header>{safe&&<Link to={safe} onClick={event=>{if(draftError)event.preventDefault()}}>返回原流程活动</Link>}{error&&<p role="alert">{error}</p>}{draftError&&<p role="alert">{draftError}</p>}{!state&&!error&&<p role="status">正在核对固定流程与活动…</p>}{error&&!state&&<button onClick={()=>setReload(n=>n+1)}>重新核对来源</button>}
 {content&&activity&&state&&<><section className="capability-panel"><h2>{content.name} · {activity.name}</h2><p>带入活动的设计依据；适用范围、排除项、限制和资源适用性仍需核对。这不代表智能装配或执行验证已完成。</p><p>保存草稿后自动登记本次来源，发布另行核对。不会修改原流程。</p></section>
 {!state.saved?<CapabilityEditor principal={principal} seed={seed} initialDraft={state.draft} onDraft={draft=>{try{persist({...latest.current,draft});setDraftError('')}catch{setDraftError('编辑内容暂时无法保留，请留在此页并复制填写内容；返回操作已暂停。')}}} initialCommand={state.command} onCommand={command=>persist({...latest.current,command:command??undefined})} onSaved={value=>void saved(value)} onCancel={()=>{if(!draftError)window.history.back()}}/>:<section className="capability-panel"><h2>能力草稿已保存</h2><p role="status">{busy?'正在登记或核实设计来源…':state.complete?'设计来源已登记，资源适用性与执行效果仍未验证。':'来源登记尚未完成。'}</p>{!state.complete&&<button disabled={busy} onClick={()=>void register(state,!!state.relation)}>{state.relation?'核实原来源登记':'继续登记来源'}</button>}{retryAllowed&&<button disabled={busy} onClick={()=>void register(state)}>重试同一份来源登记</button>}{state.complete&&<Link to={'/capabilities?'+new URLSearchParams({capability:state.saved.id,revision:state.saved.revision,digest:state.saved.digest,businessProcessReturn:safe!})}>查看能力草稿与发布条件</Link>}</section>}</>}
 </main>;
}
