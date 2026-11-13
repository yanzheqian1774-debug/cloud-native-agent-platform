import {getWorkbenchSession, workbenchPrincipalKey, type WorkbenchSession} from './digitalEmployees';

export type CapabilityReference = {resource_id:string; revision_id:string; digest:string};
export type CapabilityBinding = {kind:'EMPLOYEE'|'SKILL'|'MCP'|'KNOWLEDGE'|'ONTOLOGY'|'TOOL'|'RUNTIME_PROFILE'; reference:CapabilityReference; purpose:string};
export type CapabilityRevision = {
  schemaVersion:'business-capability.v1'; scope:{namespace:string;security_domain:string};
  capability_id:string; revision_id:string; predecessor_revision_id:string|null;
  title:string; intent:string; inputs:string; outputs:string; business_scope:string; business_domain?:string;
  exclusions:string; manual_involvement:string; acceptance_criteria:string[]; known_limitations:string;
  origin:{kind:'INDEPENDENT'|'WORKFLOW_REVISION'|'SAVED_PREPARATION';workflow:CapabilityReference|null;preparation_digest:string|null};
  bindings:CapabilityBinding[];
};
export type CapabilitySummary = {revisionId:string;title:string;intent:string;digest:string;businessDomain?:string|null;inputs?:string;outputs?:string;manualInvolvement?:string;exclusions?:string;originKind?:CapabilityRevision['origin']['kind'];employeeResponsibilities?:string[];employeeNames?:string[];employeeNamesUnavailable?:number};
export type CapabilityItem = CapabilitySummary & {capabilityId:string;aggregateVersion:number;state:'PUBLISHED'|'DRAFT';currentPublished:CapabilitySummary|null;currentDraft:CapabilitySummary|null};
export type CapabilityList = {items:CapabilityItem[];nextCursor:string|null};
export type CapabilityDetail = {members?:{kind:string;resourceId:string;revisionId:string;digest:string;name:string}[];revision:CapabilityRevision;digest:string;aggregateVersion:number;headRevisionId:string;publishedRevisionId:string|null;currentDraftRevisionId:string|null;state:'PUBLISHED'|'DRAFT';executionAuthorized:false};
export type CapabilityPreview = {
  capabilityId:string;revisionId:string;revisionDigest:string;aggregateVersion:number;impactDigest:string;
  fieldChanges:{field:string;before:unknown;after:unknown}[];
  bindingChanges:{kind:string;resourceId:string;before:CapabilityBinding|null;after:CapabilityBinding|null}[];
  previousPublishedRevisionId:string|null; automaticReferenceUpdates:false; executionAuthorized:false;
};
export type CapabilityPublishCommand = {expectedVersion:number;digest:string;impactDigest:string;commandId:string;reason:string};
export class CapabilityRequestError extends Error {
  readonly code:string;readonly status:number;readonly outcomeUnknown:boolean;
  constructor(code:string,status:number,outcomeUnknown=false){super(code);this.code=code;this.status=status;this.outcomeUnknown=outcomeUnknown}
}
const root='/api/workbench/v1/business-capabilities';
const revisionPath=(id:string,revision:string)=>`${root}/${encodeURIComponent(id)}/revisions/${encodeURIComponent(revision)}`;

// Bound reads and writes without retrying commands. Unknown write outcomes must be
// reconciled using the original command identity, never a newly generated command.
async function request<T>(path:string,principal:string,signal?:AbortSignal,payload?:object):Promise<T>{
  const controller=new AbortController();
  const abort=()=>controller.abort();
  if(signal?.aborted)abort();else signal?.addEventListener('abort',abort,{once:true});
  const timeout=window.setTimeout(abort,30_000);
  let sent=false;
  try{
    const session=await getWorkbenchSession(controller.signal);
    if(workbenchPrincipalKey(session)!==principal)throw new CapabilityRequestError('CAPABILITY_IDENTITY_CHANGED',409);
    sent=payload!==undefined;
    const response=await fetch(path,{method:payload?'POST':'GET',credentials:'same-origin',signal:controller.signal,headers:{Accept:'application/json',...(payload?{'Content-Type':'application/json','X-CSRF-Token':session.csrfToken}:{})},...(payload?{body:JSON.stringify(payload)}:{})});
    const body=await response.json().catch(()=>null);
    if(response.status===401)window.dispatchEvent(new Event('workbench-session-expired'));
    if(!response.ok)throw new CapabilityRequestError(body?.reasonCode??'CAPABILITY_UNAVAILABLE',response.status,sent&&response.status>=500);
    if(body?.schemaVersion!=='workbench-operation.v1'||!body.result)throw new CapabilityRequestError('CAPABILITY_RESPONSE_INVALID',503,sent);
    const after=await getWorkbenchSession(controller.signal);
    if(workbenchPrincipalKey(after)!==principal)throw new CapabilityRequestError('CAPABILITY_IDENTITY_CHANGED',409,sent);
    return body.result as T;
  }catch(error){
    if(error instanceof CapabilityRequestError)throw error;
    throw new CapabilityRequestError(controller.signal.aborted?'CAPABILITY_WAIT_EXPIRED':'CAPABILITY_NETWORK_UNAVAILABLE',503,sent);
  }finally{window.clearTimeout(timeout);signal?.removeEventListener('abort',abort)}
}
export async function capabilitySession(signal?:AbortSignal):Promise<WorkbenchSession>{
  return getWorkbenchSession(AbortSignal.any([signal??new AbortController().signal,AbortSignal.timeout(30_000)]));
}
export type CapabilityCatalogueFilters={query:string;domain:string;favoritesOnly:boolean};
export const listCapabilities=(principal:string,cursor:string|null=null,signal?:AbortSignal,filters?:CapabilityCatalogueFilters)=>request<CapabilityList>(root+'?'+new URLSearchParams({pageSize:'50',...(cursor?{cursor}:{}),...(filters?{query:filters.query,domain:filters.domain,favoritesOnly:String(filters.favoritesOnly)}:{})}),principal,signal);
export const listCapabilityDomains=(principal:string,signal?:AbortSignal)=>request<{domains:string[];hasUnassigned:boolean;readableFavoriteCount:number}>(root+'/domains',principal,signal);
export const readCapability=(id:string,revision:string,principal:string,signal?:AbortSignal)=>request<CapabilityDetail>(revisionPath(id,revision),principal,signal);
export const previewCapability=(id:string,revision:string,principal:string,signal?:AbortSignal)=>request<CapabilityPreview>(revisionPath(id,revision)+'/publication-preview',principal,signal);
export const publishCapability=(id:string,revision:string,command:CapabilityPublishCommand,principal:string,signal?:AbortSignal)=>request<{state:'PUBLISHED';aggregateVersion:number}>(revisionPath(id,revision)+'/publication',principal,signal,command);
export const saveCapability=(revision:CapabilityRevision,expectedVersion:number,commandId:string,principal:string,signal?:AbortSignal)=>request<unknown>(root,principal,signal,{revision,expectedVersion,commandId});

export type CapabilityWorkInput={problem:{title:string;description:string};criterion:{criterionType:'HUMAN_EVALUATED';measurement:{rubric:string};requiredEvidenceKinds:string[];evaluatorType:string;evaluatorVersion:string;applicability:{capabilityContractDigest:string;capabilityConstraints:CapabilityExecutionContract['contract']}}};
export type CapabilityExecutionContract = {workInput?:CapabilityWorkInput;contractDigest:string;admissionState:'NOT_ADMITTED';executionAuthorized:false;executionStarted:false;contract:{schemaVersion:'capability-execution-constraints.v1';scope:{tenantId:string;securityDomain:string};conversationId:string;sourceMessageId:string;capability:CapabilityReference;objective:string;inputNotes:string;inputs:string;outputs:string;acceptanceCriteria:string[];businessScope:string;exclusions:string;manualInvolvement:string;knownLimitations:string;bindings:CapabilityBinding[]}};

export type CapabilityCatalogueState={query:string;domain:string;layout:'cards'|'list';favoritesOnly:boolean;favorites:string[];scrollTop:number;loadedCount:number};
export type CapabilityCataloguePreferences={version:number;state:CapabilityCatalogueState;commandId:string|null;replayed:boolean};
export const readCapabilityPreferences=(principal:string,signal?:AbortSignal)=>request<CapabilityCataloguePreferences>(root+'/preferences',principal,signal);
export const saveCapabilityPreferences=(principal:string,expectedVersion:number,commandId:string,state:CapabilityCatalogueState,signal?:AbortSignal)=>request<CapabilityCataloguePreferences>(root+'/preferences',principal,signal,{expectedVersion,commandId,state});

export type CapabilityWorkflowSourceDetail={definition:{workflowDefinitionId:string;name:string};revision:{revisionId:string;digest:string;state:string;content:Record<string,unknown>}};
export async function readCapabilityWorkflowSource(reference:CapabilityReference,principal:string,signal?:AbortSignal){
 const value=await request<CapabilityWorkflowSourceDetail>('/api/workbench/v1/workflows/'+encodeURIComponent(reference.resource_id)+'/revisions/'+encodeURIComponent(reference.revision_id),principal,signal);
 if(value.definition?.workflowDefinitionId!==reference.resource_id||value.revision?.revisionId!==reference.revision_id||value.revision?.digest.replace(/^sha256:/,'')!==reference.digest)throw new CapabilityRequestError('CAPABILITY_SOURCE_VERSION_MISMATCH',409);
 return value;
}

export const listWorkflowDerivedCapabilities=(reference:CapabilityReference,principal:string,cursor:string|null=null,signal?:AbortSignal)=>request<CapabilityList>(root+'?'+new URLSearchParams({pageSize:'20',workflowId:reference.resource_id,workflowRevision:reference.revision_id,workflowDigest:reference.digest,...(cursor?{cursor}:{})}),principal,signal);

export const listCapabilityOntologies=(principal:string,signal?:AbortSignal)=>request<{items:{ontology_id:string;revision_id:string;digest:string;name:string;state:string}[];limitations?:string[]}>('/api/workbench/v1/business-ontologies',principal,signal);
