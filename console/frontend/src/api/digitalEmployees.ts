export type EmployeeMember = {
  kind: "AGENT" | "WORKFLOW" | "SKILL" | "MCP" | "KNOWLEDGE" | "RUNTIME_PROFILE";
  resourceId: string;
  revisionId: string;
  digest: string;
};

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
  members: EmployeeMember[];
  lifecycleState?: EmployeeLifecycleState;
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
  members: [{ kind: "AGENT"; resourceId: string; revisionId: string; digest: string }];
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

export const listAgentDefinitions = (cursor?: string, signal?: AbortSignal) =>
  request<WorkbenchPage<AgentDefinitionSummary>>(`${root}/agents?${pageQuery(cursor)}`, signal);

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
