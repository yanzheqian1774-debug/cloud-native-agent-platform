# D11 — Same-owner policy decisions for default automatic resource preparation

Status: ACCEPTED. Explicit user decision on 2026-11-04: “批准D11，实施并验证”.
Implementation status: implementation underway per current executor; not yet accepted.
The approval covers the concrete compatibility mechanism below as well as the
previously approved product direction. No further D11 approval is pending.

## Verified current boundaries

- grant_administration_application.py:654+ already supports basisType POLICY;
  Authority Postgres supports SERVICE_CREDENTIAL, real issuer identity, exact
  scope, TTL, revocation and idempotency. Self-approval is prohibited at
  authority_postgres.py:1483/1509; it does not require every issuer to be Human.
  Use these existing paths, not another authority or a wildcard administrator.
- workbench_prepared_resources.py:117 explicitly rejects a non-human actor as
  HUMAN_RESOURCE_REVIEW_REQUIRED. Bypassing it with reviewer324 in a script is
  not product automation and cannot satisfy J04.
- D10 SourceChangeOrigin currently says HUMAN_SOURCE_CHANGE, with independent
  Plan confirmation. Automatic same-meaning changes must have truthful policy
  provenance, not masquerade as a Human click or model reply.
- Legacy D324 context/model-call signatures and final Human business-result
  decisions are distinct. This proposal does not turn resource approval into
  new model allowance, business result acceptance or arbitrary external actions.
- ARCHITECTURE_GATES.md G1 permits new adapters/endpoints/Console behavior after
  a plan; G2 covers frozen Contract and State architecture changes. Only the
  policy publication/provenance additions below require this decision. Read-only
  polling, labels, existing POLICY-grant wiring and preflight work can proceed.

## Approve this additive mechanism

1. Configure a real service-credential policy subject in the EXISTING identity /
   authorization owner, e.g. service:resource-preparation-policy. It is distinct
   from each requesting user, scoped to enabled tenant/security-domain/work
   purposes, and records actual issuer, policy identity/version/digest and exact
   grant targets through the normal grant owner with POLICY basis. No use of a
   Human password, simulated signature, client-supplied principal or blanket
   resource grant. Roles/configuration constrain this issuer; existing requester
   and issuer separation, expiry/revocation/epoch and immutable old decisions stay.
2. A server-owned preparation policy consumes a trusted existing user work scope,
   purpose and exact source/task/resource commitments. It automatically decides
   valid requests for resource READ/validation/review/publication and their
   necessary assembly references. Cover existing/new/expanded/batch resources;
   no per-resource user or owner click. Scope/data identity checks and source/
   executor/I/O/side-effect compatibility are automatic prerequisites, not a
   default queue for Human approval. Technical failure is NOT published or bound.
3. Add an internal, verified policy-decision publication port behind the existing
   resource owners. Keep the existing Human review API unchanged. Resource
   approval facts identify the real policy actor/decision and exact revision;
   validation, approval, publication and execution readiness remain distinct.
   Add precise MCP read/review references under its existing Skill/MCP owner
   without reusing colliding Skill targets or assuming access to MCP endpoints.
   Unsupported executors, inaccessible sources, missing credentials, incompatible
   schemas and failed runtime checks return explicit gaps, not fake validation.
4. Add optional versioned automatic-preparation evidence in the SAME database /
   owners (policy, actor, user/work scope, exact revisions/digests, check receipts,
   commands, next step, expiry/revocation and notification facts). Old records
   serialize/hash unchanged when absent. Idempotent requests, concurrent attempts,
   lost-response readback and durable recovery create one decision/effect. Do not
   introduce a second workflow/runtime/authorization authority or new datastore.
5. Same-business-meaning source/resource changes and already authorized read-only
   continuation can be prepared and confirmed by this policy through existing
   planning/assembly/execution owners, with truthful POLICY_SOURCE_CHANGE and
   policy confirmation provenance. Show business impact and retain exact old
   Plan/Run/artifacts. Do not create a new model-origin claim. Changed goals or
   standards still need a real business decision; content-bound criteria may not
   be weakened or silently rewritten. Final business outcome remains Human-owned.
6. Existing execution/action owners continue to enforce current exact access,
   Task/Skill permissions, budget and permitted external effects. Resource policy
   does not grant access to inaccessible data, cross-tenant targets, new spending
   allowance, destructive actions or business commitments. No auto-retry of
   UNKNOWN, release of old reservations, duplicate old Run or reopening ARCH323.
   Original aggregate100 calls/USD50 includes all old history/reservations.
7. Owner notifications are append-only/nonblocking; receipt acknowledgement is
   not required to continue. Professional detail/audit/configuration remains
   available but not a mandatory business-user step. Existing interfaces remain
   as explicit expert/legacy paths; defaults become continuous preparation with
   automatic GET status updates and only necessary business decisions.
8. First enable only after isolated positive/negative/compatibility tests and
   fixed-candidate review. Preserve a fresh private backup and original run /
   UNKNOWN hashes, wait for no in-flight command, then use the existing controlled
   single-writer upgrade/activation procedure. No service replacement during the
   current in-flight M0 checkpoint. Rollback disables new policy activation and
   stops new effects; it never deletes policy or old owner facts.

## Compatibility, alternatives and acceptance

Changes: existing authorization composition/configuration, verified resource
policy publication adapter, truthful planning provenance, bounded preparation
coordinator, existing resource owner checks, BFF/Console progressive status and
notifications. No CRD/group, tenant architecture, provider/pricing/timeout or new
persistent infrastructure. Service-policy configuration alone is not proof of
activation or zero intervention; actual product-path records are required.

Alternative A: keep mechanical reviewer324 approval scripts — rejected as J04
product automation; creates misleading zero-intervention claims.
Alternative B: remove Human/authorization checks or give browser universal grants
— rejected; breaks existing boundaries and old records.
Recommended: additive policy-subject path above with old Human paths retained.

Acceptance: four product flows (existing/new/expanded/batch) show real POLICY
issuer/publication facts, no owner approval click, no copy/paste identifiers or
manual polling. One approved business scope can derive exact necessary objects,
not arbitrary grants. Test tenant/data/purpose denial, expiry/revocation, schema /
executor mismatch, failed validation not publishing, concurrent/lost responses,
no duplicate effects, unsupported MCP and isolated recovery. Preserve original
supplier/sales results and ledger/UNKNOWN; no rerunning completed cases. Record
actual operations, prompts, Human/policy decisions, technical wait and costs
before/after; do not invent missing whole-journey baselines. Frozen configuration
and generated capabilities remain separate M2/M4 validation tracks.
