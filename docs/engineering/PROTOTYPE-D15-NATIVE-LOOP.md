# D15: Native observation-driven execution loop (G1)

User scope: advance Native independently of OpenClaw; reuse current task,
resource, authorization, model accounting and result owners. Demonstrate a new
non-sales/non-delivery/non-cost question in its original conversation, with an
actual tool observation causing the model to select its next action.

## Boundary and sequence

Implement an internal runtime loop within one authorized task/attempt. It does
not change CRDs, lifecycle semantics, public frozen contracts or persistence
ownership. No new database, external service, arbitrary code or desktop access.
OpenClaw files and its independent checkout are outside scope.

1. Add a provider-independent loop with immutable goal/criteria/tool descriptors,
   bounded observations, validated actions, per-action authorization and budget
   admission, cancellation/deadline/step limits, and independent finish checking.
2. Keep model decisions and tool results separate. Persist a claim before each
   effect through an injected owner journal; terminal observations include exact
   input and output commitments. An uncertain claim is never automatically replayed.
3. Adapt existing governed model and Skill invocation owners, not their raw
   transports. Preserve their exact resource versions, principal, budget receipts
   and task/attempt correlation. No model key or endpoint in user inputs.
4. Project decisions, observable reasons, tool observations and verified results
   in the original conversation. Do not expose private chain of thought.
5. Validate an unfamiliar synthetic read-only diagnostic question with different
   possible observations. Demonstrate divergent next actions, not a fixed script.

## Validation

Core tests: observation changes next action; unsupported tool and bad arguments;
finish rejected without evidence; missing data; deterministic no-progress guard;
step/deadline/cancel limits; authorization revocation; ambiguous effects;
crash/replay; context limits; exception sanitization; independent verification.
Adapter tests must use existing isolated repositories, never reset the live DB.
Run repository checks and affected frontend checks. Real-model browser acceptance
must record decisions, exact source/tool/model references, usage, final artifacts,
and independent recomputation. Core/mock tests do not count as live acceptance.

## Risks and admission

Tool output is untrusted data. Model intent cannot widen the allowed tool set or
side effects. A successful finish requires independent evidence checks and is not
business acceptance. An expired/cancelled call cannot begin another action.
Blocking I/O requires the adapter's supervised deadline; a loop deadline alone
cannot terminate an uncooperative driver. Uncertain outcomes remain inspectable.

No production or whole-project acceptance is implied. This stage remains
incomplete until governed adapters and original-conversation demonstration pass.

## Implementation checkpoint (2026-11-09; NOT stage acceptance)

Implemented internal NativeLoop and a read-only operation library reusing
TabularDiagnostic computation and its independent evaluator. Scripted decision
conformance exercises a new application-response-time dataset with normal,
above-limit and missing-value variants. Only the latter two select original-row
inspection. These are real calculations with scripted decisions, not a model
or browser demonstration.

37 new focused tests pass; runtime plus diagnostic regression is 136 passed.
Repository lint and formatting pass. Initial full suite: 2486 passed, 692
infrastructure-dependent skips, two Git provenance failures caused by macOS
system Git exit 69. Rechecking both affected files with the installed fallback
Git: 35 passed. The final two loop hardening tests were added after full-suite
collection and are included in the 136-test regression. No tests were weakened.

Remaining implementation, in dependency order:

- Bind each runtime decision to a genuine governed model invocation, exact model
  revision, original task/attempt principal, current authorization, existing
  budget reservation/settlement and supervised provider deadline. Existing
  PlanningSuggestionService is plan-specific; do not disguise runtime decisions
  as plan proposals or bypass it with unaccounted direct HTTP calls.
- Implement durable loop/effect claims in the current execution/Skill ownership
  boundary. The current Skill store has UNIQUE(namespace, security_domain,
  attempt_id): several ordinary Skill invocations cannot be silently inserted
  for one Attempt. Choose bounded internal operations of one published executor
  revision, or explicit existing task boundaries; do not weaken that uniqueness.
- Publish a distinct loop-capable executor revision and exact resource bundle;
  preserve the installed deterministic executor identities and behavior.
- Wire the new revision into preparation, Native composition and source/tool
  capability observation, with explicit admission and isolated integration tests.
- Project actual decisions/observations and verified result in the original
  conversation. Never present scripted decisions as real model execution.
- Run actual model acceptance, compare normal/abnormal observations, capture the
  original-conversation demo, and independently verify artifacts and accounting.

No production composition, migration, real provider call, frontend route,
installation, current process restart or historical execution replay occurred in
this checkpoint. OpenClaw adapter files are untouched. Existing platform remains
on aa900c0177e921d9bea31b1e870a43217f808841. No user decision is currently needed;
remaining work is implementation and verification, not an approval wait.
