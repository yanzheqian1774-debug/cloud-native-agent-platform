import type {ManagementActions} from '../../src/api/digitalEmployees';
type Principal={principalId:string;tenantId:string;securityDomain:string};
export function managementActions(principal:Principal,target:Record<string,string|number>|null,granted=true):ManagementActions{return {subjectId:principal.principalId,tenantId:principal.tenantId,securityDomain:principal.securityDomain,generation:1,recoveryEpoch:1,readAt:'2026-11-14T00:00:00Z',target,actions:Object.fromEntries(['CREATE','REVISE','SELECT_OWNER','VALIDATE','APPROVE','PUBLISH'].map(action=>[action,{authorized:granted,lifecycleEligible:true}])),authorityGranted:false,executionStarted:false}}
export function authoringActions<T>(value:T,principal:Principal):T{
 const data=value as Record<string,unknown>;if(!data||data.basis!=='OWNER_FACT_ORDER')return value;
 const target=(item:unknown)=>{const definition=item as Record<string,string|number>;return managementActions(principal,{employeeDefinitionId:definition.employeeDefinitionId,employeeDefinitionRevisionId:definition.employeeDefinitionRevisionId,employeeDefinitionDigest:definition.employeeDefinitionDigest,aggregateVersion:data.aggregateVersion as number})};
 const result={...data,maintenanceActions:target(data.parent)};
 for(const key of ['head','draft','publication']){const entry=data[key] as {status:string;definition:unknown};if(entry?.status==='AVAILABLE')Object.assign(result,{[key]:{...entry,maintenanceActions:target(entry.definition)}})}
 return result as T;
}
