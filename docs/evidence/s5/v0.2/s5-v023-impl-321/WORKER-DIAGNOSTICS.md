# S5-V023-IMPL-321 bounded worker diagnostics

## Recovery and scope

The predecessor task `01a0ae3b-04ca-7782-b0be-a4227e2f907c` is in
`systemError`. Its final command completed with exit 0 and only read rules and
status. No product code was changed by that interrupted turn. No Kimi worker,
evaluation runner, pytest or push process was active at takeover. This task
continues in the existing 321 branch/worktree; no new Session, branch or PR.

Baseline source: `0de78aa8fe7f50325a525506f8aee33b295aca80`.
Baseline tree: `d8ddcaa33d755f39d077382cb3f17c54a2943eac`.
Earlier uncommitted quality, validation, preflight and screenshot evidence is
preserved in place, not represented as part of the diagnostic commit.

G1 plan before coding: extend private worker IPC and DeadlineMetrics, preserve
existing outcome/deadline/budget semantics, test known local failures and
sanitization, run make check, push normally and check the existing Draft PR.
No public API/Contract, database, prompt, request parameter or frontend change.

## Diagnostic path and meaning

The worker reports only allowlisted phase transitions: IPC, CONNECT,
SEND_REQUEST, WAIT_HEADERS, READ_BODY and VALIDATE_RESPONSE. CONNECT includes
TLS context setup; initial IPC includes spawn/startup. Exception categories are
TIMEOUT, TLS, REMOTE_DISCONNECT, HTTP_PROTOCOL, IO, INVALID_DATA or UNEXPECTED.
No exception message/class name, credential, header or body is serialized in
these diagnostic fields. Parent-side malformed IPC remains TRANSPORT_AMBIGUOUS.

Parent supervision retains these in `last_deadline_metrics`; the existing
restricted evaluation `call.py` result record already serializes the full
object with `asdict`, so the `deadline` record retains all added fields even
when dispatch raises. No original result records are rewritten. The existing
stale response object in old failure receipts remains historical; the preserved
invocation snapshot is authoritative for the old OUTCOME_UNKNOWN state.

`stage_seconds` measures parent-observed phase intervals (including IPC delivery
latency), not provider-side timing. `worker_exit_status` is the actual observed
exitcode, or the explicit string UNKNOWN when unavailable. A negative value
represents a signal. `worker_kill_requested` reports whether supervision invoked
kill, not proof that kill caused exit: channel-close watcher and worker exit can
race with it. Exit 0 does not imply successful provider execution. Existing
kill/join deadlines and cleanup failure semantics are unchanged.

Ordinary invalid provider JSON still returns business FAILED with
PROVIDER_RESPONSE_INVALID and supervisor RESULT_ACCEPTED: `failure_stage` is
for transport/supervision failures, not a replacement for business reason codes.

## Validation and preserved state

- `make check`: 1857 passed, 200 skipped (external-service configuration absent),
  one existing pytest configuration warning; Ruff lint and formatting passed.
- Existing nine local fixtures rerun against the diagnostic source: success,
  response-header stall, body stall, disconnect, invalid JSON, exited worker,
  malformed IPC, connection deadline and total deadline. Results are in
  `worker-diagnostic-fixtures.jsonl`. No public provider requests.
- New committed regression cases assert distinct phase/category pairs, exactly
  one dispatch, transport ambiguity, reaping/exit status and no request/response
  sentinel in serialized diagnostics. Existing cleanup test asserts UNKNOWN
  exit status when the fake unreaped process provides none.
- Parent-loss test consumes phase frames until connected, then retains its
  original forced channel-loss/worker-exit assertions.
- Read-only comparison confirmed all 31 preserved files and the complete
  policy/reservation/settlement/invocation snapshot unchanged. Four original
  reservations and three settlements remain; unknown USD0.033451 is retained,
  usage unknown. Dispatch is disabled and automation 321 is PAUSED.
- Prompt/request construction, connect/read/total 5/30/60 seconds, UNKNOWN,
  budget reservation and zero automatic retries are unchanged.

Known limit: these observations distinguish injected local failures; they do
not retrospectively identify the cause of Q01-v2-2 or prove a provider fix or
quality improvement. PostgreSQL budget integration requires its configured CI
service; local skips are not reported as executed passes.

## Proposed single diagnostic call — NOT AUTHORIZED OR EXECUTED HERE

Proposed window: 2026-09-18 10:00–10:15 Asia/Shanghai (02:00–02:15 UTC).
Preparation must finish before 10:00; no dispatch after 10:13. If approval or
preparation misses the window, stop and propose a new window; no renewal.

Exactly one NEW invocation tagged `D01-v2-diagnostic`, first-turn synthetic
input: `供应商质量不好，帮我改善。` No conversation history or second turn.
This is a new diagnostic sample using Q01's first-turn input, not a replay or
retry of the unknown Q01-v2-2 invocation. Use the committed diagnostic source
reported by PR181, retaining v2 prompt/schema, 1024 output tokens, reasoning low,
5/30/60 deadlines and zero retry. Preflight must verify complete prepared request
hash `b11f9f59edeb43b0e238d12cc77df94ea51e3bd163bbce7758b0000fceecad03`
and 4156 bytes (the existing first-turn fixture); any mismatch stops for review.

Reuse exact profile `draft-profile-revision:s5-321-real-quality:v2:1`, digest
`fc4ebbfa3e0dfecbeb2afbd7f1c63898d6505ea5e43f58cf698a19c6f29b7087`, model revision
`model-revision:s5-321-real-quality-kimi-k3:v2:1`, digest
`2ebeea7723575c682964486fbaf4292d85253cc65d785e4114c2ffd172dfcd10`, and existing
Moonshot CN Responses endpoint/connection/provider v2 exact binding. Validate
current eligibility, independent approver and execution identity through normal
Grant services, including explicit authorization of the diagnostic code source.
Do not silently mutate frozen v2 archives or bypass self-approval restrictions.

Historical prepared quote: 30477 microusd (USD0.030477) reservation. Proposed
single-call reservation ceiling USD0.034; refresh the approved price inputs and
recompute the quote before approval/execution, stopping if it exceeds the ceiling.
This is not a current market-price assertion. Debit the existing v2 ledger;
retain the four prior calls, USD0.018385 settled and USD0.033451 unresolved.
At the proposed ceiling, prior settled + unresolved + new reserve is at most
USD0.085836. Existing aggregate caps continue to apply; no ledger reset.

Stop after the one attempt for any outcome, including success. On timeout,
UNKNOWN, auth/binding/price mismatch, capture/IPC/cleanup failure or window
expiry, preserve evidence/reservation and stop without retry. Record only safe
diagnostics; keep scheduling PAUSED. This proposal does not authorize dispatch,
Ready, merge, deployment, Session closure, or quality acceptance.
