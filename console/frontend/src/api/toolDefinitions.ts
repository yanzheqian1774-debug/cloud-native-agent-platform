import {getWorkbenchSession, workbenchPrincipalKey} from './digitalEmployees';

export type ToolSource={kind:'API'|'PLUGIN'|'PLUGIN_ZIP';contentBase64:string};
export type ToolOperation={name:string;description:string;inputSchema:Record<string,unknown>|null;outputSchema:Record<string,unknown>|null;sideEffect:string;source:Record<string,unknown>;blockingIssues:string[];existing?:{toolId:string;revisionId:string;aggregateVersion:number}|null};
export type ToolPreview={files?:{path:string;bytes:number;digest:string}[];sourceDigest:string;operations:ToolOperation[];persisted:false;executionAuthorized:false};
export type ToolContent={name:string;purpose:string;inputSchema:Record<string,unknown>|null;outputSchema:Record<string,unknown>|null;sideEffect:'UNCONFIRMED'|'read-only'|'creates-file'|'external-write'};
export type ToolDraft={toolId:string;revisionId:string;digest:string;aggregateVersion:number;draftRevisionId:string|null;publishedRevisionId:string|null;record:{name:string;purpose:string;operation:ToolOperation;validation:unknown;state:string};executionAuthorized:false};
export type ToolReceipt={items:{toolId:string;revisionId:string;aggregateVersion:number;changed:boolean}[];executionAuthorized:false};
export class ToolRequestError extends Error {
 readonly code:string;readonly status:number;readonly outcomeUnknown:boolean;
 constructor(code:string,status:number,outcomeUnknown=false){super(code);this.code=code;this.status=status;this.outcomeUnknown=outcomeUnknown}
}
const root='/api/workbench/v1/tool-definitions';
async function request<T>(path:string,principal:string,signal:AbortSignal,payload?:unknown,mutation=false):Promise<T>{
 const bounded=AbortSignal.any([signal,AbortSignal.timeout(30_000)]);let sent=false;
 try{
  const session=await getWorkbenchSession(bounded);
  if(workbenchPrincipalKey(session)!==principal)throw new ToolRequestError('IDENTITY_CHANGED',409);
  sent=true;
  const response=await fetch(root+path,{method:payload===undefined?'GET':'POST',credentials:'same-origin',signal:bounded,headers:{Accept:'application/json',...(payload===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':session.csrfToken})},...(payload===undefined?{}:{body:JSON.stringify(payload)})});
  const body=await response.json().catch(()=>null);
  if(response.status===401)window.dispatchEvent(new Event('workbench-session-expired'));
  if(!response.ok)throw new ToolRequestError(body?.reasonCode??'TOOL_UNAVAILABLE',response.status,mutation&&response.status>=500);
  if(body?.schemaVersion!=='workbench-operation.v1'||body.result?.executionAuthorized!==false)throw new ToolRequestError('INVALID_RESPONSE',503,mutation);
  const after=await getWorkbenchSession(bounded);
  if(workbenchPrincipalKey(after)!==principal)throw new ToolRequestError('IDENTITY_CHANGED',409,mutation);
  return body.result as T;
 }catch(error){
  if(error instanceof ToolRequestError)throw error;
  throw new ToolRequestError(bounded.aborted?'REQUEST_TIMEOUT':'NETWORK_UNAVAILABLE',503,mutation&&sent);
 }
}
export const checkToolImportAccess=(principal:string,signal:AbortSignal)=>request<{allowed:true;executionAuthorized:false}>('/import-access',principal,signal);
export const previewToolImport=(source:ToolSource,principal:string,signal:AbortSignal)=>request<ToolPreview>('/import-preview',principal,signal,source);
export const saveToolImport=(command:ToolSource&{selected:string[];commandId:string;expectedVersions:Record<string,number>;effects?:Record<string,ToolContent['sideEffect']>},principal:string,signal:AbortSignal)=>request<ToolReceipt>('/imports',principal,signal,command,true);
export const readToolReceipt=(commandId:string,principal:string,signal:AbortSignal)=>request<ToolReceipt>('/imports/'+encodeURIComponent(commandId),principal,signal);
export const readToolDraft=(id:string,revision:string,principal:string,signal:AbortSignal)=>request<ToolDraft>('/'+encodeURIComponent(id)+'?'+new URLSearchParams({revision}),principal,signal);
export const reviseToolDraft=(id:string,command:{content:ToolContent;expectedVersion:number;commandId:string},principal:string,signal:AbortSignal)=>request<ToolReceipt>('/'+encodeURIComponent(id)+'/draft',principal,signal,command,true);
export const listToolDrafts=(cursor:string,principal:string,signal:AbortSignal)=>request<{items:{toolId:string;revisionId:string;name:string;purpose:string;sourceKind:string}[];nextCursor:string|null;executionAuthorized:false}>('?'+new URLSearchParams({cursor,pageSize:'25'}),principal,signal);

export function encodeToolSource(bytes:Uint8Array):string{
 if(!bytes.length||bytes.length>100000)throw new ToolRequestError('IMPORT_SIZE_LIMIT',422);
 let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);
 return btoa(binary);
}
