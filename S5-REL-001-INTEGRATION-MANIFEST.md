# S5-REL-001 Integration Manifest

SESSION_ID: S5-REL-001

INTEGRATED_BY: S5-REL-001

FINAL_SESSION_STATUS: `REVIEW / PASS / INTEGRATION_READY_FOR_HUMAN_GATE`

This manifest records artifact-level extraction from historical PRs #33–#38.
The integration commit is not the original evidence commit. Source branches and
commits remain provenance; no historical PR head was merged or cherry-picked.

## Source sessions

| Session | Source PR | Source branch | Source head commit | Final source-session status |
|---|---:|---|---|---|
| S5-TEST-001 / Hermes Contract Verification | #33 | `codex/s5-test-001-hermes-contract-verification` | `703d909afe9434a620ec16ab1bc69e1f6347b7d0` | `STOP / MORE_EVIDENCE_REQUIRED`; Hermes experimental and not currently certifiable |
| S5-ARCH-002 | #34 | `codex/s5-arch-002-runtime-provider-architecture` | `f49b82709cf3fb9eb80cabfee402bba45f5efb5e` | `CLOSED / PASS` |
| S5-SPIKE-004 | #35 | `codex/s5-spike-004-agent-instance-routing` | `fe827b1ee8609d177e76deebd2d88e79dd5545cb` | `CLOSED / PASS` |
| S5-SPIKE-003 | #36 | `codex/s5-spike-003-capability-contract` | `4dc49a60d96f6a6715d91c26babceff51034d142` | `CLOSED / PASS` |
| S5-ARCH-003 | #37 | `codex/s5-arch-003-core-contract-convergence` | `2ea93dcb8e2078767acb105bfc012e82b4d89d5f` | `CLOSED / PASS` |
| S5-ARCH-001 | #38 | `codex/s5-arch-001-baseline-reconciliation` | `f8c2dbcdd1945050749981f04f377aca98e6a35d` | `CLOSED / PASS` |

## Artifact mapping

`Source commit` is the final source head from which the exact artifact blob was
extracted. `PRESERVED_DURABLE` means the artifact is included in this integration;
it does not claim that experimental conclusions are Production implementation.

Artifact text is preserved from the named source snapshots. Two source files,
`checkpoint-b-live.md` and `ed-s5-001-closure.md`, had one excess blank line at
EOF removed to satisfy repository diff hygiene. This formatting-only normalization
does not change evidence text, authorship, chronology, status, or conclusions.

| Session | PR | Source commit | Source artifact | Durable repository artifact | Classification | Final disposition |
|---|---:|---|---|---|---|---|
| S5-TEST-001 | #33 | `703d909` | `experiments/s5-spike-001-runtime-hermes/README.md` | `docs/evidence/s5/runtime/hermes/README.md` | `SPIKE_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-TEST-001 | #33 | `703d909` | `experiments/s5-spike-001-runtime-hermes/evidence/checkpoint-a-environment.md` | `docs/evidence/s5/runtime/hermes/evidence/checkpoint-a-environment.md` | `SPIKE_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-TEST-001 | #33 | `703d909` | `experiments/s5-spike-001-runtime-hermes/evidence/checkpoint-a2-live.md` | `docs/evidence/s5/runtime/hermes/evidence/checkpoint-a2-live.md` | `SPIKE_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-TEST-001 | #33 | `703d909` | `experiments/s5-spike-001-runtime-hermes/evidence/checkpoint-b-live.md` | `docs/evidence/s5/runtime/hermes/evidence/checkpoint-b-live.md` | `TEST_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-TEST-001 | #33 | `703d909` | `experiments/s5-spike-001-runtime-hermes/evidence/checkpoint-c-synthesis.md` | `docs/evidence/s5/runtime/hermes/evidence/checkpoint-c-synthesis.md` | `SPIKE_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-TEST-001 | #33 | `703d909` | `experiments/s5-spike-001-runtime-hermes/evidence/ed-s5-001-closure.md` | `docs/evidence/s5/runtime/hermes/evidence/ed-s5-001-closure.md` | `FAILURE_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-TEST-001 | #33 | `703d909` | `experiments/s5-spike-001-runtime-hermes/evidence/ed-s5-001-controlled-retry-2.md` | `docs/evidence/s5/runtime/hermes/evidence/ed-s5-001-controlled-retry-2.md` | `FAILURE_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-TEST-001 | #33 | `703d909` | `experiments/s5-spike-001-runtime-hermes/evidence/evidence-debt.md` | `docs/evidence/s5/runtime/hermes/evidence/evidence-debt.md` | `FAILURE_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-TEST-001 | #33 | `703d909` | `experiments/s5-spike-001-runtime-hermes/facts/hermes-facts.md` | `docs/evidence/s5/runtime/hermes/facts/hermes-facts.md` | `SPIKE_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-TEST-001 | #33 | `703d909` | `experiments/s5-test-001-runtime-contract/ED-S5-001-BOUNDED-DIAGNOSTIC-RESULT.md` | `docs/evidence/s5/runtime/hermes/verification/ED-S5-001-BOUNDED-DIAGNOSTIC-RESULT.md` | `FAILURE_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-TEST-001 | #33 | `703d909` | `experiments/s5-test-001-runtime-contract/S5-TEST-001-RESULT.md` | `docs/evidence/s5/runtime/hermes/verification/S5-TEST-001-RESULT.md` | `TEST_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-ARCH-002 | #34 | `f49b827` | `S5-ARCH-002-RUNTIME-PROVIDER-ARCHITECTURE-V1.md` | `architecture/s5/v0.2/baselines/s5-arch-002-runtime-provider-architecture-v1.md` | `ARCHITECTURE_BASELINE` | `PRESERVED_DURABLE` |
| S5-ARCH-002 | #34 | `f49b827` | `S5-ARCH-002-CLOSEOUT.md` | `architecture/s5/v0.2/closeouts/s5-arch-002-closeout.md` | `CLOSEOUT_METADATA` | `PRESERVED_DURABLE` |
| S5-SPIKE-004 | #35 | `fe827b1` | `experiments/s5-spike-004-agent-instance-routing/README.md` | `docs/evidence/s5/agent-instance-routing/README.md` | `SPIKE_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-SPIKE-004 | #35 | `fe827b1` | `experiments/s5-spike-004-agent-instance-routing/S5-SPIKE-004-CHECKPOINT-A-RESULT.md` | `docs/evidence/s5/agent-instance-routing/S5-SPIKE-004-CHECKPOINT-A-RESULT.md` | `TEST_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-SPIKE-004 | #35 | `fe827b1` | `experiments/s5-spike-004-agent-instance-routing/S5-SPIKE-004-CHECKPOINT-B-RESULT.md` | `docs/evidence/s5/agent-instance-routing/S5-SPIKE-004-CHECKPOINT-B-RESULT.md` | `TEST_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-SPIKE-004 | #35 | `fe827b1` | `experiments/s5-spike-004-agent-instance-routing/S5-SPIKE-004-CHECKPOINT-C-RESULT.md` | `docs/evidence/s5/agent-instance-routing/S5-SPIKE-004-CHECKPOINT-C-RESULT.md` | `TEST_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-SPIKE-004 | #35 | `fe827b1` | `experiments/s5-spike-004-agent-instance-routing/S5-SPIKE-004-CLOSEOUT.md` | `docs/evidence/s5/agent-instance-routing/S5-SPIKE-004-CLOSEOUT.md` | `CLOSEOUT_METADATA` | `PRESERVED_DURABLE` |
| S5-SPIKE-003 | #36 | `4dc49a6` | `experiments/s5-spike-003-capability-contract/README.md` | `docs/evidence/s5/capability-contract/README.md` | `SPIKE_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-SPIKE-003 | #36 | `4dc49a6` | `experiments/s5-spike-003-capability-contract/S5-SPIKE-003-PLAN.md` | `docs/evidence/s5/capability-contract/S5-SPIKE-003-PLAN.md` | `SPIKE_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-SPIKE-003 | #36 | `4dc49a6` | `experiments/s5-spike-003-capability-contract/S5-SPIKE-003-CHECKPOINT-A-RESULT.md` | `docs/evidence/s5/capability-contract/S5-SPIKE-003-CHECKPOINT-A-RESULT.md` | `TEST_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-SPIKE-003 | #36 | `4dc49a6` | `experiments/s5-spike-003-capability-contract/S5-SPIKE-003-CHECKPOINT-B-RESULT.md` | `docs/evidence/s5/capability-contract/S5-SPIKE-003-CHECKPOINT-B-RESULT.md` | `TEST_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-SPIKE-003 | #36 | `4dc49a6` | `experiments/s5-spike-003-capability-contract/S5-SPIKE-003-CHECKPOINT-C-RESULT.md` | `docs/evidence/s5/capability-contract/S5-SPIKE-003-CHECKPOINT-C-RESULT.md` | `SPIKE_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-SPIKE-003 | #36 | `4dc49a6` | `experiments/s5-spike-003-capability-contract/S5-SPIKE-003-CLOSEOUT.md` | `docs/evidence/s5/capability-contract/S5-SPIKE-003-CLOSEOUT.md` | `CLOSEOUT_METADATA` | `PRESERVED_DURABLE` |
| S5-SPIKE-003 | #36 | `4dc49a6` | `experiments/s5-spike-003-capability-contract/evidence/S5-SPIKE-003-CHECKPOINT-A-EVIDENCE.json` | `docs/evidence/s5/capability-contract/evidence/S5-SPIKE-003-CHECKPOINT-A-EVIDENCE.json` | `TEST_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-SPIKE-003 | #36 | `4dc49a6` | `experiments/s5-spike-003-capability-contract/evidence/S5-SPIKE-003-CHECKPOINT-B-EVIDENCE.json` | `docs/evidence/s5/capability-contract/evidence/S5-SPIKE-003-CHECKPOINT-B-EVIDENCE.json` | `TEST_EVIDENCE` | `PRESERVED_DURABLE` |
| S5-ARCH-003 | #37 | `2ea93dc` | `S5-ARCH-003-CORE-CONTRACT-CONVERGENCE-V1.md` | `architecture/s5/v0.2/baselines/s5-arch-003-core-contract-convergence-v1.md` | `ARCHITECTURE_BASELINE` | `PRESERVED_DURABLE` |
| S5-ARCH-003 | #37 | `2ea93dc` | `S5-ARCH-003-CLOSEOUT.md` | `architecture/s5/v0.2/closeouts/s5-arch-003-closeout.md` | `CLOSEOUT_METADATA` | `PRESERVED_DURABLE` |
| S5-ARCH-001 | #38 | `f8c2dbc` | `S5-ARCH-001-BASELINE-RECONCILIATION-V1.md` | `architecture/s5/v0.2/history/s5-arch-001-baseline-reconciliation-v1.md` | `ARCHITECTURE_HISTORY` | `PRESERVED_DURABLE` |
| S5-ARCH-001 | #38 | `f8c2dbc` | `S5-ARCH-001-CLOSEOUT.md` | `architecture/s5/v0.2/closeouts/s5-arch-001-closeout.md` | `CLOSEOUT_METADATA` | `PRESERVED_DURABLE` |

## Excluded content

- #33: Hermes and Runtime Contract executable harness/provider/scripts/tests and
  the copied `prior-openclaw` subtree.
- #34: inherited Hermes files and commits.
- #35: spike-only Python implementation/tests and local `.gitignore`.
- #36: spike-only Capability/MCP/REST implementation/tests and inherited Hermes
  files and commits.
- #37: divergent Git ancestry; no durable artifact excluded.
- #38: duplicated S5-ARCH-003 baseline and divergent Git ancestry.

Experimental source imported: `0`.

## Preserved final state

- D30–D36: `ACCEPTED`; D32: `OPTION C`.
- AP-S5-001, AP-S5-010, and AP-S5-011: `ACCEPTED`.
- AP-S5-005 through AP-S5-008: `ACCEPTED`; AP-S5-009: `ACCEPTED` with its
  finalized conditional applicability.
- Runtime Contract: `NOT FROZEN`.
- Capability Contract: `NOT FROZEN`.
- `G-S5-RUNTIME-FREEZE-01`: `FAIL / UNCHANGED`.
- Hermes: `EXPERIMENTAL / NOT CURRENTLY CERTIFIABLE`; ED-S5-001 remains open.
- `HISTORICAL_FORMAL_EXECUTION: NOT_VERIFIED`.
- Architecture continuity: `CONTINUOUS_WITH_REFINEMENTS`.
- Retroactive-fiction check: `PASS`.

## Historical PR recommendation after integration verification

Subject to a separate Human Gate, recommend `CLOSE_WITHOUT_MERGE` for #33, #34,
#35, #36, #37, and #38 after this integration PR is verified and merged. No
historical PR is closed by S5-REL-001 artifact integration.
