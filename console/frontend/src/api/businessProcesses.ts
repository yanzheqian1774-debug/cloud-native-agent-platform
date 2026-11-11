import {getWorkbenchSession, workbenchPrincipalKey} from './digitalEmployees';

export type BusinessArchitecture = {
  domains: {domain_id:string; name:string; band:'MANAGEMENT'|'CORE'|'SUPPORT'}[];
  groups: {group_id:string; domain_id:string; name:string}[];
};
export type FixedBusinessReference={resource_id:string;revision_id:string;digest:string};
export type BusinessActivity = {
  employee?:FixedBusinessReference|null;
  activity_id:string; name:string; responsible_role:string|null; inputs:string[];
  outputs:string[]; completion_conditions:string[]; human_boundary:string|null;
};
export type BusinessProcessContent = {
  source_materials?:FixedBusinessReference[];
  name:string; business_code:string|null; domain_id:string; group_id:string;
  owner_description:string|null; purpose:string|null; improvement_notes:string|null;
  activities:BusinessActivity[];
  handoffs:{handoff_id?:string|null;from_activity_id:string;to_activity_id:string;event:'COMPLETED'|'RETURNED'|'NEEDS_INFORMATION';explanation:string;responsible_role:string|null}[];
};
export type BusinessReferenceDetails={items:{kind:'knowledge'|'employee';reference:FixedBusinessReference;status:'AVAILABLE'|'UNAVAILABLE';name?:string}[];executionAuthorized:false};
export type BusinessProcessRecord<T> = {
  referenceDetails?:BusinessReferenceDetails;
  objectId:string; revisionId:string|null; digest?:string; aggregateVersion:number;
  publicationState?:BusinessProcessPublicationState;
  architecture?:BusinessProcessRecord<BusinessArchitecture>;
  definitionValidation?:{status:'COMPLETE'|'INCOMPLETE';issues:{code:string;path:string;message:string}[];executionAuthorized:false};
  record:{content:T; architectureReference?:{revisionId:string;digest:string}};
};
export type BusinessProcessItem = {processId:string;revisionId:string;name:string;domainId:string;groupId:string;ownerDescription:string|null;state:'DRAFT'|'PUBLISHED';hasPublishedVersion?:boolean;aggregateVersion:number};
export class BusinessProcessRequestError extends Error {
  readonly code:string; readonly status:number; readonly outcomeUnknown:boolean;
  constructor(code:string,status:number,outcomeUnknown=false){super(code);this.code=code;this.status=status;this.outcomeUnknown=outcomeUnknown}
}
const root='/api/workbench/v1/business-processes';
// Reads have a deadline and verify the identity before and after the request.
// No mutation or automatic retry is performed by this client.
async function read<T>(path:string,principal:string,signal:AbortSignal):Promise<T>{
  const bounded=AbortSignal.any([signal,AbortSignal.timeout(30_000)]);
  try{
    const session=await getWorkbenchSession(bounded);
    if(workbenchPrincipalKey(session)!==principal)throw new BusinessProcessRequestError('IDENTITY_CHANGED',409);
    const response=await fetch(path,{credentials:'same-origin',signal:bounded,headers:{Accept:'application/json'}});
    const body=await response.json().catch(()=>null);
    if(response.status===401)window.dispatchEvent(new Event('workbench-session-expired'));
    if(!response.ok)throw new BusinessProcessRequestError(body?.reasonCode??'UNAVAILABLE',response.status);
    if(body?.schemaVersion!=='workbench-operation.v1'||!body.result)throw new BusinessProcessRequestError('INVALID_RESPONSE',503);
    const after=await getWorkbenchSession(bounded);
    if(workbenchPrincipalKey(after)!==principal)throw new BusinessProcessRequestError('IDENTITY_CHANGED',409);
    return body.result as T;
  }catch(error){
    if(error instanceof BusinessProcessRequestError)throw error;
    throw new BusinessProcessRequestError(bounded.aborted?'READ_TIMEOUT':'NETWORK_UNAVAILABLE',503);
  }
}
export const readBusinessArchitecture=(principal:string,signal:AbortSignal,revision='')=>read<BusinessProcessRecord<BusinessArchitecture>>(root+'/architecture'+(revision?'?'+new URLSearchParams({revision}):''),principal,signal);
export const readBusinessProcess=(id:string,revision:string,principal:string,signal:AbortSignal)=>read<BusinessProcessRecord<BusinessProcessContent>>(root+'/'+encodeURIComponent(id)+'?'+new URLSearchParams({revision}),principal,signal);
export const listBusinessProcesses=(principal:string,signal:AbortSignal,filters:{query:string;domainId:string;groupId:string;cursor:string})=>read<{items:BusinessProcessItem[];nextCursor:string|null}>(root+'?'+new URLSearchParams({pageSize:'25',...filters}),principal,signal);

export type BusinessProcessCommand = {kind:'ARCHITECTURE'|'PROCESS';objectId:string;expectedVersion:number;commandId:string;content:BusinessArchitecture|BusinessProcessContent};
export type BusinessProcessReceipt = {objectId:string;revisionId:string;digest:string;aggregateVersion:number;state:'DRAFT';executionAuthorized:false};
export const readBusinessProcessReceipt=(commandId:string,principal:string,signal:AbortSignal)=>read<BusinessProcessReceipt>(root+'/commands/'+encodeURIComponent(commandId),principal,signal);
async function writeBusinessProcess<T>(path:string,command:unknown,principal:string,signal:AbortSignal):Promise<T>{
  const bounded=AbortSignal.any([signal,AbortSignal.timeout(30_000)]);let sent=false;
  try{
    const session=await getWorkbenchSession(bounded);
    if(workbenchPrincipalKey(session)!==principal)throw new BusinessProcessRequestError('IDENTITY_CHANGED',409);
    sent=true;
    const response=await fetch(path,{method:'POST',credentials:'same-origin',signal:bounded,headers:{Accept:'application/json','Content-Type':'application/json','X-CSRF-Token':session.csrfToken},body:JSON.stringify(command)});
    const body=await response.json().catch(()=>null);
    if(response.status===401)window.dispatchEvent(new Event('workbench-session-expired'));
    if(!response.ok)throw new BusinessProcessRequestError(body?.reasonCode??'UNAVAILABLE',response.status,response.status>=500);
    if(body?.schemaVersion!=='workbench-operation.v1'||!body.result)throw new BusinessProcessRequestError('INVALID_RESPONSE',503,true);
    const after=await getWorkbenchSession(bounded);
    if(workbenchPrincipalKey(after)!==principal)throw new BusinessProcessRequestError('IDENTITY_CHANGED',409,true);
    return body.result as T;
  }catch(error){
    if(error instanceof BusinessProcessRequestError)throw error;
    throw new BusinessProcessRequestError(bounded.aborted?'WRITE_TIMEOUT':'NETWORK_UNAVAILABLE',503,sent);
  }
}

export const checkBusinessProcessEditorAccess=(kind:'ARCHITECTURE'|'PROCESS',objectId:string,action:'CREATE'|'REVISE'|'PUBLISH',principal:string,signal:AbortSignal)=>read<{allowed:true;kind:string;objectId:string;action:string}>(root+'/editor-access?'+new URLSearchParams({kind,objectId,action}),principal,signal);

export const handoffIdentity=(item:BusinessProcessContent['handoffs'][number])=>item.handoff_id??JSON.stringify([item.from_activity_id,item.to_activity_id,item.event]);

export const saveBusinessProcess=(command:BusinessProcessCommand,principal:string,signal:AbortSignal)=>writeBusinessProcess<BusinessProcessReceipt>(root+'/commands',command,principal,signal);
export type BusinessProcessPublicationCommand={objectId:string;revisionId:string;digest:string;expectedVersion:number;commandId:string};
export type BusinessProcessPublicationReceipt={objectId:string;revisionId:string;digest:string;contentVersion:number;publicationVersion:number;state:'PUBLISHED';executionAuthorized:false};
export type BusinessProcessPublicationState={objectId:string;published:BusinessProcessPublicationReceipt|null;draft:{revisionId:string;digest:string;aggregateVersion:number}|null;currentStateAvailable:boolean;selectedState:'CURRENT_PUBLISHED'|'MODIFICATION_DRAFT'|'HISTORICAL_PUBLISHED'|'HISTORICAL_DRAFT'|'PUBLISHED_VERSION'|'DRAFT_VERSION';executionAuthorized:false};
export const publishBusinessProcess=(command:BusinessProcessPublicationCommand,principal:string,signal:AbortSignal)=>writeBusinessProcess<BusinessProcessPublicationReceipt>(root+'/publications',command,principal,signal);
export const readBusinessProcessPublicationReceipt=(commandId:string,principal:string,signal:AbortSignal)=>read<BusinessProcessPublicationReceipt>(root+'/publications/'+encodeURIComponent(commandId),principal,signal);

export type BusinessCapabilityRelation={relation_id:string;relation_revision_id:string;relation_type:'SUPPORTS_ACTIVITY'|'DERIVED_FROM_PROCESS';process:FixedBusinessReference;activity_ids:string[];capability:FixedBusinessReference;coverage_description:string};
export type BusinessRelationWithdrawal={relationId:string;relationRevisionId:string;relationVersion:number;digest:string;state:'WITHDRAWN';reason:string;recordedAt?:string;executionAuthorized:false};
export type BusinessRelationEntry={isCurrentRelationRevision?:boolean;withdrawal?:BusinessRelationWithdrawal|null;relationId:string;relationRevisionId:string;relationVersion:number;digest:string;record:BusinessCapabilityRelation;processName:string;capabilityTitle:string;activities:{activityId:string;name:string}[];actorId:string;recordedAt:string;executionAuthorized:false};
export type BusinessRelationPage={items:BusinessRelationEntry[];nextCursor:string|null;executionAuthorized:false};
export const listBusinessCapabilityRelations=(side:'PROCESS'|'CAPABILITY',reference:FixedBusinessReference,principal:string,signal:AbortSignal,cursor='')=>read<BusinessRelationPage>(root+'/capability-relations?'+new URLSearchParams({side,identity:reference.resource_id,revision:reference.revision_id,digest:reference.digest,pageSize:'25',...(cursor?{cursor}:{})}),principal,signal);

export type BusinessRelationCommand={relation:BusinessCapabilityRelation;expectedVersion:number;commandId:string};
export type BusinessRelationReceipt={relationId:string;relationRevisionId:string;relationVersion:number;digest:string;executionAuthorized:false};
export const saveBusinessCapabilityRelation=(command:BusinessRelationCommand,principal:string,signal:AbortSignal)=>writeBusinessProcess<BusinessRelationReceipt>(root+'/capability-relations',command,principal,signal);
export const readBusinessCapabilityRelationReceipt=(commandId:string,principal:string,signal:AbortSignal)=>read<BusinessRelationEntry>(root+'/capability-relations/commands/'+encodeURIComponent(commandId),principal,signal);
export type BusinessRelationWithdrawalCommand={relationId:string;relationRevisionId:string;expectedVersion:number;digest:string;reason:string;commandId:string};
export const withdrawBusinessCapabilityRelation=(command:BusinessRelationWithdrawalCommand,principal:string,signal:AbortSignal)=>writeBusinessProcess<BusinessRelationWithdrawal>(root+'/capability-relations/withdrawals',command,principal,signal);
export const readBusinessRelationWithdrawalReceipt=(commandId:string,principal:string,signal:AbortSignal)=>read<BusinessRelationWithdrawal>(root+'/capability-relations/withdrawals/'+encodeURIComponent(commandId),principal,signal);
