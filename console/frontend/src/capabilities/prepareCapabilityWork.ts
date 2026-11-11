import {retainCapabilityPreparation} from './capabilityWorkJournal';
import {capabilitySession,type CapabilityExecutionContract} from '../api/businessCapabilities';
import {workbenchPrincipalKey} from '../api/digitalEmployees';
import {conversationRequest,type PrivateConversation} from '../api/privateConversation';
import type {BusinessProblemDetail,BusinessProblemRevision,CriterionRevision,CriteriaSetRevision} from '../api/businessWorkspace';
import type {CapabilityConversationSource,SourceReference} from '../api/conversationActions';

function ordered(value:unknown):unknown {return Array.isArray(value)?value.map(ordered):value&&typeof value==='object'?Object.fromEntries(Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([key,item])=>[key,ordered(item)])):value}
const same=(a:unknown,b:unknown)=>JSON.stringify(ordered(a))===JSON.stringify(ordered(b));

export async function prepareCapabilityWork(resolved:CapabilityExecutionContract,source:CapabilityConversationSource,principal:string,signal:AbortSignal){
 const {contract,contractDigest}=resolved,conversation=contract.conversationId;
 if(resolved.admissionState!=='NOT_ADMITTED'||resolved.executionStarted!==false||contract.schemaVersion!=='capability-execution-constraints.v1'||contract.capability.resource_id!==source.target.capabilityId||contract.capability.revision_id!==source.target.revisionId||contract.capability.digest!==source.target.digest||contract.objective!==source.target.objective||contract.inputNotes!==source.target.inputNotes)throw Error('保存来源与本次工作不一致，停止准备。');
 const key='capability:'+contractDigest,route='/'+encodeURIComponent(conversation);
 async function session(){const value=await capabilitySession(signal);if(workbenchPrincipalKey(value)!==principal)throw Error('登录身份已变化，已保存的准备保持不变。');return value}
 async function owner<T>(path:string,body?:object,headers:Record<string,string>={}):Promise<T>{
  const current=await session();
  const response=await fetch('/api/workbench/v1'+path,{method:body?'POST':'GET',signal,credentials:'same-origin',headers:{Accept:'application/json',...(body?{'Content-Type':'application/json','X-CSRF-Token':current.csrfToken}:{}),...headers},...(body?{body:JSON.stringify(body)}:{})});
  const value=await response.json();if(!response.ok)throw Error('本次工作准备尚未完成：'+(value.reasonCode??response.status)+'。原记录已保留，请核实后继续。');
  await session();return value.result;
 }
 const current=await session(),input=resolved.workInput;
 if(!input||input.problem.description!==contract.objective||input.problem.title!==contract.objective.slice(0,200)||!same(input.criterion.applicability.capabilityConstraints,contract)||input.criterion.applicability.capabilityContractDigest!==contractDigest||input.criterion.measurement.rubric!==contract.acceptanceCriteria.join('\n'))throw Error('本次目标与完成标准未能核对，尚未创建工作。');
 const payload={...input.problem,ownerId:current.principal.principalId,idempotencyKey:key+':problem'};
 const saved=await conversationRequest<PrivateConversation>(route,undefined,undefined,signal);
 const intents=saved.messages.filter(m=>m.kind==='ACTION_INTENT'&&m.facts?.readable!==false&&m.facts?.action==='CREATE_PROBLEM'&&m.facts?.messageId===contract.sourceMessageId);
 if(intents.length>1)throw Error('本次准备存在多条创建记录，请先在原会话核验，不能再次创建。');
 let intentId=intents[0]?.facts?.intentId,claimed=intents[0]?.facts?.attemptState==='UNKNOWN';
 if(!intentId){
  const auth=await session();const intent=await conversationRequest<{intentId:string;claimed:boolean}>(route+'/intents',auth.csrfToken,{idempotencyKey:key+':intent',expectedVersion:saved.conversation.version,messageId:contract.sourceMessageId,action:'CREATE_PROBLEM',payload,source,expectedOwnerVersion:0,confirmed:true},signal);intentId=intent.intentId;claimed=intent.claimed;
 }
 let problem:BusinessProblemRevision;
 if(claimed){
  const receipt=await conversationRequest<{state:string;source?:SourceReference}>(route+'/intents/'+encodeURIComponent(intentId),undefined,undefined,signal);
  if(receipt.state!=='SUCCEEDED'||receipt.source?.kind!=='PROBLEM')throw Error('原创建动作已提交，结果仍待核验；不会重复创建。请在原会话核验回执。');
  const target=receipt.source.target,detail=await owner<BusinessProblemDetail>('/problems/'+encodeURIComponent(target.problemId));
  const revision=detail.revisions.find(r=>r.revision_id===target.revisionId&&r.digest===target.problemDigest);
  if(!revision)throw Error('原创建结果的固定版本未能核对。');problem=revision;
 }else{
  if(intents[0]&&intents[0].facts?.ownerRequestKey!==payload.idempotencyKey)throw Error('已有创建记录的请求不一致，请在原会话核验。');
  problem=(await owner<{revision:BusinessProblemRevision}>('/problems',payload,{'X-Conversation-ID':conversation,'X-Conversation-Intent':intentId})).revision;
 }
 if(problem.description!==input.problem.description||problem.title!==input.problem.title)throw Error('已创建目标与本次准备不一致，停止后续准备。');
 const problemPath='/problems/'+encodeURIComponent(problem.business_problem_id);
 let detail=await owner<BusinessProblemDetail>(problemPath);
 if(detail.problem.current_revision_id!==problem.revision_id)throw Error('业务目标已被修改，请重新核对后继续。');
 const matches=(criterion:CriterionRevision)=>same(criterion.applicability,input.criterion.applicability)&&same(criterion.measurement,input.criterion.measurement)&&criterion.criterion_type===input.criterion.criterionType&&criterion.evaluator_type===input.criterion.evaluatorType&&criterion.evaluator_version===input.criterion.evaluatorVersion;
 const sets=await owner<{revisions:CriteriaSetRevision[]}>(problemPath+'/criteria-sets'),existing=await owner<{revisions:CriterionRevision[]}>(problemPath+'/criteria');
 const latest=sets.revisions.at(-1);
 if(latest&&(latest.problem_revision_id!==problem.revision_id||latest.ordered_criterion_revision_ids.length!==1))throw Error('本次工作已有不同的完成标准，请先核验。');
 let criterion=latest?existing.revisions.find(c=>c.revision_id===latest.ordered_criterion_revision_ids[0]):undefined;
 if(latest&&(!criterion||!matches(criterion)))throw Error('本次工作已有不同的完成标准，请先核验。');
 if(!latest){
  const candidates=existing.revisions.filter(matches);
  if(candidates.length>1)throw Error('已保存多条本次完成标准，请先核验，不能重复准备。');
  criterion=candidates[0];
 }
 if(!criterion)criterion=(await owner<{revision:CriterionRevision}>('/success-criteria',{...input.criterion,problemId:problem.business_problem_id,idempotencyKey:key+':criterion'})).revision;
 if(!matches(criterion))throw Error('保存的完成标准未能核对。');
 if(!latest)await owner(problemPath+'/criteria-sets',{problemRevisionId:problem.revision_id,orderedCriterionRevisionIds:[criterion.revision_id],expectedVersion:detail.problem.aggregate_version,idempotencyKey:key+':criteria-set'});
 detail=await owner<BusinessProblemDetail>(problemPath);
 const confirmedSets=await owner<{revisions:CriteriaSetRevision[]}>(problemPath+'/criteria-sets'),confirmedSet=confirmedSets.revisions.at(-1);
 if(detail.problem.current_revision_id!==problem.revision_id||!confirmedSet||confirmedSet.problem_revision_id!==problem.revision_id||confirmedSet.ordered_criterion_revision_ids.length!==1||confirmedSet.ordered_criterion_revision_ids[0]!==criterion.revision_id)throw Error('目标或完成标准在准备期间发生变化，已停止后续操作，请核验。');
 if(detail.problem.current_state==='DRAFT')await owner(problemPath+'/lifecycle',{toState:'ACTIVE',expectedVersion:detail.problem.aggregate_version,idempotencyKey:key+':activate'});
 else if(detail.problem.current_state!=='ACTIVE')throw Error('本次工作已进入其他阶段，请读取原会话进展。');
 await retainCapabilityPreparation(resolved,{problemId:problem.business_problem_id,criterionRevisionId:criterion.revision_id},principal,signal);
 return {problemId:problem.business_problem_id,criterionRevisionId:criterion.revision_id,executionStarted:false as const};
}
