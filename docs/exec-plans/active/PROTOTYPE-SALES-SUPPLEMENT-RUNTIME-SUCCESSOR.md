# Sales supplement runtime successor — bounded G1

Task: preserve fixed 1044e411 and its independent 28-case review. In a derivative
worktree, wire the actual app entrypoint's default-false sales-v2 and supplement
parameters; provide a compatible close/rollback profile for Human supplement
records; prepare only the four existing v2 frontend overlays on the exact
installed JX02 frontend. No actual installation, activation, new login, Grant,
publication, provider sampling or business execution. Do not alter JX03.

## Gate review before code

Read AGENTS, Architecture Gates, Decision Status, accepted D11, workflow/DoD,
current app/bootstrap/composition/proposal readers and the preserved preflight.
This is G1 for a bounded entrypoint adapter and read-only compatibility wiring.
No public CRD/frozen Contract, Task/Workflow/Runtime lifecycle, authentication,
tenant, datastore or cross-owner authority changes are needed. D11 explicitly
requires rollback to disable new effects without deleting historical facts.
No G2 condition found. Configuration authorizes no identity or resource access.

## Design and interfaces

1. Add a strict, documented two-boolean feature configuration consumed by
   app._configure_workbench, with default false. Use the existing environment
   names only after real code consumes them; malformed values or supplement
   true without sales-v2 true fail closed. App forwards both exact parameters
   to the existing bootstrap. No live environment/config file is changed.
2. Retain 1044's ProposalRevision Human origin reader regardless of write flag.
   Compose original-key GET receipt ports when the existing owners are present,
   independently of the supplement write flag; keep current exact authority
   checks unchanged. Compose the two POST adapters only with explicit enabled
   flags and all existing dependencies. No new database or receipt ownership.
3. Compatible close/rollback target is this successor code (the reader floor)
   with both feature flags false and the preserved finite JX02 frontend.
   New adapter writes and confirmation of an unconfirmed Human supplement stop;
   old/new proposals and receipts remain readable
   only with their existing exact permissions. Legacy Plan confirmation and Run admission stay separate governed owners;
   the origin-specific close guard does not invent
   a cancellation, revoke existing approvals, or grant execution. Already
   confirmed results recover by GET, not a repeated confirmation POST.
   Never downgrade to an unmodified 4f1 reader after new Human-origin writes.
   No row deletion, origin rewriting, migration or old-digest change.
4. Offline frontend composition: exact installed 205 source files plus only
   PreparedDeliverySummary.tsx, artifactProvenance.ts, salesGrossProfitReport.ts,
   SalesGrossProfitArtifactView.tsx already present in 9e/1044. Preserve all
   other JX02 sources. JX03 tree/assets stay untouched; do not claim combined
   JX03 semantic acceptance. No new product path or fabricated actual Run.

## Validation

- Actual app function startup with default/off/on/invalid combinations;
  capture real forwarded parameters without actual DB/runtime/provider startup.
- Real existing BFF/owner transactions in disposable UUID64335 PostgreSQL:
  create an isolated Human supplement, switch to reader-only close profile,
  recover original-key receipts and old/new Plan/proposal records; POST absent;
  denied/revoked/foreign reads stay denied; old rows/hashes unchanged.
- Legacy serialization golden unchanged; reader-floor profile accepts old/new
  records without mutating their origin/digest. Exact current ACL remains.
- Required backend lint/format/full tests and unchanged normal commit hooks.
  macOS make is unavailable under the unaccepted Xcode license; run the same
  required commands directly. No hooks bypass and no actual DSN in tests.
- Offline combined frontend lint/build, existing original-path JX01/JX02 and
  saved gross-profit-v2 readback/negative cases. Keep fixture/actual acceptance
  distinct; no rerun of the frozen JX03 browser suite or actual two business Runs.
- Verify 1044/JX03 fixed source hashes, installed source/bundle, protected
  business/authority rows, budget/UNKNOWN and original artifacts unchanged.

## Delivery

Freeze successor commit/tree, focused diff, exact supported flags and compatible
close instructions, current checks, offline frontend source/build manifest and
original-path screenshots. Continue existing output entry; preserve all earlier
candidate packs. No independent acceptance, deployment or business acceptance
is inferred from author tests.

## Supported configuration and compatible close

These keys are now parsed by actual app._configure_workbench via
SalesSupplementFeatures, not merely listed as example environment variables:

| SALES_GROSS_PROFIT_V2_CANDIDATE | SALES_SUPPLEMENT_CANDIDATE | Behavior |
| --- | --- | --- |
| unset/false | unset/false | V2 registry off; historical GET readers retained; new supplement writes/confirmation closed |
| true | false | Existing v2 owner support only; supplement writes/confirmation closed |
| true | true | Two POST adapters and Human-supplement confirmation can run only under existing exact authority |
| false/unset | true | Fail closed before building runtime dependencies |

Only exact lowercase `true`/`false` are accepted. Other supplied strings fail
closed. Both flags default false and provide no Grants, role, issuer, source,
publication, model budget or execution admission. Closing does not cancel or
rewrite already approved Plan/Run facts; execution authority remains separate.

Historical receipt GET ports use exactly the 1044 grant builders/handlers.
They are registered with both existing owners even when writes are disabled;
missing dependencies leave them unavailable. They never repeat POST. The
Planning owner carries the supplement mode across its BFF transaction adapter;
unconfirmed Human-origin confirmation while closed returns 409
SALES_SUPPLEMENT_WRITES_DISABLED after checking exact Plan APPROVE authority.
Legacy-origin confirmation remains unchanged. Existing approvals recover by
read-only Plan history, not repeated confirmation while closed.

The compatible rollback profile retains this successor's reader-capable code
and all 1044 dependencies, sets both flags false, keeps Native stopped after
verifying no in-flight commands, and serves the preserved JX02 finite frontend.
New/old origins and original receipts are still readable with current exact
permissions. Switching back to unmodified 4f1 after Human-origin writes remains
unsupported. No database snapshot restore, record deletion, digest/origin
rewriting, old UNKNOWN replay or Grant rewrite is part of close/rollback.
No actual installation or close operation was performed in this task.

## Author checks recorded before freeze

Targeted backend: 43 passed (new runtime/compatibility, existing owner cases and
bootstrap), followed by 11 passed in the expanded runtime set, including two
real bootstrap owner/mode propagation cases; explicit disposable UUID64335 DB, fixture sessions/ACL, no actual
provider or Run. Offline frontend: exact installed 205 sources + four v2
files =207 sources; all other 203 preserved; lint/build and 25 saved original-path
browser cases passed (18 JX01/JX02,7 original sales/v2 positive/negative cases).
Browser backend fallback is explicitly 127.0.0.1:1, so it cannot use actual
19436. These are isolated author checks, not live UI/IAM/business acceptance.
Full required checks and normal commit hook outcome are recorded in the final
external evidence manifest after freeze. Existing warnings are retained.
