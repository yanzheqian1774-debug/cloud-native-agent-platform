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

## Proposed single second-turn diagnostic — NOT EXECUTED

This supersedes the first-turn proposal. Offline reconstruction uses the saved
Q01-v2-1 successful response, its understanding and clarification question, the
original synthetic user first turn and second-turn addition, and the existing
v2 context builder. Retaining saved context message IDs (provenance IDs, not
execution IDs), uiRevision=5, two user messages and currentDraft=null exactly
reproduces Q01-v2-2 content and prepared provider bytes. No preceding model call
is needed. This is provider-request equivalence, not continuation of the old
UNKNOWN lifecycle or proof of its historical cause.

- First user fact: `供应商质量不好，帮我改善。`
- Second user fact: `只看A供应商的来料，目标低于1%。`
- Saved understanding/question and message IDs remain in restricted local
  evidence; they are not copied into diagnostic logs.
- Full request: **5061 bytes**, SHA-256
  `bc88a41bc18aafe657239f23f9b2cfb770a48cacc2e813affddfe158f892c0f8`.
- New inert job: `D01-v2-round2-diagnostic`; new idempotency key:
  `s5-321-diagnostic-round2-20260918-once`.
- A fresh service context/turn/invocation/snapshot must be created after
  authorization. Do not pass old parent/predecessor IDs: the old context head
  is UNKNOWN. Do not invoke the original key, mutate its state or resume it.
  The existing begin API permits a new context with the reconstructed content;
  provider payload does not include invocation IDs, so bytes remain equivalent.
- Use the final synchronized PR181 source/tree reported in its delivery receipt,
  retaining v2 instructions/schema, 1024 output tokens, reasoning low, foreground,
  store=false, 5/30/60-second deadlines and zero automatic retries.
- Recheck prepare-only hash and byte length against the final code before
  approval and again at dispatch; any difference is a stop, not an adjustment.

Exact binding remains profile `draft-profile-revision:s5-321-real-quality:v2:1`,
digest `fc4ebbfa3e0dfecbeb2afbd7f1c63898d6505ea5e43f58cf698a19c6f29b7087`,
model revision `model-revision:s5-321-real-quality-kimi-k3:v2:1`, digest
`2ebeea7723575c682964486fbaf4292d85253cc65d785e4114c2ffd172dfcd10`, provider revision
`provider-revision:s5-321-real-quality-moonshot:v2:1`, digest
`133c392a57806747ffcff94e227a40e81411bf073d905638caa55f48a6a287d5`.
The unchanged endpoint revision `endpoint-revision:s5-321-real-quality-cn-responses:1`
has digest `41cd867a3ed6bc30cc68ceaab67690fbc16d9521b45bb93f28431804f43a75a6`;
connection revision `connection-profile-revision:s5-321-real-quality-cn:1` has
`a15c057c00a1917e5808117e05c1920a15ec4a57e8aa412334e2d257ff378d92`.
This is the same kimi-k3/Moonshot CN Responses route. No frozen v2 archive is
rewritten; the synchronized diagnostic code source is separately bound.

### Reserve audit

[Official Kimi pricing](https://platform.kimi.com/docs/pricing/chat.md) was
refetched: kimi-k3 uncached input CNY20/million, output CNY100/million; document
SHA-256 `34225b80b0ec0ee85738b8c7ba20a98f7cfe110e478b0e6040c22cff5edd865a`.
[Bank of China](https://www.boc.cn/sourcedb/whpj/) published USD buying
CNY669.65/100 at 2026-09-17 17:58:39 +08. Existing 10% safety margin retained.
Using 5061 input-token upper bound and 1024 output ceiling, refreshed quote is
33448 microusd. Existing ledger uses the slightly more conservative CNY6.6960/USD:

`ceil(5061 * 3285544 / 1000000) + ceil(1024 * 16427719 / 1000000)`
`= 16629 + 16822 = 33451 microusd = USD0.033451`.

Thus USD0.034 remains sufficient now, with USD0.000549 above the existing quote.
Actual reservation is USD0.033451 in existing ledger
`kimi-real-s5-321-quality-v2-round-1`; it is a NEW reservation, separate from the
old unknown USD0.033451. No ledger reset/policy rewrite. Prior USD0.018385 settled
+ old unknown + proposed reserve = USD0.085287. Current quote must still fit
both existing ledger price inputs and USD0.034 at execution; otherwise stop
without dispatch and request a revised bounded plan, even if only slightly over.

### Identity and Grant audit for the proposed window

Read-only audit found active generation **2**, digest
`fd87b71c07b0d7502de44e11cce3a14acfa664b5ed00fc7e6aae07a236e0b6b2`, recovery epoch 1.

| Existing identity / evidence | Current expiry (Asia/Shanghai) | Covers proposed window? |
|---|---|---|
| executor credential-s5-321-quality-owner / human:321-quality-owner | 2026-09-18 00:00:00 | No |
| approver credential-admin / human:admin | 2026-09-17 18:31:59.285174 | No |
| 16 old exact Grant members | 2026-09-17 18:30 or 2026-09-18 00:00 | No; also wrong invocation targets |
| existing sessions | no later than respective credential expiry | No |

No new invocation/Grant has been created, no identity or expiry has been changed,
and no old authorization is treated as renewed. The two principals remain
separate; human:admin has the existing GRANT_ADMIN INSPECT/DECIDE meta-grants in
tenant-a/quality, not newly invented approval authority. Those meta-grants are
scope-wide by existing design; preparation is restricted to this one invocation
inside the dedicated 321 store. No role or self-approval rule change.

### One approval package and exact preparation/dispatch windows

Human may approve the following package once; it has NOT been executed:

1. Authorize the existing deployment/identity operator to activate generation 3
   in the dedicated 321 environment, changing only these two existing credential
   expiry values to **2026-09-18T02:15:00Z** (10:15 +08). Preserve principals,
   credential hashes, scopes, grants, tombstones, policy and recovery epoch.
   No 319 configuration/credentials are touched. If generation has advanced or
   a credential is revoked/mismatched, stop; do not overwrite newer state.
2. With freshly authenticated executor and independent admin sessions, prepare
   the new job between 09:50 and 09:55 +08. A new service.begin creates the new
   pending Draft request, with no provider dispatch. Before 09:55 approve its
   exact REQUEST/READ/CANCEL members via normal Grant service with
   **notBefore=2026-09-18T01:55:00Z**, **expiresAt=2026-09-18T02:15:00Z**.
3. At/after 09:55, resume only this newly created pending request to obtain its
   exact MODEL_GOVERNANCE/INVOKE_MODEL request. Approve it before 10:00 with
   **notBefore=2026-09-18T02:00:00Z**, **expiresAt=2026-09-18T02:15:00Z**.
   Persist actual new invocation/request/decision/grant IDs and exact resources;
   verify issuer differs from subject, active generation, epoch, revocations,
   binding and effective times. Do not call begin again during preparation.
   Existing service resolve requires an effective Draft grant before producing
   the Model request, hence these distinct preparation times are necessary.
4. Preparation must finish before 09:59:30. Dispatch is allowed only in
   **2026-09-18 10:00–10:13 +08**, with evidence/cleanup completed by 10:15.
   Immediately recheck both current exact grants, new identities, payload hash,
   quote and original ledger state before the sole dispatch. Expired grants,
   missed preparation time or any mismatch aborts; never auto-renew the window.
5. A dedicated one-shot driver must use an exclusive lock and O_EXCL intent,
   refuse existing new-key invocation/intent/reservation except the explicitly
   prepared AUTHORIZATION_PENDING record, and persist its identity before
   dispatch. It must not run run_comparison.py or clear run-started/terminal-stop.
   Existing automation stays PAUSED. On an exception, read final invocation
   state without another begin; serialize safe deadline diagnostics, not stale
   pre-dispatch response state or exception text. Capture failures are a stop.

Any result ends this one-shot attempt, including success, non-2xx, timeout,
UNKNOWN, capture/IPC/cleanup failure. No second call, retry or automatic schedule.
Success does not establish that the historical failure cause has been repaired,
and is not model-quality acceptance. Preserve all four original calls and their
unknown usage/reservation. No Ready, PR merge, deployment or Session closure.

Restricted evidence: `/Users/tristan/Documents/s5-v023-impl-321-real-quality/diagnostic-round2-plan/`
contains inert proposed-job.json, reconstruct.py, request-equivalence.json,
authority-window-audit.json and quote-audit.json. No provider credential, request
body or model answer is copied into repository diagnostic evidence.
