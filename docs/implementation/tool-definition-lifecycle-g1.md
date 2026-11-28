# F3 Tool lifecycle and exact employee candidates — G1

Authority: F3 resource-edit68/resource-check68/resource-version68/tool-test and
“加入交付分析员候选”, verified frozen prototype source. This continues
F3_TOOL_IMPORT_LIFECYCLE_PLAN, not a Workflow publication extension.

Implementation uses the existing TOOL owner, sessions/CSRF/current exact grants,
0061 immutable source/revision/receipt tables and optimistic aggregate version.
No new database/migration, public CRD, runtime, model provider or auth system.
Current installation/source/full are not changed by this isolated candidate.

## Lifecycle

POST /api/workbench/v1/tool-definitions/{tool_id}/commands accepts exact
revisionId/digest/expectedVersion plus commandId and validate/successor/test/publish.
It shares the original scope advisory lock and immutable command receipts.
Replays require current permissions and identical actor/payload; changed payloads
conflict. Original GET /imports/{commandId} is also the recovery path. No caller
supplied actual output or effective grants are accepted.

Validation checks the bounded existing Skill contract subset and explicit effect,
rejecting original unsupported-source diagnostics. It does not claim connection,
plugin execution, Native decision, model, or business acceptance. Publication
requires an exact prior validation and an independent TOOL PUBLISH aggregate
grant, fixing the same immutable revision; tests remain separately visible.
The current draft pointer clears. Successor creates a new immutable draft while
old tuples remain byte-identical. Edits already create immutable revisions, so
old revision validation/test results never validate an edited revision.

TOOL VALIDATE can use existing MAINTAIN_SCOPE under original revocation rules.
TOOL PUBLISH and TEST require independent exact aggregate grants; neither import,
READ nor maintenance scope supplies them. No grant is minted by these endpoints.

## Tests and actual observations

Without a mapping, all declarations are NOT_EXECUTED with actual=null. API/external
sources and example.invalid remain NOT_EXECUTED in this computation-only path.
A mapped Plugin/ZIP declaration only tests its contract against the registered
computation; toolSourceInvoked=false explicitly records that package code did not run. No free HTTP/plugin subprocess or model runner exists here. Existing
MCP operations keep their original published-MCP tool-test owner, current exact
INVOKE_MCP_TOOL policy/issuer/claim/UNKNOWN controls and UI; this stage does not
clone them as a different Tool or bypass their budget/timeout.

Optional TOOL_CONTRACT_TEST_POLICY is private0600, same-owner, canonical,
non-symlink and read again by byte digest before each test. Default unset means
no computation mapping. Enabled mappings bind browser subject/scope, exact Tool
revision/digest and exact published owned Skill revision/digest/operation/expiry.
Original independent ResourceManagement policy/issuer plus current exact Skill
MANAGE_RESOURCE and READ_RESOURCE are checked on the same transaction; mapping
is not an effective grant and grants are not issued here. An absent management
owner blocks enabled mappings, while disabled mappings need not build an owner.

The executor is the existing registered Skill resource-test computation, with its
READ_ONLY policy, synthetic-input requirement, schema/size/depth/timeout bounds.
Native definitions use the original computation-only test adapter, never a Native
Attempt/model decision. Actual output comes from that executor and is compared to
expected; caller expected is never copied into actual. modelCalls=0 and the
verification level ISOLATED_REGISTERED_SKILL_COMPUTATION are explicit. This does
not consume or reset model ledgers, grant business execution, or assert a plugin
package itself ran. Real calls still require their original admission/budget.

An empty expectation is a definite NOT_EXECUTED input result, never a vacuous
pass or an untracked UNKNOWN. Tests save the input/expected case and exact revision identity separately from
actual observations/resultId/provider observation/executor proof. Errors and
NOT_EXECUTED remain evidence, not successful calls. Current saved draft/current
fixed publication are allowed test targets. Other historical revisions cannot
silently substitute. UI preserves an original pending command before POST and
recovers by GET only after unknown outcome; a failed readback cannot erase it.

## Exact Tool candidates and impact

GET /tool-definitions/candidates advertises only currently published exact Tool
versions under existing LIST/current READ. Tool details link to the original
Digital Employee assembly with its exact candidate tuple; the picker re-reads
current candidates and requires explicit selection, then normal save/validation.
This is a real additive TOOL MemberKind/BFF member, never a renamed Skill.
Existing Agent/member semantics, employee independent permissions and lifecycle
remain unchanged. Tool bindings require exact current READ on create/decide and
published eligibility checked in the same locked DB transaction. Immutable old
PUBLISH receipts prove retained old published tuples, so a later Tool publication
does not force an existing employee to upgrade; an unpublished draft has no such
proof. No automatic migration of definitions, tasks, plans or outcomes occurs.

Tool history shows only currently readable exact revisions and original-actor
command/test receipts. Authorized exact Employee reference facts are inspected;
impactComplete=false and automaticMigration=false remain explicit. UI counts
actual Tool members as Tool business resources, retains F3 pages/navigation and
keeps ontology absence distinct from zero. Candidate/addition is configuration,
not actual tool invocation or business acceptance.

## Validation and remaining acceptance

Use only isolated fixture PostgreSQL at127.0.0.1:53439 for affected backend tests;
never root53428/64335 or actual64330. Pure tests run the registered sales executor
and independently assert both mismatch and known constant contract success.
Real BFF tests use ordinary session/CSRF/grants, including denied publish/test,
revoked replay and exact Tool READ before original Employee creation. Frontend
checks use the unchanged fifteen feature flags. Parent integrates with the owned
Skill entry batch and runs one normal release gate; no per-patch full/commit.
Installed ordinary account/UI evidence, real external/paid-provider tool calls and
business execution remain separate acceptance work after actual installation.

## Exact published bindings (same batch)

A later resource publication must not invalidate a still-published Employee's exact retained member. Default new member validation and standalone candidate discovery remain current-only. Trusted bound reads must reread the canonical Employee revision/publication fact, check membership, exact digest and owner publication fact for an old head, and current enabled/unarchived/nondeprecated eligibility. Caller continues current exact READ/USE/INVOKE checks. Historical inspection is never an execution authorization. The same check follows capability observation, planning resolution, resource preparation, instance assembly, execution lineage, Native prepared readback and final Skill invocation. No auto-upgrade, policy rewrite, replay or real model call. Directed isolated tests only; no migrations.
