import {readWorkbenchSession,WorkbenchRequestError,type WorkbenchSession} from './businessWorkspace';
export type ModelIdentity={revision_id:string;digest:string;provider_id?:string;endpoint_id?:string;profile_id?:string};
export type ModelDirectoryItem={modelId:string;revisionId:string;digest:string;revision:number;name:string;capabilities:string[];compatibility:string[];invocationLimits:{name:string;value:number;unit:string}[];provider:ModelIdentity;endpoint:ModelIdentity;connectionProfile:ModelIdentity;createdAt:string;isCurrentRevision:boolean;state:string;lifecycleHighWater:{ordinal:number;fact_id:string;fact_digest:string}|null;availability:'NOT_MEASURABLE';price:'NOT_MEASURABLE'};
export type ModelDirectoryPage={subject:string;scope:{tenantId:string;securityDomain:string};basis:'CURRENT_EXACT_MODEL_READ';executionAuthority:'NONE';items?:ModelDirectoryItem[];item?:ModelDirectoryItem;nextCursor?:string|null};
const expiry=(s:WorkbenchSession)=>Math.min(Date.parse(s.session.expiresAt),Date.parse(s.session.idleExpiresAt));
export function modelLink(item:ModelDirectoryItem,params:URLSearchParams){const next=new URLSearchParams(params);next.set('model',item.modelId);next.set('revision',item.revisionId);next.set('digest',item.digest);return '/models?'+next}
const valid=(item:ModelDirectoryItem)=>!!item&&typeof item.modelId==='string'&&!!item.modelId&&typeof item.revisionId==='string'&&!!item.revisionId&&/^[a-f0-9]{64}$/.test(item.digest)&&typeof item.name==='string'&&Array.isArray(item.capabilities)&&Array.isArray(item.compatibility)&&Array.isArray(item.invocationLimits)&&item.availability==='NOT_MEASURABLE'&&item.price==='NOT_MEASURABLE';
export async function readModelDirectory(params:URLSearchParams,signal:AbortSignal){
 const before=await readWorkbenchSession(signal),selected=params.has('model')||params.has('revision')||params.has('digest');
 let path='/api/workbench/v1/model-directory';
 if(selected){if(!params.get('model')||!params.get('revision')||!/^[a-f0-9]{64}$/.test(params.get('digest')??''))throw Error('REQUEST_INVALID');path+='/'+encodeURIComponent(params.get('model')!)+'/revisions/'+encodeURIComponent(params.get('revision')!)+'?'+new URLSearchParams({digest:params.get('digest')!})}
 else path+='?'+new URLSearchParams({query:params.get('query')??'',pageSize:'50',...(params.get('cursor')?{cursor:params.get('cursor')!}:{})});
 const response=await fetch(path,{credentials:'same-origin',signal,headers:{Accept:'application/json'}}),body=await response.json().catch(()=>null);
 if(response.status===401)window.dispatchEvent(new Event('workbench-session-expired'));
 if(!response.ok)throw new WorkbenchRequestError(body?.reasonCode??'MODEL_DIRECTORY_UNAVAILABLE',response.status,body?.requestId);
 const value=body?.result as ModelDirectoryPage,after=await readWorkbenchSession(signal),until=expiry(after);
 if(!Number.isFinite(expiry(before))||expiry(before)<=Date.now()||!Number.isFinite(until)||until<=Date.now()||JSON.stringify(before.principal)!==JSON.stringify(after.principal)||value?.subject!==after.principal.principalId||value?.scope?.tenantId!==after.principal.tenantId||value?.scope?.securityDomain!==after.principal.securityDomain||value.basis!=='CURRENT_EXACT_MODEL_READ'||value.executionAuthority!=='NONE')throw Error('MODEL_DIRECTORY_IDENTITY_CHANGED');
 if(selected){if(!value.item||!valid(value.item)||value.item.modelId!==params.get('model')||value.item.revisionId!==params.get('revision')||value.item.digest!==params.get('digest'))throw Error('MODEL_DIRECTORY_EXACT_MISMATCH')}
 else if(!Array.isArray(value.items)||!value.items.every(valid)||(value.nextCursor!==null&&typeof value.nextCursor!=='string'))throw Error('MODEL_DIRECTORY_RESPONSE_INVALID');
 return {value,until};
}
