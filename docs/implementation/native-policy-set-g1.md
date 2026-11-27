# P1: one exact-host manager, typed Human / bound-Service leaves

Status: G1 internal composition successor; default OFF. No CRD, lifecycle,
authentication, budget cap, grants, schema, claim/fence or UNKNOWN changes.
The frozen 66 and P0 packages are inputs, not edited. Integration base is
32b1b5c2a17fbf4a10bf98774b780bb9b52186d5 (66 dbb0ff + P0 d8390fab).

## Actual gap and existing owners

`native_host_service.main` takes the machine lock using the execution database
fingerprint before constructing its single assembly. Starting a second service
manager for the same database is forbidden. Replacing the Human-only manager
with the P0 Service-only manager would stop discovering Human work.

`Discovery` already provides the necessary read-only leaf: page/current/maintain/
stopped. Human uses original `_owned_receipt`; Service uses
`BoundServiceExecutionBridge` / `_service_receipt` and the real
ServicePlanningRegistry, 0070 / 0073 and current exact START authorization.
The multiplex layer must not implement another authorization owner.

## Explicit opt-in composition

A new private `native-exact-host-policy-set.v1` document will contain exactly two
bounded typed leaves, HUMAN_OWNED and BOUND_SERVICE. Each points to an existing
exact-host configuration and SHA, plus a private explicit environment-file SHA.
The environment file stores paths/configuration selectors, not inline tokens.
Both leaves must have the same canonical execution DB fingerprint and state
root; manager capacity/poll/stop/restart bounds are global. Each leaf has a unique
(namespace, securityDomain, principalId); duplicate scope is rejected even if
policies differ. No string prefix is accepted as proof of Service identity.

The set is not a grant. Before assembling, validate all files/pins, exact mode,
identity and disjoint scopes. Build each original assembly with an immutable
explicit environment mapping. Construct the original Discovery for that leaf;
its original owner proves eligibility. A candidate must have exactly one
scope-selected leaf AND pass that leaf's current owner check. No match,
ambiguity, authorization error or unavailable observation means no launch;
never fall back from Service to Human.

Legacy absence of the new selector uses the unchanged singleton path. Existing
mixed OWNED_BUSINESS + NATIVE_BOUND_SERVICE environment remains forbidden.
A child receives only its selected immutable leaf environment. The child still
uses the original startup observation, source/policy pins, exact command and
subject. No process-wide `os.environ` mutation is used during assembly or tick.

## DI closure needed before activation

1. `build_native_dispatch_from_environment(environment=None)` snapshots an
   explicit mapping (legacy None captures current environment). Every get/getenv
   in this builder must consume it.
2. `Configuration(path, environment=None)` validates and captures leaf-specific
   paths; pin verification uses the captured leaf. Legacy ambient change checks
   remain for the singleton case.
3. `prepared_native_composition.compose` -> `NativeLoopRuntime` ->
   `build_planning_runtime` -> existing
   `provider_budget_extension.configure_from_environment(owner, environment)`.
   Preserve Native base 20 / $1 and <=24 guard independently from the approved
   global ledger selector 200 / $20 and exact eligible context / allowance.
4. `OwnedBusinessWorkReader` -> retained readers and
   `ontology_action_correction.project` must use an explicit captured correction
   selector. Other callers retain legacy default behavior; empty leaf environment
   must not accidentally fall back to the parent environment.
5. `HostService.launch` selects its leaf configuration only after the current
   observation, then passes original leaf startup manifest/policy pins and child
   environment. Global children/state/worker locks remain one manager's.
6. Maintain and stopped callbacks route by the same exact identity, never current
   latest policy. Changed/removed leaf cannot adopt an old child; original owner
   failure closes control and preserves UNKNOWN/exit-proof handling.

## Minimal implementation stages and meaningful checks

A. Implement a bounded typed discovery router with exact scope selection,
   duplicate/no-match rejection, deterministic fair page interleaving, preserved
   current/maintain/stopped calls, and no writes/assembly/launch side effects.
   Four controlled tests: simultaneous Human/Service discovery; duplicate and
   unknown scopes reject; revocation/UNKNOWN never fall back; maintain/stopped
   remain on original leaf across page refresh.
B. Close the explicit environment DI chain above and add constructor tests with
   contradictory ambient selectors, showing each leaf's own policies reach
   the original builder and ambient state remains byte-for-byte unchanged.
C. Mount a single opt-in manager after pinning the set and leaves. Test one
   original machine lock and maxHosts across both actors, current recheck before
   Popen, child-specific environment/startup pins, restart and durable WAIT.
D. Isolated real owner test: one Human preparation plus one Service preparation
   from P0, one manager, both discovered under real authorization; withdrawing
   either leaf does not authorize the other. Controlled transport/Kubernetes
   must be labelled; no actual model call or production activation.

A alone is a feasibility primitive, not simultaneous platform availability.
B/C/D are activation gates. No factory is called in a read-only check merely to
inspect configuration: existing constructors migrate/configure, so constructor
validation is confined to disposable isolated DBs and records this fact.
No actual/private reads, DB, signals, model, grant or runtime changes authorized
for this implementation agent. Root owns eventual reviewed activation.

## First feasibility candidate (not mountable / not deployable)

Implemented: A routing primitive, and explicit environment parameters threaded
through the B source chain. Default singleton call shape is retained when no
explicit mapping is supplied. Correction readers capture a copy, including empty
map semantics; budget configure consumes only the supplied leaf selector.
Original per-loop/global budget fields and all caps are unchanged.

Executed: 21 controlled pure/config tests in 1.65 seconds (includes existing P0
config regressions; earlier 20-pass run overlaps, do not add). The production
reconciler function is exercised with controlled repository/transport factories,
not real PostgreSQL. It proves explicit Service environment is forwarded despite
contradictory ambient Human mode and does not mutate the ambient environment.
It does not prove the complete real model/budget constructor or two live workers.

Not implemented in this candidate: private typed-set loader, CLI opt-in,
HostService per-child configuration selection, combined startup/exit tests, real
Human+Service owner PG. The router is intentionally not imported by the running
manager. Thus no new mixed-mode activation path exists yet; old mixed-mode
rejection remains. C/D above remain required before runtime activation.

## R2 working successor (R1 feasibility bytes retained separately)

Typed loader and the opt-in main branch are now implemented. The new selector is
NATIVE_EXACT_HOST_POLICY_SET_CONFIGURATION; it is mutually exclusive with the
legacy singleton configuration. All nine actual loaded DI module paths must
match the pinned source root. Per-leaf environment files have a fixed key allowlist;
only PATH/HOME/TMPDIR/LANG/LC_ALL/TZ/PYTHONPATH process settings are inherited.
Model TLS uses the original pinned runtime tls.caFile (or system CA when null),
not ambient SSL_CERT_FILE / proxy / token variables. An explicit CA must exist
and its bytes are rechecked; original transport verifies TLS unchanged.

One manager owns the same original machine fingerprint lock, state directory,
maxHosts and worker identities. Child startup uses its selected leaf pins and
environment. The original WAIT exit-proof code now selects wait_access for that
exact candidate; it cannot silently skip Service stop confirmation. A failed
leaf observation is recorded, with no fallback, while unrelated leaf discovery
can continue. Closing attempts both assemblies even if one close fails.

Executed R2 evidence: 45 pure/config/physical-process regressions PASS 7.91s;
23 config/import-root tests PASS 2.13s; explicit CA mutation/missing negative PASS;
physical dual-child withdrawal test PASS 0.43s. These groups overlap.
Two isolated original-owner PG tests PASS 99.72s on port 53429: Human actual
adoption/Plan/START/Discovery, Service original 0070/73/START/registered-tool
execution and original-chat read. Each test has an explicitly empty controlled
peer. Therefore these do NOT demonstrate two real owners on the same database
and same active generation. They are not actual provider or production evidence.

Remaining release gate: same-DB, same-current-generation real Human and Service
assembly composition together, without mixing separately initialized authority
fixtures, and independent review. No actual policy set or credentials are made.
No deployment readiness claim until this gate closes.

## R3 same-database evidence and remaining product integration

R2 is retained unchanged as historical limited review. R3 adds startup-only
PolicySetAssembly and exact service_leaf lookup returning the original runtime,
work and execution repository; no request-time rebuild or identity synthesis.
All ten DI modules are pinned to their actually imported source root. Partial
construction and shutdown close all constructed owners.

The shared random-DB test declares Human and Service identities before its one
active generation, creates both preparations through their original owner
chains, and verifies the exact two preparations together. The original Service
registered tools complete and write their actual result/artifacts; the Human
preparation remains discoverable, and its later original revocation denies it.
The fixture no longer replays v9 foundation SQL over an already verified v34
plan-reference FK. It explicitly verifies that FK, without deleting constraints
or copying Plan/START/admission rows. Shared counts expect two real runs.

Joint-r8 passed 127.67s. Joint-factory-r9 passed 64.90s: real typed configuration
loader, both original reconciler builders, real repositories/authorizers and
WorkReaders/Service bridge construct in that same database, and both exact
preparations are discovered. StaticAuthorityLoader's generation input and the
Kubernetes adapter are explicitly controlled fixture ports; no generation
controller ceremony or actual Kubernetes is claimed. The factory test uses the
registered deterministic Skill mode without a Native model runtime. It proves
startup owner composition, not model transport/budget-configuration acceptance.
Final manager/config/assembly/physical-child group: 49 passed 5.93s, overlapping
prior groups. Own random database cleanup was confirmed.

This joint test exposed a real receipt-replay cross-connection governance lock.
R3 consumes the independently authored fixed-cycle-receipt-lock patch
069aec448e9e3fc16885c4654b5c8ba4360fbeea2fd5daf2e53e3cfa07633e23;
the read observation transaction closes before the original current READ
call_scope, which rechecks the immutable receipt in the same owner transaction.
The failed r6 trace and its narrowly cancelled waiting statement are retained;
only that fixture query was cancelled, then normal fixture cleanup removed its
random database. Later r8/r9 reached PASS without cancellation.

This is an engineering candidate, default off and not actual deployment.
Remaining product gates: explicitly versioned native_readonly Service policy
and generic adapter/runtime combined validation; exact real per-leaf model,
credential, source and budget pins; actual future schedule/authority windows;
independent review and root-controlled full checks/installation. No real model
or natural DAILY cycle, no new authority, no UNKNOWN repair and no 0078 ANSWER
activation occurred. Unfilled public templates deliberately fail validation.
