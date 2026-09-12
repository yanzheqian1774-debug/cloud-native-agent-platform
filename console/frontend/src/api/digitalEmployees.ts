export type EmployeeMember = {
  kind: "AGENT" | "WORKFLOW" | "SKILL" | "MCP" | "KNOWLEDGE" | "RUNTIME_PROFILE";
  resourceId: string;
  revisionId: string;
  digest: string;
};

export type PublicationState = "PUBLISHED" | "NOT_PUBLISHED";

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

  constructor(reasonCode: string, status: number) {
    super(reasonCode);
    this.reasonCode = reasonCode;
    this.status = status;
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
