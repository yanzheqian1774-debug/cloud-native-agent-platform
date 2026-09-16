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
