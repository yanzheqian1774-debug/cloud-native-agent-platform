import { WorkbenchRequestError } from "../api/businessWorkspace";

export type ExactRef = { resource_id: string; revision_id: string; digest: string };
export type Requirement = { requirement_id: string; kind: string; name: string; purpose: string; required: boolean; selected: ExactRef | null; preparation: string };
export type Task = { task_id: string; title: string; responsibility: string; employee_requirement_id: string; depends_on: string[]; inputs: string[]; outputs: string[]; requirement_ids: string[]; criterion_revision_ids?: string[]; operation?: string; input_kinds?: string[]; output_kind?: string };
export type PlanningPolicy = { schema_version: "planning-policy.v2"; mode: "FREE" | "TEMPLATE_ASSISTED" | "STRICT_WORKFLOW"; template: "procurement-overdue.v1" | null; required_operations: string[]; prohibited_operations: string[]; business_acceptance_as_task: false };
export type Semantics = { schema_version?: string; policy?: PlanningPolicy; title: string; business_rules: string[]; boundaries: string[]; stages: { stage_id: string; title: string; task_ids: string[] }[]; tasks: Task[]; requirements: Requirement[]; target: { problem: ExactRef; criteria: ExactRef } };
export type Proposal = { proposal_id: string; revision: number; invocation_id?: string; semantics: Semantics };
export type Snapshot = {proposal_digest?:string; preparation_contract?: string; execution_eligible?: false; checked_at: string; observations: { requirement_id: string; status: string; reason: string; exact_reference?: ExactRef|null; publication_checked?: boolean; permission_checked?: boolean; io_status?: string; availability_status?: string; discovery_status?: string }[] };
export type ProposalRead = { display_translation?: {semantics: Semantics; metadata: {source_digest: string; translation_digest: string; translation_version: number; source: string; created_at: string; review_status: string}} | null; proposal: Proposal; digest: string; snapshot: Snapshot | null; generated_at?: string | null; validation?: { status: string; natural_language_coverage: string } };
export type Confirmation = { execution_summary?:{state:string;basis:string}; plan: { plan_id: string; version: number; source_proposal_revision: number; semantics: Semantics }; digest: string; approval: { approval_decision_id: string; decided_at: string }; execution_status: "NOT_STARTED" };
export type Conversation = { invocation_id: string; request: {answers: string[]}; submitted_at: string; generated_at?: string; questions?: string[]; kind?: string };
export type History = { resourceAutomation?:{enabled:boolean;policyVersion?:string;policyStamp?:string}; conversation?: Conversation[]; proposals: Proposal[]; plans: Confirmation[] };

async function request<T>(path: string, csrf?: string, body?: object): Promise<T> {
  const response = await fetch(`/api/workbench/v1/planning-v2/${path}`, {
    method: body ? "POST" : "GET", credentials: "same-origin",
    headers: { Accept: "application/json", ...(body ? { "Content-Type": "application/json", "X-CSRF-Token": csrf ?? "" } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const value = await response.json();
  if (!response.ok) throw new WorkbenchRequestError(value.reasonCode ?? "PLANNING_UNAVAILABLE", response.status);
  return value.result as T;
}
export const history = (id: string) => request<History>(`${encodeURIComponent(id)}/history`);
export const proposal = (id: string, revision: number) => request<ProposalRead>(`${encodeURIComponent(id)}?version=${revision}`);
export const refresh = (id: string, revision: number, csrf: string) => request<{ snapshot: Snapshot }>(`${encodeURIComponent(id)}/resources`, csrf, { version: revision });
export const confirm = (id: string, revision: number, digest: string, expectedPlanVersion: number, csrf: string, idempotencyKey: string) => request<Confirmation>(`${encodeURIComponent(id)}/confirm`, csrf, { version: revision, digest, expectedPlanVersion, idempotencyKey });

export type Candidate={name:string;reference:ExactRef;selected:boolean;publication:'PUBLISHED';permission:'READABLE';assessment:{status:string;missingOperations:string[];declaredOperations?:string[];sourceSchemas:string[];configuration:Record<string,unknown>;executionReady:false}};
export type CandidateGroup={requirementId:string;kind:string;state:string;candidates:Candidate[];executionReady:false};
export type CandidatesRead={proposalDigest:string;proposalRevision:number;groups:CandidateGroup[];executionReady:false};
export type SourceChangeSpec={plan_version:number;plan_digest:string;expected_proposal_revision:number;old_source:ExactRef;new_source:ExactRef;reason:string;idempotency_key:string;new_target?:Semantics['target']&{criterion_revision_ids:string[];expected_problem_version:number};criterion_revision_map?:Record<string,string>};
export type SourceChangeEvidence={state:string;before:{name:string;reference:ExactRef;contentDigest:string};after:{name:string;reference:ExactRef;contentDigest:string};schema:string;contentChanged:boolean;criterionImpacts:{criterionRevisionId:string;reason:string}[];executionReady:false};
export type SourceChangeRead={previousPlan:{planId:string;version:number;digest:string};requestId:string;actor:string;createdAt:string;request:SourceChangeSpec&{proposal_id:string};evidence:SourceChangeEvidence;proposal:Proposal|null;digest:string|null;confirmationRequired:boolean;executionStarted:false};
export const candidates=(id:string,revision:number,kind?:string)=>request<CandidatesRead>(`${encodeURIComponent(id)}/candidates?version=${revision}${kind?`&kind=${encodeURIComponent(kind)}`:''}`);
export const previewSourceChange=(id:string,spec:SourceChangeSpec,csrf:string)=>request<SourceChangeEvidence>(`${encodeURIComponent(id)}/source-change-preview`,csrf,spec);
export const prepareSourceChange=(id:string,spec:SourceChangeSpec,csrf:string)=>request<SourceChangeRead>(`${encodeURIComponent(id)}/source-changes`,csrf,spec);
export const sourceChange=(id:string,key:string)=>request<SourceChangeRead>(`${encodeURIComponent(id)}/source-changes/by-key/${encodeURIComponent(key)}`);

export type SourceChangeTarget={target:NonNullable<SourceChangeSpec['new_target']>;criterionRevisionMap:Record<string,string>;criteria:{revision:number;check:string|null;revisionId:string}[]};
export const sourceChangeTarget=(id:string,version:number)=>request<SourceChangeTarget>(`${encodeURIComponent(id)}/source-change-target?version=${version}`);

export type ResourcePreparation={resourceSnapshot?:Snapshot;schemaVersion:'resource-preparation.v1';requestKey:string;planId:string;planVersion:number;planDigest:string;subject:string;state:'READY'|'PARTIALLY_READY'|'BLOCKED';policy:{id:string;version:string;digest:string;actor:string};resources:{kind:string;reference:ExactRef;name?:string;state:string;case?:string;reason?:string;decisionId?:string;checks?:Record<string,unknown>[];publication?:Record<string,unknown>|null}[];assembly:{state:string;reason?:string;definition?:ExactRef;reused?:boolean};executionStarted:false;createdAt:string;nextStep:string};
export const prepareResources=(id:string,version:number,key:string,csrf:string)=>request<ResourcePreparation>(`${encodeURIComponent(id)}/resource-preparation`,csrf,{version,idempotencyKey:key});
export const readResourcePreparation=(id:string,version:number,key:string)=>request<ResourcePreparation>(`${encodeURIComponent(id)}/resource-preparation?${new URLSearchParams({version:String(version),key})}`);
export const automaticSourceChange=(id:string,spec:SourceChangeSpec,csrf:string)=>request<SourceChangeRead>(`${encodeURIComponent(id)}/source-changes/automatic`,csrf,spec);

export type EmployeeOption={employeeDefinitionId:string;employeeDefinitionRevisionId:string;employeeDefinitionDigest:string;role:string;publicationState:string};
export async function resourceEmployeeOptions(){const response=await fetch('/api/workbench/v1/employees?pageSize=100',{credentials:'same-origin',headers:{Accept:'application/json'}});const body=await response.json();if(!response.ok)throw new WorkbenchRequestError(body.reasonCode??'EMPLOYEE_LIST_UNAVAILABLE',response.status);return body.result as {items:EmployeeOption[];nextCursor:string|null}}
export const selectEmployeeResources=(id:string,approved:Confirmation,revision:number,employee:ExactRef,key:string,csrf:string)=>request<{confirmation:Confirmation;sourceChangeRequestId:string|null;executionStarted:false}>(`${encodeURIComponent(id)}/resource-selection`,csrf,{version:approved.plan.version,digest:approved.digest,expectedProposalRevision:revision,employee,idempotencyKey:key});
