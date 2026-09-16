# S5-V023-IMPL-320 implementation evidence

## Absolute-deadline repair from integrated main (new candidate)

Human authorizes a separate bounded repair from main
`d22aa01ce50c9de7b6ad3b142007d62dc68c2b5d`, tree
`011e63f7cbfaf3ffe3ebc726ce84a3600ed5cede`, on
`codex/s5-v023-impl-320-kimi-absolute-deadline` in worktree `d3d2`.
PR #177 is merged and its Human acceptance remains bound only to its recorded
source/tree. This repair requires a new Draft PR and separate review; it does not
rewrite the historical A05 NOT_PROVEN evidence below.

### Deadline mechanism and environment boundary

Kimi alone now supervises one spawned request worker. The parent starts one
monotonic total deadline before launch. DNS/TCP/TLS, send, headers/body, IPC and
result validation cannot reset it. A separate connection cutoff conservatively
includes spawn/startup and ends only when TLS completion is received by the parent.
A readable result loses at equality or after the cutoff; validation must also
finish before total expiry. A successful decision precedes cleanup; cleanup is
not represented as work completed within the request deadline.

The parent uses nonblocking anonymous socket IPC, including request transfer;
partial result frames and blocked request delivery cannot block its deadline
wait. No request or credential value is in process arguments or added environment
variables. The child never invokes the credential resolver or owner/database
ports. Its stdout/stderr go to the null device, core dumps are disabled, and
parent-channel loss terminates it. No secret temporary file is created. Python
may create ordinary multiprocessing control sockets/source bytecode caches;
neither stores application request or credential content.

At decision, the parent closes its endpoints, kills its exact worker if alive,
and joins it with at most one second of cleanup wait. Decision and cleanup seconds,
reason, PID and reaped status are measured separately in private transport
metrics. Failed/overrun cleanup cannot return success; an unreaped worker prevents
another dispatch through that transport instance. There is no retry, restart,
background reaper, process pool or remote cancellation claim.

This is validated on Python 3.12/macOS with POSIX spawn/socketpair and backend
thread execution; Linux GitHub CI validation is pending for this commit. The
current guarded script/ASGI hosting permits child processes. Windows, daemon
multiprocessing hosts, restricted process creation, interactive unguarded main
modules, and uninterruptible kernel/process creation failure are not certified.
It is not a hard-realtime scheduler guarantee: parent scheduling can delay
observing a cutoff, and an unkillable OS task is exposed as cleanup failure rather
than claimed reclaimed within one second. No new service or persistent dependency,
OpenAI modification, business state, authorization or budget contract change.

### Validation before commit

Focused Kimi/OpenAI/Draft/PostgreSQL/workflow suite: **91 passed**. Final
phase-wiring refinement (actual DNS/TCP/TLS/send/getresponse/read entry-point fault
injection) then passed **7 tests**; only those affected tests changed afterward.
Final repository `make check` after that refinement: **1818 passed / 201 skipped**;
Ruff lint/format passed. Normal hooks and new-head CI follow the commit.
The isolated database is `s5_v023_impl_320_deadline_r1` in the retained 320-owned
PostgreSQL container; existing migration 0024 is reused, not modified. No other
Session database or previous browser ledger is reset.

| Evidence | Result and exact limit |
| --- | --- |
| Injected socket.getaddrinfo / socket.connect / SSLContext.wrap_socket stalls | Parent connect cutoff kills/reaps worker; these are actual function-entry fault injections, not real stalled DNS/TCP/TLS networks |
| Injected send/headers/body stall | Parent total cutoff, one worker, no restart, exact PID no longer exists |
| Real local HTTPS delayed headers / slow body / cumulative phases | All reject otherwise-valid JSON at total cutoff; body chunks do not refresh it; HTTP count remains one |
| Equality and result race | Deterministic cutoff ordering; equality loses; parent validation finishing after deadline rejects a valid result |
| Partial result / blocked large request IPC | Nonblocking supervision reaches total expiry and reaps worker |
| Parent channel loss | EOF injection during actual local HTTPS causes child exit; not a remote cancellation assertion |
| Secret diagnostics / cleanup fault | Injected stdout/stderr and exception text absent from capture, core disabled, no new secret files; fake unreapable process cannot yield success or restart |
| Real deadline + PostgreSQL + same-key recovery | OUTCOME_UNKNOWN; same key yields no new HTTP call; one unchanged worst-case reservation, zero settlements, new operation denied at cap |
| Existing A04 / OpenAI / owner regression | Preserved; no source edits to OpenAI or owner/state/budget implementations |

Local measured cutoffs (seconds; configured connection=1, total=2):

| Case | Decision elapsed | Separate cleanup | Reaped |
| --- | --- | --- | --- |
| Injected DNS | 1.005651 | 0.005457 | true |
| Injected TCP | 1.003305 | 0.009560 | true |
| Injected TLS | 1.002445 | 0.002379 | true |
| Injected send | 2.004186 | 0.002825 | true |
| Injected headers | 2.002422 | 0.006204 | true |
| Injected body | 2.003729 | 0.008485 | true |
| HTTPS late headers | 2.002341 | 0.003268 | true |
| HTTPS slow body | 2.001863 | 0.003772 | true |
| HTTPS cumulative phases | 2.001931 | 0.001885 | true |

The small scheduling/observation excess shown above is disclosed as decision
elapsed, not hidden in cleanup. Cleanup remained below one second in all asserted
real-process tests. A synthetic delayed-parent-validation test deliberately delays
validation to prove late success rejection; it is not network timing evidence.

Incremental local logs/JUnit (with deadline metrics) are retained under the existing
recovery directory `/Users/tristan/Documents/S5-V023-IMPL-320-recovery-20260916T154202/`,
with `DEADLINE-LOCAL-SHA256SUMS`. Earlier lint line-length failures are retained;
r1/r2/r3/r4 intermediate suites are not relabeled final-source evidence. Mock server
connection-close diagnostics during parent-loss/late-header teardown are expected
fixture consequences, not extra provider attempts. Historical reports and hashes
remain intact. Repository gates and new-head automated CI are recorded after they
actually complete, not assumed from the prior candidate.

A05 repair is locally validated, with final Linux CI/Human review pending; it is
not automatically accepted or production-certified. Separate real-call authority
has been supplied by Human, but configuration/start prerequisites remain pending;
this task makes **zero real provider calls**. Ready, merge, deployment, release and
Session closure are not authorized for this new candidate.


## Human bounded acceptance registration

Human explicitly confirmed `PASS_WITH_CONSTRAINTS / BOUNDED_ACCEPTED` in the
continuing S5-V023-IMPL-320 “Human 有界接受最小登记” instruction.
Accepted source is `e1bacd7c69bbd5ded49bb86fb97567f65002f040`, tree
`f8861027c033b4b4a980782d0d62e43bf16c130a`, parent
`aaa2b773c28a02d4fa16455704e8fe4034a5c585`.
This registration commit records that decision; it does not mean Human accepted
the registration commit's new SHA.

The accepted scope is the local HTTPS mock Kimi adapter implementation: exact
configuration and authorization, structured output, A04 conservative measurement,
and A13 budget refusal with same-key zero additional dispatch. It does not include
real model quality, production availability or the complete business workflow.

A05 remains `PARTIAL / NOT_PROVEN` and its obligation remains `OPEN`: the current
implementation lacks a complete absolute deadline mechanism across headers/body.
Its disposition must be explicitly decided before real provider calls. Session
remains `OPEN`; the PR remains Draft. This acceptance does not authorize Ready,
merge, real credentials/provider calls, deployment, release, cleanup or Session close.
Real provider remains `PENDING / NOT_AUTHORIZED / NOT_EXECUTED`.

Acceptance basis and immutable external record are in
`/Users/tristan/Documents/S5-V023-IMPL-320-recovery-20260916T154202/`:

- `FINAL-ACCEPTANCE-PREFLIGHT.md`, SHA-256
  `97284067164765edb0dd16d877be68b632a329eb74d5530665618bc3fba23e6f`.
- `HUMAN-BOUNDED-ACCEPTANCE-e1bacd7.md`, SHA-256
  `9bec091bf3dcf06666faa8444e7961b7c54687b5dad13f110492cd3c34c8f98f`.

Accepted-source CI: dedicated run/job `35068758162 / 104705045883`, attempt 1,
SUCCESS, actual checkout at accepted source/tree, focused `67 passed`, Chromium
`4/4`; ledger reservations `10`, dispatch before refusal/after refusal/after same-key
continuation `10/10/10`. All 11 jobs succeeded. Five dedicated jobs checked out the
accepted source; six general/Identity jobs checked out PR merge
`6dff9e183981cb13be2092efb92156758e4a4fe6`, with the same tree and parents
`7fffd064cfe999cdd1c72833cdb7c151d87f2230` and the accepted source.
Preflight contains the full run/job/attempt/checkout table and preserved failure
history. Historical sections below keep their original source identities; they
are not new-head evidence. No previous report, checksum manifest or failed-run
record is overwritten by this registration.


## Boundary

The authorized follow-up from fixed candidate `aaa2b77` supersedes the previous
blanket A04/A05/A13 claims. See [precise follow-up evidence](FOLLOWUP-A04-A05-A13.md)
and [updated acceptance index](A01-A16-INDEX.md). Historical r3/CI identities below
remain unchanged and do not prove the new budget browser journey.

This record belongs only to `S5-V023-IMPL-320` and its isolated branch/worktree.
It does not modify or claim 319 assets. Real Kimi calls remain
`PENDING / NOT_AUTHORIZED / NOT_EXECUTED`; credentials and provider calls are
fake/local only.

## Fixed startup identity

| Item | Value |
| --- | --- |
| Base | `7fffd064cfe999cdd1c72833cdb7c151d87f2230` |
| Base tree | `478339c80655a7679c4756629958906e0d70fa71` |
| Branch | `codex/s5-v023-impl-320-kimi-responses-adapter` |
| Worktree | `/Users/tristan/.codex/worktrees/17b3/cloud-native-agent-platform` |
| Starter SHA-256 | `f07e79c7ea7c3219ff5ae78d3d96a70519e2a38f5a826797b39171565c4372eb` |
| Reuse review SHA-256 | `a079466835813389ac552ffc4dda4b14a896c8d8ee7e627582f33136891d6817` |
| Identifier/base audit | `PASS`; no competing 320 owner and `origin/main` exactly matched fixed base/tree before mutation |

## Official contract checkpoint

On 2026-09-16 the public Kimi Responses and thinking-model documentation still
listed `/v1/responses`, `kimi-k3`, nested `reasoning.effort` with
`low/high/max`, `text.format` JSON Schema, aggregate/detailed usage, and the
documented response states. This is documentation evidence only; no API probe,
credential read, or model request was performed.

## Implementation result

- Normal implementation commit: `d738798bfea5041fa4e8c7cd5f1e4ecea55f725d`.
- Implementation tree: `d378e40635187dc07f7564cf75bee1c22539b554`.
- Added the independent `kimi-responses-draft / v1 / KIMI_RESPONSES_V1`
  request projection, strict response parser, one-shot HTTPS transport and exact
  private-file resolver. OpenAI adapter source was not modified.
- Bootstrap accepts only the exact Kimi or exact OpenAI tuple. It constructs
  Kimi only with an explicit official `reasoningEffort` value and rejects mixed
  protocol/adapter/schema tuples.
- Added 320-owned contract, PostgreSQL budget/restart, local HTTPS mock,
  Chromium, cleanup and CI assets. Existing migrations `0019`, `0023`, and
  `0024` are applied unchanged to 320-owned test databases; no migration was
  added or modified.

## Validation ledger

### Preserved failure history

1. The first frontend lint attempt exited `127` with `eslint: command not
   found` because this isolated worktree had no `node_modules`. `npm ci` from
   the locked package set completed successfully; lint/build then passed.
2. A broad exploratory command pointed the inherited 319-exclusive PostgreSQL
   reset test at the 320 database. Its ownership guard correctly rejected the
   database name before reset or mutation (`78 passed, 2 setup errors`). The
   command was not weakened or retried against the 319 database. The legal
   320-owned targeted suite subsequently passed.
3. The first PR head exposed that the 320-only Playwright spec was not excluded
   from the default browser collection. The default job failed before test
   execution because its intentionally absent 320 credentials were required.
   Commit `c0687efcb252b7c7c7e138fa5d7286f6a1e8d245` added the exact exclusion
   and a regression assertion without changing the dedicated 320 collection.
4. On that corrected head, the first general-browser CI attempt executed 77
   existing scenarios and recorded one unrelated mobile focus-transfer timeout
   (`76 passed / 1 failed`). The retained attempt-2 rerun of only the failed CI
   job passed `77/77`; no provider request or application retry was performed.

### Successful commands before the normal commit

| Command / boundary | Result |
| --- | --- |
| Kimi + OpenAI adapter contract regression | `30 passed`; Kimi has an independent parser/transport; OpenAI projection remains unchanged |
| Draft/authorization/UNKNOWN/model-binding plus Kimi/OpenAI and 320 PostgreSQL budget tests | `78 passed` against the task-owned PostgreSQL asset |
| Kimi budget reservation without dispatch, same-ledger close/reopen and cap recovery | `PASS`; reservation survives restart, no provider dispatch occurs in the test |
| frontend `npm run lint` | `PASS` |
| frontend live-mode `npm run build` | `PASS`; build digest `44706dbbaa7c5fe87b7009a7db5137b0219437e95dff03bc7df502222432182a` before commit |
| dedicated Playwright collection | `3` tests in one task-owned file, workers `1`, retries `0` |
| PostgreSQL + local HTTPS + Chromium acceptance, second clean asset | `3/3 expected`, `0` unexpected, duration `8784.197ms` |
| `make check` | `PASS`; Ruff, format, `1793 passed / 194 skipped`, one upstream deprecation warning |
| `git diff --check` | `PASS` |

The exact committed implementation was then revalidated against a third clean,
320-owned database. The focused Kimi/OpenAI, authorization, model-binding,
budget/restart and workflow suite passed `77` tests. The HTTPS/Chromium
acceptance passed `3/3 expected` with `0 unexpected` in `8540.538ms`; its
machine-readable record is retained at
`/tmp/s5-v023-impl-320-acceptance-r3.mpUExU` and binds source
`d738798bfea5041fa4e8c7cd5f1e4ecea55f725d`, tree
`d378e40635187dc07f7564cf75bee1c22539b554`, and frontend build digest
`44706dbbaa7c5fe87b7009a7db5137b0219437e95dff03bc7df502222432182a`.
Its screenshots are SHA-256
`def94259a2f3713dd5bc6735ff6a08f565da347174c940272e9f5d6ca10a5cf8`
and `b3d8a3fd28ffdc5c791dbada2b2a90e74ed536f3a42c0c67062744116172bd64`.

The pre-commit browser evidence is retained at
`/tmp/s5-v023-impl-320-acceptance-r2.pwJWfp`. Its screenshots are SHA-256
`def94259a2f3713dd5bc6735ff6a08f565da347174c940272e9f5d6ca10a5cf8`
and `0acb6b23f916b090b21afba81cd5a5e983d5130699126d03dd1923b3e71eca0c`.
The original successful pre-refactor run is separately retained at
`/tmp/s5-v023-impl-320-acceptance.Wh56qu`; neither directory was deleted or
rebuilt.

### Budget and dispatch proof

The dedicated acceptance uses immutable ledger
`s5-v023-impl-320-kimi-mock-provider`, `callCap=10`,
`totalCostCapMicrousd=10000000`, currency `USD`, and the explicit label
`TEST_ONLY_SYNTHETIC_USD_QUOTE / NOT_KIMI_PRICE`. The second run recorded:

```text
reservationCount = 3
dispatchCount = 3
dispatchCount <= reservationCount <= 10
realProviderCalls = 0
```

The separate restart test proves the conservative unequal case by making a
reservation, performing no credential resolution or dispatch, closing the
composition, reopening the same ledger, and observing the original reservation
at the cap check.

## A01-A16

| Acceptance | Result |
| --- | --- |
| A01 exact identity/config | `PASS` |
| A02 OpenAI compatibility | `PASS` |
| A03 Kimi request contract | `PASS` |
| A04 Kimi response contract | `PASS`; strict valid output success is separate from incomplete measurement and conservative budget retention |
| A05 one-shot transport/TLS/timeout/redirect/disconnect | `PARTIAL`; distinct tested branches pass, strict whole-lifecycle hard deadline `NOT_PROVEN`; see follow-up matrix |
| A06 fake exact-file credential and data boundary | `PASS` |
| A07 inherited dispatch ordering | `PASS` |
| A08 exact authorization rejection/current admission | `PASS` |
| A09 concurrency/UNKNOWN/no redispatch | `PASS` |
| A10 call/cost cap and restart | `PASS` |
| A11 aggregate usage and worst-case retention | `PASS` |
| A12 positive product journey | `PASS` |
| A13 negative product journeys | `PASS` on modified local r7 source; new formal budget-denial journey included, 10/10/10 dispatch counts; final-head CI recorded externally after push |
| A14 bounded synthetic-only run | `PASS`; real provider calls `0` |
| A15 repository/local validation | `PASS` |
| A16 sole Draft PR exact-head automated CI | `PASS`; Draft PR `#177`, corrected implementation head `c0687efcb252b7c7c7e138fa5d7286f6a1e8d245`, all `11/11` checks successful; CI run `35063749388` attempt `2` retains the preceding timeout attempt |

## Preserved assets and limitations

- PostgreSQL container: `s5-v023-impl-320-postgres`, host port `55432`.
- 320-owned databases: `s5_v023_impl_320_acceptance`,
  `s5_v023_impl_320_acceptance_r2`, and exact-commit validation successor
  `s5_v023_impl_320_acceptance_r3`. No 319 or other Session database was reset,
  cleaned, or migrated.
- Single-call timeouts: connect `2s`, read `3s`, total `5s`. Cross-call
  cumulative machine wait remains `NOT_IMPLEMENTED / HUMAN DECISION PENDING`.
- `4096/low` and all USD quote numbers are mock-only. Real region/account,
  credential, Kimi price/FX, data retention, token/timeout values and 24-hour
  authorization remain Human decisions.
- Real provider: `PENDING / NOT_AUTHORIZED / NOT_EXECUTED`; calls `0`.
- Ready/merge/deploy/release/Session close: `NOT_AUTHORIZED`.

## Draft PR and CI identity

- Sole Draft PR: `#177`, base `main`, branch
  `codex/s5-v023-impl-320-kimi-responses-adapter`.
- Corrected implementation head/tree:
  `c0687efcb252b7c7c7e138fa5d7286f6a1e8d245` /
  `6310d5616bebb23867368c4674a7b34485ab0c29`.
- Dedicated Kimi run/job: `35063749325 / 104689420586 / SUCCESS`.
- General CI run: `35063749388 / attempt 2 / SUCCESS`; failed-job rerun
  `104690245490 / SUCCESS`.
- Other exact-head workflow runs: `35063749199`, `35063749270`,
  `35063749275`, `35063749369`, and `35063749439`, all successful.
