# S5 v0.2 Architecture Evidence Baseline

This directory is the durable architecture record integrated by S5-REL-001.
It preserves accepted architecture separately from current implementation.
Source code and tests remain authoritative for implemented behavior.

## Accepted architecture

- [Digital Employee Golden Demo Scope and Acceptance Candidate v1](../../../S5-ARCH-006-DIGITAL-EMPLOYEE-GOLDEN-DEMO-V1.md)
  defines the S5-ARCH-006 Product Demo scope, layered acceptance contract,
  implementation gap map, and portfolio handoff. Its Human Golden Demo Scope
  Gate passed with constraints; the Session is `CLOSING / READY_TO_CLOSE`,
  pending Human Close Confirmation, and authorizes no implementation or freeze.
- [Runtime Provider Architecture v1](baselines/s5-arch-002-runtime-provider-architecture-v1.md)
  defines the accepted Runtime Provider model. Its acceptance does not freeze the
  Runtime Contract or certify a Provider.
- [Core Contract Convergence v1](baselines/s5-arch-003-core-contract-convergence-v1.md)
  records the reasoning for D30–D36 and AP-S5-001/AP-S5-010/AP-S5-011.
- [S5-ARCH-003 Closeout](closeouts/s5-arch-003-closeout.md) records the final
  human decisions: D30–D36 accepted, D32 Option C, and AP-S5-001/AP-S5-010/
  AP-S5-011 accepted.

## History and closeouts

- [Historical D1–D16 reconciliation](history/s5-arch-001-baseline-reconciliation-v1.md)
  preserves `HISTORICAL_FORMAL_EXECUTION: NOT_VERIFIED`, architecture continuity
  `CONTINUOUS_WITH_REFINEMENTS`, and a passed retroactive-fiction check.
- [S5-ARCH-001 Closeout](closeouts/s5-arch-001-closeout.md)
- [S5-ARCH-002 Closeout](closeouts/s5-arch-002-closeout.md)

## Contract and certification state

- Runtime Contract: `NOT FROZEN`.
- Capability Contract: `NOT FROZEN`.
- `G-S5-RUNTIME-FREEZE-01`: `FAIL / UNCHANGED`.
- Native Runtime: reference / Golden Path candidate.
- OpenClaw: heterogeneous Runtime / shared-Gateway proof candidate.
- Hermes: experimental Managed Runtime candidate, not currently certifiable,
  and not a v0.2 Golden Demo blocker.

Supporting success, failure, and debt evidence is indexed under
[S5 evidence](../../../docs/evidence/s5/README.md). Artifact-level source
provenance is recorded in the
[S5-REL-001 integration manifest](../../../S5-REL-001-INTEGRATION-MANIFEST.md).
