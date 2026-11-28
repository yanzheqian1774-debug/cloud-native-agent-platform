import {listReadableResources} from "./resourceDirectory";
export type EmployeeMember = {
  kind: "AGENT" | "WORKFLOW" | "SKILL" | "MCP" | "KNOWLEDGE" | "RUNTIME_PROFILE" | "TOOL";
  resourceId: string;
  revisionId: string;
  digest: string;
};

export type ResponsibilityBinding = {responsibility:string; member:EmployeeMember};

export type PublicationState = "PUBLISHED" | "NOT_PUBLISHED";
export type EmployeeLifecycleState =
  | "DRAFT"
  | "VALIDATED"
  | "APPROVED"
  | "PUBLISHED"
  | "REJECTED"
  | "DEPRECATED";

export type EmployeeDefinitionSummary = {
  employeeDefinitionId: string;
  employeeDefinitionRevisionId: string;
  employeeDefinitionDigest: string;
  role: string;
  publicationState: PublicationState;
};

export type EmployeeDefinition = EmployeeDefinitionSummary & {
  resourceKind: "DIGITAL_EMPLOYEE_DEFINITION";
  responsibilities: string[];
  responsibilityBindings?: ResponsibilityBinding[];
  members: EmployeeMember[];
  lifecycleState?: EmployeeLifecycleState;
  aggregateVersion?: number;
};

export type WorkbenchSession = {
  schemaVersion: "workbench-session.v1";
  principal: { principalId: string; tenantId: string; securityDomain: string };
  session: { expiresAt: string; idleExpiresAt: string };
  csrfToken: string;
};

export type EmployeeCreateCommand = {
  employeeDefinitionId: string;
  employeeDefinitionRevisionId: string;
  role: string;
  responsibilities: string[];
  responsibilityBindings?: ResponsibilityBinding[];
  members: EmployeeMember[];
  predecessorEmployeeRevisionId?: string;
  expectedVersion: number;
  commandId: string;
};

export type EmployeeLifecycleCommand = {
  employeeDefinitionDigest: string;
  expectedVersion: number;
  commandId: string;
};

export type EmployeeCommandResult = {
  resourceKind: "DIGITAL_EMPLOYEE_DEFINITION";
  employeeDefinitionId: string;
  employeeDefinitionRevisionId: string;
  employeeDefinitionDigest: string;
  aggregateVersion: number;
  lifecycleState: EmployeeLifecycleState;
};

export type ExactGrantRequest = {
  owner: "EMPLOYEE" | "AGENT";
  action: "CREATE" | "READ" | "VALIDATE" | "APPROVE" | "PUBLISH";
  resource: string;
};

export type GrantRequestStatus = {
  requestId: string;
  state: "PENDING" | "APPROVED" | "REJECTED";
  aggregateVersion: number;
  submittedAt: string;
  purpose:
    | "WORKBENCH_EMPLOYEE_LIFECYCLE"
    | "CONTINUE_PROBLEM_READ"
    | "WORKBENCH_SUCCESS_CRITERIA";
  requestedActions: string[];
  applicant?: {principalId:string;tenantId:string;securityDomain:string};
  requestedGrants?: {owner:string;action:string;resource:string}[];
};

export type GrantDecisionResult = {
  schemaVersion: "exact-grant-decision-result.v1";
  requestId: string;
  decisionId: string;
  state: "APPROVED" | "REJECTED";
  aggregateVersion: number;
  decidedAt: string;
  notBefore?: string;
  expiresAt?: string;
};

export type AgentDefinitionSummary = {
  definitionId: string;
  name: string;
  revisionId: string;
  digest: string;
  title: string;
  enabled: boolean;
  archived: boolean;
};

export type AgentDefinitionRevision = {
  definitionId: string;
  revisionId: string;
  digest: string;
  name: string;
  role: {
    title: string;
    duties: string[];
    businessPurpose: string;
    capabilities: string[];
  };
};

export type WorkbenchPage<T> = { items: T[]; nextCursor?: string };

type EmployeeDefinitionReference = {
  authorityKind: string;
  employeeDefinitionId: string;
  employeeDefinitionRevisionId: string;
  digest: string;
};

export type EmployeeInstance = {
  instanceId: string;
  employeeDefinition?: EmployeeDefinitionReference;
  legacyDefinitionReference?: EmployeeDefinitionReference;
  ownerId: string;
  organizationId: string;
  lifecycle: string;
  execution: { state: string; reasonCode: string };
  health: { state: string; reasonCode: string };
};

export type EmployeeAssignment = {
  assignmentId: string;
  instanceId: string;
  assigneeId: string;
  businessRole: string;
  lifecycle: string;
  effectiveFrom: string;
  effectiveUntil: string | null;
  binding: { state: string; reasonCode: string };
};

export type EmployeePlacement = {
  placementId: string;
  requestId: string;
  decision: string;
  runtimeInstanceId: string;
  policyVersion: string;
  compatibilityFacts: string[];
  limitationCodes: string[];
  decidedAt: string;
  digest: string;
  binding: {
    instanceId: string;
    assignmentId: string;
    attemptId: string;
    agentInstanceId: string;
  };
};

export type EmployeePlacementReadContext = {
  instanceId: string;
  assignmentId: string;
  placementId: string;
  attemptId: string;
  agentInstanceId: string;
};

export class DigitalEmployeeRequestError extends Error {
  reasonCode: string;
  status: number;
  unknownResult: boolean;

  constructor(reasonCode: string, status: number, unknownResult = false) {
    super(reasonCode);
    this.reasonCode = reasonCode;
    this.status = status;
    this.unknownResult = unknownResult;
  }
}

export type EmployeeControlledState =
  | "authentication required"
  | "validation error"
  | "denied"
  | "not found"
  | "stale"
  | "conflict"
  | "backend unavailable"
  | "retryable";

export function employeeControlledState(error: DigitalEmployeeRequestError): EmployeeControlledState {
  if (error.status === 401) return "authentication required";
  if (error.status === 403) return "denied";
  if (error.status === 404) return "not found";
  if (error.status === 409) return error.reasonCode.includes("STALE") ? "stale" : "conflict";
  if (error.status === 422) return "validation error";
  if (error.status >= 500) return "backend unavailable";
  return "retryable";
}

type WorkbenchEnvelope<T> = {
  schemaVersion: "workbench-operation.v1";
  result: T;
  continuationIds: string[];
};

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      signal,
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new DigitalEmployeeRequestError("WORKBENCH_NETWORK_UNAVAILABLE", 503);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new DigitalEmployeeRequestError(
      body?.reasonCode ?? "WORKBENCH_READ_UNAVAILABLE",
      response.status,
    );
  }
  if (body?.schemaVersion !== "workbench-operation.v1" || !("result" in body)) {
    throw new DigitalEmployeeRequestError("WORKBENCH_RESPONSE_INVALID", 503);
  }
  return (body as WorkbenchEnvelope<T>).result;
}

export function workbenchPrincipalKey(session: WorkbenchSession): string {
  const { principalId, tenantId, securityDomain } = session.principal;
  return `${tenantId}\u0000${securityDomain}\u0000${principalId}`;
}

export async function getWorkbenchSession(signal?: AbortSignal): Promise<WorkbenchSession> {
  let response: Response;
  try {
    response = await fetch(`${root}/session`, {
      signal,
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new DigitalEmployeeRequestError("WORKBENCH_NETWORK_UNAVAILABLE", 503);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new DigitalEmployeeRequestError(body?.reasonCode ?? "AUTHENTICATION_REQUIRED", response.status);
  }
  if (body?.schemaVersion !== "workbench-session.v1" || !body?.principal || !body?.csrfToken) {
    throw new DigitalEmployeeRequestError("WORKBENCH_SESSION_INVALID", 503);
  }
  return body as WorkbenchSession;
}

async function command<T>(
  path: string,
  payload: object,
  expectedPrincipalKey: string,
  signal?: AbortSignal,
): Promise<T> {
  const session = await getWorkbenchSession(signal);
  if (workbenchPrincipalKey(session) !== expectedPrincipalKey) {
    throw new DigitalEmployeeRequestError("WORKBENCH_SESSION_CONTEXT_CHANGED", 409);
  }
  let response: Response;
  try {
    response = await fetch(path, {
      method: "POST",
      signal,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "x-csrf-token": session.csrfToken,
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new DigitalEmployeeRequestError("EMPLOYEE_COMMAND_RESULT_UNKNOWN", 503, true);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new DigitalEmployeeRequestError(
      body?.reasonCode ?? "EMPLOYEE_COMMAND_REJECTED",
      response.status,
      response.status >= 500,
    );
  }
  if (body?.schemaVersion !== "workbench-operation.v1" || !("result" in body)) {
    throw new DigitalEmployeeRequestError("EMPLOYEE_COMMAND_RESULT_UNKNOWN", 503, true);
  }
  return (body as WorkbenchEnvelope<T>).result;
}

async function authorizationCommand<T>(
  path: string,
  payload: object,
  idempotencyKey: string,
  expectedPrincipalKey: string,
  signal?: AbortSignal,
): Promise<T> {
  const session = await getWorkbenchSession(signal);
  if (workbenchPrincipalKey(session) !== expectedPrincipalKey) {
    throw new DigitalEmployeeRequestError("WORKBENCH_SESSION_CONTEXT_CHANGED", 409);
  }
  let response: Response;
  try {
    response = await fetch(path, {
      method: "POST",
      signal,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "x-csrf-token": session.csrfToken,
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new DigitalEmployeeRequestError("AUTHORIZATION_RESULT_UNKNOWN", 503, true);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new DigitalEmployeeRequestError(
      body?.reasonCode ?? "AUTHORIZATION_REQUEST_REJECTED",
      response.status,
      response.status >= 500,
    );
  }
  return body as T;
}

const root = "/api/workbench/v1";

function pageQuery(cursor?: string, pageSize = 50): string {
  return new URLSearchParams({
    pageSize: String(pageSize),
    ...(cursor ? { cursor } : {}),
  }).toString();
}

export async function listAgentDefinitions(cursor?: string, signal?: AbortSignal):Promise<WorkbenchPage<AgentDefinitionSummary>> {
  try{return await request<WorkbenchPage<AgentDefinitionSummary>>(`${root}/agents?${pageQuery(cursor)}`, signal)}catch(error){
    if(!(error instanceof DigitalEmployeeRequestError)||![403,404].includes(error.status))throw error;
    const page=await listReadableResources('agent','','PUBLISHED',cursor??null,signal);
    return {items:page.items.filter(x=>x.enabled&&x.isCurrentPublished).map(x=>({definitionId:x.identity,revisionId:x.revisionId,digest:x.digest,name:x.name,title:'可读的已发布 Agent',enabled:x.enabled,archived:false})),nextCursor:page.nextCursor??undefined};
  }
}

export const getAgentDefinitionRevision = (
  definitionId: string,
  revisionId: string,
  signal?: AbortSignal,
) =>
  request<AgentDefinitionRevision>(
    `${root}/agents/${encodeURIComponent(definitionId)}/revisions/${encodeURIComponent(revisionId)}`,
    signal,
  );

export const listEmployeeDefinitions = (cursor?: string, signal?: AbortSignal) =>
  request<WorkbenchPage<EmployeeDefinitionSummary>>(`${root}/employees?${pageQuery(cursor)}`, signal);

export const getEmployeeDefinition = (
  id: string,
  revisionId: string,
  signal?: AbortSignal,
) =>
  request<EmployeeDefinition>(
    `${root}/employees/${encodeURIComponent(id)}/revisions/${encodeURIComponent(revisionId)}`,
    signal,
  );

export const createEmployeeDefinition = (
  payload: EmployeeCreateCommand,
  expectedPrincipalKey: string,
  signal?: AbortSignal,
) => command<EmployeeCommandResult>(`${root}/employees`, payload, expectedPrincipalKey, signal);

function lifecycleCommand(
  suffix: "validation" | "approvals" | "publication",
  id: string,
  revisionId: string,
  payload: EmployeeLifecycleCommand,
  expectedPrincipalKey: string,
  signal?: AbortSignal,
) {
  return command<EmployeeCommandResult>(
    `${root}/employees/${encodeURIComponent(id)}/revisions/${encodeURIComponent(revisionId)}/${suffix}`,
    payload,
    expectedPrincipalKey,
    signal,
  );
}

export const validateEmployeeDefinition = (
  id: string,
  revisionId: string,
  payload: EmployeeLifecycleCommand,
  expectedPrincipalKey: string,
  signal?: AbortSignal,
) => lifecycleCommand("validation", id, revisionId, payload, expectedPrincipalKey, signal);
export const approveEmployeeDefinition = (
  id: string,
  revisionId: string,
  payload: EmployeeLifecycleCommand,
  expectedPrincipalKey: string,
  signal?: AbortSignal,
) => lifecycleCommand("approvals", id, revisionId, payload, expectedPrincipalKey, signal);
export const publishEmployeeDefinition = (
  id: string,
  revisionId: string,
  payload: EmployeeLifecycleCommand,
  expectedPrincipalKey: string,
  signal?: AbortSignal,
) => lifecycleCommand("publication", id, revisionId, payload, expectedPrincipalKey, signal);

export const submitEmployeeGrantRequest = (
  grants: ExactGrantRequest[],
  idempotencyKey: string,
  expectedPrincipalKey: string,
  signal?: AbortSignal,
) => authorizationCommand<GrantRequestStatus>(
  `${root}/authorization/grant-requests`,
  {
    schemaVersion: "exact-grant-request.v1",
    purpose: "WORKBENCH_EMPLOYEE_LIFECYCLE",
    requestedGrants: grants,
    continuationIds: [],
  },
  idempotencyKey,
  expectedPrincipalKey,
  signal,
);

export async function inspectEmployeeGrantRequest(
  requestId: string,
  expectedPrincipalKey: string,
  signal?: AbortSignal,
): Promise<GrantRequestStatus> {
  const session = await getWorkbenchSession(signal);
  if (workbenchPrincipalKey(session) !== expectedPrincipalKey) {
    throw new DigitalEmployeeRequestError("WORKBENCH_SESSION_CONTEXT_CHANGED", 409);
  }
  let response: Response;
  try {
    response = await fetch(`${root}/authorization/grant-requests/${encodeURIComponent(requestId)}`, {
      signal,
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new DigitalEmployeeRequestError("WORKBENCH_NETWORK_UNAVAILABLE", 503);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new DigitalEmployeeRequestError(body?.reasonCode ?? "AUTHORIZATION_REQUEST_NOT_FOUND", response.status);
  }
  return body as GrantRequestStatus;
}

export const decideEmployeeGrantRequest = (
  requestId: string,
  payload: {
    expectedVersion: number;
    decision: "APPROVE" | "REJECT";
    reasonCategory: string;
    basisType: "TICKET" | "POLICY";
    basisReference: string;
    expiresAt?: string;
  },
  idempotencyKey: string,
  expectedPrincipalKey: string,
  signal?: AbortSignal,
) => authorizationCommand<GrantDecisionResult>(
  `${root}/authorization/grant-requests/${encodeURIComponent(requestId)}/decisions`,
  { schemaVersion: "exact-grant-decision.v1", ...payload },
  idempotencyKey,
  expectedPrincipalKey,
  signal,
);

export const getEmployeeInstance = (id: string, signal?: AbortSignal) =>
  request<EmployeeInstance>(`${root}/instances/${encodeURIComponent(id)}`, signal);

export const getEmployeeAssignment = (
  instanceId: string,
  assignmentId: string,
  signal?: AbortSignal,
) =>
  request<EmployeeAssignment>(
    `${root}/instances/${encodeURIComponent(instanceId)}/assignments/${encodeURIComponent(assignmentId)}`,
    signal,
  );

export const getEmployeePlacement = (
  context: EmployeePlacementReadContext,
  signal?: AbortSignal,
) =>
  request<EmployeePlacement>(
    `${root}/instances/${encodeURIComponent(context.instanceId)}`
      + `/assignments/${encodeURIComponent(context.assignmentId)}`
      + `/placements/${encodeURIComponent(context.placementId)}`
      + `?${new URLSearchParams({
        attemptId: context.attemptId,
        agentInstanceId: context.agentInstanceId,
      })}`,
    signal,
  );

export type EmployeeRelationMode = 'history' | 'instances' | 'assignments';
export type EmployeeRelationItem = EmployeeDefinition | EmployeeInstance | EmployeeAssignment;
export type EmployeeRelationPage = {
  relation: 'READ_EMPLOYEE_HISTORY' | 'READ_EMPLOYEE_INSTANCES' | 'READ_INSTANCE_ASSIGNMENTS';
  parent: {employeeDefinitionId?:string;employeeDefinitionRevisionId?:string;employeeDefinitionDigest?:string;instanceId?:string};
  items: EmployeeRelationItem[];
  nextCursor: string | null;
  visibility: 'AUTHORIZED_ONLY';
  scanLimited: boolean;
  executionStarted: false;
};
export function getEmployeeRelations(definition:EmployeeDefinitionSummary,mode:EmployeeRelationMode,instanceId:string|undefined,cursor?:string,signal?:AbortSignal){
  const parent=mode==='assignments'?`${root}/instances/${encodeURIComponent(instanceId??'')}`:`${root}/employees/${encodeURIComponent(definition.employeeDefinitionId)}/revisions/${encodeURIComponent(definition.employeeDefinitionRevisionId)}`;
  return request<EmployeeRelationPage>(`${parent}/${mode}?${pageQuery(cursor,25)}`,signal);
}

export type EmployeeAuthoringTarget = {status:'AVAILABLE';definition:EmployeeDefinition;maintenanceActions?:ManagementActions}|{status:'NOT_AVAILABLE'|'NONE'|'WITHDRAWN'};
export type EmployeeAuthoring = {
 maintenanceActions?:ManagementActions;
 basis:'OWNER_FACT_ORDER';
 parent:Pick<EmployeeDefinitionSummary,'employeeDefinitionId'|'employeeDefinitionRevisionId'|'employeeDefinitionDigest'>;
 aggregateVersion:number;
 head:EmployeeAuthoringTarget;publication:EmployeeAuthoringTarget;draft:EmployeeAuthoringTarget;
 executionStarted:false;
};
export const getEmployeeAuthoring=(item:EmployeeDefinitionSummary,signal?:AbortSignal)=>request<EmployeeAuthoring>(`${root}/employees/${encodeURIComponent(item.employeeDefinitionId)}/revisions/${encodeURIComponent(item.employeeDefinitionRevisionId)}/authoring`,signal);

export type EmployeeWorkRecords = {
 schemaVersion:'employee-work-records.v1';subject:string;scope:{tenantId:string;securityDomain:string};
 employeeDefinition:Pick<EmployeeDefinitionSummary,'employeeDefinitionId'|'employeeDefinitionRevisionId'|'employeeDefinitionDigest'>;
 items:{executionDigest:string;originConversationId?:string|null;originVerified?:boolean;participation:'COORDINATION'|'TASK_EXECUTION';title:string;planVersion:number;state:string;tasks:{taskId:string;title:string}[]}[];
 scanLimited:boolean;visibility:'AUTHORIZED_ONLY';executionStarted:false;
};
export const getEmployeeWorkRecords=(item:EmployeeDefinitionSummary,signal?:AbortSignal)=>request<EmployeeWorkRecords>(`${root}/employees/${encodeURIComponent(item.employeeDefinitionId)}/revisions/${encodeURIComponent(item.employeeDefinitionRevisionId)}/work-records`,signal);

export type TeamMember = {employeeDefinitionId:string;employeeRevisionId:string;employeeDigest:string;responsibility:string;handoff:string};
export type TeamSummary = {teamId:string;revisionId:string;title:string;ownerId:string;memberCount:number;digest:string;aggregateVersion:number};
export type TeamWorkReference = {workflowRunId:string;preparationDigest:string;problemId:string;problemRevisionId:string;problemDigest:string};
export type TeamRecord = {schemaVersion:'team-definition.v1'|'team-definition.v2';work_links?:{workflow_run_id:string;preparation_digest:string;business_problem_id:string;problem_revision_id:string;problem_digest:string}[];scope:{namespace:string;security_domain:string};team_id:string;revision_id:string;title:string;goal:string;owner_id:string;members:{employee_definition_id:string;employee_revision_id:string;employee_digest:string;responsibility:string;handoff:string}[];predecessor_revision_id:string|null};
export type TeamDetail = {revision:TeamRecord;digest:string;aggregateVersion:number;headRevisionId:string;maintenanceActions?:ManagementActions};
export type SaveTeamCommand = {workLinks?:TeamWorkReference[];teamId:string;revisionId:string;title:string;goal:string;ownerId:string;members:TeamMember[];predecessorRevisionId:string|null;expectedVersion:number;commandId:string};
export type SaveTeamResult = {teamId:string;revisionId:string;digest:string;aggregateVersion:number;replayed:boolean;decisionId:string};
export const listTeams=(cursor?:string,signal?:AbortSignal)=>request<WorkbenchPage<TeamSummary>>(`${root}/teams?${pageQuery(cursor)}`,signal);
export const readTeam=(id:string,revision:string,signal?:AbortSignal)=>request<TeamDetail>(`${root}/teams/${encodeURIComponent(id)}/revisions/${encodeURIComponent(revision)}`,signal);
export const saveTeam=(payload:SaveTeamCommand,principal:string,signal?:AbortSignal)=>command<SaveTeamResult>(`${root}/teams`,payload,principal,signal);

export type TeamWorkPage = {teamId:string;revisionId:string;teamDigest:string;items:import("../problems/currentWorkDirectoryApi").DirectoryItem[];linkedCount:number;unavailableCount:number};
export const readTeamWork=(id:string,revision:string,signal?:AbortSignal)=>request<TeamWorkPage>(`${root}/teams/${encodeURIComponent(id)}/revisions/${encodeURIComponent(revision)}/work`,signal);

export type TeamOwnerCandidate={principalId:string;label:string;source:'CURRENT_SESSION'|'LOCAL_TEST_ACCOUNT'};
export const listTeamOwnerCandidates=(signal?:AbortSignal)=>request<{items:TeamOwnerCandidate[];authorityGranted:false}>(`${root}/teams/owner-candidates`,signal);

export type ManagementActions={status?:'AVAILABLE'|'UNAVAILABLE';subjectId:string;tenantId:string;securityDomain:string;generation:number;recoveryEpoch:number;readAt:string;target:Record<string,string|number>|null;actions:Record<string,{authorized:boolean;lifecycleEligible:boolean}>;authorityGranted:false;executionStarted:false};
export const getManagementCollectionActions=(kind:'teams'|'employees',signal?:AbortSignal)=>request<ManagementActions>(`${root}/${kind}/capabilities`,signal);

const fixedWorkPath=(team:import('./fixedWorkDrafts').FixedTeam)=>`${root}/teams/${encodeURIComponent(team.teamId)}/revisions/${encodeURIComponent(team.revisionId)}/fixed-work-drafts`;
export const listFixedWorkDrafts=(team:import('./fixedWorkDrafts').FixedTeam,cursor?:string,signal?:AbortSignal)=>request<import('./fixedWorkDrafts').FixedPage>(`${fixedWorkPath(team)}?${new URLSearchParams({pageSize:'25',...(cursor?{cursor}:{})})}`,signal);
export const readFixedWorkDraft=(team:import('./fixedWorkDrafts').FixedTeam,work:string,revision:string,signal?:AbortSignal)=>request<import('./fixedWorkDrafts').FixedResult>(`${fixedWorkPath(team)}/${encodeURIComponent(work)}/revisions/${encodeURIComponent(revision)}`,signal);
export const saveFixedWorkDraft=(team:import('./fixedWorkDrafts').FixedTeam,body:import('./fixedWorkDrafts').FixedCommand,principal:string,signal?:AbortSignal)=>command<import('./fixedWorkDrafts').FixedResult>(fixedWorkPath(team),body,principal,signal);

export type FixedWorkActivityResult={workId:string;revisionId:string;workDigest:string;windowLimit:50;automaticTriggerStatus:'NOT_OBSERVED';items:{eventId:string;preparationDigest:string;runId:string;recordedAt:string;state:string;aggregateVersion:number}[]};
export const readFixedWorkActivity=(team:import('./fixedWorkDrafts').FixedTeam,work:string,revision:string,signal?:AbortSignal)=>request<FixedWorkActivityResult>(`${fixedWorkPath(team)}/${encodeURIComponent(work)}/revisions/${encodeURIComponent(revision)}/activity`,signal);

export type FixedWorkReadResult={state:'READ_READY'|'NO_RECORD';workDigest:string;runId?:string;preparationDigest?:string};
export const prepareFixedWorkRead=(team:import('./fixedWorkDrafts').FixedTeam,work:string,revision:string,body:{workDigest:string;commandId:string},principal:string,signal?:AbortSignal)=>command<FixedWorkReadResult>(`${fixedWorkPath(team)}/${encodeURIComponent(work)}/revisions/${encodeURIComponent(revision)}/activity-read`,body,principal,signal);

export type FixedNaturalPreview={team:import("./fixedWorkDrafts").FixedTeam;instruction:string;instructionDigest:string;previous:{workId:string;revisionId:string;digest:string}|null;candidateTrigger:import("./fixedWorkDrafts").FixedTrigger|null;proposedTitle:string;issues:string[];modelInvoked:false;executionEnabled:false;authorityGranted:false;validation:"CONFIGURATION_STRUCTURE_ONLY"};
export const previewFixedWorkInstruction=(team:import("./fixedWorkDrafts").FixedTeam,body:{instruction:string;title?:string;previous:{workId:string;revisionId:string;digest:string}|null},principal:string,signal?:AbortSignal)=>command<FixedNaturalPreview>(`${root}/teams/${encodeURIComponent(team.teamId)}/revisions/${encodeURIComponent(team.revisionId)}/fixed-work-preview`,body,principal,signal);

export type FixedSourceReference={resource_id:string;revision_id:string;digest:string};
export type FixedSourceFact={record:{work:FixedSourceReference;team:import('./fixedWorkDrafts').FixedTeam;subjectId:string;conversationId:string;commandId:string;executionEnabled:false};digest:string};
export type FixedSourcePreview={work:FixedSourceReference;team:import('./fixedWorkDrafts').FixedTeam;subjectId:string;conversationId:string;title:string;description:string;criteria:{revision_id:string;measurement:Record<string,unknown>}[];target:{problem:FixedSourceReference;criteria:FixedSourceReference;criterion_revision_ids:string[]}};
export type FixedSourceResult={state:'NO_CONVERSATION'|'AWAITING_CONFIRMED_TARGET'|'READY_TO_CONFIRM'|'BOUND'|'SUPERSEDED';work?:FixedSourceReference;handoff?:FixedSourceFact;preview?:FixedSourcePreview;previewDigest?:string;binding?:FixedSourceFact;executionEnabled:false};
const fixedSourcePath=(team:import('./fixedWorkDrafts').FixedTeam,item:import('./fixedWorkDrafts').FixedItem)=>`${fixedWorkPath(team)}/${encodeURIComponent(item.draft.workId)}/revisions/${encodeURIComponent(item.draft.revisionId)}`;
export const readFixedWorkSource=(team:import('./fixedWorkDrafts').FixedTeam,item:import('./fixedWorkDrafts').FixedItem,signal?:AbortSignal)=>request<FixedSourceResult>(fixedSourcePath(team,item)+'/source',signal);
export const prepareFixedWorkConversation=(team:import('./fixedWorkDrafts').FixedTeam,item:import('./fixedWorkDrafts').FixedItem,body:{conversationId:string;workDigest:string;commandId:string},principal:string,signal?:AbortSignal)=>command<FixedSourceFact>(fixedSourcePath(team,item)+'/conversation',body,principal,signal);
export const confirmFixedWorkSource=(team:import('./fixedWorkDrafts').FixedTeam,item:import('./fixedWorkDrafts').FixedItem,body:{conversationId:string;workDigest:string;commandId:string;previewDigest:string},principal:string,signal?:AbortSignal)=>command<FixedSourceResult>(fixedSourcePath(team,item)+'/source',body,principal,signal);

export const previewFixedWorkSuccession=(team:import('./fixedWorkDrafts').FixedTeam,item:import('./fixedWorkDrafts').FixedItem,body:import('./fixedWorkSuccession').SuccessionCommand,principal:string,signal?:AbortSignal)=>command<import('./fixedWorkSuccession').SuccessionResult>(fixedSourcePath(team,item)+'/succession/preview',body,principal,signal);
export const commitFixedWorkSuccession=(team:import('./fixedWorkDrafts').FixedTeam,item:import('./fixedWorkDrafts').FixedItem,body:import('./fixedWorkSuccession').SuccessionCommand,principal:string,signal?:AbortSignal)=>command<import('./fixedWorkSuccession').SuccessionResult>(fixedSourcePath(team,item)+'/succession',body,principal,signal);
export const readFixedWorkSuccession=(team:import('./fixedWorkDrafts').FixedTeam,item:import('./fixedWorkDrafts').FixedItem,key:string,signal?:AbortSignal)=>request<import('./fixedWorkSuccession').SuccessionResult>(fixedSourcePath(team,item)+'/succession/commands/'+encodeURIComponent(key),signal);
