import {readWorkbenchSession, WorkbenchRequestError} from './businessWorkspace';

export type McpToolInvocation = {invocationId:string;invokedAt:string|null;outcome:'TOOL_RESPONSE_RECEIVED'|'TOOL_ERROR'|'CANCELLED_BEFORE_DISPATCH'|'NOT_DISPATCHED'|'RESULT_UNKNOWN'};
export type SavedMcpTool = {name:string;description?:string;inputSchema?:unknown;outputSchema?:unknown;annotations?:Record<string,unknown>;sideEffect?:unknown;selectedInSavedSnapshot:boolean;invocations?:McpToolInvocation[];invocationsTruncated?:boolean};
export type McpToolSnapshot = {snapshotId:string;digest:string;capturedAt:string|null;protocolRevision:string|null;tools:SavedMcpTool[];toolsTruncated:boolean};
export type McpTools = {identity:string;name:string;revisionId:string;revisionDigest:string;sourceRevisionState:string;sourceEnabled:boolean;sourceArchived:boolean;unattributedSourceInvocationCount?:number;invocationWindowTruncated?:boolean;snapshots:McpToolSnapshot[];snapshotsTruncated:boolean;availability:'EXACT_SNAPSHOT_SAVED'|'NO_EXACT_SNAPSHOT';executionAuthority:'NONE';subject:string;scope:{tenantId:string;securityDomain:string}};
export type McpSourceReference = {identity:string;revision:string;digest:string};
export const toolsScope = (v: Pick<McpTools,'subject'|'scope'>)=>JSON.stringify([v.subject,v.scope.tenantId,v.scope.securityDomain]);

export async function readMcpTools(ref:McpSourceReference,signal:AbortSignal):Promise<McpTools>{
 const before=await readWorkbenchSession(signal);
 const response=await fetch('/api/workbench/v1/resource-directory/mcp/'+[ref.identity,ref.revision].map(encodeURIComponent).join('/')+'/tools',{signal,credentials:'same-origin',headers:{Accept:'application/json'}});
 const body=await response.json().catch(()=>null);
 if(response.status===401)window.dispatchEvent(new Event('workbench-session-expired'));
 if(!response.ok)throw new WorkbenchRequestError(body?.reasonCode??'MCP_TOOLS_UNAVAILABLE',response.status,body?.requestId);
 const value=body?.result as McpTools,after=await readWorkbenchSession(signal);
 if(JSON.stringify(before.principal)!==JSON.stringify(after.principal)||!value?.scope||value.subject!==after.principal.principalId||value.scope.tenantId!==after.principal.tenantId||value.scope.securityDomain!==after.principal.securityDomain)throw Error('MCP_TOOLS_IDENTITY_CHANGED');
 if(value.identity!==ref.identity||value.revisionId!==ref.revision||value.revisionDigest!==ref.digest||value.executionAuthority!=='NONE')throw Error('MCP_TOOLS_REFERENCE_MISMATCH');
 return value;
}
