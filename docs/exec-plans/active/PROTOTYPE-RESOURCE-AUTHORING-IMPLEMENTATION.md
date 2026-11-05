# Resource authoring and P08/P10 closure — 2026-11-05

Scope: explicit user instruction to complete create/import/edit and MCP connection
configuration using existing resource owners, and advance P08/P10 visual parity.
G1: additive trusted BFF adapter and Console forms, not a new identity model,
resource lifecycle or runtime owner. DECISION_STATUS explicitly says implementation
interfaces are not automatically frozen. Preserve all existing action meanings,
D11 policy review/publication and legacy private API. Register separate bounded
CREATE_RESOURCE/MANAGE_RESOURCE/CONNECT_MCP actions on existing SKILL owner with
kind-specific exact targets; never reinterpret READ_RESOURCE as write authority.
Use existing grant owner/current session, caller transaction and policy issuer,
existing resource repository/lifecycle and existing command ledger; no new DB,
CRD, secret backend or public frozen contract. New policy disabled by default,
explicit same-scope subjects/kinds/expiry and real independent service identity.
Creating resource and granting its exact management/read permissions are atomic.
Imports remain drafts, preserve supplied operations, reject secrets/foreign fields;
edit is CAS, new published successor preserves old revision and consumers.

MCP uses existing bounded loopback Streamable HTTP transport. Explicit connection
checks, discovery and tool selection are separate from actual Tool invocation;
no tools/call in this stage. Credential references are references, not installed
credentials; unsupported authenticated/external connections must fail explicitly.
Never claim connection health is usable discovered tools or execution success.
Commands recover by read-only receipt; no automatic retry of unknown effects.

Implement UI as current logged-in resource management, Chinese business fields,
create/import/successor/edit/validate/publish/history local to existing catalog;
no legacy default identity/header. Match S/M prototype frame and page-specific
forms; details inline and technical schema behind disclosure. Verify real isolated
PG/HTTP current grants, no-permission/cross-scope/stale/double-submit/secret-negative,
actual local MCP handshake/discovery/no tools-call, then browser states, lint/build
and full code checks. Fixed source/bundle activation at idle single-writer boundary,
fresh backup, historical supplier/sales/D10/new-continuation GET regressions, no
old execution or UNKNOWN retry/model/budget writes. P08/P10 work is independent
of resource write enablement and keeps exact source/criteria/version semantics.
Record all remaining page/state differences; full package stays OPEN if incomplete.
