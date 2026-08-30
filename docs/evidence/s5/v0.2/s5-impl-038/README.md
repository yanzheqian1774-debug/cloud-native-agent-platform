# S5-IMPL-038 — Checkpoint A Defect Correction Evidence

## Boundary and correction

This uncommitted G1 candidate corrects frontend handling of normal SSE closure
after a synchronously accepted terminal `journey-event.v1` envelope. The shared
subscriber now owns an authoritative synchronous stream state, validates every
delivery through the strict parser/reducer, closes immediately after terminal
acceptance, and ignores only the transport-close callback that follows that
accepted terminal state. A disconnect before terminal remains explicit
`JOURNEY_STREAM_UNAVAILABLE`.

The stream is bound to the requested journey, tenant and security domain.
Canonical revision and digest continuity is enforced between events, with a
change allowed only for `CORRECTION_ACCEPTED`. Envelope identity and payload
snapshot, execution, approval, Evidence and citation identifiers must agree.
Malformed schema, identity, digest, sequence, duplicate and post-terminal input
continues to fail closed. Component cleanup closes silently. There is no polling,
timer, reconnect, fixture, snapshot or synthetic fallback.

No backend, API, DTO, Package 7, bridge, Workflow, Runtime, Evidence, tenant,
authorization, dependency, lockfile, CI, architecture or governance behavior is
changed.

## Entry and collision evidence

- Worktree: `/Users/tristan/.codex/worktrees/486f/cloud-native-agent-platform`.
- Baseline, local HEAD and remote `main`:
  `ad438d1e535555715518214fe1b609492aaab601`.
- Exact-main CI `33291740512`: completed successfully for that SHA.
- Branch: `codex/s5-impl-038-terminal-sse-completion-state`, created from the
  exact baseline after branch, PR, issue and worktree collision checks returned
  no S5-IMPL-038 collision.
- S5-TEST-007 remained on its separate worktree with the same seven untracked
  authorized Package 8 paths. It was inspected read-only and never modified.

## Regression and validation evidence

- Focused frontend and existing backend stream matrix: `51 passed`; one existing
  Starlette/httpx deprecation warning.
- Frozen Package 8 acceptance and Package 7 compatibility matrix, executed
  read-only with caches disabled in the frozen worktree: `28 passed`; the same
  existing warning.
- Fresh external frontend copy using the locked dependency graph: `npm ci`,
  ESLint, TypeScript and Vite production build passed; npm reported zero
  vulnerabilities.
- Full `make check`: Ruff lint passed, Ruff format verification passed, and
  `943 passed`; the same existing warning.
- The regression matrix covers terminal success, terminal failure,
  `RESUME_UNAVAILABLE`, pre-terminal disconnect, malformed schema, journey,
  tenant/domain, revision/digest/snapshot mismatch, gap/reorder, byte-identical
  and conflicting duplicates, post-terminal delivery, repeated close, cleanup,
  Product/Technical shared consumption, and no timer/reconnect fallback.

All-files pre-commit, post-hook `make check`, terminal diff/status audit and the
final changed-path list are recorded in the Checkpoint A terminal handoff after
they are run against this Evidence file.

## Browser QA

The in-app Browser exercised the genuine checksum-validated Package 7 materialized
root through the existing backend start, correction, exact approval and rerun
contracts. No coordinator seed or frontend fixture was used.

- Product retained all six ordered events through terminal
  `EXECUTION_SUCCEEDED` after normal SSE closure and did not render an unavailable
  replacement.
- Technical retained the same six events, sequence, terminal disposition and
  backend identity spine without a false alert.
- All observed backend requests returned HTTP 200.
- No console warning/error was present during normal completion.
- No reconnect request appeared during the post-terminal observation window.
- Desktop Product and Technical views had zero horizontal overflow.
- At `390x844`, English and Simplified Chinese Product/Technical views retained
  terminal success, had zero horizontal overflow, and contained no
  `SYNTHETIC_PREVIEW` classification.

The deterministic reducer/subscriber matrix verifies terminal failure,
`RESUME_UNAVAILABLE`, and pre-terminal disconnect dispositions. The existing
backend API matrix verifies unknown/restart-lost resume as an HTTP 200 terminal
`RESUME_UNAVAILABLE`; broker tests cover expiration and bounded eviction. The
current live Product route exposes no authorized control that produces a failed
Package 7 execution or sends a custom `Last-Event-ID`, so those two transport
variants were not fabricated in Browser QA. An attempted genuine server
interruption was observed without a browser error during the bounded window;
the candidate therefore makes no stronger Browser claim for that attempt.

### Terminal validation classification

| Scenario | Validation method | Result |
|---|---|---|
| Terminal success followed by normal closure | `BROWSER_DIRECT` | Six ordered events preserved in Product and Technical; no false unavailable state or reconnect |
| Product/Technical identity equality | `BROWSER_DIRECT` | Equal canonical revision, digest, snapshots, execution, approval and placement identity |
| Desktop and `390x844`, English and zh-CN | `BROWSER_DIRECT` | Terminal state retained, no overflow, console error or synthetic fallback |
| Terminal execution failure followed by closure | `AUTOMATED_SUBSCRIBER` | Terminal failure remains `TERMINAL`; closure is a no-op |
| `RESUME_UNAVAILABLE` followed by closure | `AUTOMATED_SUBSCRIBER` | Explicit resume terminal remains `TERMINAL`; closure is a no-op |
| Unknown/restart-lost resume cursor | `BACKEND_API` | HTTP 200 SSE with terminal `RESUME_UNAVAILABLE` |
| Expired or evicted resume cursor | `BACKEND_API` | Existing bounded broker/API contract returns unavailable rather than fallback |
| Pre-terminal transport interruption | `AUTOMATED_SUBSCRIBER` | Becomes explicit `JOURNEY_STREAM_UNAVAILABLE` and closes |
| Malformed schema, identity or digest | `AUTOMATED_SUBSCRIBER` | Fails closed with stable reason code |
| Sequence gap, reorder or post-terminal event | `AUTOMATED_SUBSCRIBER` | Fails closed |
| Byte-identical duplicate | `AUTOMATED_SUBSCRIBER` | Idempotent with no duplicate UI delivery |
| Conflicting duplicate ID | `AUTOMATED_SUBSCRIBER` | Fails closed |
| Repeated terminal close callback | `AUTOMATED_SUBSCRIBER` | No state change |
| Component cleanup | `AUTOMATED_SUBSCRIBER` | Closes silently without visible failure |

No automated subscriber or backend API scenario is claimed as a genuine Browser
journey. No scenario in the required regression matrix is `NOT_CLAIMED`.

## Limitations

Replay remains process-local, bounded and best-effort exactly as before. This
change adds no durability, polling, exactly-once guarantee or production claim.
It does not grant Package 8, release, deployment or architecture acceptance.

## Checkpoint C terminal audit

Checkpoint C revalidated local HEAD and remote `main` at the exact durable
baseline, the expected branch, the six-path allowlist, absence of an existing
remote branch or PR, and the unchanged frozen S5-TEST-007 seven-path state.
S5-REL-040 is collision-free as the primary REL allocation candidate and
S5-REL-041 is collision-free as its fallback; neither Session was started.

Fresh terminal validation repeated the focused matrix (`51 passed`) and the
read-only Package 7/8 compatibility matrix (`28 passed`). A fresh external
frontend copy passed `npm ci`, `npm audit` with zero vulnerabilities, ESLint,
TypeScript and the Vite production build.

Direct Browser reconfirmation repeated the genuine correction, exact approval
and rerun journey. Product and Technical each retained the same six ordered
events through terminal `EXECUTION_SUCCEEDED`; there was no alert, console
warning/error, horizontal overflow, `SYNTHETIC_PREVIEW` classification or
post-terminal reconnect during the observation window. Every observed backend
request returned HTTP 200.

The terminal commit, push, Draft PR and exact-head CI facts belong to the final
Checkpoint C handoff and are not predicted by this pre-commit Evidence record.
