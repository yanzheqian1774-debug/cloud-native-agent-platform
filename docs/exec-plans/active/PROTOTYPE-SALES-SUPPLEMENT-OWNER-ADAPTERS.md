# Same-case sales supplement owner adapters — finite G1

Task authority: continuation of the already reviewed sales-v2 exact admission
preparation. One writer; derivative of 576f905d including the already verified
9e32812d v2 implementation. No actual publish, Grant change, Run, model,
installation or renewal. The expired JX03 fixture and all original keys remain.

## Gate assessment

AGENTS.md, ARCHITECTURE_GATES.md, DECISION_STATUS.md, accepted D11 and the
ARCH323 closeout/identity boundaries were inspected. This is G1: two additive
internal BFF adapters behind a default-false composition flag, using existing
Skill and Planning owners, existing exact authority and receipt storage. No
new CRD, DB/migration, identity/tenant model, resource ownership transfer or
Task/Run/Workflow/Runtime lifecycle is introduced. No explicit Frozen Contract
covering these internal optional planning provenance fields was found; code
alone is not freeze evidence under DECISION_STATUS.md. Existing public paths
and old serializers/digests must remain unchanged. Do not reopen ARCH323.

D11 allows additive same-owner evidence; changed criteria require a real
explicit business-owner action. The supplement therefore requires an explicit
Human requester, current exact reads of the new criteria and resources, and a
truthful Human-supplement origin. It never invents policy/model approval.

## Implementation

1. Prepared Skill successor adapter: exact MANAGE_RESOURCE on the existing
   Skill plus READ_RESOURCE on its exact published predecessor, aggregate CAS,
   published-revision/digest and current-draft guards. Use the existing
   SkillMcpService successor/edit methods in the BFF transaction. Keep generic
   ResourceManagement.owned unchanged; do not synthesize ownership receipts.
   Store a small exact receipt in existing prepared_resource_commands; GET
   original key rechecks current authority and never repeats the write.
2. Planning supplement adapter: append a proposal under the same Plan lineage,
   no model invocation, same exact Problem and source/content, unchanged task
   graph/operations/role/boundaries. Bind real new seven-criterion set and
   published new Skill/Employee refs, validate exact predecessor/member changes
   and source/contract. Preserve raw model proposal and all old Plan versions.
   Confirmation and execution remain separate existing owners. Store/recover
   original-key receipt in the existing command table, with current-read checks.
   New optional versioned Human supplement origin serializes old records exactly
   as before. No D10 equal-source workaround or namespace switch.
3. Register both only under an explicit default-false composition option.
   No runtime JSON/config changes and no frontend change/build.

## Validation

Disposable UUID PostgreSQL on 64335 only; never actual 64330 DSN. Real BFF/owner
transactions with explicit fixture identities and exact grants. Positive:
prepared successor and same-case source-preserving proposal, real returned
revision/digest, receipt recovery and legacy rows unchanged. Negative:
missing/revoked read or manage, foreign actor/scope/key, stale aggregate or
published ref, duplicate key/conflicting payload, existing draft, invalid
source/criteria/member/target, service actor, default-disabled composition.
Verify no Grant/provider/execution writes. Relevant legacy owner/Plan tests,
then required backend make check and normal commit hooks. No rerun of earlier
model samples, six-scene JX03 browser suite, or real original business Runs.

## Delivery

Fixed commit/tree, focused patch, tests and old serialization evidence;
source/actual runtime protection audit; original conversation return route and
remaining real version/criterion/employee/Grant/confirmation receipts. The
candidate is not installed or business-accepted.

## Reviewable interface and receipt examples

Composition is Python-only: `build_workbench_composition(...,
sales_v2_candidate=True, sales_supplement_candidate=True)` additionally needs
its existing planning and prepared-resource dependencies. Both flags default
false; actual runtime configuration and deployment are unchanged. There is
no schema migration. Disable by omitting the new composition flag; historical
receipts/proposals stay preserved. This does not grant any permission.

| Adapter | Method and path after `/api/workbench/v1` | Current exact authority |
| --- | --- | --- |
| Skill draft | POST `/prepared-resources/skill/{identity}/revisions/{revision}/successors` | SKILL MANAGE_RESOURCE on `skill-invocation:resource-management:skill:{identity}` and READ_RESOURCE on `skill-invocation:prepared-resource:{identity}:{revision}` |
| Skill receipt | GET same path + `/by-key/{command_key}` | Same current authority, same actor/scope |
| Supplement proposal | POST `/planning-v2/{proposal_id}/sales-supplements` | PLAN READ/PREPARE on `plan:v2:{proposal_id}`; exact old/new Employee, Skill, source and criteria reads |
| Supplement receipt | GET same path + `/by-key/{request_key}` | PLAN READ and current target/criteria/selected-resource reads; same actor/scope |

Skill POST fields are `expectedVersion`, `expectedPublishedDigest`, `content`,
`reason`, `commandKey`. The path binds the exact published predecessor. Receipt
contains predecessor and draft exact refs, current aggregate version, content
hash (distinct from lifecycle revision hash), reason/key, state DRAFT and
`published=false`, `executionStarted=false`. Successor then edit appends two
immutable draft revisions via the existing owner. Neither is a publication.
Generic ResourceManagement create/import ownership proof remains unchanged.

Supplement POST fields are `plan_version`, `plan_digest`,
`expected_proposal_revision`, `source_snapshot`, `new_target`, `employee`,
`skill`, `reason`, `idempotency_key`. Every ref contains `resource_id`,
`revision_id`, `digest`; new_target is the existing ProblemTarget shape.
The seven criterion records/set, published Skill and direct Employee successor
must already exist with real owner receipts. This adapter creates none of them.
The sole Employee member replacement must be the original selected Skill.
The original Employee is read as published historical composition without
requiring its old Skill to remain current; its exact READ and immutable hash
are still checked. New Employee/member availability is checked normally.
Only five bounded read-only sales-v2 operations and the fixed source content
hash are accepted. Task graph, stages, business rules and boundaries are copied.

The supplement receipt contains the new proposal, proposal digest, exact saved
request and original key; invocation_id is null and origin kind is
HUMAN_RESOURCE_SUPPLEMENT. It states confirmation_required=true,
modelCalls=0, executionStarted=false, businessAcceptance=OPEN. Normal Plan
confirmation rechecks the saved receipt, new target/source/resources and exact
reads. It remains a separate explicit action; Run admission is separate again.
No policy/model origin is forged and no old Plan/model proposal/Run is edited.

Original-key GET is historical receipt recovery, not current execution readiness.
It never replays POST or renews an expired identity. Repeated identical POST
returns the stored receipt after current authority checks; a changed payload
with the same key conflicts. Actor/scope and operation prefixes isolate keys.
CAS/predecessor conflicts return 409; unavailable target/receipt returns 404;
explicit-service/blank-reason requests are rejected. The existing BFF performs
session, CSRF and transaction handling. Failures persist no partial owner writes.

## Verification and remaining real-world evidence

Tests use explicit fixture sessions/ACL and disposable UUID databases only.
Positive receipts are recorded in JUnit properties for reproducibility; those
identities/publications are **isolated fixtures**, never actual IAM or business
acceptance evidence. Normal commit hooks run unchanged. Required lint, format
and full pytest checks are run directly: macOS make is unavailable because of
the unaccepted Xcode license; no license or system setting is changed.

Current delivery evidence lives outside the checkout under
`work/evidence/sales-supplement-owner-adapters`. The final delivery manifest
records exact commit/tree, checks, patch and original-source preservation.
The default-off candidate is not installed. Actual identity/session/issuer,
precise Grants, seven new criterion/set receipts, Skill successor review and
publication, Employee successor publication, supplemental proposal/confirmation
and independent execution receipts remain required. No new real receipt is
claimed by the fixture tests. Existing 43-call/16-unsettled history is preserved;
there is no UNKNOWN replay, settlement or new model sampling.
