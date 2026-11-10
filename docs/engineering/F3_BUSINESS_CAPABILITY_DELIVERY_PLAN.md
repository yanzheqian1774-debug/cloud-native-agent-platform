# F3 business capability delivery plan

Status: G1 design and dependency inspection; implementation not yet delivered.
Baseline: 0a80395d96b2805b60dfbb5f239f26d0bd436e50. Frozen UI: V6.9-F3.

## Scope and authority

Deliver the frozen capability collection/detail and durable authoring, not a renamed
resource directory. Retain existing authorization, budget, audit and all exact
historical references. OpenClaw remains isolated/off; no new Native execution.

S5-ARCH-018 authority must be read with the forward record in governance REGISTRY:
its decision file still says proposal, while REGISTRY records Human-confirmed,
durably integrated PASS_WITH_CONSTRAINTS and PR 97. Reuse the existing database,
domain-owned typed ports and adapters; no new infrastructure or control-plane owner.

## Inspection findings that constrain implementation

- SolutionBlueprint v1 requires canonical_workflow_revision and role_definition
  references. It cannot truthfully represent an independently authored capability
  lacking a workflow. Keep this existing logical contract and its digests unchanged.
- The saved non-table conversation has a plan, four participants, a fixed Employee,
  Skill, Knowledge and Runtime Profile. These are real exact references; the plan
  has NOT been verified as a published WorkflowDefinition. Employee is NOT Agent.
- BlueprintAuthority is in-memory only. Neither a prototype nor that authority
  proves a durable, trusted business-capability service exists.
- Current authority_configuration OWNER_ACTIONS has no business capability owner.
  Adding explicit actions is not permission to reuse Workflow grants or broaden
  existing administrator grants. Production activation needs its own exact grants.

## Proposed internal representation and interfaces

Use a BusinessCapability revision aggregate in the Console resource domain, with
scope, stable capability ID, immutable revision/digest, predecessor, title, intent,
inputs, outputs, scope/exclusions, manual involvement, acceptance criteria and limits.
A tagged origin is INDEPENDENT, WORKFLOW_REVISION or SAVED_PREPARATION. The latter
records the verified preparation digest, not a fabricated workflow revision.
An optional Blueprint reference is allowed only after exact owner verification.
Typed fixed bindings include EMPLOYEE plus SKILL, MCP, KNOWLEDGE, ONTOLOGY and TOOL
where an existing owner can verify them. Unsupported owner bindings return a clear
reason; they are not invented or silently converted to another kind. Runtime/Profile
remains an execution prerequisite, distinct from the five resource categories.

Repository ports: immutable add/read, scoped bounded list, compare-and-set draft
head, append lifecycle decisions, publication head and command receipts. Reuse
existing PostgreSQL transaction, conflict, schema-compatibility and recovery patterns.
No generic cross-domain mutation and no new database. Public CRDs remain untouched.

Service/API: scope and exact action authorization before lookup; verify each fixed
member against its owning service, digest and scope. Preserve one visible published
version plus one current modification draft. Each edit appends a revision but does
not expose revision administration as the normal business journey. Publication and
reference upgrades use one existing-style consolidated impact confirmation, not a
confirmation per member. Source snapshots and old conversations never upgrade.

## Delivery sequence and acceptance

1. Finish actual saved-conversation -> fixed Knowledge/Skill -> original conversation
   walkthrough with fully loaded content. Record route equality and zero execution.
2. Define aggregate/ports and exact owner/action mapping; implement isolated durable
   save/read with real PostgreSQL. Prove restart/fresh-session equality, replay,
   conflicts, denied member, wrong digest, concurrent draft edits and scope isolation.
3. Connect F3 collection/detail/create/edit to trusted APIs. Independent creation and
   workflow-derived creation must both show truthful source. Do not force workflow.
4. Deliver successor diff, consolidated impacts and publication; verify old execution
   digest and original resource references unchanged. Fresh session reads saved data.
5. Original entry -> capability -> Employee -> multiple fixed resource types -> exact
   original entry. Conversation try-use prepares source context; it does not invoke a
   model or claim a newly successful run while Native policy/budget is unavailable.
6. Install with guarded source-only deployment after required checks; compare actual
   pages to frozen F3, submit complete stage to prototype reviewer with remaining gaps.

Frontend lint/build and focused backend/frontend tests are required for code changes.
Real persisted/browser evidence supplements tests; fixtures are never live acceptance.

## Risks and stop conditions

Resolve authority/action mapping and typed resource owners before enabling live writes.
If existing authorization architecture cannot admit the new resource through its
established configuration seam, or cross-plane/frozen semantics must change, stop that
change for a concrete architecture decision. Continue independent approved work.
Do not silently grant permissions, renew model budgets, restart unknown executions,
change lifecycle meaning, or use Blueprint mandatory workflow fields as placeholders.

## Reviewer acceptance additions (2026-11-11)

Current publication plus one modification draft; genuine independent/workflow sources;
centralized impact confirmation; understandable denied/missing-input reason and next
step. Reviewer feedback is product acceptance guidance, not expanded authority.
