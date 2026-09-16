# S5-V023-IMPL-320 — Kimi Responses adapter implementation plan

## Status and authority

| Field | Value |
| --- | --- |
| Session | `S5-V023-IMPL-320` |
| Type | `G1 / PLAN_REQUIRED` |
| Task status | `ACTIVE / HUMAN_AUTHORIZED` |
| Fixed base | source `7fffd064cfe999cdd1c72833cdb7c151d87f2230`; tree `478339c80655a7679c4756629958906e0d70fa71` |
| Branch | `codex/s5-v023-impl-320-kimi-responses-adapter` |
| Governing decision | accepted `S5-V023-ARCH-318` and accepted `ADR-0005` |
| Real provider gate | `PENDING / NOT_AUTHORIZED / NOT_EXECUTED` |
| Ready, merge, deploy, release, close | `NOT_AUTHORIZED` |

The Human-supplied starter and reuse review matched SHA-256
`f07e79c7ea7c3219ff5ae78d3d96a70519e2a38f5a826797b39171565c4372eb`
and `a079466835813389ac552ffc4dda4b14a896c8d8ee7e627582f33136891d6817`.
At startup, the exact base/tree matched `origin/main`; repository content,
refs/worktrees and all visible GitHub pull requests contained no competing 320
owner. This task uses the already isolated `17b3` worktree and never modifies
the 319 worktree, branch, PR, database, or acceptance assets.

## 1. Official contract checkpoint

The public Kimi documentation was re-read before coding on 2026-09-16:

- [Responses API](https://platform.kimi.com/docs/api/responses) currently exposes
  exact `POST /v1/responses`, lists `kimi-k3`, accepts typed input,
  `max_output_tokens`, `reasoning.effort`, and `text.format` JSON Schema, and
  reports completed/incomplete/failed/in-progress plus aggregate and detailed
  usage.
- [Thinking models](https://platform.kimi.com/docs/guide/use-thinking-models)
  currently lists `low`, `high`, and `max` for K3 reasoning strength and says K3
  always reasons. For Responses the request projection is the documented nested
  `reasoning: {"effort": "low"}` shape; the Chat Completions spelling is not
  reused.
- No-tool requests omit `tools`, `tool_choice`, and `parallel_tool_calls`.
  `truncation` is omitted because the current Responses request schema does not
  list it. The mock sends `store=false` and `background=false`, and sends no
  `previous_response_id`.

These are public-contract inputs for isolated contract tests, not evidence of a
real provider call, account availability, quality, price, retention, or
certification. Any incompatible public-contract change discovered later fails
closed and is recorded rather than guessed around.

## 2. Architecture Gate and affected components

This is G1: it adds one provider-specific adapter and exact internal composition
selection under accepted ARCH-318 owners. It changes no public API/CRD,
Kubernetes API group, lifecycle, authorization owner, Control Plane boundary,
persistent technology, migration, or financial contract.

| Component | Planned bounded change | Compatibility rule |
| --- | --- | --- |
| `kimi_responses_draft_adapter.py` | add `kimi-responses-draft / v1`, protocol `KIMI_RESPONSES_V1`, Kimi request projection, strict parser, bounded one-shot HTTPS transport | separate identity and errors; no retry, redirect, fallback, model substitution, raw-content persistence, or remote cancel claim |
| `draft_assistance_bootstrap.py` | parse the exact protocol/adapter tuple and instantiate only the matching configuration/resolver/transport | OpenAI tuple and projection remain unchanged; mixed tuple fails closed |
| exact credential boundary | reuse the existing exact private-file semantics through a provider-neutral internal implementation if needed | no env, default-directory, client-secret, or implicit credential fallback |
| backend tests | add isolated Kimi contract/config/transport tests and retain the complete OpenAI suite | prove request shape, response/usage/error classification, one dispatch maximum, and cross-adapter rejection |
| 320 acceptance assets | add task-owned fixture, local HTTPS mock, cleanup, Playwright config/spec and exact-head CI | no overwrite or reuse of mutable 319 assets; fake credential and synthetic data only |
| 310 browser harness | minimally select the 320 fixture under a new exact environment gate | existing 319 and non-Draft paths remain unchanged |
| governance/evidence | add this plan, one Registry row, and bounded evidence record | record failures and exact identities; never claim real AI quality |

If implementation requires a frozen/public contract change, owner/lifecycle or
UNKNOWN change, authentication architecture change, new database/dependency,
multi-currency contract, dynamic routing, or a real provider call, the affected
work stops for G2 escalation.

## 3. Exact configuration and invariants

- Adapter tuple: `kimi-responses-draft / v1 / KIMI_RESPONSES_V1`.
- Exact Model Governance Provider/Model/Endpoint/Connection Profile identities,
  revisions and digests continue to be checked before dispatch; no latest,
  display-name, environment, runtime, or default fallback.
- Local mock profile: `mock-kimi-k3-320`, `maximumOutputTokens=4096`,
  `reasoningEffort=low`, `callCap=10`, `totalCostCapMicrousd=10000000`.
- Mock prices are deterministic USD test inputs labeled
  `TEST_ONLY_SYNTHETIC_USD_QUOTE / NOT_KIMI_PRICE`; they are not Kimi prices or
  CNY conversion.
- All reservations use one immutable 320 ledger. Evidence records reservations
  and dispatches separately and proves `dispatches <= reservations <= 10`,
  including a reservation-without-dispatch case and restart reconstruction.
- Existing authorization, current 30-second admission, Resource Use, budget,
  durable dispatch CAS, credential resolution, transport ordering, Evidence and
  UNKNOWN/no-redispatch semantics are reused unchanged.
- Single connect/read/total timeouts remain explicit. Cross-call cumulative
  machine wait is `NOT_IMPLEMENTED / HUMAN DECISION PENDING`.

## 4. Implementation sequence

1. Add isolated Kimi contract tests and adapter implementation.
2. Add exact tuple selection to bootstrap and prove all Kimi/OpenAI mismatch
   permutations fail closed while OpenAI regression remains byte-for-byte in
   behavior.
3. Add 320-owned fixture/mock/browser/cleanup/CI assets and minimal harness gate.
4. Run focused backend tests, authorization/budget/concurrency/restart/UNKNOWN
   regressions, frontend lint/build, dedicated PostgreSQL + HTTPS + Chromium
   acceptance, and `make check`.
5. Inspect diff/status and evidence for secrets or raw content, commit normally,
   non-force push the sole branch, create one Draft PR, and follow its exact-head
   automated CI to terminal. Fix ordinary failures on the same branch and retain
   failure history.

## 5. Acceptance matrix

| ID | Required result |
| --- | --- |
| A01 | Separate Kimi/OpenAI identities and exact Kimi governance tuple; every mixed tuple fails closed. |
| A02 | Existing OpenAI adapter tests and projection behavior pass unchanged. |
| A03 | Exact Kimi path/model, typed input, strict schema, `reasoning.effort=low`, 4096 ceiling, and absence of all tool/truncation/state-continuation fields. |
| A04 | Completed valid JSON succeeds; schema invalid, refusal, incomplete, failed, nonterminal, missing/invalid usage never become a successful draft. |
| A05 | HTTP rejection/redirect/TLS/disconnect/connect-read-total timeout have zero retry and at most one dispatch. |
| A06 | Fake exact private file only; no env/default fallback; no credential/raw prompt/raw response in logs or evidence. |
| A07 | Resource Use -> reservation -> current admission -> dispatch CAS -> credential -> transport ordering remains unchanged. |
| A08 | Either exact grant denied/expired/revoked causes zero mock calls. |
| A09 | Same-key race has one winner; UNKNOWN observe/cancel remains unsupported and never redispatches or fabricates cancellation. |
| A10 | Call/cost caps fail closed; reservation and dispatch counts differ legitimately; one ledger survives composition restart. |
| A11 | Aggregate usage settles only when valid; missing/invalid usage retains worst case; evidence carries the test-only quote label. |
| A12 | HTTPS Chromium journey completes clarification, supplement, editable draft, Human confirmation, formal Problem creation and authorized readback. |
| A13 | Browser denial/budget/nonterminal negative journeys show no false success and no extra dispatch. |
| A14 | Synthetic data and fake credential only; real provider calls exactly zero. |
| A15 | Focused tests, frontend lint/build, dedicated acceptance, and `make check` pass with focused diff. |
| A16 | The one Draft PR exact head reaches terminal success for dedicated and regular automated checks. |

## Execution result

A01-A16 passed for the bounded local/mock scope. The sole Draft PR is `#177`.
The corrected implementation head
`c0687efcb252b7c7c7e138fa5d7286f6a1e8d245` reached `11/11` successful checks;
the dedicated Kimi workflow is run `35063749325`, and general CI run
`35063749388` succeeded on attempt `2` while retaining the prior mobile
focus-transfer timeout attempt. Real provider execution remains
`PENDING / NOT_AUTHORIZED / NOT_EXECUTED`.

## 6. Pending Human decisions and limits

China/other region, account/project availability, credential owner, Kimi data
retention and deletion conditions, CNY-to-USD policy, real price, real
reasoning/output ceilings, real timeout values, 24-hour authorization semantics,
cross-call cumulative wait, and any real sample remain pending. `4096/low` is a
mock contract value only. Real provider status remains
`PENDING / NOT_AUTHORIZED / NOT_EXECUTED`.
