# Bounded Kimi non-2xx diagnostics

Continuation of the existing real-provider acceptance, without a new formal
implementation number. G1 plan; baseline source
`e51334aa9780291b3d077a1edb698dca630a6b3f`, tree
`535fdd12cd11e4f2a029f03170f2a100e0fd8b49`.

## Scope and compatibility

Add bounded, fail-closed non-2xx diagnostics to the private Kimi transport and
its existing anonymous worker IPC. Do not extend ProviderObservation, durable
Evidence, runtime configuration, CRDs or database schemas. An opt-in acceptance
collector can save the sanitized transport diagnostic in an owner-only task
record. It is not canonical Evidence or a provider billing record.

Retain HTTP status, UTC receipt time, configured host/path, latency, validated
provider request ID with header provenance, Retry-After, and bounded error
type/code/message. Missing, invalid, discarded and truncated values are explicit.
Never persist raw bodies, authorization or request content. Error identifiers
and messages use a finite vocabulary; unknown text is discarded rather than
assuming regular-expression replacement can remove every sensitive value.
Request IDs and Retry-After accept narrow formats and reject credential echoes.
Only sanitized diagnostics cross the result IPC. No automatic file logging.

Preserve request fields, A05 deadline/cleanup, authorization, budget and zero
retries. Reject late results before exposing their diagnostics. Success has no
non-2xx diagnostic. Diagnostic retention is bounded independently of body size.

## Protocol review

Official sources read 2026-09-16:
https://platform.kimi.com/docs/api/responses.md and
https://platform.kimi.com/docs/api/errors .
The Responses schema documents model/input/instructions/max_output_tokens,
reasoning.effort=low and text.format json_schema. It describes response
store/background as fixed false but omits them from request properties. This
does not prove rejection or acceptance of explicit false request fields.
Keep both existing false values and all approved data conditions; do not remove
them to obtain a successful request. If the diagnostic identifies a protocol
conflict, stop and report it instead of retrying with altered fields.

## Validation and execution

Test credential echoes, unrecognized text, length bounds, non-JSON errors,
missing request IDs, worker propagation, one dispatch and A05 regressions.
Run repository quality checks. Commit the candidate and record its source/tree;
the candidate is not main acceptance. Use the existing acceptance database,
ledger, exact credential reference and first synthetic input. A fresh invocation
and current exact grants are mandatory. At most one additional dispatch, total
at most two; preserve the first failure and USD0.070493 reservation. Stop after
the response, unknown outcome, or a blocking admission failure. Do not send the
second synthetic input. No main merge, release or asset cleanup.

## 2026-09-17 Evidence focus blocker amendment (Human authorized)

Continue #179 on its existing diagnostic branch. The original candidate remains
Human accepted only for its bounded diagnostic scope; new commits require a new
candidate decision. Preserve CI attempt 1 and its missing trace evidence.

Before editing focus behavior, reproduce the close/Tab sequence in an isolated
browser using synthetic traceability data and the actual application components.
Record only event type, key, route and focus target; retain failure screenshots
and traces outside the original acceptance assets. Test both 390x844 and desktop.
Distinguish this controlled frontend experiment from the real-service Wave 3B
journey, which remains in the full browser CI gate.

Use observable dialog/route/request readiness, never sleeps, longer timeouts,
retries or removed assertions. If lifecycle focus competes with user navigation,
repair only Evidence focus ownership and directly related tests. Bound repetition
to ten cases per viewport per experiment; stop to inspect any failure. Validate
normal close restoration, subsequent Tab destination and user focus preservation
while a delayed projection loads. Run make check, frontend lint/build and affected
browser checks; commit normally and non-force push the existing Draft PR, then
record exact checkout and CI terminal results. Do not change #180, main, the
original acceptance services/database/browser, interaction contracts or 321 scope.

### Evidence and minimal correction

A production build under bounded 6x CPU scheduling stress reproduced both mobile
and desktop failures: Enter changed the URL while the inspector DOM remained;
Tab focused a link in that departing inspector, then unmount returned focus to
body. The original negative `:focus` assertion waited for a nonexistent element.
This is a reproduced mechanism, not proof of the original CI event sequence
(attempt 1 has no trace). Development builds passed the old sequence; passing
runs alone did not establish a transient failure.

Removing the inspector synchronously fixes the departing-DOM target. A stronger
focus-preservation assertion then exposed the shell's delayed heading focus
stealing the user's Tab destination. Evidence return navigation now marks its
focus ownership in local router state; only that return bypasses shell heading
focus. The existing claim/fact restoration still yields to user input. No URL,
authorization, provider, persistent schema or interaction contract changes.

The real-service test now observes close-button focus, inspector disappearance
and intercepted projection request readiness. It verifies the actual Tab target
and preserves that same element after response release, on mobile and desktop.
The synthetic browser regression additionally tests immediate Enter/Tab under
controlled scheduling and records allowlisted focus events, with failure traces
and screenshots. Old production code fails the atomic-close assertion in both
viewports; the corrected code passed ten repetitions per viewport (20 total),
with retries disabled. An intermediate candidate failed focus preservation and
was fixed before further repetition; all evidence is retained outside Git.

Local validation: make check exited 0 (1838 passed, 200 dependency-gated skips),
and frontend lint/build passed. The original real-service Wave 3B spec passed
once in dedicated PostgreSQL/Qdrant assets. The amended three-repeat real-service
run stopped before its first journey at backend restart readiness (zero completed
journeys); its 20-second health gate was not relaxed. Host load was high, but that
is context rather than a proven cause. Full new-candidate CI must independently
validate the real-service journey. No old CI rerun was used. A prior harness
attempt also hit the macOS UNIX-socket path limit; moving only its new runtime to
a short path resolved that setup error. Neither setup failure is model evidence.
