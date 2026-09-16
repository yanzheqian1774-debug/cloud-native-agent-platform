# Fixed-candidate follow-up: A04 / A05 / A13

## Authority and identity

Starts at `aaa2b773c28a02d4fa16455704e8fe4034a5c585` / tree
`b349c6cc78e26d404d9993dc1d8ca6dd06e5f58a`, same single writer,
branch/worktree and Draft PR `#177`. No product source or migration was changed.

## A04 contract conclusion

Accepted ARCH-318 sections 4.2 and 6.1 define usable output separately from
transport/validation failure. Section 9.1 requires unavailable token/cost
measurements to be `NOT_COLLECTED` / `NOT_MEASURABLE`, never fabricated zero;
section 9.2 separates invocation outcome from owner measurement/Evidence writes.

Current `ProviderObservation` validates the typed clarification/draft fields, not
usage completeness. The Kimi parser allows strict valid completed output to be
`SUCCEEDED` while missing/invalid usage produces `input_tokens=output_tokens=None`.
This conforms to the accepted separation; the previous A04 plan wording was wrong.

`PostgresProviderCallBudget.record_usage` writes a settlement only when both
aggregate token counts are present, nonnegative/valid and within reservation
bounds, and computed cost is within the reserved worst case. Missing, partial,
or out-of-bound usage produces no settlement and retains the worst-case charge.
It never deletes the reservation or releases the call-count slot. Valid settlement
only replaces the conservative cost used by subsequent budget admission.

Added five PostgreSQL assertions for absent, partial and out-of-bound usage:
valid output remains successful, settlement count remains zero and the original
worst-case reservation remains unchanged. Adapter assertions separately prove
usable typed output and absent token measurement. No contract/behavior change.

## A05 exact coverage matrix

| Branch | Evidence | Result / limit |
| --- | --- | --- |
| configuration error | missing-CA test; unknown reasoning and mixed tuple tests | PASS; TLS configuration failure before transport attempt, not a handshake failure |
| TLS certificate validation | actual local self-signed server with default trust store | PASS; `SSLCertVerificationError` cause, one connection attempt, zero HTTP requests |
| connect timeout | injected HTTPSConnection raises TimeoutError from connect; timeout argument asserted | PASS, deterministic branch/unit evidence; not a real stalled network integration |
| read timeout | local server delays headers 1.5s with read timeout 1s and total 5s | PASS; one HTTP dispatch, ambiguous result; not independent total-deadline proof |
| independent total expiry | virtual monotonic time exhausts total after connect before request | PASS for post-connect guard only; zero HTTP requests, one attempt |
| strict whole-lifecycle hard deadline across headers/body | existing source sets socket timeout once using remaining budget | NOT_PROVEN; this work does not claim continuous absolute-deadline enforcement or slow-trickle protection |
| redirect | local 307 response | PASS; rejected without following Location, one dispatch |
| disconnect | local socket shutdown | PASS; ambiguous result, no redispatch |
| zero automatic retry | dispatch counters in all failure tests, UNKNOWN observe/cancel browser journey | PASS; no fallback/model replacement/cancellation fabrication |

A05 is therefore PARTIAL / WITH_EXPLICIT_LIMITATION, not a blanket PASS.
The unproved whole-lifecycle deadline is follow-up work under the existing bounded
transport contract, not permission to change accepted public/owner semantics.

## A13 product budget refusal

The fourth dedicated browser test consumes the same immutable ledger through
explicit authorized product form/button operations up to cap 10, then submits a
new operation at the cap. This new operation is rejected by the formal budget
owner; it does not replace the ledger/profile or reuse a failed key to evade cap.
The public owner-mapped error is `PROVIDER_BUDGET_DENIED`.

The page presents an alert and no successful draft/formal creation. Dispatch is
`10 before -> 10 after`; clicking the product's continuation button returns
original invocation metadata with the same denial and keeps dispatch at `10`.
The test attaches those counts and retains a refusal screenshot.

## Validation and preserved history

- Focused Kimi/OpenAI/Draft/budget/workflow suite: `65 passed` on r4 test asset.
- frontend lint/build: PASS; build warning is existing large chunk advisory.
- `make check`: Ruff/format PASS, `1796 passed / 199 skipped`, one upstream warning.
- r4 `/tmp/s5-v023-impl-320-acceptance-r4.8FHDB5`: 3/4; wrong alert locator.
- r5 `/tmp/s5-v023-impl-320-acceptance-r5.ujPm1P`: 3/4; wrong public reason code.
- r6 `/tmp/s5-v023-impl-320-acceptance-r6.uMz6GI`: 3/4; original metadata continuation
  removed the old alert; first refusal and dispatch checks had already passed.
- r7 `/tmp/s5-v023-impl-320-acceptance-r7.JLw4wF`: 4/4, duration 49482.807ms;
  reservations/dispatches 10/10; refusal and same-key continuation 10/10/10.

These databases/directories are all 320-owned, retained without reset or deletion.
r7 records HEAD `aaa2b77` with `sourceWorktreeDirty=true`: it is pre-commit working
source evidence, not new-head evidence. Old r3 and old CI retain their old identities.
Final committed-head coverage will be supplied by new-head automatic CI.

Real provider remains `PENDING / NOT_AUTHORIZED / NOT_EXECUTED`, calls zero.
No Ready/merge/deploy/release/Session-close authority is granted.
