# F3 workbench read responsiveness (G1, 2026-11-12)

## Evidence and boundary

Installed source 94982788 and actual browser evidence under
`../evidence/f3-business-capability-design-20261111/resource-employee-capability-main-r1`
prove the fixed conversation/capability/employee/Skill return chain for devadmin,
including reloading the fixed Skill. No business write or model invocation occurred.
The separate `resource-employee-capability-main-timing-r1/timing.json` observed a
15.356 s conversation GET and 9.225 s session GET during initial concurrent reads.
The later employee-to-Skill segment was 5.923 s; reload/return readiness 3.997 s.
These are one-run observations, not percentiles or proof of root cause. Request
paths omit query strings; same path does not establish duplicate requests.

`workbench_bff.operation_endpoint` is async but calls `invoke_owner` synchronously.
`LIST_CURRENT_WORK` performs snapshot, visibility, Native question and outcome
reads inside that call. Investigate event-loop interference before attributing the
whole delay to model reasoning, networking or changing execution timeouts. Prior
frontend task prefetch/worker experiments were rolled back; do not replay them.

## Intended bounded implementation after causal validation

1. Add a controlled concurrency regression: hold the directory owner read while
   requesting an unrelated lightweight endpoint. Verify the lightweight request
   can finish before the directory operation is released. Use the actual BFF
   composition and preserve session, grants and owner envelope validation.
2. If this confirms starvation, isolate the synchronous LIST_CURRENT_WORK owner
   invocation through the existing framework worker mechanism. Keep its full
   authorization/transaction/audit unit together. Do not share a live connection
   across threads, split its transaction, cache authorization or bypass exact
   resource checks. Inspect authorizer/service thread assumptions first.
3. Bound simultaneous work and test authorization generation/revocation, error
   propagation and response identity. Disconnection must not cause redispatch or
   duplicate audit/owner effects. No model or mutation endpoint is included.
4. Re-run the same actual navigation/read sequence with the same records and
   feature flags in an owned isolated runtime before installation. Separate
   initial homepage contention from navigation segments, compare payload facts,
   and verify original database records and policy/budget state are preserved.
5. Run normal repository checks, then frozen-source installation and real main
   verification. Report measured improvement or non-improvement honestly.

No public API, schema, CRD, lifecycle, Native budget, OpenClaw enablement or new
infrastructure change is authorized by this plan. A thread-confinement or ownership
conflict requires resolving the existing architecture constraint, not weakening it.

## Remaining mainline acceptance

This performance increment does not close ordinary-role resource/employee access,
all resource types, nonzero scroll return, current real-model execution or full F3
visual/functional acceptance. Continue those alongside verified safe delivery;
the fixed-reference admin read chain is one proven case, not total completion.

Causal diagnostic completed against the actual BFF router with controlled owner
and session/authority fixtures: while LIST_CURRENT_WORK was held by a threading
Event, an independent session request could not finish within 400 ms; releasing
the owner allowed both responses to complete successfully. Exactly one owner
invocation occurred. Evidence: `workbench-read-responsiveness-r1/controlled-before.json`.
This establishes shared event-loop interference in the controlled router, not the
fraction of total main latency attributable to it. At that diagnostic point,
production code was unchanged.

The second actual main read-only run additionally awaited completed employee
name/status resolution and saved conversation progress; both passed with original
records unchanged. See `resource-employee-capability-main-settled-r2`. Its Skill
segment (3.366 s) differs from the earlier 5.923 s without any code change: do not
report that variation as an optimization win.

## Candidate verification (2026-11-12)

The candidate moves only GET LIST_CURRENT_WORK's complete owner authorization
and transaction into an AnyIO worker with a one-operation capacity limiter.
Queued requests reauthenticate before owner entry. The worker is not abandoned
on cancellation; the BFF does not redispatch it. No frontend or API contract
changes are included.

48 targeted BFF/current-work checks passed, including an unrelated session read
finishing while the owner is held and a queued logged-out request being rejected
without entering the owner. 20 existing authorization PostgreSQL checks passed
using fixture-created disposable databases, not the installed application database.

An owned isolated runtime was restarted with exactly one file changed from its
frozen source: workbench_bff.py. That original file matched main HEAD 94982788.
Three identical current-work/session request pairs ran before and after on the
same application database. Session durations before: 3935.8, 2184.7, 1272.8 ms;
after: 350.4, 21.5, 727.4 ms. Two after sessions finished before the directory;
the third still waited. This small sample demonstrates improved responsiveness,
not complete elimination of contention or a whole-platform latency percentile.
Do not attribute the directory's own timing variation entirely to this patch.

All requests returned 200. Directory payloads matched except readAt; principal
identity matched. Seven protected execution, upgrade, budget and generation
tables retained identical hashes. Main source/process identity was unchanged;
no model or execution worker was enabled. Evidence:
`../evidence/f3-business-capability-design-20261111/workbench-read-responsiveness-r1/actual-comparison.json`.
Main installation, installed before/after navigation, and broader role/page
acceptance remain pending.
