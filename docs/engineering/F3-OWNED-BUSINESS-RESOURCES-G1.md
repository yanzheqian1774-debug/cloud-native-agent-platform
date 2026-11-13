# Owned business resource/readonly adapter — G1 implementation plan

Base e226db0. Part C/D of F3-OWNED-BUSINESS-ADMISSION-G1; default disabled.

Reuse ResourceAutomation and ReadonlyContinuation and existing exact grant,
resource test, assembly and execution owners. New internal read-only owner port
is automation.owned_business.work(connection, context, exact problem,
source_digest=None, history=False). It returns only an existing admission and
current scope; it never grants or creates work. Bootstrap/policy/persistence are
owned by the companion admission package, not duplicated here.

When a legacy exact work cannot match, resolve that existing fact within the
current owner transaction. Derive a bounded WorkScope/ReadonlyWork carrying
admission identity/policy digest; enforce exact source/capability/employee,
actual member skill/runtime references and allowed task operations. Never use
publication or READ as USE/START. Disallow automatic creation of alternate
employee definitions/skills/runtime profiles for this scope. Keep legacy behavior unchanged.

All existing grant requests, resource validation, runtime probing, USE/START,
execution idempotency and worker authority remain. Bind derived scope digest
into preparation/continuation receipts so policy/admission changes cannot reuse
old preparation. Reads revalidate revocation; history mode may not feed grants.

Tests: default-off and legacy compatibility; allowed derived exact scope;
wrong source/capability/member/operation, revoked/expired/foreign binding,
READ without START, forbidden automatic synthesis, changed policy receipt;
real owner integration after shared owner lands. No DB/model/real host action.
No frozen contract, CRD, lifecycle, model or new infrastructure changes.

Additional implementation discoveries
- Automatic coverage must enumerate the admitted exact employee revisions,
  rather than select an unrelated latest published employee and fail later.
- ContinuationWork's static works list is adapted to the same saved admission;
  absent owner injection does not consume an owned-business receipt.
- Eligibility alone is insufficient for revoke/claim races. The original Native
  authorization_bundle_check invokes authorize_dispatch in its own transaction,
  checking the exact Attempt->Run/preparation and receipt before existing grant
  checks. The shared admission reader serializes current work/revoke on its
  existing exact-admission lock. No new lifecycle transition or effect executor.
- Historical direct compositions may legitimately have capability=None. In this
  branch the exact already-published employee/member tuple remains mandatory;
  no synthetic capability is created. An explicit mismatched capability fails.

Package ownership: this branch adds the Native authorization callback/closure;
companion admission branch owns only the ContinuationWork.load owner injection.
Standalone consumption tests use a controlled admission read port with actual
resource/grant/Plan/Native-queue owners; this is not evidence of a real deployed
standing policy or provider invocation. Shared persistence integration is separate.

### Same-owner integration and Native host provenance

- Explicit `question-activity-input.problemId` requires that exact problem's READ;
  the unscoped legacy entry retains BUSINESS_PROBLEM LIST. Source discovery and
  confirmation pass the existing owner connection into the owned work reader.
- Owned planning-input observation uses only the admission scope's exact employee,
  agent, runtime, skill and source bindings. Member READ remains mandatory; visible
  operations are intersected with the standing scope. This is not USE/START.
- The host environment variable is `OWNED_BUSINESS_ADMISSION_POLICY`.
  When set, startup configuration `policyFiles` must include that variable with
  the SHA-256 of the exact owned file. Startup and each current observation reject
  missing or changed file bytes via the existing provenance verifier. When unset,
  the prior host configuration remains compatible. This does not activate a policy.
- Startup-preparation tooling must carry that exact path/hash alongside authority,
  loop and continuation policies before the governed worker is started; omission
  is a startup failure, not permission to run without admission verification.

### Offline startup preparation r2 (follow-up to the preserved r1 evidence script)

The r1 `new-native-question-startup-plan-r1/prepare_startup.py` is retained unchanged.
Its exact three-policy list and mandatory legacy `works` match are not valid for
new owned-business work. An r2 preparer must branch on the prepared receipt's
`ownedBusiness` proof, never append the new problem to the old `works` allowlist.

For an owned receipt, require enabled continuation policy plus the exact owned
admission policy path/digest in `policyPaths` and output `policyFiles`. Require an
owner-produced read-only export of the actual persisted admission and preparation:
same admissionId/recordDigest/policyDigest/scopeId/authorizationBasisDigest,
actor/tenant/domain, generation, exact actual problem/source/content digest,
current expiry, rule binding and prepared digest. Compare the receipt against the
immutable record and current policy selection; do not accept a caller-written
`consumer` flag as evidence. Missing/unknown/revoked/mismatched provenance stops
preparation. The runtime owner still rechecks current grants/policy/record; an
offline export or host manifest is not a grant and cannot override revocation.

Preserve the precise `governed-execution:prepared:<preparationDigest>` authorization
resource and host source/launch hashes. Legacy receipts continue through the
existing exact `works` branch. The r2 preparer is planned, not implemented or run
by this C/D patch; root owns real installation/configuration and actual host launch.
