# S5-V023-IMPL-319 real-provider acceptance call package

## Gate status

`PENDING / NOT_AUTHORIZED / NOT_EXECUTED`.

This package is a request for a separate Human gate. It does not authorize reading
the credential reference, enabling the real adapter, sending either payload, retrying
an ambiguous call, accepting provider terms, or spending funds. The shipped product
composition enables only the visibly labelled deterministic synthetic transport.

## Proposed exact call boundary

| Field | Proposed bounded value |
| --- | --- |
| Provider | OpenAI API; a new reviewed Model Governance Provider revision must be created at the gate |
| Provider-native model | exact string `gpt-5.6-luna`; no alias substitution or fallback |
| Endpoint | `POST https://api.openai.com/v1/responses` |
| Mode | foreground, text-only, no tools, no files, no web access, `store=false`, no `previous_response_id` |
| Output | strict `problem-draft-assistance-output.v1`: either one clarification question or `{title, description}` |
| Credential reference | `secretref://s5-v023-impl-319/openai-acceptance/v1`; value must remain outside Git, logs, Evidence and this package |
| Calls | at most 2 accepted dispatch admissions; zero automatic retry; an ambiguous transport result remains `OUTCOME_UNKNOWN` |
| Per-call input ceiling | 2,048 tokens and 16,384 UTF-8 bytes |
| Per-call output ceiling | 512 tokens, including reasoning/output accounting enforced by the adapter |
| Timeouts | connect 5 seconds; response 30 seconds; whole two-call acceptance 75 seconds |
| Spend stop | USD 0.01 total hard ceiling; stop before dispatch if the project cannot enforce/observe the ceiling |

The current OpenAI model page lists Responses API and structured outputs for
`gpt-5.6-luna`, with text pricing of USD 0.20/M input tokens and USD 1.20/M output
tokens as checked on 2026-09-15. At the ceilings above, two calls have a calculated
token-price upper bound of USD 0.002048 before any provider-specific minimums or
future price change. The Human gate must re-check model availability and price rather
than treating this note as a current authorization.

Official sources:

- <https://developers.openai.com/api/docs/models/gpt-5.6-luna>
- <https://developers.openai.com/api/docs/guides/your-data>

## Immutable synthetic inputs

Call 1 input:

```text
供应商质量有问题
```

Expected kind: `NEEDS_CLARIFICATION`.

Call 2 input, only after the first response is accepted and a new turn receives
separate exact authorization:

```text
供应商质量有问题

用户补充：目标是在季度末前把来料缺陷率降到百分之一以内，并由质量负责人确认。
```

Expected kind: `DRAFT_READY`. These are synthetic acceptance strings, not production
or personal data. The adapter must reject any other content under this gate.

## Data and Evidence policy

- Human approval must name the OpenAI organization/project and affirm its actual
  retention configuration. OpenAI's official data-controls page says API data is not
  used for training unless explicitly opted in, while default abuse-monitoring logs
  may contain prompts/responses and are retained for up to 30 days. `store=false`
  avoids Responses application-state storage but does not by itself assert ZDR.
- If the Human gate requires Zero Data Retention, the named project must already be
  approved/configured for it. Background mode is prohibited.
- Persist only allowlisted `model-draft-assistance-invocation-evidence.v1`: exact
  internal Model/Provider/Endpoint/Profile/adapter identities, authorization refs,
  binding snapshot/high-water, bounded provider request/correlation ID, call count,
  latency, token measurements, typed status and limitation codes.
- Do not persist raw prompt/response, their plain digest, HMAC commitment, pepper,
  credential, Authorization header, provider raw body or unrestricted diagnostics.
- Resource Use and Evidence completion use deterministic operation IDs. Their repair
  never authorizes another provider call.

## Acceptance and stop conditions

Pass requires two exact grants and current admission per call, exact resolver match,
one clarification then one schema-valid draft, at most two provider dispatches,
complete Resource Use/Evidence references, no raw-content persistence, visible
`REAL_PROVIDER` labelling, and no formal Problem until the Human clicks confirm.

Stop immediately, with no replacement call, on any credential-resolution failure,
model/endpoint/profile/digest mismatch, revocation/expiry/high-water change, budget
gate failure, unexpected tool use, policy mismatch, non-synthetic input, schema
failure, timeout, ambiguous transport, cancellation request, evidence allowlist
violation, or total spend reaching USD 0.01. Timeout/ambiguity stays `UNKNOWN` and may
only observe the original provider correlation. A retry requires a separately visible
successor action and new authorization outside this package.
