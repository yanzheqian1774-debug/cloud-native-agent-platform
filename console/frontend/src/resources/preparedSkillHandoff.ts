import {readWorkbenchSession,WorkbenchRequestError,type WorkbenchSession} from '../api/businessWorkspace';
import type {DirectoryItem} from '../api/resourceDirectory';
import type {SkillMcpResource} from '../api/skillMcpResources';
import {verifyManagedResource} from './managementCommandState';

export type PreparedSkillRead={kind:'skill';identity:string;aggregateVersion:number;publishedRevisionId:string|null;successorPreparationEnabled?:boolean;revision:{revisionId:string;digest:string;state:string;content:Record<string,unknown>}};
export type PreparedIntent={version:1;principal:string;identity:string;revision:string;digest:string;commandKey:string;expectedVersion:number;content:Record<string,unknown>;reason:string;rejected?:boolean;managementKey?:string;managementRejected?:boolean};
export type PreparedReceipt={schemaVersion:'prepared-skill-successor-receipt.v1';actor:string;predecessor:{resource_id:string;revision_id:string;digest:string};draft:{resource_id:string;revision_id:string;digest:string};aggregateVersion:number;commandKey:string;reason:string;contentDigest:string;state:'DRAFT';published:false;executionStarted:false};
const id=(v:unknown):v is string=>typeof v==='string'&&v.length>0&&v.length<=200;
const digest=(v:unknown):v is string=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
export const actor=(s:WorkbenchSession)=>JSON.stringify(s.principal);
export const marker=(principal:string,item:DirectoryItem)=>'prepared-skill-maintenance.v1:'+JSON.stringify([principal,item.identity,item.revisionId,item.digest]);
export const preparedPath=(item:{identity:string;revisionId:string})=>'prepared-resources/skill/'+encodeURIComponent(item.identity)+'/'+encodeURIComponent(item.revisionId);
export const successorPath=(intent:PreparedIntent)=>'prepared-resources/skill/'+encodeURIComponent(intent.identity)+'/revisions/'+encodeURIComponent(intent.revision)+'/successors';
export async function request<T>(path:string,signal?:AbortSignal,body?:unknown,csrf?:string):Promise<T>{
 const response=await fetch('/api/workbench/v1/'+path,{method:body?'POST':'GET',credentials:'same-origin',signal:signal?AbortSignal.any([signal,AbortSignal.timeout(15000)]):AbortSignal.timeout(15000),headers:{Accept:'application/json',...(body?{'Content-Type':'application/json','X-CSRF-Token':csrf??''}:{})},...(body?{body:JSON.stringify(body)}:{})});const value=await response.json().catch(()=>null);
 if(response.status===401)window.dispatchEvent(new Event('workbench-session-expired'));
 if(!response.ok)throw new WorkbenchRequestError(value?.reasonCode??'PREPARED_SKILL_UNAVAILABLE',response.status);
 if(!value?.result)throw Error('PREPARED_SKILL_RECEIPT_UNAVAILABLE');return value.result as T;
}
export function safeContent(value:unknown):asserts value is Record<string,unknown>{
 if(!value||typeof value!=='object'||Array.isArray(value)||JSON.stringify(value).length>200000)throw Error('请输入有效的技能配置对象，且不超过200KB。');
 const visit=(v:unknown)=>{if(Array.isArray(v))v.forEach(visit);else if(v&&typeof v==='object')for(const [k,x] of Object.entries(v)){if(['authorization','password','token','api_key','apikey','cookie','secret'].includes(k.toLowerCase()))throw Error('配置不能包含明文凭据，请使用凭据引用。');visit(x)}};visit(value);
}
export function decodeIntent(raw:string,principal:string,item:DirectoryItem):PreparedIntent{
 if(raw.length>220000)throw Error('原后继操作核对依据无效，请保留原记录。');const i=JSON.parse(raw) as PreparedIntent;
 if(i.version!==1||i.principal!==principal||i.identity!==item.identity||i.revision!==item.revisionId||i.digest!==item.digest||!id(i.commandKey)||i.commandKey.length<8||i.commandKey.length>120||!Number.isSafeInteger(i.expectedVersion)||i.expectedVersion<1||typeof i.reason!=='string'||!i.reason.trim()||i.reason.length>1000||(i.managementKey!==undefined&&(!id(i.managementKey)||i.managementKey.length<8||i.managementKey.length>120)))throw Error('原后继操作与当前账号或版本不符，请保留原记录。');safeContent(i.content);return i;
}
export function verifyPrepared(value:PreparedReceipt,i:PreparedIntent):void{
 const principal=JSON.parse(i.principal);
 if(value?.schemaVersion!=='prepared-skill-successor-receipt.v1'||value.actor!==principal.principalId||value.commandKey!==i.commandKey||value.reason!==i.reason||value.predecessor?.resource_id!==i.identity||value.predecessor.revision_id!==i.revision||value.predecessor.digest!==i.digest||value.draft?.resource_id!==i.identity||!id(value.draft.revision_id)||value.draft.revision_id===i.revision||!digest(value.draft.digest)||!digest(value.contentDigest)||value.aggregateVersion!==i.expectedVersion+2||value.state!=='DRAFT'||value.published!==false||value.executionStarted!==false)throw Error('后继回执与原请求不符，保留原操作，不接续维护。');
}
export function verifyRead(value:PreparedSkillRead,item:DirectoryItem){if(value?.kind!=='skill'||value.identity!==item.identity||value.revision?.revisionId!==item.revisionId||value.revision.digest!==item.digest||!Number.isInteger(value.aggregateVersion)||value.aggregateVersion<1)throw Error('原技能版本核对未通过。')}
function includesValues(actual:unknown,expected:unknown):boolean{if(Array.isArray(expected))return Array.isArray(actual)&&actual.length===expected.length&&expected.every((v,i)=>includesValues(actual[i],v));if(expected&&typeof expected==='object'){if(!actual||typeof actual!=='object'||Array.isArray(actual))return false;return Object.entries(expected).every(([k,v])=>includesValues((actual as Record<string,unknown>)[k],v))}return Object.is(actual,expected)}
export async function verifyAdoption(value:unknown,i:PreparedIntent,prepared:PreparedReceipt,session:WorkbenchSession,signal?:AbortSignal){
 const r=value as {schemaVersion:string;action:string;kind:string;identity:string;commandKey:string;aggregateVersion:number;preparedCommandKey:string;preparedSuccessor:PreparedReceipt['draft'];resource:SkillMcpResource;executionStarted:boolean;modelCalls:number};
 if(r?.schemaVersion!=='resource-management-receipt.v1'||r.action!=='adopt-prepared'||r.kind!=='skill'||r.identity!==i.identity||r.commandKey!==i.managementKey||r.preparedCommandKey!==i.commandKey||!(['resource_id','revision_id','digest'] as const).every(k=>r.preparedSuccessor?.[k]===prepared.draft[k])||r.executionStarted!==false||r.modelCalls!==0||r.aggregateVersion!==prepared.aggregateVersion)throw Error('维护接续回执与原后继不符，保留原操作。');
 verifyManagedResource(r.resource);if(r.resource.resourceId!==i.identity||r.resource.kind!=='skill'||r.resource.aggregateVersion!==r.aggregateVersion)throw Error('维护接续的资源身份与原请求不符。');const listed=await request<{subject:string;scope:{tenantId:string;securityDomain:string};items:SkillMcpResource[]}>('resource-management/skill',signal);const after=await readWorkbenchSession(signal);
 if(actor(after)!==actor(session)||listed.subject!==session.principal.principalId||listed.scope.tenantId!==session.principal.tenantId||listed.scope.securityDomain!==session.principal.securityDomain)throw Error('当前登录身份已变化，旧结果不再显示。');
 const current=listed.items.find(x=>x.resourceId===i.identity);verifyManagedResource(current);const draft=current.revisions.find(x=>x.revisionId===prepared.draft.revision_id);
 if(current.kind!=='skill'||current.aggregateVersion<r.aggregateVersion||!draft||draft.digest!==prepared.draft.digest||!includesValues(draft.content,i.content))throw Error('后继当前配置尚未读回或与原提交不符，保留原操作。');return current;
}
