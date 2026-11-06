# GPT-6.1 SOL planning migration — bounded G1

Human direction 2026-11-06: switch the platform supplier/sales planning runtime
from Kimi to exact `gpt-6.1-sol` to compare the existing failures. This supersedes
the earlier no-model-change constraint for planning only. The owner supplied a
local project key; metadata GET returned HTTP200 and exact model ID. Billing and
Responses execution remain unverified. No Codex login credential is used.

## Implementation

Preserve current prompts, graph/input_kinds validators, 5/55/60-second timeout,
8192 output ceiling, worker cleanup and no retry. OpenAI planning explicitly sends
reasoning low, Standard service_tier default and explicit caching mode without
breakpoints (no cache writes expected). Accept only reasoning/message envelopes,
exact model, completed response and the unchanged strict inner output contract.
Reject unexpected service tier or cache usage for cost reconciliation; retain the
reservation when reliable Standard uncached metering is absent. No fallback.
Legacy OpenAI and Kimi request shapes remain unchanged.

Use the SAME original ledger. Its immutable root policy/history is not rewritten.
A separate append-only profile-price binding names the exact root-policy digest,
new profile digest and same original policy caps; every new reservation binds its
price revision in the same transaction. A settlement guard prevents an old binary
from pricing GPT reservations with Kimi prices. New runtime startup requires this
explicitly prepared schema/binding; it must not auto-migrate/reprice old rows.
Existing development admission continues owning the approved aggregate100/USD50;
the root8/USD10 is preserved historical policy, not a reset. New model authority,
configuration and role continuation remain independent prerequisites.

## Stages and evidence

1. Isolated code and real64335 PostgreSQL tests: profile parser, correct protocol,
   reasoning envelope, HTTP/timeout/UNKNOWN/no retry, bad usage/tier, immutable
   mixed-price ledger, original UNKNOWN retained, caps and cross-profile denial.
2. Freeze reviewable source/config template and isolated evidence. Keep actual
   installed3ced914 during fixed UI review. No private key in artifacts/logs.
3. Prepare fresh exact provider/endpoint/connection/model/profile resources and
   owner-readable authorization/config manifest. Existing D8/D9 fresh bounded
   task+context admission is the shortest candidate route: current enabled local
   accounts and separate real issuer, exact new configuration/model target,
   preserved recovery evidence and100/USD50 aggregate. This route does not
   require reviving the expired legacy323 continuity. Its old preflight alone
   must not be reported as blocking every new request. Actual independent
   signature remains distinct from source/config metadata.
4. Once platform authority is effective, new supplier and sales requests only,
   same approved aggregate ledger. Record returned model/status/usage/estimate,
   timeout/validation/Plan/Run/artifact separately. UNKNOWN stops same-condition
   sampling; no old replay or release. Unrun cases remain unverified.

Official evidence (checked2026-11-06):
https://developers.openai.com/api/docs/models/gpt-6.1-sol
https://developers.openai.com/api/docs/pricing
https://developers.openai.com/api/docs/guides/prompt-caching
https://developers.openai.com/api/reference/typescript/resources/responses
Standard uncached short-input rates are2/10USD per million input/output tokens.
The explicit mode without breakpoints avoids cache writes; unexpected cache
counters or service tier never produce a falsely settled estimate.

Cross-generation OC-323-CHAIN-v1.1 work is checkpointed in the original branch's
stash. It is not installed or claimed complete. GPT shortest dependencies take
priority, UI-01 remains queued. S04 candidate3d52282 is inherited but not installed.

## Historical receipt compatibility closeout

Current-price comparison previously refused old Kimi receipt reads after profile
switch. Add a read-only historical binding check after the existing exact READ
permissions: original ledger, exact reservation/invocation, immutable root or
reservation-bound price digest, then existing settlement projection. Historical
GET never dispatches, settles, releases or reprices old UNKNOWN. No permission
grant is created and foreign/tampered receipts remain rejected. Include real
isolatedPG mixed-price reads and grant-before-lookup negatives.

First mandatory full run:2616 passed/257 skipped/1 existing cancellation boundary
failed before endpoint acceptance at its1-second STARTUP deadline; same unchanged
test recheck passed in3.58s. Preserve both logs; do not weaken/remove the test.
Historical compatibility changes require a fresh complete mandatory run.

The named GPT v1 Standard/uncached price policy pins2/10USD rates and a short-input
bound below272000 tokens. Zero, legacy Kimi/older rates or a long-input bound are
configuration errors; a future pricing/model change requires an explicit revision.
Historical reads are additionally scope-bound and work in READ ONLY transactions.
