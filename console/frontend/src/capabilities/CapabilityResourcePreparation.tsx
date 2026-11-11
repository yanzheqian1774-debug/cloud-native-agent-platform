import {useCapabilityAdvance} from './useCapabilityAdvance';
import {useEffect,useRef,useState} from 'react';
import {capabilitySession,type CapabilityExecutionContract} from '../api/businessCapabilities';
import {workbenchPrincipalKey} from '../api/digitalEmployees';
import {conversationRequest} from '../api/privateConversation';
import {planningRequest} from '../planning/planningRequests';
import type {Confirmation,History,ResourcePreparation} from '../planning/api';
import {capabilityJournalPath,readCapabilityJournal,type CapabilityJournal} from './capabilityWorkJournal';

type Selection={confirmation:Confirmation;capabilitySource:{conversationId:string;sourceMessageId:string;contractDigest:string};preflight:{employeeReference:unknown};executionStarted:false};
const stable=(value:unknown):string=>JSON.stringify(value,(_key,item)=>item&&typeof item==='object'&&!Array.isArray(item)?Object.fromEntries(Object.entries(item).sort(([a],[b])=>a.localeCompare(b))):item);
export function CapabilityResourcePreparation({conversation,messageId,principal,journal,onRefresh,autoContinue=false,onStop}:{conversation:string;messageId:string;principal:string;journal:CapabilityJournal;onRefresh:()=>void;autoContinue?:boolean;onStop?:()=>void}){
 const [busy,setBusy]=useState(false),[status,setStatus]=useState(''),[error,setError]=useState(''),[ready,setReady]=useState<ResourcePreparation|null>(null);
 const alive=useRef(true),flight=useRef(false);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[]);
 async function verify(){const s=await capabilitySession();if(!alive.current||workbenchPrincipalKey(s)!==principal)throw Error('登录身份或当前工作已变化，请读取原记录。');return s}
 async function act(){
  if(flight.current)return;flight.current=true;setBusy(true);setError('');setReady(null);
  try{
   const s=await verify(),expected={principal:JSON.stringify(s.principal),isCurrent:()=>alive.current};
   let latest=await readCapabilityJournal(conversation,messageId,principal,AbortSignal.timeout(30_000));
   if(latest.version!==journal.version||latest.contractDigest!==journal.contractDigest||latest.state?.problemId!==journal.state?.problemId)throw Error('当前办理进展已变化，请重新读取。');
   const state=latest.state!,original=state.confirmedPlan;
   if(!original)throw Error('尚未保存已确认方案，请先读取原确认记录。');
   const source=await conversationRequest<CapabilityExecutionContract>('/'+encodeURIComponent(conversation)+'/sources/'+encodeURIComponent(messageId)+'/execution-contract');
   if(source.contractDigest!==journal.contractDigest||source.contract.conversationId!==conversation||source.contract.sourceMessageId!==messageId)throw Error('资源与原会话目标未能核对。');
   const employees=source.contract.bindings.filter(b=>b.kind==='EMPLOYEE');
   if(employees.length!==1)throw Error('当前能力没有唯一的固定数字人，停止资源准备。');
   const employee=employees[0].reference,path='planning-v2/'+encodeURIComponent(original.id),reference={capabilityConversationId:conversation,capabilityMessageId:messageId,capabilityContractDigest:journal.contractDigest};
   const history=await planningRequest<History>(path+'/history',undefined,{},expected);
   const approved=history.plans.find(p=>p.plan.version===original.version&&p.plan.plan_id===original.id&&p.digest===original.digest);
   if(!approved||approved.plan.semantics.target.problem.resource_id!==state.problemId)throw Error('已确认方案未能从原记录核实。');
   async function save(phase:string,extra:Partial<NonNullable<CapabilityJournal['state']>>={}){
    const auth=await verify();await conversationRequest(capabilityJournalPath(conversation,messageId),auth.csrfToken,{expectedVersion:latest.version,idempotencyKey:'capability:'+journal.contractDigest+':journal:'+latest.version,contractDigest:journal.contractDigest,state:{...latest.state,phase,...extra}});
    latest=await readCapabilityJournal(conversation,messageId,principal,AbortSignal.timeout(30_000));
    if(latest.contractDigest!==journal.contractDigest||latest.state?.problemId!==state.problemId||latest.state.phase!==phase)throw Error('资源准备进展尚未核实，请读取原记录。');onRefresh();
   }
   const selectionKey='capability-select:'+original.digest;
   setStatus('正在核对本次固定数字人与资料');
   if(state.phase==='PLAN_CONFIRMED'){
    await save('RESOURCE_SELECTING');
    await planningRequest(path+'/resource-selection',{version:original.version,digest:original.digest,expectedProposalRevision:approved.plan.source_proposal_revision,employee,idempotencyKey:selectionKey,...reference},{},expected);
   }
   const selection=await planningRequest<Selection>(path+'/resource-selection?'+new URLSearchParams({version:String(original.version),key:selectionKey,...reference}),undefined,{},expected);
   if(selection.executionStarted!==false||stable(selection.preflight.employeeReference)!==stable(employee)||selection.capabilitySource.conversationId!==conversation||selection.capabilitySource.sourceMessageId!==messageId||selection.capabilitySource.contractDigest!==journal.contractDigest||selection.confirmation.plan.plan_id!==original.id||stable(selection.confirmation.plan.semantics.target)!==stable(approved.plan.semantics.target))throw Error('资源选择结果与本次固定能力不一致，停止准备。');
   const selected=selection.confirmation,selectedPlan={id:selected.plan.plan_id,version:selected.plan.version,digest:selected.digest};
   if(latest.state?.selectedPlan&&stable(latest.state.selectedPlan)!==stable(selectedPlan))throw Error('已保存的资源方案发生变化，停止准备。');
   if(latest.state?.phase==='RESOURCE_SELECTING')await save('RESOURCES_SELECTED',{selectedPlan});
   const key='capability-resources:'+selected.digest;
   if(latest.state?.phase==='RESOURCES_SELECTED'){
    setStatus('正在检查固定资源的可用性');await save('RESOURCES_PREPARING');
    await planningRequest(path+'/resource-preparation',{version:selected.plan.version,idempotencyKey:key},{},expected);
   }
   const prepared=await planningRequest<ResourcePreparation>(path+'/resource-preparation?'+new URLSearchParams({version:String(selected.plan.version),key}),undefined,{},expected);
   if(prepared.planId!==selected.plan.plan_id||prepared.planVersion!==selected.plan.version||prepared.planDigest!==selected.digest||prepared.requestKey!==key||prepared.executionStarted!==false||stable(prepared.assembly.definition)!==stable(employee))throw Error('资源准备结果尚未核实，不会启动执行。');
   const resources=prepared.resources.map(r=>({kind:r.kind==='runtime'?'RUNTIME_PROFILE':r.kind.toUpperCase(),reference:r.reference}));
   const bindings=source.contract.bindings;
   if(bindings.some(b=>b.kind!=='EMPLOYEE'&&!resources.some(r=>r.kind===b.kind&&stable(r.reference)===stable(b.reference)))||resources.some(r=>['SKILL','MCP','KNOWLEDGE'].includes(r.kind)&&!bindings.some(b=>b.kind===r.kind&&stable(b.reference)===stable(r.reference))))throw Error('准备后的资源不符合本次固定范围。');
   if(prepared.state!=='READY')throw Error('固定资源尚未全部就绪，已保留检查记录，不会启动执行。');
   if(latest.state?.phase!=='RESOURCES_READY')await save('RESOURCES_READY',{selectedPlan,resourcePreparationKey:key});
   await verify();setReady(prepared);
  }catch(cause){onStop?.();if(alive.current)setError(cause instanceof Error&&/[\u4e00-\u9fff]/.test(cause.message)?cause.message:'资源准备状态尚未核实，请读取原记录，不会自动重新提交。')}
  finally{flight.current=false;if(alive.current){setBusy(false);setStatus('')}}
 }
 useCapabilityAdvance(autoContinue&&journal.state?.phase==='PLAN_CONFIRMED',JSON.stringify([principal,conversation,messageId,journal.contractDigest,'PLAN_CONFIRMED']),()=>act());
 const phase=journal.state?.phase;
 if(!['PLAN_CONFIRMED','RESOURCE_SELECTING','RESOURCES_SELECTED','RESOURCES_PREPARING','RESOURCES_READY'].includes(phase??''))return null;
 return <section aria-label="本次固定资源准备"><button type="button" disabled={busy} onClick={()=>void act()}>{busy?'正在准备固定资源…':phase==='PLAN_CONFIRMED'?'继续准备资源':phase==='RESOURCES_READY'?'读取资源准备记录':'核实并继续准备资源'}</button>{busy&&<p role="status">{status}</p>}{error&&<p role="alert">{error}</p>}{ready&&<div><p>本次固定资源已就绪，尚未启动执行。</p><ul>{ready.resources.map(r=><li key={r.kind+':'+r.reference.resource_id}>{r.name??r.kind}：已核验</li>)}</ul></div>}</section>;
}
