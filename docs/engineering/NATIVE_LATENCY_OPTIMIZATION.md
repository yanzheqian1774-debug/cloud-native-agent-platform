# G1 Native latency optimization

Scope: retain current Kubernetes Tasks, owner receipts, exact authorization, budget reservations/settlement, revocation and UNKNOWN handling. No frozen contracts, lifecycle, public endpoint or infrastructure changes.

1. Measure existing same-input production/test document runs. Separate provider HTTP, supervisor, tool, input wait and workflow overhead. Add private supervision cancellation-check timing and per-loop authority timing; nested times are not additive.
2. Discover authorized sources before the first problem-understanding request. Persist source selection in the original conversation, then invoke understanding with question plus confirmed source. Existing interrupted claims never replay. This removes an unnecessary model round across source families.
3. Within a single linearized authorization bundle, reuse its already-read credential and delegation SQL predicate for each grant. Keep exact grant locks, fresh bundle reads, active generation, revocation and expiry predicates. No cross-request cache or polling-delay change. Eliminate duplicate authority reads while processing non-effect IPC stage notifications; check each supervision iteration and before result acceptance/cleanup.
4. Validate source-first recovery and identity boundaries, real PostgreSQL authorization/revocation/continuity tests, supervision deadline/cancellation tests, frontend lint/build and repository checks. Compare read-only authority profiles before/after.
5. Freeze whole source, preserve DB/budgets/UNKNOWN, install only while idle. Create explicitly bounded successor Native validation ledger for the requested new tests, preserving predecessor spend and cumulative $2 ceiling; do not reset any old ledger.
6. Real same questions/source snapshot and production/test answers. Record complete browser demos, journal/provider receipts and independent report findings/citations. Compare end-to-end and active (excluding answer wait) timing, model call counts and quality. Historical baseline was not an idle benchmark; disclose this limitation.

Risk review: credential/predicate reuse only within the same locked/repeatable-read bundle; standalone reads retain existing behavior. Stage messages never authorize effects; deadline checks remain per message and acceptance still performs fresh cancellation checks. Source discovery remains authorized and cannot select or execute without user input. No batching of formal Task transitions or approval bypass.

## Measurement interpretation

`nativeLoop.performance.authority` counts fresh authorization checks and their elapsed time. Responses receipt `deadline.cancellation_checks` and `cancellation_seconds` include the polling/acceptance checks. These times overlap with provider HTTP time and with each other; they must not be summed into an end-to-end total. `stage_seconds` are arrival offsets, not exclusive stage durations. Provider HTTP includes network and provider processing and does not isolate inference.

Source-first discovery never produces a draft or approval: after selecting authorized input the model still interprets the question, and the existing planning, policy confirmation and prepared-execution owners remain authoritative. A reload with an unverified claimed request does not repeat it.
