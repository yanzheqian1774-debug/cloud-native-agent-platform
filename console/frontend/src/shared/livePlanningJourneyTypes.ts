export type JourneyState = "LIVE" | "STALE" | "DENIED" | "UNAVAILABLE" | "ERROR";
export type KnowledgeState = "AVAILABLE" | "STALE" | "EXPIRED" | "DENIED" | "NOT_FOUND" | "UNAVAILABLE" | "ERROR";

export interface JourneyIdentity {
  tenantId: string; securityDomain: string; canonicalWorkflowRevisionId: string;
  canonicalDigest: string; sharedSnapshotId: string; graphSnapshotId: string;
  platformExecutionIdentity: string | null; approvalId: string; placementDecisionId: string;
  evidenceIds: string[]; citationIds: string[];
}

export interface JourneyCitation {
  citationId: string; retrievalEvidenceId: string; authorizationDecisionId: string;
  knowledgePackId: string; knowledgePackVersion: string; knowledgePackDigest: string;
  documentId: string; documentVersion: string; documentDigest: string;
  sectionId: string; chunkId: string; status: "AVAILABLE" | "STALE";
}

export interface JourneyOutcome {
  outcomeId: string; classification: "SUCCEEDED" | "FAILED" | "UNKNOWN";
  summary: string; comparableMetric: string; comparableValue: number | null;
}

export interface JourneyRevision {
  revision: number; predecessorRevisionId: string | null; objective: string;
  lifecycle: "PENDING_APPROVAL" | "APPROVED" | "EXECUTABLE" | "SUPERSEDED";
  approvalState: "PENDING" | "APPROVED" | "REJECTED"; identity: JourneyIdentity;
  planTaskIds: string[]; matchState: "MATCHED" | "PARTIAL" | "ROLE_GAP" | "DENIED" | "ERROR";
  placementState: "PLACED" | "UNAVAILABLE" | "STALE" | "DENIED" | "ERROR";
  knowledgeState: KnowledgeState;
  executionState: "NOT_REQUESTED" | "AUTHORIZED_HANDOFF" | "RUNNING" | "SUCCEEDED" | "FAILED" | "UNAVAILABLE";
  answer: string | null; citations: JourneyCitation[]; outcome: JourneyOutcome | null; limitationCodes: string[];
}

export interface JourneyProjection { projection: "PRODUCT" | "TECHNICAL"; identity: JourneyIdentity; revision: JourneyRevision; }

export interface LivePlanningJourney {
  schemaVersion: 1; journeyId: string; state: JourneyState;
  provenance: "LIVE_EXECUTION" | "SYNTHETIC_PREVIEW"; reasonCode: string;
  product: JourneyProjection; technical: JourneyProjection;
  predecessor: JourneyRevision | null; successor: JourneyRevision;
}
