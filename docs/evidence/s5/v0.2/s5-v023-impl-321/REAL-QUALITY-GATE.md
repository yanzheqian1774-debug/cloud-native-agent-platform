# Separate real-model quality gate — NOT AUTHORIZED / NOT MEASURED

The G1 implementation authorization permits deterministic engineering validation,
not real provider dispatch. No applicable independent call authorization has been
received. No real credential was read; 319 windows, budgets and credentials cannot
be inherited.

Frozen cases: `console/backend/tests/fixtures/s5_321_quality_cases.json`.
Use the 16 human-review oracles in the G1 plan. Maximum proposed comparison: old v1
and new v2, 16 cases each, at most two dispatches per case (64 total), no retry or
provider fallback. Input at most 16384 UTF-8 bytes per invocation, output at most
1024 tokens. These are proposed caps, not authority to call or a monetary budget.

Before execution, Human must fix candidate source/tree, exact model/provider/
endpoint/profile revisions and digests, adapter revision and policy digest,
dataset digest, credential reference, current authorization window, numerical
currency/cost cap and pricing authority, timeout/cancellation bounds, provider
retention/training/region policy, and raw-output review/retention permissions.
All these provider-specific values are PENDING; they must not be guessed.

Review both versions against fixed case oracles without repairing outputs before
scoring. Record raw counts for repeated questions, unsupported atomic facts,
missing required facts, semantic edits, user sends and confirmations. Unknown,
timeout, refusal and budget failures remain in the denominator. Model factual
claims cannot gain platform authorization. A supported sourceRef proves only an
input reference exists; semantic entailment requires review.

Stop on unauthorized dispatch, content persistence, authorization leakage, cap or
window exhaustion. Quality hard failures remain failures. Engineering tests,
manual corrections and formal Problem creation never upgrade model-quality status.
