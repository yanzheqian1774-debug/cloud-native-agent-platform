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

export async function listWorkflowSkillOperations():Promise<WorkflowSkillOperationDirectory>{
  let response:Response;
  try{response=await fetch("/api/internal/v0.2.2/resources/skill",{headers:{Accept:"application/json"}})}catch{throw new WorkflowSkillOperationDirectoryError("SKILL_OPERATION_DIRECTORY_NETWORK_UNAVAILABLE",503)}
  const body:unknown=await response.json().catch(()=>null);
  if(!response.ok)throw new WorkflowSkillOperationDirectoryError(errorReason(body),response.status);
  if(!Array.isArray(body))throw new WorkflowSkillOperationDirectoryError("SKILL_OPERATION_DIRECTORY_INVALID",502);
  const entries:WorkflowSkillOperationEntry[]=[],names=new Set<string>();let rejectedResources=0;
  for(const resource of body){
    if(!object(resource)||resource.kind!=="skill"||!eligibleLifecycleStates.has(String(resource.lifecycleState))||resource.enabled!==true||resource.archived!==false||!text(resource.resourceId)||!text(resource.name)||!text(resource.publishedRevisionId)||!Array.isArray(resource.revisions)){rejectedResources+=1;continue}
    const revision=resource.revisions.find(item=>object(item)&&item.revisionId===resource.publishedRevisionId);
    if(!object(revision)||revision.state!=="PUBLISHED"||!text(revision.revisionId)||!text(revision.digest)||!revisionDigest.test(revision.digest)||!object(revision.content)||!Array.isArray(revision.content.operations)||revision.content.operations.length===0){rejectedResources+=1;continue}
    let valid=true;const parsed:WorkflowSkillOperation[]=[];
    for(const candidate of revision.content.operations){const item=operation(candidate);if(!item||names.has(`${resource.resourceId}:${revision.revisionId}:${revision.digest}:${item.name}`)){valid=false;break}parsed.push(item)}
    if(!valid){rejectedResources+=1;continue}
    for(const item of parsed){names.add(`${resource.resourceId}:${revision.revisionId}:${revision.digest}:${item.name}`);entries.push({skillName:resource.name,skillId:resource.resourceId,skillRevisionId:revision.revisionId,skillDigest:revision.digest,operation:item})}
  }
  return {entries,rejectedResources};
}
