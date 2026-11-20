import {getWorkbenchSession,workbenchPrincipalKey} from './digitalEmployees';
export type ExactReference={kind:"AGENT"|"SKILL"|"MCP"|"KNOWLEDGE"|"RUNTIME_PROFILE";resourceId:string;revisionId:string;digest?:string|null};
export type SkillOperationBinding={skillId:string;skillRevisionId:string;skillDigest:string;operation:string};
export type WorkflowTask={taskId:string;name:string;dependsOn:string[];inputs:string[];outputs:string[];capabilityRequirements:string[];references:ExactReference[];skillOperationBindings?:SkillOperationBinding[]|null;retryLimit:number;timeoutSeconds:number;failurePolicy:"FAIL_WORKFLOW"|"SKIP_DEPENDENTS"};
export const hasSkillOperationBindings=(task:WorkflowTask)=>Boolean(task.skillOperationBindings?.length);
export const referenceSupportsBinding=(task:WorkflowTask,binding:SkillOperationBinding)=>task.references.some(reference=>reference.kind==="SKILL"&&reference.resourceId===binding.skillId&&reference.revisionId===binding.skillRevisionId&&reference.digest===binding.skillDigest);
export type WorkflowContent={description:string;tasks:WorkflowTask[];inputs:string[];outputs:string[];runtimeProfile:ExactReference};
export type WorkflowRevision={revisionId:string;predecessorRevisionId:string|null;state:string;digest:string;content:WorkflowContent;createdAt:string;publicationBasis?:WorkflowPolicyReview};
export type WorkflowDefinition={workflowDefinitionId:string;name:string;aggregateVersion:number;lifecycleState:string;currentDraftRevisionId:string|null;publishedRevisionId:string|null;revisions:WorkflowRevision[];reviews:Array<{reviewId:string;digest:string}>;relationships:unknown[];consumers:unknown[]};
export type WorkflowPolicyReview={schemaVersion:'workflow-policy-review.v1';reviewId:string;revisionId:string;digest:string;actor:string;reviewedAt:string;policyBasis:{type:'DEVELOPMENT_ADMINISTRATOR';issuer:string;authorityGeneration:number;commandDigest:string}};
export type WorkflowProjection={definition:WorkflowDefinition;productProjection:Record<string,unknown>;technicalProjection:Record<string,unknown>;policyPublicationAvailable?:boolean};
export class WorkflowDefinitionRequestError extends Error{reasonCode:string;status:number;constructor(reasonCode:string,status:number){super(reasonCode);this.reasonCode=reasonCode;this.status=status}}
export type WorkflowControlledState="validation error"|"denied"|"not found"|"conflict"|"stale"|"backend unavailable"|"partial"|"retryable"|"recovery required"|"unsupported";
export const workflowControlledState=(error:WorkflowDefinitionRequestError):WorkflowControlledState=>error.status===403?"denied":error.status===404?"not found":error.status===409?(error.reasonCode.includes("STALE")?"stale":"conflict"):error.status===422?"validation error":error.status===501?"unsupported":error.status>=500?"backend unavailable":"retryable";
const object=(value:unknown):value is Record<string,unknown>=>Boolean(value)&&typeof value==="object"&&!Array.isArray(value);
const errorReason=(body:unknown)=>{if(!object(body))return "WORKFLOW_DEFINITION_UNAVAILABLE";const detail=body.detail;if(object(detail)&&typeof detail.reasonCode==="string")return detail.reasonCode;if(Array.isArray(detail)){const reason=detail.find(item=>object(item)&&typeof item.reasonCode==="string");if(object(reason)&&typeof reason.reasonCode==="string")return reason.reasonCode}return "WORKFLOW_DEFINITION_UNAVAILABLE"};
async function request<T>(path:string,init?:RequestInit):Promise<T>{let response:Response;try{response=await fetch(path,{...init,headers:{Accept:"application/json","Content-Type":"application/json",...init?.headers}})}catch{throw new WorkflowDefinitionRequestError("WORKFLOW_DEFINITION_NETWORK_UNAVAILABLE",503)}const body:unknown=await response.json().catch(()=>null);if(!response.ok)throw new WorkflowDefinitionRequestError(errorReason(body),response.status);return body as T}
const root="/api/internal/v0.2.2/workflow-definitions";
export const trustedWorkflowAuthoring=import.meta.env.VITE_BUSINESS_CAPABILITIES_ENABLED==='true'&&import.meta.env.VITE_RESOURCE_DIRECTORY_ENABLED==='true';
export const listWorkflowDefinitions=async()=>{
 if(!trustedWorkflowAuthoring)return request<WorkflowProjection[]>(root);
 const value=await trustedRead<{items:{workflowDefinitionId:string}[]}>('/workflows');
 return Promise.all(value.items.map(item=>getWorkflowDefinition(item.workflowDefinitionId)));
};
export const getWorkflowDefinition=(id:string)=>trustedWorkflowAuthoring?trustedRead<WorkflowProjection>(`/workflows/${encodeURIComponent(id)}/authoring`):request<WorkflowProjection>(`${root}/${encodeURIComponent(id)}`);
export const createWorkflowDefinition=(name:string,content:WorkflowContent)=>trustedWorkflowAuthoring?submitWorkflowCommand({action:"create",name,content}):request<WorkflowProjection>(root,{method:"POST",body:JSON.stringify({name,content})});
export const editWorkflowDefinition=(definition:WorkflowDefinition,content:WorkflowContent)=>trustedWorkflowAuthoring?submitWorkflowCommand({action:"edit",workflowId:definition.workflowDefinitionId,expectedVersion:definition.aggregateVersion,content}):request<WorkflowProjection>(`${root}/${encodeURIComponent(definition.workflowDefinitionId)}/draft`,{method:"PUT",body:JSON.stringify({expectedVersion:definition.aggregateVersion,content})});
export const validateWorkflowDefinition=(id:string,expectedVersion:number)=>trustedWorkflowAuthoring?submitWorkflowCommand({action:"validate",workflowId:id,expectedVersion}):request<WorkflowProjection>(`${root}/${encodeURIComponent(id)}/validation`,{method:"POST",body:JSON.stringify({expectedVersion})});
export const reviewWorkflowDefinition=(id:string,expectedVersion:number,digest:string,reason:string)=>{if(!reason.trim())return Promise.reject(new WorkflowDefinitionRequestError("WORKFLOW_REVIEW_REASON_REQUIRED",400));return trustedWorkflowAuthoring?submitWorkflowCommand({action:"review",workflowId:id,expectedVersion,digest,reason:reason.trim()}):request<WorkflowProjection>(`${root}/${encodeURIComponent(id)}/reviews`,{method:"POST",body:JSON.stringify({expectedVersion,digest,decision:"APPROVE",reason:reason.trim()})})};
export const publishWorkflowDefinition=(id:string,expectedVersion:number,digest:string,reviewId:string)=>trustedWorkflowAuthoring?submitWorkflowCommand({action:"publish",workflowId:id,expectedVersion,digest,reviewId}):request<WorkflowProjection>(`${root}/${encodeURIComponent(id)}/publications`,{method:"POST",body:JSON.stringify({expectedVersion,digest,reviewId})});
export const publishWorkflowByPolicy=(id:string,expectedVersion:number,digest:string)=>{
 if(!trustedWorkflowAuthoring)return Promise.reject(new WorkflowDefinitionRequestError('WORKFLOW_POLICY_PUBLICATION_DISABLED',403));
 return submitWorkflowCommand({action:'policy-publish',workflowId:id,expectedVersion,digest});
};
export const successorWorkflowDefinition=(id:string,expectedVersion:number)=>trustedWorkflowAuthoring?submitWorkflowCommand({action:"successor",workflowId:id,expectedVersion}):request<WorkflowProjection>(`${root}/${encodeURIComponent(id)}/successors`,{method:"POST",body:JSON.stringify({expectedVersion})});
export const compareWorkflowRevisions=(id:string,left:string,right:string)=>trustedWorkflowAuthoring?trustedRead<Record<string,unknown>>(`/workflows/${encodeURIComponent(id)}/comparison?${new URLSearchParams({leftRevisionId:left,rightRevisionId:right})}`):request<Record<string,unknown>>(`${root}/${encodeURIComponent(id)}/comparison?${new URLSearchParams({leftRevisionId:left,rightRevisionId:right})}`);

type WorkflowCommand={action:'create'|'edit'|'validate'|'review'|'publish'|'successor'|'policy-publish';commandKey?:string;workflowId?:string;expectedVersion?:number;name?:string;content?:WorkflowContent;digest?:string;reason?:string;reviewId?:string};
type PendingWorkflowCommand={principal:string;command:WorkflowCommand};
const pendingKey='workflow-authoring-pending-v1';
const pendingCommand=():PendingWorkflowCommand|null=>{try{return JSON.parse(sessionStorage.getItem(pendingKey)??'null')}catch{throw new WorkflowDefinitionRequestError('WORKFLOW_PENDING_RECORD_UNREADABLE',409)}};
export const hasPendingWorkflowCommand=()=>trustedWorkflowAuthoring&&pendingCommand()!==null;
async function trustedRead<T>(path:string,expectedPrincipal?:string):Promise<T>{
 const signal=AbortSignal.timeout(30_000),before=await getWorkbenchSession(signal),principal=workbenchPrincipalKey(before);
 if(expectedPrincipal&&expectedPrincipal!==principal)throw new WorkflowDefinitionRequestError('WORKFLOW_IDENTITY_CHANGED',409);
 const response=await fetch('/api/workbench/v1'+path,{credentials:'same-origin',signal,headers:{Accept:'application/json'}}),body=await response.json().catch(()=>null);
 if(!response.ok)throw new WorkflowDefinitionRequestError(body?.reasonCode??'WORKFLOW_READ_UNAVAILABLE',response.status);
 if(body?.schemaVersion!=='workbench-operation.v1'||!body.result)throw new WorkflowDefinitionRequestError('WORKFLOW_RESPONSE_INVALID',503);
 if(workbenchPrincipalKey(await getWorkbenchSession(signal))!==principal)throw new WorkflowDefinitionRequestError('WORKFLOW_IDENTITY_CHANGED',409);
 return body.result as T;
}
export async function recoverWorkflowCommand():Promise<WorkflowProjection>{
 const pending=pendingCommand();if(!pending)throw new WorkflowDefinitionRequestError('WORKFLOW_PENDING_RECORD_NOT_FOUND',404);
 const command=pending.command;
 const receipt=await trustedRead<{commandKey:string;workflowId:string;action:string}>((command.action==='policy-publish'?'/workflows/policy-publications/':'/workflows/commands/')+encodeURIComponent(command.commandKey!)+ '?' +new URLSearchParams({...((command.action!=='policy-publish')?{action:command.action}:{}),...(command.workflowId?{workflowId:command.workflowId}:{})}),pending.principal);
 if(receipt.commandKey!==command.commandKey||receipt.action!==command.action||(command.workflowId&&receipt.workflowId!==command.workflowId))throw new WorkflowDefinitionRequestError('WORKFLOW_RECEIPT_MISMATCH',409);
 const result=await trustedRead<WorkflowProjection>('/workflows/'+encodeURIComponent(receipt.workflowId)+'/authoring',pending.principal);
 sessionStorage.removeItem(pendingKey);return result;
}
async function submitWorkflowCommand(input:WorkflowCommand):Promise<WorkflowProjection>{
 if(pendingCommand())throw new WorkflowDefinitionRequestError('WORKFLOW_COMMAND_RECOVERY_REQUIRED',409);
 const session=await getWorkbenchSession(AbortSignal.timeout(30_000)),principal=workbenchPrincipalKey(session),command={...input,commandKey:'workflow-command:'+crypto.randomUUID()};
 // Persist one immutable command before sending; recovery never creates a new key.
 sessionStorage.setItem(pendingKey,JSON.stringify({principal,command}));
 return dispatchWorkflowCommand({principal,command},false);
}
export async function retryOriginalWorkflowCommand():Promise<WorkflowProjection>{
 const pending=pendingCommand();if(!pending)throw new WorkflowDefinitionRequestError('WORKFLOW_PENDING_RECORD_NOT_FOUND',404);
 return dispatchWorkflowCommand(pending);
}
async function dispatchWorkflowCommand(pending:PendingWorkflowCommand,preserveUnknown=true):Promise<WorkflowProjection>{
 const signal=AbortSignal.timeout(30_000),session=await getWorkbenchSession(signal),{principal,command}=pending;
 if(workbenchPrincipalKey(session)!==principal)throw new WorkflowDefinitionRequestError('WORKFLOW_IDENTITY_CHANGED',409);
 try{
  const response=await fetch(command.action==='policy-publish'?'/api/workbench/v1/workflows/policy-publications':'/api/workbench/v1/workflows/commands',{method:'POST',credentials:'same-origin',signal,headers:{Accept:'application/json','Content-Type':'application/json','X-CSRF-Token':session.csrfToken},body:JSON.stringify(command)});
  const body=await response.json().catch(()=>null);
  if(!response.ok){
   if(!preserveUnknown&&response.status<500)sessionStorage.removeItem(pendingKey);

   throw new WorkflowDefinitionRequestError(body?.reasonCode??'WORKFLOW_COMMAND_UNAVAILABLE',response.status);
  }
  return await recoverWorkflowCommand();
 }catch(error){
  if(error instanceof WorkflowDefinitionRequestError)throw error;
  throw new WorkflowDefinitionRequestError('WORKFLOW_COMMAND_RECOVERY_REQUIRED',503);
 }
}
