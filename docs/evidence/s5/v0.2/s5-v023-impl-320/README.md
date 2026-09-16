# S5-V023-IMPL-320 implementation evidence

## Boundary

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
| A04 Kimi response contract | `PASS` |
| A05 one-shot transport/TLS/timeout/redirect/disconnect | `PASS` |
| A06 fake exact-file credential and data boundary | `PASS` |
| A07 inherited dispatch ordering | `PASS` |
| A08 exact authorization rejection/current admission | `PASS` |
| A09 concurrency/UNKNOWN/no redispatch | `PASS` |
| A10 call/cost cap and restart | `PASS` |
| A11 aggregate usage and worst-case retention | `PASS` |
| A12 positive product journey | `PASS` |
| A13 negative product journeys | `PASS` |
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
