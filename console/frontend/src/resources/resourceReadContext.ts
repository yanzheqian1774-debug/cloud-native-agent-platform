import type {WorkbenchSession} from '../api/businessWorkspace';
import type {Ref} from '../api/preparedExecution';

export type ResourceReadContext={
 version:1;href:string;reference:Ref;execution:{digest:string;problemId:string};
 conversation:string|null;detailScroll:number;listScroll:number;openSections:string[];
 savedAt:number;
};
const sections=['configuration','declarations','operations'];
const digest=(v:unknown):v is string=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const identity=(v:unknown):v is string=>typeof v==='string'&&v.length>0&&v.length<=200;
export const validResourceContextId=(v:string|null):v is string=>!!v&&/^[a-f0-9-]{36}$/.test(v);
export const resourceReadScope=(s:WorkbenchSession)=>JSON.stringify([s.principal.principalId,s.principal.tenantId,s.principal.securityDomain,s.session.expiresAt]);
const storageKey=(s:WorkbenchSession,id:string)=>'resource-read.v1:'+resourceReadScope(s)+':'+id;
const latestKey=(s:WorkbenchSession,href:string)=>'resource-read-latest.v1:'+resourceReadScope(s)+':'+href;

/** Only an exact Skill destination on this origin; never an arbitrary return URL. */
export function exactResourceHref(href:string,reference:Ref):string{
 const url=new URL(href,window.location.origin);
 if(url.origin!==window.location.origin||url.hash||!['/skills','/catalog'].includes(url.pathname))throw Error('RESOURCE_RETURN_UNSAFE');
 const params=url.searchParams,allowed=['selected','resourceRevision','resourceDigest','fromExecution','returnConversation','query','status','kind','resourceContext'];
 if(Array.from(params.keys()).some(k=>!allowed.includes(k)||params.getAll(k).length!==1))throw Error('RESOURCE_RETURN_UNSAFE');
 if(params.get('selected')!==reference.resource_id||params.get('resourceRevision')!==reference.revision_id||!digest(reference.digest)||!identity(reference.resource_id)||!identity(reference.revision_id))throw Error('RESOURCE_RETURN_VERSION_MISMATCH');
 if(params.has('resourceDigest')&&params.get('resourceDigest')!==reference.digest)throw Error('RESOURCE_RETURN_VERSION_MISMATCH');
 if(params.has('kind')&&params.get('kind')!=='skill')throw Error('RESOURCE_RETURN_UNSAFE');
 if(params.has('fromExecution')&&!digest(params.get('fromExecution')))throw Error('RESOURCE_RETURN_UNSAFE');
 if((params.get('query')?.length??0)>200||(params.get('status')?.length??0)>32||(params.has('returnConversation')&&!identity(params.get('returnConversation'))))throw Error('RESOURCE_RETURN_UNSAFE');
 params.delete('resourceContext');params.set('resourceDigest',reference.digest);params.sort();
 return url.pathname+'?'+params;
}
function decode(value:string|null):ResourceReadContext{
 if(!value||value.length>12000)throw Error('RESOURCE_RETURN_CONTEXT_MISSING');
 const c=JSON.parse(value) as ResourceReadContext;
 if(c.version!==1||!c.reference||!c.execution||!digest(c.execution.digest)||!identity(c.execution.problemId)||typeof c.href!=='string'||(c.conversation!==null&&!identity(c.conversation))||!Number.isFinite(c.savedAt)||Date.now()-c.savedAt>30*60*1000||c.savedAt>Date.now()+1000)throw Error('RESOURCE_RETURN_CONTEXT_INVALID');
 if(![c.detailScroll,c.listScroll].every(n=>Number.isFinite(n)&&n>=0&&n<=10000000)||!Array.isArray(c.openSections)||c.openSections.some(k=>!sections.includes(k)))throw Error('RESOURCE_RETURN_CONTEXT_INVALID');
 if(exactResourceHref(c.href,c.reference)!==c.href||new URL(c.href,window.location.origin).searchParams.get('returnConversation')!==c.conversation)throw Error('RESOURCE_RETURN_CONTEXT_INVALID');
 return c;
}
export function loadResourceReadContext(session:WorkbenchSession,id:string):ResourceReadContext{
 if(!validResourceContextId(id))throw Error('RESOURCE_RETURN_CONTEXT_INVALID');
 return decode(sessionStorage.getItem(storageKey(session,id)));
}
export function saveResourceReadContext(session:WorkbenchSession,context:Omit<ResourceReadContext,'version'|'savedAt'|'href'> & {href:string}):{id:string;context:ResourceReadContext}{
 const id=crypto.randomUUID(),value:ResourceReadContext={...context,version:1,savedAt:Date.now(),href:exactResourceHref(context.href,context.reference)};
 decode(JSON.stringify(value));
 try{sessionStorage.setItem(storageKey(session,id),JSON.stringify(value));sessionStorage.setItem(latestKey(session,value.href),id)}catch{throw Error('RESOURCE_RETURN_STORAGE_UNAVAILABLE')}
 return {id,context:value};
}
export function findResourceReadContext(session:WorkbenchSession,href:string,reference:Ref):{id:string;context:ResourceReadContext}|null{
 const base=exactResourceHref(href,reference),url=new URL(href,window.location.origin);
 let id=url.searchParams.get('resourceContext');
 if(!id){try{id=sessionStorage.getItem(latestKey(session,base))}catch{return null}}
 if(!id)return null;
 const context=loadResourceReadContext(session,id);
 if(context.href!==base)throw Error('RESOURCE_RETURN_VERSION_MISMATCH');
 return {id,context};
}
export function resourceReturnHref(id:string,context:ResourceReadContext){
 if(!validResourceContextId(id))throw Error('RESOURCE_RETURN_CONTEXT_INVALID');
 const href=exactResourceHref(context.href,context.reference),url=new URL(href,window.location.origin);
 url.searchParams.set('resourceContext',id);return url.pathname+'?'+url.searchParams;
}
