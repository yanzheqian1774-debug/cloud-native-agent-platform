# G1: bounded source body for retained initial understanding

Status: isolated implementation candidate; disabled; no model registration,
publication, real invocation or production mutation authorized by this document.

## Evidence and change boundary

The published `v3-relation-adoption` adapter deliberately projects a selected
source to metadata. Its test asserts that document body is absent. The observed
NEEDS_DATA is therefore a valid response to an incomplete input, not a failed
model. Preserve that invocation and the old adapter, instructions, schema,
profile, policy and historical request payloads.

Introduce an immutable `v3-relation-adoption-source` adapter revision. Reuse the
existing output schema and instruction bytes. Its new policy/profile digests
must be explicitly reviewed before activation. Keep one model invocation per
new message, the original shared allowance and deadline, and the existing
complete encoded-request input bound. No additional tools or data domains.

## Trusted input boundary

Only a server-sealed current UNDERSTANDING question may receive source body.
The source reader must perform current exact READ and return the exact published
synthetic snapshot. A same-source continuation compares the server metadata
digest to the original pending question's inputSourceDigest. A first selection
still requires the existing adoption owner's explicit source-null transition
checks. A name, user-supplied reference, client snapshot or claimed digest cannot
authorize content. Stored raw-byte content digests must not be recomputed from
parsed JSON with different lexical formatting.

Native and planning questions and independent conversation context retain
metadata-only input. C1 remains unchanged. Body is untrusted data, never source
instructions, business authority, proof of execution or a result.

## Current retained conversation compatibility

The current conversation has already selected a source and has a successful
NEEDS_DATA result. Continuing with that same exact source is supported; it is
not source replacement. Do not require a new conversation or repeat the old
model request. Retain explicitly configured old C2 readers and admissions when
enabling the successor. Resolve each historical invocation with its recorded
profile; never use only the current default or an arbitrary latest profile.
Adoption ancestry must continue through the exact retained old/new C2 results.

## Implementation and acceptance

1. New immutable adapter policy and bounded trusted attachment helper; existing
   old policy output remains byte-identical. Reject malformed, changed,
   non-synthetic or unverified source envelopes before any dispatch.
2. Optional runtime wiring, default off; retain old C2 and C1 readers. Current
   pending owner and source continue to use exact version/CAS checks.
3. Exact offline candidate and NEEDS_HUMAN_REVIEW review packet, same shared
   ledger/allowance/caps/deadline. Registration sequence is checked by root.
4. Offline complete runtime prepare tests, zero network/credential resolution;
   whole-payload bound includes source body. Old C2 payload exclusion regression.
5. Isolated real-owner tests for old C2 NEEDS_DATA to new successor with same
   selected source; source-null selection, wrong subject/source/version,
   revoked READ and stale question failures; no duplicated invocation/adoption.
6. Browser continuation through the existing fixed input with controlled model
   results; actual model acceptance and deployment are root-owned later gates.

No migration, new public contract, CRD change, new ledger, implicit business
grant, USE/START renewal or UNKNOWN retry is part of this package. The separate
owned-business admission package remains necessary for new business execution.

## Isolated validation / delivery status

Base e157d33231ab2151fb5eb2cc52fef85c5f86d476 includes the same-transaction
source lock fix and the supervised successful-cleanup fix. New code remains off
unless BOTH `UNDERSTANDING_SOURCE_ADOPTION_RUNTIME_FILE` and
`F3_UNDERSTANDING_SOURCE_ADOPTION_POLICY` are supplied. Keep the old C2 and C1
runtime/policy environment variables intact. No migration is introduced.

The full targeted set collected 128 tests: 127 passed; one newly added foreign
administrator fixture lacked the actual controller readiness generation. Only
that fixture was corrected to use its real generation (no allow decision), and
the failing case passed separately. Source-null, retained old C2 NEEDS_DATA with
same selected source, READ revoked before dispatch and before adoption, foreign
subject, old profile/history and default-off boundaries are covered. Model
responses/usage are controlled; sessions, READ/revocation, exact source and
adoption persistence use the real isolated PostgreSQL owners. Complete runtime
Responses prepare tests use no network or live credential and include full
payload bounds. Production model semantics are NOT accepted by these tests.

Evidence under work/evidence/f3-understanding-parallel-20261113:
`adoption-source-body-complete-r1.log` and `adoption-source-subject-r1.log`.
Earlier invalid-observation fixture failures are retained in r1/r2 logs; no
production check was relaxed. Final Ruff and formatting pass; a punctuation-only
fixture lint correction followed the targeted run. Normal combined commit hook,
default-off actual install and human review/actual successor validation remain
root-owned gates. No actual system, model call, table or allowance was modified.
