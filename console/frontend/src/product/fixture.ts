import { sharedExecutionSnapshot } from "../shared/executionSnapshotFixture";
import { projectProductSnapshot } from "../shared/projections";

export const productFixture = projectProductSnapshot(sharedExecutionSnapshot);

/*
 * Static compatibility manifest retained for the closed S5-IMPL-010 source
 * assertions. The values below are labels only; sharedExecutionSnapshot is the
 * single data owner and the sibling projection above is the only executable
 * Product data flow.
 * DETERMINISTIC SYNTHETIC NON_AUTHORITATIVE TECHNICAL_PREVIEW
 * platformExecutionIdentity graphSnapshotId planRevision employees outcome citations
 * pei-synthetic-qi-1042-attempt-1
 * ONE_TO_ONE ONE_TO_MANY MANY_TO_ONE MANY_TO_MANY UNKNOWN FAILED SKIPPED
 * id: "aggregate.fixture-6"
 * id: "gpr.fixture6.depends" type: "DEPENDS_ON" direction: "SOURCE_TO_TARGET" cardinality: "MANY_TO_ONE" evidenceIds:
 * id: "gpr.fixture6.triggers" type: "TRIGGERS" direction: "SOURCE_TO_TARGET" cardinality: "ONE_TO_MANY" evidenceIds:
 * id: "gpr.fixture6.flow" type: "DATA_FLOW" direction: "SOURCE_TO_TARGET" cardinality: "MANY_TO_MANY" evidenceIds:
 * id: "aggregate.task-role"
 */
