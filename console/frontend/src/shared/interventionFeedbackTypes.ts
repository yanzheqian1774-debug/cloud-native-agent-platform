export type CaptureProvenance = "LIVE_EXECUTION" | "SYNTHETIC_PREVIEW";
export type InterventionLifecycle = "RECORDED" | "EXCLUDED" | "RETAINED" | "TOMBSTONED";
export type OutcomeAssessment = "SATISFIED" | "PARTIALLY_SATISFIED" | "UNSATISFIED";
export type FeedbackReasonCode = "MISSING_TASK" | "EXTRA_TASK" | "WRONG_DATA" | "INSUFFICIENT_DATA" | "WRONG_KNOWLEDGE" | "WRONG_ROLE" | "WRONG_SKILL" | "WRONG_CAPABILITY" | "WRONG_ORDER" | "MISSING_CONSTRAINT" | "WRONG_OUTPUT_FORMAT" | "CITATION_NOT_USEFUL";

export interface InterventionFeedbackIdentity {
  journeyId: string;
  tenantId: string;
  securityDomain: string;
  predecessorRevisionId: string | null;
  successorRevisionId: string;
  platformExecutionIdentity: string;
  outcomeId: string;
  evidenceIds: string[];
  provenance: CaptureProvenance;
}

export interface InterventionEventRecord {
  schemaVersion: 1;
  recordId: string;
  interventionEventId: string;
  recordDigest: string;
  lifecycle: InterventionLifecycle;
  supersedesRecordId: string | null;
  journeyId: string;
  predecessorRevisionId: string;
  predecessorRevisionDigest: string;
  successorRevisionId: string;
  successorRevisionDigest: string;
  affectedElementReference: string;
  correctionPatchReference: string;
  eventKind: string;
  reasonCode: string;
  principalId: string;
  decisionTime: string;
  tenantId: string;
  securityDomain: string;
  platformExecutionIdentity: string;
  outcomeId: string;
  executionEvidenceIds: string[];
  provenance: CaptureProvenance;
  optimizationUseConsentDecision: "GRANTED" | "DENIED";
}

export interface OutcomeFeedbackRecord {
  schemaVersion: 1;
  feedbackId: string;
  feedbackDigest: string;
  revision: number;
  supersedesFeedbackId: string | null;
  journeyId: string;
  canonicalWorkflowRevisionId: string;
  platformExecutionIdentity: string;
  outcomeId: string;
  evidenceId: string;
  assessment: OutcomeAssessment;
  reasonCodes: FeedbackReasonCode[];
  principalId: string;
  decisionTime: string;
  tenantId: string;
  securityDomain: string;
  provenance: CaptureProvenance;
}

export interface OutcomeFeedbackView {
  lifecycle: "RECORDED" | "SUPERSEDED";
  record: OutcomeFeedbackRecord;
}

export interface InterventionFeedbackProjection {
  projection: "PRODUCT" | "TECHNICAL";
  identity: InterventionFeedbackIdentity;
  interventions: InterventionEventRecord[];
  outcomeFeedback: OutcomeFeedbackView[];
}

export interface InterventionFeedbackResponse {
  schemaVersion: 1;
  state: "READY";
  reasonCode: "INTERVENTION_FEEDBACK_READY";
  product: InterventionFeedbackProjection;
  technical: InterventionFeedbackProjection;
}

export interface InterventionCaptureCommand {
  predecessorRevisionId: string;
  successorRevisionId: string;
  outcomeId: string;
  evidenceId: string;
  eventKind: "CONSTRAINT_CHANGED";
  affectedElementReference: "CONSTRAINT";
  correctionPatchReference: "CONSTRAINT_PATCH";
  reasonCode: "MISSING_CONSTRAINT";
  optimizationUseConsentDecision: "GRANTED" | "DENIED";
}

export interface OutcomeFeedbackCommand {
  outcomeId: string;
  evidenceId: string;
  assessment: OutcomeAssessment;
  reasonCodes: FeedbackReasonCode[];
  supersedesFeedbackId: string | null;
}
