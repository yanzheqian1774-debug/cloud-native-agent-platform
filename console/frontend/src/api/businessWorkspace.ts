import type {DraftAssistanceResult} from "./draftAssistanceTypes";

const PREFIX="/api/workbench/v1";

export type WorkbenchSession={schemaVersion:"workbench-session.v1";principal:{principalId:string;tenantId:string;securityDomain:string};session:{expiresAt:string;idleExpiresAt:string};csrfToken:string};
export type Scope={namespace:string;security_domain:string};
export type BusinessProblemRevision={scope:Scope;business_problem_id:string;revision_id:string;revision:number;predecessor_revision_id:string|null;title:string;description:string;owner_id:string;created_by:string;created_at:string;digest:string};
export type BusinessProblemAggregate={scope:Scope;business_problem_id:string;owner_id:string;current_state:string;aggregate_version:number;current_revision_id:string;created_by:string;created_at:string;updated_at:string};
export type BusinessProblemDetail={problem:BusinessProblemAggregate;revisions:BusinessProblemRevision[];lifecycle:unknown[]};
export type CriterionRevision={scope:Scope;success_criterion_id:string;revision_id:string;revision:number;predecessor_revision_id:string|null;criterion_type:string;measurement:Record<string,unknown>;required_evidence_kinds:string[];evaluator_type:string;evaluator_version:string;applicability:Record<string,unknown>;created_by:string;created_at:string;digest:string};
export type CriteriaSetRevision={scope:Scope;set_revision_id:string;business_problem_id:string;problem_revision_id:string;revision:number;predecessor_set_revision_id:string|null;ordered_criterion_revision_ids:string[];created_by:string;created_at:string;digest:string};
export type ProblemCreatorContinuation={schemaVersion:"problem-creator-continuation.v1";relation:"PROBLEM_CREATOR";purpose:"CONTINUE_PROBLEM_READ";state:"AVAILABLE"|"CONSUMED"|"EXPIRED";expiresAt:string;continuationId?:string;requestId?:string};
export type GrantRequestStatus={requestId:string;state:"PENDING"|"APPROVED"|"REJECTED";aggregateVersion:number;submittedAt:string;purpose:string;requestedActions:string[]};
export type GrantDecisionResult={schemaVersion:"exact-grant-decision-result.v1";requestId:string;decisionId:string;state:"APPROVED"|"REJECTED";aggregateVersion:number;decidedAt:string;notBefore?:string;expiresAt?:string};
export type ExactGrantRequest={owner:"SUCCESS_CRITERION"|"SUCCESS_CRITERIA_SET";action:"CREATE"|"READ"|"REVISE";resource:string};
export type {DraftAssistanceResult} from "./draftAssistanceTypes";
type Envelope<T>={schemaVersion:"workbench-operation.v1";result:T;continuationIds:string[]};
type ErrorBody={reasonCode?:string;requestId?:string};

export class WorkbenchRequestError extends Error{
  readonly reasonCode:string;readonly status:number;readonly requestId?:string;
  constructor(reasonCode:string,status:number,requestId?:string){super(reasonCode);this.reasonCode=reasonCode;this.status=status;this.requestId=requestId}
}

async function decode<T>(response:Response):Promise<T>{
  const body=await response.json().catch(()=>null) as ErrorBody|null;
  if(response.status===401)window.dispatchEvent(new Event("workbench-session-expired"));
  if(!response.ok)throw new WorkbenchRequestError(body?.reasonCode??"WORKBENCH_UNAVAILABLE",response.status,body?.requestId);
  return body as T;
}

async function read<T>(path:string):Promise<T>{
  const envelope=await decode<Envelope<T>>(await fetch(`${PREFIX}${path}`,{credentials:"same-origin",headers:{Accept:"application/json"}}));
  return envelope.result;
}

async function write<T>(path:string,csrfToken:string,payload:Record<string,unknown>):Promise<T>{
  const envelope=await decode<Envelope<T>>(await fetch(`${PREFIX}${path}`,{method:"POST",credentials:"same-origin",headers:{Accept:"application/json","Content-Type":"application/json","X-CSRF-Token":csrfToken},body:JSON.stringify(payload)}));
  return envelope.result;
}

async function authorizationWrite<T>(path:string,csrfToken:string,idempotencyKey:string,payload:Record<string,unknown>):Promise<T>{
  return decode<T>(await fetch(`${PREFIX}${path}`,{method:"POST",credentials:"same-origin",headers:{Accept:"application/json","Content-Type":"application/json","X-CSRF-Token":csrfToken,"Idempotency-Key":idempotencyKey},body:JSON.stringify(payload)}));
}

export const newIdempotencyKey=(operation:string)=>`${operation}:${crypto.randomUUID()}`;
export const readWorkbenchSession=async(signal?:AbortSignal)=>decode<WorkbenchSession>(await fetch(`${PREFIX}/session`,{credentials:"same-origin",headers:{Accept:"application/json"},signal}));
export const listBusinessProblems=()=>read<{problems:BusinessProblemRevision[]}>("/problems");
export const readBusinessProblem=(problemId:string)=>read<BusinessProblemDetail>(`/problems/${encodeURIComponent(problemId)}`);
export const readCriteriaSets=(problemId:string)=>read<{revisions:CriteriaSetRevision[]}>(`/problems/${encodeURIComponent(problemId)}/criteria-sets`);
export const readProblemCriteria=(problemId:string)=>read<{revisions:CriterionRevision[]}>(`/problems/${encodeURIComponent(problemId)}/criteria`);

export function createBusinessProblem(csrfToken:string,input:{title:string;description:string;ownerId:string;idempotencyKey:string;draftInvocationId?:string}){
  return write<{revision:BusinessProblemRevision;creatorContinuation:ProblemCreatorContinuation}>("/problems",csrfToken,input);
}

export function beginDraftAssistance(csrfToken:string,input:{idempotencyKey:string;content:string;parentContextId?:string;parentTurnId?:string;expectedParentVersion?:number;predecessorInvocationId?:string}){
  return write<DraftAssistanceResult>("/draft-assistance/invocations",csrfToken,input);
}

export function resubmitDraftAssistance(csrfToken:string,invocationId:string,input:{idempotencyKey:string;content:string}){
  return write<DraftAssistanceResult>(`/draft-assistance/invocations/${encodeURIComponent(invocationId)}/resubmit`,csrfToken,input);
}

export function readDraftAssistance(invocationId:string){return read<DraftAssistanceResult>(`/draft-assistance/invocations/${encodeURIComponent(invocationId)}`)}
export type DraftReadiness={invocationId:string;contextId:string;checkedAt:string;permissionsCurrent:boolean;checks:{draft:boolean;model:boolean;context:boolean};dispatchRevalidationRequired:true};
export function readDraftReadiness(invocationId:string){return read<DraftReadiness>(`/draft-assistance/invocations/${encodeURIComponent(invocationId)}/readiness`)}
export async function readDraftContextAdmission(contextId:string){return decode<{status:string;reasonCode:string|null}>(await fetch(`${PREFIX}/authorization/context-admissions/${encodeURIComponent(contextId)}`,{credentials:"same-origin",headers:{Accept:"application/json"}}))}
export function observeDraftAssistance(csrfToken:string,invocationId:string){return write<DraftAssistanceResult>(`/draft-assistance/invocations/${encodeURIComponent(invocationId)}/observe`,csrfToken,{})}
export function cancelDraftAssistance(csrfToken:string,invocationId:string){return write<DraftAssistanceResult>(`/draft-assistance/invocations/${encodeURIComponent(invocationId)}/cancel`,csrfToken,{})}
export function rejectDraftAssistance(csrfToken:string,invocationId:string){return write<DraftAssistanceResult>(`/draft-assistance/invocations/${encodeURIComponent(invocationId)}/reject`,csrfToken,{})}
export function linkDraftAssistanceProblem(csrfToken:string,invocationId:string,input:{problemId:string;problemRevisionId:string;problemDigest:string}){return write<DraftAssistanceResult>(`/draft-assistance/invocations/${encodeURIComponent(invocationId)}/problem-link`,csrfToken,input)}

export function submitProblemReadGrantRequest(csrfToken:string,continuationId:string,idempotencyKey:string){
  return authorizationWrite<GrantRequestStatus>("/authorization/grant-requests",csrfToken,idempotencyKey,{schemaVersion:"exact-grant-request.v1",purpose:"CONTINUE_PROBLEM_READ",requestedGrants:[],continuationIds:[continuationId]});
}

export function submitSuccessCriteriaGrantRequest(csrfToken:string,requestedGrants:ExactGrantRequest[],idempotencyKey:string){
  return authorizationWrite<GrantRequestStatus>("/authorization/grant-requests",csrfToken,idempotencyKey,{schemaVersion:"exact-grant-request.v1",purpose:"WORKBENCH_SUCCESS_CRITERIA",requestedGrants,continuationIds:[]});
}

export const inspectGrantRequest=async(requestId:string)=>decode<GrantRequestStatus>(await fetch(`${PREFIX}/authorization/grant-requests/${encodeURIComponent(requestId)}`,{credentials:"same-origin",headers:{Accept:"application/json"}}));

export function decideGrantRequest(csrfToken:string,requestId:string,input:{expectedVersion:number;decision:"APPROVE"|"REJECT";reasonCategory:string;basisType:"TICKET"|"POLICY";basisReference:string;expiresAt?:string;idempotencyKey:string}){
  const {idempotencyKey,...payload}=input;
  return authorizationWrite<GrantDecisionResult>(`/authorization/grant-requests/${encodeURIComponent(requestId)}/decisions`,csrfToken,idempotencyKey,{schemaVersion:"exact-grant-decision.v1",...payload});
}

export function reviseBusinessProblem(csrfToken:string,problemId:string,input:{predecessorRevisionId:string;expectedVersion:number;title:string;description:string;ownerId:string;idempotencyKey:string}){
  return write<{revision:BusinessProblemRevision}>(`/problems/${encodeURIComponent(problemId)}/revisions`,csrfToken,input);
}

export function writeCriterion(csrfToken:string,input:{successCriterionId?:string;predecessorRevisionId?:string;expectedVersion?:number;criterionType:"HUMAN_EVALUATED";measurement:{rubric:string};requiredEvidenceKinds:string[];evaluatorType:string;evaluatorVersion:string;applicability:Record<string,unknown>;idempotencyKey:string}){
  return write<{revision:CriterionRevision}>("/success-criteria",csrfToken,input);
}

export function writeCriteriaSet(csrfToken:string,problemId:string,input:{problemRevisionId:string;predecessorSetRevisionId?:string;orderedCriterionRevisionIds:string[];expectedVersion:number;idempotencyKey:string}){
  return write<{revision:CriteriaSetRevision}>(`/problems/${encodeURIComponent(problemId)}/criteria-sets`,csrfToken,input);
}

export function transitionBusinessProblem(csrfToken:string,problemId:string,input:{toState:"ACTIVE";expectedVersion:number;idempotencyKey:string}){
  return write<{businessProblemId:string;aggregateVersion:number}>(`/problems/${encodeURIComponent(problemId)}/lifecycle`,csrfToken,input);
}

export async function logoutWorkbenchSession(){const session=await readWorkbenchSession();const response=await fetch(`${PREFIX}/session`,{method:"DELETE",credentials:"same-origin",headers:{"X-CSRF-Token":session.csrfToken,Accept:"application/json"}});if(!response.ok)await decode(response);}
