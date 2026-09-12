const PREFIX="/api/workbench/v1";

export type WorkbenchSession={schemaVersion:"workbench-session.v1";principal:{principalId:string;tenantId:string;securityDomain:string};session:{expiresAt:string;idleExpiresAt:string};csrfToken:string};
export type Scope={namespace:string;security_domain:string};
export type BusinessProblemRevision={scope:Scope;business_problem_id:string;revision_id:string;revision:number;predecessor_revision_id:string|null;title:string;description:string;owner_id:string;created_by:string;created_at:string;digest:string};
export type BusinessProblemAggregate={scope:Scope;business_problem_id:string;owner_id:string;current_state:string;aggregate_version:number;current_revision_id:string;created_by:string;created_at:string;updated_at:string};
export type BusinessProblemDetail={problem:BusinessProblemAggregate;revisions:BusinessProblemRevision[];lifecycle:unknown[]};
export type CriterionRevision={scope:Scope;success_criterion_id:string;revision_id:string;revision:number;predecessor_revision_id:string|null;criterion_type:string;measurement:Record<string,unknown>;required_evidence_kinds:string[];evaluator_type:string;evaluator_version:string;applicability:Record<string,unknown>;created_by:string;created_at:string;digest:string};
export type CriteriaSetRevision={scope:Scope;set_revision_id:string;business_problem_id:string;problem_revision_id:string;revision:number;predecessor_set_revision_id:string|null;ordered_criterion_revision_ids:string[];created_by:string;created_at:string;digest:string};
type Envelope<T>={schemaVersion:"workbench-operation.v1";result:T;continuationIds:string[]};
type ErrorBody={reasonCode?:string;requestId?:string};

export class WorkbenchRequestError extends Error{
  readonly reasonCode:string;readonly status:number;readonly requestId?:string;
  constructor(reasonCode:string,status:number,requestId?:string){super(reasonCode);this.reasonCode=reasonCode;this.status=status;this.requestId=requestId}
}

async function decode<T>(response:Response):Promise<T>{
  const body=await response.json().catch(()=>null) as ErrorBody|null;
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

export const newIdempotencyKey=(operation:string)=>`${operation}:${crypto.randomUUID()}`;
export const readWorkbenchSession=async()=>decode<WorkbenchSession>(await fetch(`${PREFIX}/session`,{credentials:"same-origin",headers:{Accept:"application/json"}}));
export const listBusinessProblems=()=>read<{problems:BusinessProblemRevision[]}>("/problems");
export const readBusinessProblem=(problemId:string)=>read<BusinessProblemDetail>(`/problems/${encodeURIComponent(problemId)}`);
export const readCriteriaSets=(problemId:string)=>read<{revisions:CriteriaSetRevision[]}>(`/problems/${encodeURIComponent(problemId)}/criteria-sets`);
export const readProblemCriteria=(problemId:string)=>read<{revisions:CriterionRevision[]}>(`/problems/${encodeURIComponent(problemId)}/criteria`);

export function createBusinessProblem(csrfToken:string,input:{title:string;description:string;ownerId:string;idempotencyKey:string}){
  return write<{revision:BusinessProblemRevision}>("/problems",csrfToken,input);
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
