import { WorkbenchRequestError } from "../api/businessWorkspace";

export type ExactRef = { resource_id: string; revision_id: string; digest: string };
export type Requirement = { requirement_id: string; kind: string; name: string; purpose: string; required: boolean; selected: ExactRef | null; preparation: string };
export type Task = { task_id: string; title: string; responsibility: string; employee_requirement_id: string; depends_on: string[]; inputs: string[]; outputs: string[]; requirement_ids: string[]; criterion_revision_ids?: string[]; operation?: string; input_kinds?: string[]; output_kind?: string };
export type PlanningPolicy = { schema_version: "planning-policy.v2"; mode: "FREE" | "TEMPLATE_ASSISTED" | "STRICT_WORKFLOW"; template: "procurement-overdue.v1" | null; required_operations: string[]; prohibited_operations: string[]; business_acceptance_as_task: false };
export type Semantics = { schema_version?: string; policy?: PlanningPolicy; title: string; business_rules: string[]; boundaries: string[]; stages: { stage_id: string; title: string; task_ids: string[] }[]; tasks: Task[]; requirements: Requirement[]; target: { problem: ExactRef; criteria: ExactRef } };
export type Proposal = { proposal_id: string; revision: number; invocation_id?: string; semantics: Semantics };
export type Snapshot = { checked_at: string; observations: { requirement_id: string; status: string; reason: string }[] };
export type ProposalRead = { proposal: Proposal; digest: string; snapshot: Snapshot | null; generated_at?: string | null; validation?: { status: string; natural_language_coverage: string } };
export type Confirmation = { plan: { plan_id: string; version: number; source_proposal_revision: number; semantics: Semantics }; digest: string; approval: { approval_decision_id: string; decided_at: string }; execution_status: "NOT_STARTED" };
export type Conversation = { invocation_id: string; request: {answers: string[]}; submitted_at: string; generated_at?: string; questions?: string[]; kind?: string };
export type History = { conversation?: Conversation[]; proposals: Proposal[]; plans: Confirmation[] };

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
