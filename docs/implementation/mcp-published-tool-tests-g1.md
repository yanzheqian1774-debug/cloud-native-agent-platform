# Published MCP tool tests and bounded successor reads (G1)

This is an additive, default-off management slice. It does not complete general MCP execution or automatically enable a private policy. Root alone performs real migration, policy registration, grants and actual service verification.

## Original owners and boundaries

The browser keeps the existing session/CSRF authentication. Published MCP content, lifecycle, discovery snapshot and selected tool remain owned by SkillMcpService. Legacy draft-priority `_invocation_source` is unchanged. Both paths reuse the equivalent transport request function; the new path explicitly verifies current published revision. READ/CONNECT/MANAGE never substitute for INVOKE_MCP_TOOL.

A private exact policy binds original browser subject/scope, published MCP ref, selected discovery snapshot/tool/schema, published synthetic source/content digest, endpoint, arguments and expiry. Initial supported arguments are exactly sourceDigest, not arbitrary arguments. ReadOnlyHint is not authority. Formal GrantAdministration uses an independent SERVICE_ONLY issuer and the additive SKILL/INVOKE_MCP_TOOL canonical tuple. Explicit requestability is a separate deployment prerequisite. The policy is not itself an effective grant.

PREPARE validates READ and exact resource/source, commits immutable intent without tool grant or network. This makes the exact invocation target discoverable to the existing grant validator. Explicit dispatch commits formal grant decision plus durable claim before network. A separate transaction rechecks current rights, policy and published head under resource share lock, then invokes once. Finalization appends the actual result. A claimed request with no result is UNKNOWN; same binding with another key is blocked. Expiry is excluded from binding identity, so lease renewal does not evade UNKNOWN. Known success may be deliberately tested again with a new user action.

Response loss is UNKNOWN, never retryable failure. HTTP/transport exceptions after a committed claim conservatively retain UNKNOWN even when a later rights check prevented HTTP. Repeat dispatch only returns the existing receipt. An internal finalizer may append the exact already obtained result using its original claim ticket; no public route mints tickets or reruns a tool. GET needs current exact READ and original subject, not an old expired invocation grant. Tool output is redacted before persistence.

0076 creates only append-only requests/facts and its own checksum ledger. Startup checks schema compatibility; it does not migrate. With the environment absent or disabled no routes or target adapter are installed. Actual activation must apply migration through root, configure the exact policy and requestability, and retain the independent issuer.

## Curated READ v3 (separate policy increment)

Existing v1/v2 parser, canonical digest and v2 two-selector limit are unchanged. Explicit v3 permits at most three unique logical resources: at most one MCP and at most two skill/employee selectors. MCP uses the existing prepared-mcp:prepared-resource reference, not the skill prefix. Published head, anchor publication, full canonical digest and predecessor chain are checked through the original owner. Static identity tombstones, local account/source identity, historical orphan fail-closed, dynamic revocation and rejected requests remain authoritative. No automatic anchor registration, creator inference, Agent/Knowledge or wildcard selector is added. Root must first observe the actual initial MCP publication before registering its exact anchor. Curated READ never grants tool invocation.

## UI

Existing resource detail Test tab hosts published tool test controls/history. Discovery/health are not presented as a real call. Unknown records only offer receipt readback and block new dispatch for their binding. Persisted PREPARED records offer explicit same-key continuation after readback. Refresh/session changes do not send automatically. Existing employee selected-upgrade/publication behavior is unchanged.

## Validation scope

Disposable random planning323 databases on isolated port 53428; actual browser session, current grant owner, resource owner and durable receipt tables. Local HTTP fixtures bind random ports and run initialize/tools-call. They do not contact actual port19761, real provider, production DB or alter actual policy. Tests cover response loss, concurrent same-key dispatch, late result finalization, head race, formal surrender and current READ loss. The process-loss case interrupts between phases in the harness; it is not an OS-kill experiment. Frontend tests use controlled route responses and existing F3 shell, not installed acceptance. Actual ordinary MCP publication→tool test→selected employee upgrade→new exact READ remains root's subsequent actual verification.

## R2 source fence

Knowledge selection now reuses original prepared_execution_resources.published under the dispatch transaction (exact current published head, state and archive with FOR SHARE). Additional original knowledge-revision.v1 canonical digest includes predecessor identity when present, and original record scope/ID/aggregate columns must agree. Explicit enabled=false or purge rejects, while legacy Knowledge records without enabled remain valid (the original owner does not define that field). MCP then Knowledge lock order is consistent on prepare/claim/transport. Original Knowledge UPDATE/purge cannot change the locked source before send. Source content digest remains an independent check. No old lifecycle or revision is rewritten.

## R3 durable integrity

Request hashes seal scope, original subject, command key and canonical binding digest. Readback verifies those values against every scalar column and the validated ToolBinding before choosing a policy binding. Facts are restricted to empty, one ordinal-1 claim, or claim plus ordinal-2 result; each fact seal includes the original request hash/key/scope/binding and each result includes its exact claim hash. Request discovery and pending checks use validated receipts rather than scalar-only rows. Requests and facts reject UPDATE/DELETE via database triggers. The separate migration ledger still accepts its normal version insert. Unapplied0076 checksum changes require the final candidate migration; no installed schema was altered.

Disposable superuser fault injection explicitly disables only the request immutable trigger to demonstrate detection of a corrupted scalar binding digest, then restores it. Another direct INSERT simulates an orphan result with a correct self hash. Neither can dispatch or display success; tests independently verify all request/fact UPDATE/DELETE operations are rejected. This models storage corruption, not an exposed administration capability.
