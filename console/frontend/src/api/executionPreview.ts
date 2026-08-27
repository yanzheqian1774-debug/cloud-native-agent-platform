import type {
  ExecutionState,
  SharedExecutionSnapshot,
  SnapshotEdge,
  SnapshotNode,
} from "../shared/executionSnapshotTypes";

export type PreviewMode = "live" | "synthetic-preview";
export type LiveFailureState = "DENIED" | "NOT_FOUND" | "AUTHORITY_MISSING" | "ERROR";

export class ExecutionPreviewError extends Error {
  readonly state: LiveFailureState;
  readonly reasonCode: string;

  constructor(state: LiveFailureState, reasonCode: string) {
    super(reasonCode);
    this.state = state;
    this.reasonCode = reasonCode;
  }
}

interface BackendResponse {
  schemaVersion: 1;
  state: "COMPLETE" | "PARTIAL" | "STALE";
  sharedSnapshotId: string;
  graphSnapshotId: string;
  platformExecutionIdentity: string;
  snapshot: Record<string, unknown>;
}

interface BackendNode {
  node_id: string;
  node_type: string;
  label_key: string;
  phase: string;
  visibility: "PRODUCT" | "TECHNICAL" | "BOTH" | "DETAIL_ONLY";
  evidence_ids: string[];
  limitation_codes: string[];
}

interface BackendRelation {
  relation_id: string;
  source_node_id: string;
  target_node_id: string;
  relation_types: string[];
  direction: "SOURCE_TO_TARGET";
  declared_cardinality: "ONE_TO_ONE" | "ONE_TO_MANY" | "MANY_TO_ONE" | "MANY_TO_MANY";
  evidence_ids: string[];
  projection_visibility: "PRODUCT" | "TECHNICAL" | "BOTH" | "DETAIL_ONLY";
}

function object(value: unknown, code: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new ExecutionPreviewError("ERROR", code);
  return value as Record<string, unknown>;
}

function string(value: unknown, code: string): string {
  if (typeof value !== "string" || !value) throw new ExecutionPreviewError("ERROR", code);
  return value;
}

function phase(value: string): ExecutionState {
  return (["PENDING", "RUNNING", "SUCCEEDED", "FAILED", "DENIED", "SKIPPED", "BLOCKED", "UNKNOWN"].includes(value)
    ? value === "SUCCEEDED" ? "COMPLETED" : value
    : "UNKNOWN") as ExecutionState;
}

export async function fetchExecutionPreview(
  namespace: string,
  workflowName: string,
  taskName: string,
  signal?: AbortSignal,
): Promise<SharedExecutionSnapshot> {
  const url = `/api/internal/preview/v1/executions/${encodeURIComponent(namespace)}/${encodeURIComponent(workflowName)}/${encodeURIComponent(taskName)}`;
  let response: Response;
  try {
    response = await fetch(url, { headers: { Accept: "application/json" }, signal });
  } catch {
    throw new ExecutionPreviewError("ERROR", "PREVIEW_NETWORK_UNAVAILABLE");
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = object(object(payload, "PREVIEW_ERROR_ENVELOPE_INVALID").detail, "PREVIEW_ERROR_ENVELOPE_INVALID");
    const state = string(detail.state, "PREVIEW_ERROR_STATE_INVALID") as LiveFailureState;
    if (!["DENIED", "NOT_FOUND", "AUTHORITY_MISSING", "ERROR"].includes(state)) throw new ExecutionPreviewError("ERROR", "PREVIEW_ERROR_STATE_INVALID");
    throw new ExecutionPreviewError(state, string(detail.reasonCode, "PREVIEW_ERROR_REASON_INVALID"));
  }
  const result = payload as BackendResponse;
  if (result.schemaVersion !== 1 || !["COMPLETE", "PARTIAL", "STALE"].includes(result.state)) throw new ExecutionPreviewError("ERROR", "PREVIEW_VERSION_OR_STATE_INVALID");
  const source = object(result.snapshot, "PREVIEW_SNAPSHOT_INVALID");
  const graph = object(source.graph, "PREVIEW_GRAPH_INVALID");
  const graphNodes = graph.nodes as BackendNode[];
  const graphRelations = graph.relations as BackendRelation[];
  if (!Array.isArray(graphNodes) || !Array.isArray(graphRelations)) throw new ExecutionPreviewError("ERROR", "PREVIEW_GRAPH_INVALID");
  const nodes: SnapshotNode[] = graphNodes.map((node) => ({
    id: node.node_id,
    type: node.node_type,
    labelKey: node.label_key,
    phase: phase(node.phase),
    visibility: node.visibility,
    evidenceIds: node.evidence_ids,
    limitationCodes: node.limitation_codes,
  }));
  const edges: SnapshotEdge[] = graphRelations.map((relation) => ({
    id: relation.relation_id,
    source: relation.source_node_id,
    target: relation.target_node_id,
    rawRelations: relation.relation_types.map((type) => ({
      id: `${relation.relation_id}:${type}`,
      source: relation.source_node_id,
      target: relation.target_node_id,
      type,
      direction: relation.direction,
      cardinality: relation.declared_cardinality,
      evidenceIds: relation.evidence_ids,
      visibility: relation.projection_visibility,
    })),
  }));
  const authorization = object(source.authorization, "PREVIEW_AUTHORIZATION_INVALID");
  const outcome = object(source.outcome, "PREVIEW_OUTCOME_INVALID");
  const runtime = object(source.runtime, "PREVIEW_RUNTIME_INVALID");
  const sourceVersions = object(source.sourceVersions, "PREVIEW_SOURCE_VERSIONS_INVALID");
  const workflow = object(sourceVersions.workflow, "PREVIEW_WORKFLOW_VERSION_INVALID");
  const taskVersions = sourceVersions.tasks as Array<Record<string, unknown>>;
  const selectedTask = Array.isArray(taskVersions) ? taskVersions.find((item) => item.name === taskName) ?? taskVersions[0] : undefined;
  if (!selectedTask) throw new ExecutionPreviewError("ERROR", "PREVIEW_TASK_VERSION_INVALID");
  const decision = string(authorization.decision, "PREVIEW_AUTHORIZATION_INVALID") as "ALLOW" | "DENY";
  const calls = authorization.providerCallCount;
  const citations = source.citations as string[];
  if (!Number.isInteger(calls) || !Array.isArray(citations) || (decision === "DENY" && (calls !== 0 || citations.length))) throw new ExecutionPreviewError("ERROR", "DENY_REQUIRES_ZERO_PROVIDER_EFFECTS");
  const executionId = result.platformExecutionIdentity;
  const workflowId = string(workflow.name, "PREVIEW_WORKFLOW_VERSION_INVALID");
  const taskId = string(selectedTask.name, "PREVIEW_TASK_VERSION_INVALID");
  const revisionId = string(workflow.resourceVersion, "PREVIEW_WORKFLOW_VERSION_INVALID");
  const outcomeClassification = string(outcome.classification, "PREVIEW_OUTCOME_INVALID");
  const outcomeStatus = outcomeClassification === "SUCCEEDED" ? "PASS" : outcomeClassification === "UNKNOWN" ? "UNKNOWN" : "FAIL";
  return {
    snapshotKind: "AUTHORIZED_LIVE_EXECUTION_SNAPSHOT",
    readModelState: result.state,
    sharedSnapshotId: result.sharedSnapshotId,
    classification: ["DETERMINISTIC", "LIVE", "TECHNICAL_PREVIEW"],
    selectedContext: { employeeId: "definition.live.native", revisionId, workId: workflowId, workflowId, taskId, executionId, graphSnapshotId: result.graphSnapshotId },
    questionKey: "live.execution.question",
    questions: [],
    correctionRevision: revisionId,
    taskKeys: [taskId],
    employees: [{ id: "definition.live.native", nameKey: "live.employee.name", roleKey: "live.employee.role", descriptionKey: "live.employee.description", responsibilityKeys: [], allowedKeys: [], prohibitedKeys: [], capabilities: [], runtimeId: "NATIVE", previewInstanceCount: 1, previewState: result.state }],
    nodes,
    edges,
    groups: [],
    approval: { state: "APPROVED", decidedAt: null, decisionFingerprint: result.sharedSnapshotId },
    authorization: { decision, reasonCode: string(authorization.reasonCode, "PREVIEW_AUTHORIZATION_INVALID"), providerCallCount: calls as number, requestId: result.sharedSnapshotId },
    outcome: { id: string(outcome.reference ?? `outcome.${executionId}`, "PREVIEW_OUTCOME_INVALID"), status: outcomeStatus, summaryKey: `live.outcome.${outcomeStatus.toLowerCase()}`, evidenceIds: (source.evidence as Array<Record<string, unknown>>).map((item) => string(item.recordId, "PREVIEW_EVIDENCE_INVALID")) },
    citations: citations.map((id) => ({ citationId: id, evidenceId: id, assetId: id, revisionId, labelKey: "live.citation" })),
    runtimeSupport: [{ id: "NATIVE", classification: string(runtime.classification, "PREVIEW_RUNTIME_INVALID"), availability: "LIVE_EVIDENCE", support: "NOT_CERTIFIED", providerCorrelationId: runtime.providerCorrelationId as string | null }],
    requestedRuntimeId: "NATIVE",
    effectiveRuntimeId: "NATIVE",
    definition: { id: "definition.live.native", revisionId },
    instances: [{ id: "instance.live.native", eligible: true, selected: true, reasonCode: "LIVE_NATIVE_SELECTION" }],
    conditions: [{ owner: "execution-evidence", state: result.state === "COMPLETE" && outcomeStatus === "PASS" ? "COMPLETED" : outcomeStatus === "UNKNOWN" ? "UNKNOWN" : result.state === "COMPLETE" ? "FAILED" : "UNAVAILABLE", reasonCode: result.state }],
    recovery: { state: "DOWNSTREAM", reasonCode: "EXACTLY_ONCE_NOT_CLAIMED", exactlyOnce: false },
    limitations: source.limitationCodes as string[],
  };
}
