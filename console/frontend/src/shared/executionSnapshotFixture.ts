import type { SharedExecutionSnapshot } from "./executionSnapshotTypes.ts";

function deepFreeze<T>(value: T): Readonly<T> {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    Object.values(value).forEach((item) => deepFreeze(item));
  }
  return value;
}

const snapshot: SharedExecutionSnapshot = {
  snapshotKind: "BOUNDED_SYNTHETIC_FRONTEND_SNAPSHOT",
  classification: ["DETERMINISTIC", "SYNTHETIC", "NON_AUTHORITATIVE", "TECHNICAL_PREVIEW", "NO_NETWORK", "NO_RUNTIME_OR_PROVIDER_INVOCATION"],
  selectedContext: {
    employeeId: "de.synthetic.customer-insight.v1",
    revisionId: "plan-revision.synthetic.qi-1042.r1",
    workId: "work.synthetic.qi-1042",
    workflowId: "workflow.synthetic.complaint-analysis.v1",
    taskId: "task.synthetic.analyze",
    executionId: "pei-synthetic-qi-1042-attempt-1",
    graphSnapshotId: "gps:v0.2-candidate:fixture-6-product",
  },
  questionKey: "product.question.default",
  questions: ["product.question.default", "product.question.alternate"],
  correctionRevision: "plan-revision.synthetic.qi-1042.r2",
  taskKeys: ["product.task.collect", "product.task.analyze", "product.task.recommend"],
  employees: [
    { id: "de.synthetic.customer-insight.v1", nameKey: "product.employee.mira.name", roleKey: "product.employee.mira.role", descriptionKey: "product.employee.mira.description", responsibilityKeys: ["product.employee.mira.responsibility"], allowedKeys: ["product.employee.mira.allowed"], prohibitedKeys: ["product.employee.common.prohibited"], capabilities: ["CAPABILITY_SYNTHETIC_COMPLAINT_READ", "CAPABILITY_SYNTHETIC_SUMMARIZE"], runtimeId: "NATIVE", previewInstanceCount: 1, previewState: "SYNTHETIC_PREVIEW_NOT_ORCHESTRATED" },
    { id: "de.synthetic.quality-analysis.v1", nameKey: "product.employee.aria.name", roleKey: "product.employee.aria.role", descriptionKey: "product.employee.aria.description", responsibilityKeys: ["product.employee.aria.responsibility"], allowedKeys: ["product.employee.aria.allowed"], prohibitedKeys: ["product.employee.common.prohibited"], capabilities: ["CAPABILITY_SYNTHETIC_QUALITY_ANALYSIS"], runtimeId: "NATIVE", previewInstanceCount: 1, previewState: "SYNTHETIC_PREVIEW_NOT_ORCHESTRATED" },
  ],
  nodes: [
    { id: "problem.synthetic.qi-1042", type: "BUSINESS_PROBLEM", labelKey: "product.graph.problem", phase: "COMPLETED", visibility: "PRODUCT", evidenceIds: ["evidence.synthetic.plan.001"], limitationCodes: [] },
    { id: "plan-revision.synthetic.qi-1042.r1", type: "PLAN", labelKey: "product.graph.plan", phase: "COMPLETED", visibility: "BOTH", evidenceIds: ["evidence.synthetic.plan.001"], limitationCodes: [] },
    { id: "workflow.synthetic.complaint-analysis.v1", type: "WORKFLOW", labelKey: "product.graph.workflow", phase: "RUNNING", visibility: "BOTH", evidenceIds: ["evidence.synthetic.workflow.001"], limitationCodes: [] },
    { id: "task.synthetic.collect", type: "TASK", labelKey: "product.task.collect", phase: "COMPLETED", visibility: "BOTH", evidenceIds: ["evidence.synthetic.depends.006"], limitationCodes: [] },
    { id: "task.synthetic.analyze", type: "TASK", labelKey: "product.task.analyze", phase: "RUNNING", visibility: "BOTH", evidenceIds: ["evidence.synthetic.flow.006"], limitationCodes: [] },
    { id: "task.synthetic.recommend", type: "TASK", labelKey: "product.task.recommend", phase: "UNKNOWN", visibility: "BOTH", evidenceIds: [], limitationCodes: ["OUTCOME_NOT_YET_AVAILABLE"] },
    { id: "de.synthetic.customer-insight.v1", type: "DEFINITION", labelKey: "product.employee.mira.role", phase: "RUNNING", visibility: "BOTH", evidenceIds: ["evidence.synthetic.assignment.001"], limitationCodes: [] },
    { id: "instance.synthetic.customer-insight.001", type: "INSTANCE", labelKey: "product.graph.instance", phase: "RUNNING", visibility: "BOTH", evidenceIds: ["evidence.synthetic.instance.001"], limitationCodes: ["SINGLE_SYNTHETIC_INSTANCE_ONLY"] },
    { id: "runtime.synthetic.native.001", type: "RUNTIME_REALIZATION", labelKey: "technical.graph.runtime", phase: "RUNNING", visibility: "TECHNICAL", evidenceIds: ["evidence.synthetic.runtime.001"], limitationCodes: ["NOT_CERTIFIED"] },
    { id: "capability.synthetic.complaint-read", type: "CAPABILITY", labelKey: "technical.graph.capability", phase: "COMPLETED", visibility: "TECHNICAL", evidenceIds: ["evidence.synthetic.capability.001"], limitationCodes: ["SYNTHETIC_PROVIDER_EVIDENCE"] },
    { id: "approval.synthetic.plan-r1", type: "APPROVAL", labelKey: "technical.graph.approval", phase: "BLOCKED", visibility: "TECHNICAL", evidenceIds: ["evidence.synthetic.approval.001"], limitationCodes: [] },
    { id: "knowledge-asset.synthetic.quality.v1", type: "KNOWLEDGE", labelKey: "technical.graph.knowledge", phase: "COMPLETED", visibility: "TECHNICAL", evidenceIds: ["evidence.synthetic.quality.002"], limitationCodes: ["SYNTHETIC_KNOWLEDGE_ONLY"] },
    { id: "outcome.synthetic.qi-1042", type: "OUTCOME", labelKey: "product.graph.outcome", phase: "UNKNOWN", visibility: "BOTH", evidenceIds: ["evidence.synthetic.quality.002"], limitationCodes: ["OUTCOME_PRESENTATION_ONLY"] },
  ],
  edges: [
    { id: "aggregate.problem-plan", source: "problem.synthetic.qi-1042", target: "plan-revision.synthetic.qi-1042.r1", rawRelations: [{ id: "gpr.problem-plan", source: "problem.synthetic.qi-1042", target: "plan-revision.synthetic.qi-1042.r1", type: "DECOMPOSES_TO", direction: "SOURCE_TO_TARGET", cardinality: "ONE_TO_ONE", evidenceIds: ["evidence.synthetic.plan.001"], visibility: "PRODUCT" }] },
    { id: "aggregate.plan-workflow", source: "plan-revision.synthetic.qi-1042.r1", target: "workflow.synthetic.complaint-analysis.v1", rawRelations: [{ id: "gpr.plan-workflow", source: "plan-revision.synthetic.qi-1042.r1", target: "workflow.synthetic.complaint-analysis.v1", type: "CONTAINS", direction: "SOURCE_TO_TARGET", cardinality: "ONE_TO_ONE", evidenceIds: ["evidence.synthetic.workflow.001"], visibility: "BOTH" }] },
    { id: "aggregate.fixture-6", source: "task.synthetic.analyze", target: "task.synthetic.collect", rawRelations: [
      { id: "gpr.fixture6.depends", source: "task.synthetic.analyze", target: "task.synthetic.collect", type: "DEPENDS_ON", direction: "SOURCE_TO_TARGET", cardinality: "MANY_TO_ONE", evidenceIds: ["evidence.synthetic.depends.006"], visibility: "BOTH" },
      { id: "gpr.fixture6.triggers", source: "task.synthetic.analyze", target: "task.synthetic.collect", type: "TRIGGERS", direction: "SOURCE_TO_TARGET", cardinality: "ONE_TO_MANY", evidenceIds: ["evidence.synthetic.triggers.006"], visibility: "BOTH" },
      { id: "gpr.fixture6.flow", source: "task.synthetic.analyze", target: "task.synthetic.collect", type: "DATA_FLOW", direction: "SOURCE_TO_TARGET", cardinality: "MANY_TO_MANY", evidenceIds: ["evidence.synthetic.flow.006"], visibility: "BOTH" },
    ] },
    { id: "aggregate.task-role", source: "task.synthetic.analyze", target: "de.synthetic.customer-insight.v1", rawRelations: [{ id: "gpr.task-role", source: "task.synthetic.analyze", target: "de.synthetic.customer-insight.v1", type: "ASSIGNED_TO", direction: "SOURCE_TO_TARGET", cardinality: "MANY_TO_ONE", evidenceIds: ["evidence.synthetic.assignment.001"], visibility: "BOTH" }] },
    { id: "aggregate.role-instance", source: "de.synthetic.customer-insight.v1", target: "instance.synthetic.customer-insight.001", rawRelations: [{ id: "gpr.role-instance", source: "de.synthetic.customer-insight.v1", target: "instance.synthetic.customer-insight.001", type: "EXECUTED_BY", direction: "SOURCE_TO_TARGET", cardinality: "ONE_TO_MANY", evidenceIds: ["evidence.synthetic.instance.001"], visibility: "BOTH" }] },
    { id: "aggregate-workflow-outcome", source: "workflow.synthetic.complaint-analysis.v1", target: "outcome.synthetic.qi-1042", rawRelations: [{ id: "gpr.workflow-outcome", source: "workflow.synthetic.complaint-analysis.v1", target: "outcome.synthetic.qi-1042", type: "PRODUCES", direction: "SOURCE_TO_TARGET", cardinality: "MANY_TO_ONE", evidenceIds: ["evidence.synthetic.outcome.001"], visibility: "BOTH" }] },
    { id: "aggregate-instance-runtime", source: "instance.synthetic.customer-insight.001", target: "runtime.synthetic.native.001", rawRelations: [{ id: "gpr.instance-runtime", source: "instance.synthetic.customer-insight.001", target: "runtime.synthetic.native.001", type: "EXECUTED_BY", direction: "SOURCE_TO_TARGET", cardinality: "MANY_TO_ONE", evidenceIds: ["evidence.synthetic.runtime.001"], visibility: "TECHNICAL" }] },
    { id: "aggregate-task-capability", source: "task.synthetic.analyze", target: "capability.synthetic.complaint-read", rawRelations: [{ id: "gpr.task-capability", source: "task.synthetic.analyze", target: "capability.synthetic.complaint-read", type: "REQUESTS", direction: "SOURCE_TO_TARGET", cardinality: "MANY_TO_MANY", evidenceIds: ["evidence.synthetic.capability.001"], visibility: "TECHNICAL" }] },
    { id: "aggregate-capability-approval", source: "capability.synthetic.complaint-read", target: "approval.synthetic.plan-r1", rawRelations: [{ id: "gpr.capability-approval", source: "capability.synthetic.complaint-read", target: "approval.synthetic.plan-r1", type: "AUTHORIZED_BY", direction: "SOURCE_TO_TARGET", cardinality: "MANY_TO_ONE", evidenceIds: ["evidence.synthetic.approval.001"], visibility: "TECHNICAL" }] },
    { id: "aggregate-task-knowledge", source: "task.synthetic.analyze", target: "knowledge-asset.synthetic.quality.v1", rawRelations: [{ id: "gpr.task-knowledge", source: "task.synthetic.analyze", target: "knowledge-asset.synthetic.quality.v1", type: "REFERENCES", direction: "SOURCE_TO_TARGET", cardinality: "MANY_TO_MANY", evidenceIds: ["evidence.synthetic.quality.002"], visibility: "TECHNICAL" }] },
  ],
  groups: [],
  approval: { state: "PENDING_HUMAN_REVIEW", decidedAt: null, decisionFingerprint: "sha256:synthetic-plan-r1" },
  authorization: { decision: "ALLOW", reasonCode: "SYNTHETIC_POLICY_ALLOW", providerCallCount: 1, requestId: "capability-request.synthetic.qi-1042.001" },
  outcome: { id: "outcome.synthetic.qi-1042", status: "PASS", summaryKey: "product.outcome.summary", evidenceIds: ["evidence.synthetic.complaints.001", "evidence.synthetic.quality.002"] },
  citations: [{ citationId: "citation.synthetic.quality.001", evidenceId: "evidence.synthetic.quality.002", assetId: "knowledge-asset.synthetic.quality.v1", revisionId: "revision.synthetic.quality.v1", labelKey: "product.citation.quality" }],
  runtimeSupport: [
    { id: "NATIVE", classification: "COMPONENT_TESTED_CANDIDATE", availability: "AVAILABLE", support: "NOT_CERTIFIED", providerCorrelationId: "provider-correlation.synthetic.native.001" },
    { id: "OPENCLAW", classification: "EXPERIMENTAL", availability: "CURRENTLY_UNAVAILABLE", support: "SUPPORT_NOT_GRANTED", providerCorrelationId: null },
    { id: "HERMES", classification: "EXPERIMENTAL", availability: "NOT_CURRENTLY_CERTIFIABLE", support: "SUPPORT_NOT_GRANTED", providerCorrelationId: null },
  ],
  requestedRuntimeId: "NATIVE",
  effectiveRuntimeId: "NATIVE",
  definition: { id: "de.synthetic.customer-insight.v1", revisionId: "plan-revision.synthetic.qi-1042.r1" },
  instances: [{ id: "instance.synthetic.customer-insight.001", eligible: true, selected: true, reasonCode: "SYNTHETIC_ELIGIBLE_NATIVE" }],
  conditions: [
    { owner: "INSTANCE", state: "RUNNING", reasonCode: "SYNTHETIC_PREVIEW_ONLY" },
    { owner: "TASK", state: "RUNNING", reasonCode: "PRESENTATION_NOT_EXECUTION" },
    { owner: "WORKFLOW", state: "UNKNOWN", reasonCode: "NO_LIVE_ORCHESTRATION" },
  ],
  recovery: { state: "DOWNSTREAM", reasonCode: "RECOVERY_ORCHESTRATION_NOT_IMPLEMENTED", exactlyOnce: false },
  limitations: ["SYNTHETIC_KNOWLEDGE_ONLY", "NO_LIVE_RUNTIME", "NO_LIVE_PROVIDER", "NO_RECOVERY_ORCHESTRATION", "NO_EXACTLY_ONCE_CLAIM"],
};

export const sharedExecutionSnapshot = deepFreeze(snapshot) as SharedExecutionSnapshot;
export const defaultSelectedExecutionContext = sharedExecutionSnapshot.selectedContext;
