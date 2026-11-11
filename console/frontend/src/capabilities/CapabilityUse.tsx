import {prepareCapabilityWork} from './prepareCapabilityWork';
import {useEffect,useRef,useState,type FormEvent} from 'react';
import {useNavigate} from 'react-router-dom';
import {capabilitySession,readCapability,type CapabilityDetail,type CapabilityExecutionContract} from '../api/businessCapabilities';
import {workbenchPrincipalKey} from '../api/digitalEmployees';
import {conversationRequest,type PrivateConversation} from '../api/privateConversation';
import type {CapabilityConversationSource} from '../api/conversationActions';

export function CapabilityUse({detail,principal,conversation,onCancel}:{detail:CapabilityDetail;principal:string;conversation:string|null;onCancel:()=>void}){
 const navigate=useNavigate(),[objective,setObjective]=useState(detail.revision.intent),[notes,setNotes]=useState(''),[checked,setChecked]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [key]=useState(()=>crypto.randomUUID());const pending=useRef(false),submitted=useRef<{conversation:string;body:{idempotencyKey:string;expectedVersion:number;source:CapabilityConversationSource}}|null>(null);
 const [locked,setLocked]=useState(false),alive=useRef(true),controller=useRef<AbortController|null>(null);
 useEffect(()=>{alive.current=true;controller.current=new AbortController();return()=>{alive.current=false;controller.current?.abort()}},[]);
 async function prepare(event:FormEvent){
  event.preventDefault();if(pending.current)return;
  if(!objective.trim()||!notes.trim()){setChecked(false);setError('请填写本次目标与资料范围，不能只输入空格。');return}
  pending.current=true;setBusy(true);setError('');
  try{
   const signal=AbortSignal.any([controller.current?.signal??new AbortController().signal,AbortSignal.timeout(30_000)]),session=await capabilitySession(signal);
   if(workbenchPrincipalKey(session)!==principal)throw Error('登录身份已变化，请返回详情重新读取。');
   const current=await readCapability(detail.revision.capability_id,detail.revision.revision_id,principal,signal);
   if(current.digest!==detail.digest||current.state!=='PUBLISHED')throw Error('所选发布版本未能核对，请重新读取。');
   if(!alive.current)return;setLocked(true);
   if(!submitted.current){
    const id=conversation??(await conversationRequest<{conversation_id:string}>('',session.csrfToken,{idempotencyKey:'capability-conversation:'+key,title:detail.revision.title},signal)).conversation_id;
    const data=await conversationRequest<PrivateConversation>('/'+id,undefined,undefined,signal);
    submitted.current={conversation:id,body:{idempotencyKey:'capability-source:'+key,expectedVersion:data.conversation.version,source:{kind:'CAPABILITY',target:{capabilityId:detail.revision.capability_id,revisionId:detail.revision.revision_id,digest:detail.digest,objective:objective.trim(),inputNotes:notes.trim()}}}};
   }
   if(!alive.current)return;const command=submitted.current;
   await conversationRequest('/'+command.conversation+'/sources',session.csrfToken,command.body,signal);
   const saved=await conversationRequest<PrivateConversation>('/'+command.conversation,undefined,undefined,signal);
   const sourceMessage=saved.messages.find(message=>message.request_key===command.body.idempotencyKey&&message.facts?.readable!==false);
   if(!sourceMessage)throw Error('准备记录尚未读回，请沿用本次提交重试核实。');
   const checkedContract=await conversationRequest<CapabilityExecutionContract>('/'+command.conversation+'/sources/'+sourceMessage.message_id+'/execution-contract',undefined,undefined,signal),contract=checkedContract.contract,target=command.body.source.target;
   if(!contract||checkedContract.admissionState!=='NOT_ADMITTED'||checkedContract.executionAuthorized!==false||checkedContract.executionStarted!==false||!/^[a-f0-9]{64}$/.test(checkedContract.contractDigest)||contract.schemaVersion!=='capability-execution-constraints.v1'||contract.scope.tenantId!==session.principal.tenantId||contract.scope.securityDomain!==session.principal.securityDomain||contract.conversationId!==command.conversation||contract.sourceMessageId!==sourceMessage.message_id||contract.capability.resource_id!==target.capabilityId||contract.capability.revision_id!==target.revisionId||contract.capability.digest!==target.digest||contract.objective!==target.objective||contract.inputNotes!==target.inputNotes||JSON.stringify(contract.bindings)!==JSON.stringify(current.revision.bindings)||JSON.stringify(contract.acceptanceCriteria)!==JSON.stringify(current.revision.acceptance_criteria)||contract.exclusions!==current.revision.exclusions||contract.inputs!==current.revision.inputs||contract.outputs!==current.revision.outputs||contract.businessScope!==current.revision.business_scope||contract.manualInvolvement!==current.revision.manual_involvement||contract.knownLimitations!==current.revision.known_limitations)throw Error('准备记录已保存，但固定执行范围未能核对。请沿用本次记录重试核实，尚未启动执行。');
   await prepareCapabilityWork(checkedContract,command.body.source,principal,signal);
   const after=await capabilitySession(signal);if(workbenchPrincipalKey(after)!==principal)throw Error('登录身份已变化，请重新读取原会话。');
   if(!alive.current)return;navigate('/work?'+new URLSearchParams({conversation:command.conversation}));
  }catch(cause){if(alive.current)setError(cause instanceof Error&&/[\u4e00-\u9fff]/.test(cause.message)?cause.message:'准备尚未确认完成。请核对登录与资料范围后重试；将沿用同一次提交。')}
  finally{pending.current=false;if(alive.current)setBusy(false)}
 }
 return <section className="capability-panel" aria-label="能力本次输入"><h2>使用 {detail.revision.title}</h2><p>使用已发布的固定版本；维护草稿不会改变本次准备。</p><form onSubmit={checked?prepare:event=>{event.preventDefault();if(!objective.trim()||!notes.trim()){setError('请填写本次目标与资料范围，不能只输入空格。');return}setError('');setChecked(true)}}>
 <fieldset disabled={busy||locked}><legend>本次输入</legend><label>希望完成什么<textarea aria-label="希望完成什么" required maxLength={2000} value={objective} onChange={event=>{setObjective(event.target.value);setChecked(false)}}/></label><p>所需资料：{detail.revision.inputs}</p><label>已提供的资料与范围<textarea aria-label="已提供的资料与范围" required maxLength={6000} placeholder="说明本次资料、范围及仍缺少的信息" value={notes} onChange={event=>{setNotes(event.target.value);setChecked(false)}}/></label></fieldset>
 <details><summary>本次版本与固定分工</summary><ul>{detail.revision.bindings.map(binding=><li key={binding.kind+binding.reference.resource_id}>{detail.members?.find(member=>member.kind===binding.kind&&member.resourceId===binding.reference.resource_id&&member.revisionId===binding.reference.revision_id)?.name??binding.purpose} · {binding.purpose}</li>)}</ul><p>交付内容：{detail.revision.outputs}</p><p>人工参与：{detail.revision.manual_involvement}</p></details>
 {error&&<p role="alert">{error}</p>}{checked&&<div className="capability-notice"><h3>确认保存到{conversation?'原会话':'新会话'}</h3><p>目标与资料说明已填写，将保留本能力的固定版本和完成标准。将固定本次范围和完成标准，并返回会话继续准备方案、查看进度和结果。</p></div>}
 <div className="capability-actions"><button type="submit" disabled={busy}>{busy?'正在核实并保存…':checked?locked?'核实本次准备记录':'准备工作并进入会话':'检查输入并继续'}</button><button type="button" disabled={busy} onClick={onCancel}>返回能力</button></div></form></section>;
}
