# IMPL-297 — Bounded owner and authorization addendum

Session: `S5-V023-IMPL-297`.
Decision: `ACCEPTED_BOUNDED_OWNER_AND_AUTHORIZATION_ADDENDUM`.
Status: `HUMAN_ACCEPTED / BRANCH_RECORDED / NOT_MAIN_DURABLE`.

This records the Human decision in the continuation after the
[PARTIAL_DRAFT recovery checkpoint](../../../docs/engineering/S5-V023-IMPL-297-RECOVERY-CHECKPOINT.md).
The earlier checkpoint and its 21/62 test results remain historical partial
work; this decision was not granted at that time. No approval date is inferred.
This addendum does not amend historical ADRs or grant merge, release or closure.

## Owners and commit boundaries

Business Problem owns Problem/Criteria and exact binding writes; Workflow
Control owns Plan and approval writes; Execution retains execution authority.
Owners may expose caller-owned connection/transaction ports. The 297 application
coordinator begins, commits and rolls back one PostgreSQL transaction and calls
those ports; it must not write another owner's tables itself.

Preparation commits the Plan and its exact Problem/Criteria association together.
Approval commits its exact decision, binding validation and concurrency checks
together. Historical published content and approvals are never backfilled.
A pending association is not approval authority: the exact Plan status and its
append-only decision remain authoritative.

## Claims and replay

Each write command has a distinct namespace. Owner-owned claims store trusted
scope/actor/key, a normalized digest covering every business semantic request
field (including exact revisions/digests, Workflow/Employee/Instance/Assignment
and expected versions), and exact result identities. No bearer credential or
full sensitive request is copied into a claim.

Claim and business writes commit atomically. Rollback leaves no successful claim;
concurrent equal requests yield one result; equal key/digest returns original
identities; changed payload conflicts. Replay requires current authorization,
including read authorization, before claim disclosure. No independently committed
IN_PROGRESS window is allowed. Planning replay never authorizes provider
redispatch and must not use the Execution dispatch claim.

Owner claim capabilities are preferred. A schema gap must be reported with exact
differences after reusable ports are implemented. Migrations 0001–0017 and any
new migration remain outside this decision's implementation authority.

## Trusted actions

Reuse the server-owned bearer verifier. Explicit independent owner/action/resource
grants are required for Problem/Criteria create, read/list, revise, lifecycle and
Plan prepare, read, approve. Missing grants fail closed before protected lookup.
START implies neither PREPARE nor APPROVE; a creator is not implicitly an approver;
Plan reads do not grant Evidence disclosure. Two-person separation is not required,
but APPROVE authority is independent. New IDs use a scoped collection/create target;
listing returns only its authorized scope. Existing grant meanings are unchanged.

Exact naming and matching rules are implementation details recorded before editing
in the 297 continuation and in the implementation document; arbitrary wildcard
expansion and client-supplied identity/authorization decisions are prohibited.

## Implementation and proof scope

The decision permits owner ports, coordinator, authorization consumption,
normal HTTP/schema/bootstrap, isolated tests/CI selection and 297 documentation.
Frontend, 295 assets, execution supervision, provider protocols and deployment
topology are unchanged. Real PostgreSQL/HTTP proof must cover rollback, concurrency,
payload conflicts, independent grant denial, cross-scope and revoked replay,
restart readback, approved Plan consumption and zero provider calls for invalid
or unapproved identities. Ordinary commit, non-force push and one Draft PR remain
authorized. IMPLEMENTED requires normal entry and validation to pass.
