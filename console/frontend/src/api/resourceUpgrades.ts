import {getWorkbenchSession,workbenchPrincipalKey} from './digitalEmployees';
export type UpgradeReference={resourceId:string;revisionId:string;digest:string};
export type UpgradeConsumer={original:UpgradeReference;successorRevisionId:string};
export type UpgradeSelection={oldSkill:UpgradeReference;newSkill:UpgradeReference;employees:UpgradeConsumer[];capabilities:UpgradeConsumer[]};
export type UpgradeCommand=UpgradeSelection & {commandId:string;reviewDigest:string;reason:string};
export type UpgradeMember={kind:string;resource_id:string;revision_id:string;digest:string};
export type UpgradeEmployee={definitionId:string;revisionId:string;role:string;responsibilities:string[];members:UpgradeMember[];responsibilityBindings?:{responsibility:string;member:UpgradeMember}[]};
export type UpgradeBinding={reference:Omit<UpgradeMember,'kind'>;purpose:string};
export type UpgradePreview={reviewDigest:string;preview:{employees:{before:UpgradeEmployee;after:UpgradeEmployee;aggregateVersion:number}[];capabilities:{capabilityId:string;bindingChanges:{kind:string;resourceId:string;before:UpgradeBinding|null;after:UpgradeBinding|null}[]}[]}};
export type UpgradeReceipt={schemaVersion:string;batchId:string;result:{resource:{identity:string;revisionId:string;digest:string};employees:unknown[];capabilities:unknown[]}};
export class UpgradeRequestError extends Error {readonly code:string;readonly unknownOutcome:boolean;constructor(code:string,unknownOutcome=false){super(code);this.code=code;this.unknownOutcome=unknownOutcome}}
export async function upgradeRequest<T>(action:'preview'|'submit'|'receipt',payload:UpgradeSelection|UpgradeCommand,principal:string):Promise<T>{
 const controller=new AbortController();const timeout=window.setTimeout(()=>controller.abort(),30_000);let sent=false;
 try{
  const session=await getWorkbenchSession(controller.signal);
  if(workbenchPrincipalKey(session)!==principal)throw new UpgradeRequestError('IDENTITY_CHANGED');
  sent=true;
  const response=await fetch('/api/workbench/v1/resource-upgrades/'+action,{method:'POST',credentials:'same-origin',signal:controller.signal,headers:{Accept:'application/json','Content-Type':'application/json','X-CSRF-Token':session.csrfToken},body:JSON.stringify(payload)});
  const body=await response.json().catch(()=>null);
  if(!response.ok)throw new UpgradeRequestError(body?.detail?.reasonCode??body?.reasonCode??'UPGRADE_UNAVAILABLE',action==='submit'&&(response.status>=500||response.status===408||!body));
  if(!body?.result)throw new UpgradeRequestError('UPGRADE_UNREADABLE',action==='submit');
  const after=await getWorkbenchSession(controller.signal);
  if(workbenchPrincipalKey(after)!==principal)throw new UpgradeRequestError('IDENTITY_CHANGED',action==='submit');
  return body.result as T;
 }catch(e){if(e instanceof UpgradeRequestError)throw e;throw new UpgradeRequestError('UPGRADE_CONNECTION_UNCONFIRMED',sent&&action==='submit')}
 finally{window.clearTimeout(timeout)}
}
export function verifiedReceipt(value:UpgradeReceipt,command:UpgradeCommand){
 if(value?.schemaVersion!=='selected-resource-upgrade-receipt.v1'||!value.batchId||value.result?.resource.identity!==command.newSkill.resourceId||value.result.resource.revisionId!==command.newSkill.revisionId||value.result.resource.digest!==command.newSkill.digest||value.result.employees?.length!==command.employees.length||value.result.capabilities?.length!==command.capabilities.length)throw new UpgradeRequestError('UPGRADE_RECEIPT_UNREADABLE',true);
 return value;
}
