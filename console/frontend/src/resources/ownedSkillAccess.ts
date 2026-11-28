import {readWorkbenchSession} from '../api/businessWorkspace';
export type OwnedResourceKind='skill'|'mcp';
export type OwnedResourceAccess={kind:OwnedResourceKind;identity:string;revisionId:string;digest:string};
export type OwnedResourceAccessDirectory={subject:string;scope:{tenantId:string;securityDomain:string};accessCandidates?:OwnedResourceAccess[]};
export type OwnedSkillAccess=OwnedResourceAccess&{kind:'skill'};
export type OwnedSkillAccessDirectory=Omit<OwnedResourceAccessDirectory,'accessCandidates'>&{accessCandidates?:OwnedSkillAccess[]};
export function ownedResourceCandidate(value:unknown):value is OwnedResourceAccess{
 if(!value||typeof value!=='object')return false;
 const v=value as Record<string,unknown>;
 return (v.kind==='skill'||v.kind==='mcp')&&typeof v.identity==='string'&&v.identity.length>0&&typeof v.revisionId==='string'&&v.revisionId.length>0&&typeof v.digest==='string'&&/^[a-f0-9]{64}$/.test(v.digest);
}
export function ownedSkillCandidate(value:unknown):value is OwnedSkillAccess{return ownedResourceCandidate(value)&&value.kind==='skill'}
export function ownedResourceIdentities(page:{subject:string;scope:{tenantId:string;securityDomain:string}}|null,directory:OwnedResourceAccessDirectory|null,kind:OwnedResourceKind){
 if(!page||!directory||page.subject!==directory.subject||page.scope.tenantId!==directory.scope.tenantId||page.scope.securityDomain!==directory.scope.securityDomain)return new Set<string>();
 return new Set((Array.isArray(directory.accessCandidates)?directory.accessCandidates:[]).filter(ownedResourceCandidate).filter(x=>x.kind===kind).map(x=>x.identity));
}
export function ownedSkillIdentities(page:Parameters<typeof ownedResourceIdentities>[0],directory:OwnedResourceAccessDirectory|null){return ownedResourceIdentities(page,directory,'skill')}
export function resourceMaintenanceHref(kind:OwnedResourceKind,identity:string,search:string){
 const old=new URLSearchParams(search),next=new URLSearchParams({kind,managedResource:identity});
 const conversation=old.get('returnConversation');if(conversation)next.set('returnConversation',conversation);
 return (kind==='skill'?'/skills':'/mcp')+'?'+next;
}
export function skillMaintenanceHref(identity:string,search:string){return resourceMaintenanceHref('skill',identity,search)}
export async function readOwnedResourceAccess(kind:OwnedResourceKind,signal:AbortSignal){
 const before=await readWorkbenchSession(signal),response=await fetch('/api/workbench/v1/resource-management/'+kind,{credentials:'same-origin',signal,headers:{Accept:'application/json'}});
 if(!response.ok)throw Error(kind==='skill'?'OWNED_SKILL_ACCESS_UNAVAILABLE':'OWNED_MCP_ACCESS_UNAVAILABLE');
 const body=await response.json(),after=await readWorkbenchSession(signal),directory=body?.result as OwnedResourceAccessDirectory|undefined;
 if(JSON.stringify(before.principal)!==JSON.stringify(after.principal)||!directory||directory.subject!==after.principal.principalId||directory.scope?.tenantId!==after.principal.tenantId||directory.scope?.securityDomain!==after.principal.securityDomain)throw Error(kind==='skill'?'OWNED_SKILL_ACCESS_IDENTITY_CHANGED':'OWNED_MCP_ACCESS_IDENTITY_CHANGED');
 return directory;
}
export function readOwnedSkillAccess(signal:AbortSignal){return readOwnedResourceAccess('skill',signal)}
