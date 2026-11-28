import {readWorkbenchSession} from '../api/businessWorkspace';
export type OwnedSkillAccess={kind:'skill';identity:string;revisionId:string;digest:string};
export type OwnedSkillAccessDirectory={subject:string;scope:{tenantId:string;securityDomain:string};accessCandidates?:OwnedSkillAccess[]};
export function ownedSkillCandidate(value:unknown):value is OwnedSkillAccess{
 if(!value||typeof value!=='object')return false;
 const v=value as Record<string,unknown>;
 return v.kind==='skill'&&typeof v.identity==='string'&&v.identity.length>0&&typeof v.revisionId==='string'&&v.revisionId.length>0&&typeof v.digest==='string'&&/^[a-f0-9]{64}$/.test(v.digest);
}
export function ownedSkillIdentities(page:{subject:string;scope:{tenantId:string;securityDomain:string}}|null,directory:OwnedSkillAccessDirectory|null){
 if(!page||!directory||page.subject!==directory.subject||page.scope.tenantId!==directory.scope.tenantId||page.scope.securityDomain!==directory.scope.securityDomain)return new Set<string>();
 return new Set((Array.isArray(directory.accessCandidates)?directory.accessCandidates:[]).filter(ownedSkillCandidate).map(x=>x.identity));
}
export function skillMaintenanceHref(identity:string,search:string){
 const old=new URLSearchParams(search),next=new URLSearchParams({kind:'skill',managedResource:identity});
 const conversation=old.get('returnConversation');if(conversation)next.set('returnConversation',conversation);
 return '/skills?'+next;
}
export async function readOwnedSkillAccess(signal:AbortSignal){
 const before=await readWorkbenchSession(signal),response=await fetch('/api/workbench/v1/resource-management/skill',{credentials:'same-origin',signal,headers:{Accept:'application/json'}});
 if(!response.ok)throw Error('OWNED_SKILL_ACCESS_UNAVAILABLE');
 const body=await response.json(),after=await readWorkbenchSession(signal),directory=body?.result as OwnedSkillAccessDirectory|undefined;
 if(JSON.stringify(before.principal)!==JSON.stringify(after.principal)||!directory||directory.subject!==after.principal.principalId||directory.scope?.tenantId!==after.principal.tenantId||directory.scope?.securityDomain!==after.principal.securityDomain)throw Error('OWNED_SKILL_ACCESS_IDENTITY_CHANGED');
 return directory;
}
