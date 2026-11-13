# Structured understanding wire successor (G1, default off)

## Evidence and scope

Actual settled responses 344aae9a / c90e7c4b failed locally with
UNDERSTANDING_DUPLICATE / ADOPTION_TOKEN_KIND. Existing V2_SCHEMA allows repeated
array field names; inherited relation schema independently permits a null token.
This is a wire/domain mismatch, not a transport retry condition. Preserve both
failed invocations and their metering. No automatic retry or model call here.

Introduce an independently identified internal adapter/wire successor. Existing
v1-v3 policies, profile digests, persisted results, public API and frozen owners
remain unchanged. No migration, new infrastructure, permissions, budget increase,
deadline change or new routing call. The original single response still supplies
both routing and the complete understanding or typed Native answer.

## Official provider constraints checked 2026-11-14

Source: https://developers.openai.com/api/docs/guides/structured-outputs

Root must be an object; nested anyOf is supported. Every object declares all
properties required and additionalProperties=false. Do not use if/then/else,
allOf, not or dependentSchemas. Use enum for exact known values and bounded arrays.
Refusal, incomplete output and business invariants remain locally checked.
This does not claim that a real provider request has been accepted or succeeded.

## Wire and compilation

Root is {result: <nested anyOf of complete valid branches>}. A DRAFT_READY or
NEEDS_CLARIFICATION understanding is an object with exactly goal, scope, time,
constraints, successCriteria and openItems. Each fixed slot holds the original
value/source/sourceRefs; openItems has at most seven entries, preserving original
five-to-twelve domain items. Empty-result branches retain an empty array.

Compile branches from the SAME already sealed SERVER_CURRENT_CONVERSATION used
by the request. No current question => no CURRENT_QUESTION branch. UNDERSTANDING
permits the three full result kinds; PLANNING/NATIVE permits only the original
CURRENT_QUESTION_ANSWER. Current token is a required string enum containing only
the original token; all other branches require null. No client input selects this
token and the decoder never inserts or repairs it. Typed Native candidates and
contract digest come only from the existing validated answerContract; CONFIRM,
CHANGE, REJECT and UNCLEAR each have a legal candidate/null branch.

Strict JSON parsing rejects duplicate object keys. Normalize only the structural
fixed slots into original field records, in fixed order, preserving all model
text/provenance and the actual returned token. Re-run existing domain validation
and exact snapshot route/owner checks. Do not ignore duplicate fields, infer an
answer, merge conflicting meanings, or replace malformed values.

## Implemented composition and release boundary

A/B: new immutable adapter `v4-structured-conversation` and output wire
`conversation-understanding-wire.v4`. The policy digest includes the static
branch template, instruction and compiler/decoder version markers. Actual
prepare narrows this template from the sealed snapshot. The FULL serialized
request (including schema) is included in the original input bound. Completion
recompiles from that exact prepared request and rejects schema drift; it does not
consult a newer journal. Old adapters retain their own policies and decoders.

C: explicit optional `STRUCTURED_UNDERSTANDING_RUNTIME_FILE` and
`F3_STRUCTURED_UNDERSTANDING_POLICY` compose the successor.
The immediate predecessor must be the installed typed v3 service. Historical
services remain typed/source/adoption/C1 in order. Native typed-answer settlement
selects only a unique installed adapter/profile ID/profile digest triple and
calls its original budget reader on the existing connection. Missing/duplicate
profiles fail closed. Default off and startup cleanup are tested.

D: ordinary-session BFF tests use actual conversation/adoption/READ/CAS owners,
actual Responses prepare and SSE decoding with a controlled HTTPS socket. They
prove one new response, one adoption, repeated GET/POST without dispatch, old C1
reading, revoked source READ refusal, and an explicitly requested successor of
a retained FAILED invocation in the same conversation. These tests retain the
existing controlled usage fixture; a separate actual PostgreSQL budget test
proves old/new profile pricing and settlements share the same ledger and cannot
be substituted. This is complementary evidence, not a claim of one full real
provider+budget+business execution demonstration. No production calls occurred.

Root alone registers/prices/approves/publishes/enables the concrete successor.
The standing approval record must name this candidate; do not claim an individual
human review or reuse a prior frozen policy digest. Same original allowance,
ledger, call/cost cap and deadline; no new permissions. Concrete runtime input
and output limits must fit the already authorized context and provider model.
Existing failed and UNKNOWN facts remain unchanged. Actual provider acceptance
and a bounded original-conversation demonstration remain release verification.

## Validation matrix

Pure: fixed slots/no duplicates; 0/7 openItems; required slots/extra field rejection;
duplicate JSON keys rejection; current null/missing/wrong/stale token rejection;
no-question current relation rejection; UNDERSTANDING vs Native/Planning kinds;
independent answer while question pending; valid full draft with original refs;
typed CONFIRM/CHANGE/REJECT/UNCLEAR and foreign candidate/contract rejection;
all schema objects closed/required, no root anyOf or unsupported composition;
old policy schema/digests unchanged. No network or credentials.

Adapter stage: exact prepared schema and input budget, one SSE response, refusal,
incomplete SSE retains TRANSPORT_AMBIGUOUS/UNKNOWN, completed invalid output remains failed/settled, no retry, raw-to-domain identity.
Owner stage: original target/source/subject/version CAS, revoked grant and stale
question, one call/one settlement, historical GET uses old decoder. Release needs
root normal checks and bounded actual verification, never rerun old failures.
