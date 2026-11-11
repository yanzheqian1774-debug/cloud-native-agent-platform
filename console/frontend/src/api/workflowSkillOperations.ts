import {readWorkbenchSession} from './businessWorkspace';
import {listReadableResources} from './resourceDirectory';

export type WorkflowSkillOperation={
  name:string;
  inputSchema:Record<string,unknown>;
  outputSchema:Record<string,unknown>;
  sideEffectClass:"READ_ONLY";
  executorId:string;
  executorRevision:string;
  executorConfigurationDigest:string;
  sideEffectPolicy:{policyId:string;policyRevision:string;policyDigest:string};
  ioLimits:{policyId:string;policyRevision:string;maxInputBytes:number;maxOutputBytes:number;maxObjectDepth:number;maxProperties:number;timeoutMs:number};
};

export type WorkflowSkillOperationEntry={skillName:string;skillId:string;skillRevisionId:string;skillDigest:string;operation:WorkflowSkillOperation};
export type WorkflowSkillOperationDirectory={entries:WorkflowSkillOperationEntry[];rejectedResources:number};

export class WorkflowSkillOperationDirectoryError extends Error{
  reasonCode:string;
  status:number;
  constructor(reasonCode:string,status:number){super(reasonCode);this.reasonCode=reasonCode;this.status=status}
}

const revisionDigest=/^(?:sha256:)?[a-f0-9]{64}$/;
const bareDigest=/^[a-f0-9]{64}$/;
const eligibleLifecycleStates=new Set(["DRAFT","VALIDATED","HUMAN_REVIEWED","PUBLISHED"]);
const object=(value:unknown):value is Record<string,unknown>=>Boolean(value)&&typeof value==="object"&&!Array.isArray(value);
const text=(value:unknown):value is string=>typeof value==="string"&&value.length>0;
const identity=(value:unknown):value is string=>text(value)&&new TextEncoder().encode(value).length<=500;
const positiveInteger=(value:unknown):value is number=>typeof value==="number"&&Number.isInteger(value)&&value>0;
const errorReason=(body:unknown)=>{if(!object(body))return "SKILL_OPERATION_DIRECTORY_UNAVAILABLE";const detail=body.detail;if(object(detail)&&text(detail.reasonCode))return detail.reasonCode;if(Array.isArray(detail)){const reason=detail.find(item=>object(item)&&text(item.reasonCode));if(object(reason)&&text(reason.reasonCode))return reason.reasonCode}return "SKILL_OPERATION_DIRECTORY_UNAVAILABLE"};

function operation(value:unknown):WorkflowSkillOperation|null{
  if(!object(value)||Object.keys(value).sort().join(",")!==["executorConfigurationDigest","executorId","executorRevision","inputSchema","ioLimits","name","outputSchema","sideEffectClass","sideEffectPolicy"].sort().join(","))return null;
  if(!text(value.name)||!value.name.trim()||value.name.length>200||!object(value.inputSchema)||!object(value.outputSchema)||value.sideEffectClass!=="READ_ONLY"||!identity(value.executorId)||!identity(value.executorRevision)||!text(value.executorConfigurationDigest)||!bareDigest.test(value.executorConfigurationDigest)||!object(value.sideEffectPolicy)||!object(value.ioLimits))return null;
  const policy=value.sideEffectPolicy,limits=value.ioLimits;
  if(Object.keys(policy).sort().join(",")!==["policyDigest","policyId","policyRevision"].sort().join(",")||!identity(policy.policyId)||!identity(policy.policyRevision)||!text(policy.policyDigest)||!bareDigest.test(policy.policyDigest))return null;
  if(Object.keys(limits).sort().join(",")!==["maxInputBytes","maxObjectDepth","maxOutputBytes","maxProperties","policyId","policyRevision","timeoutMs"].sort().join(",")||!identity(limits.policyId)||!identity(limits.policyRevision)||![limits.maxInputBytes,limits.maxOutputBytes,limits.maxObjectDepth,limits.maxProperties,limits.timeoutMs].every(positiveInteger))return null;
  return value as WorkflowSkillOperation;
}

async function legacyResources():Promise<unknown[]>{
  let response:Response;
  try{response=await fetch("/api/internal/v0.2.2/resources/skill",{headers:{Accept:"application/json"}})}catch{throw new WorkflowSkillOperationDirectoryError("SKILL_OPERATION_DIRECTORY_NETWORK_UNAVAILABLE",503)}
  const body:unknown=await response.json().catch(()=>null);
  if(!response.ok)throw new WorkflowSkillOperationDirectoryError(errorReason(body),response.status);
  if(!Array.isArray(body))throw new WorkflowSkillOperationDirectoryError("SKILL_OPERATION_DIRECTORY_INVALID",502);
  return body;
}

async function trustedResources():Promise<unknown[]>{
  const signal=AbortSignal.timeout(30_000),before=await readWorkbenchSession(signal);
  const resources:unknown[]=[],seen=new Set<string>(),cursors=new Set<string>();let cursor:string|null=null;
  do{
    const page=await listReadableResources('skill','','PUBLISHED',cursor,signal,'workflow-skill-operations');
    if(!Array.isArray(page.items))throw new WorkflowSkillOperationDirectoryError('SKILL_OPERATION_DIRECTORY_INVALID',502);
    for(const item of page.items){
      if(item.kind!=='skill'||item.state!=='PUBLISHED'||!item.enabled||!item.isCurrentPublished){resources.push(null);continue}
      const key=JSON.stringify([item.identity,item.revisionId]),source=item.workflowOperations;
      if(seen.has(key)||!source||source.identity!==item.identity||source.revisionId!==item.revisionId||source.digest!==item.digest)throw new WorkflowSkillOperationDirectoryError('SKILL_OPERATION_DIRECTORY_INVALID',502);
      seen.add(key);
      resources.push({kind:'skill',resourceId:item.identity,name:item.name,lifecycleState:source.lifecycleState,enabled:source.enabled,archived:source.archived,publishedRevisionId:source.publishedRevisionId,revisions:[{revisionId:item.revisionId,digest:item.digest,state:item.state,content:{operations:source.operations}}]});
    }
    cursor=page.nextCursor;
    if(cursor){
      if(cursors.has(cursor)||cursors.size>=19)throw new WorkflowSkillOperationDirectoryError('SKILL_OPERATION_DIRECTORY_TOO_LARGE',503);
      cursors.add(cursor);
    }
  }while(cursor);
  const after=await readWorkbenchSession(signal);
  if(JSON.stringify(before.principal)!==JSON.stringify(after.principal))throw new WorkflowSkillOperationDirectoryError('SKILL_OPERATION_DIRECTORY_IDENTITY_CHANGED',409);
  return resources;
}

export async function listWorkflowSkillOperations():Promise<WorkflowSkillOperationDirectory>{
  const trusted=import.meta.env.VITE_BUSINESS_CAPABILITIES_ENABLED==='true'&&import.meta.env.VITE_RESOURCE_DIRECTORY_ENABLED==='true';
  let body:unknown[];
  try{body=await (trusted?trustedResources():legacyResources())}
  catch(error){if(error instanceof WorkflowSkillOperationDirectoryError)throw error;throw new WorkflowSkillOperationDirectoryError('SKILL_OPERATION_DIRECTORY_UNAVAILABLE',503)}
  const entries:WorkflowSkillOperationEntry[]=[],names=new Set<string>();let rejectedResources=0;
  for(const resource of body){
    if(!object(resource)||resource.kind!=="skill"||!eligibleLifecycleStates.has(String(resource.lifecycleState))||resource.enabled!==true||resource.archived!==false||!text(resource.resourceId)||!text(resource.name)||!text(resource.publishedRevisionId)||!Array.isArray(resource.revisions)){rejectedResources+=1;continue}
    const revision=resource.revisions.find(item=>object(item)&&item.revisionId===resource.publishedRevisionId);
    if(!object(revision)||revision.state!=="PUBLISHED"||!text(revision.revisionId)||!text(revision.digest)||!revisionDigest.test(revision.digest)||!object(revision.content)||!Array.isArray(revision.content.operations)||revision.content.operations.length===0){rejectedResources+=1;continue}
    let valid=true;const parsed:WorkflowSkillOperation[]=[],localNames=new Set<string>();
    for(const candidate of revision.content.operations){const item=operation(candidate);if(!item||localNames.has(item.name)||names.has(`${resource.resourceId}:${revision.revisionId}:${revision.digest}:${item.name}`)){valid=false;break}localNames.add(item.name);parsed.push(item)}
    if(!valid){rejectedResources+=1;continue}
    for(const item of parsed){names.add(`${resource.resourceId}:${revision.revisionId}:${revision.digest}:${item.name}`);entries.push({skillName:resource.name,skillId:resource.resourceId,skillRevisionId:revision.revisionId,skillDigest:revision.digest,operation:item})}
  }
  return {entries,rejectedResources};
}
