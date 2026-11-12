# F3 independent tool import and lifecycle — G1 implementation plan

Baseline: installed ba5d56; frozen V6.9-F3 tool-import68/tool-source682 and
resource-edit68/resource-versions68 plus worker fixed-reference flows.
This stage must deliver the existing product flow, not a replacement settings
system or a preview-only claim of tool-management completion.

## Required journey

Tools → choose API description / existing MCP operation / platform plugin →
parse and preview operations → select operations and declared effect → save
persistent drafts → edit → validate exact candidate → publish exact revision →
maintainer-managed digital-employee binding → automatic fixed task references
through the existing assembly chain → invocation through authorized work.
Back/exit/return preserve import text, selected operations, draft identity and
resource context without resubmitting commands. Published revisions never move
existing bindings automatically. Tool source identity and executable authority
are distinct.

## Owners and interfaces

Saved MCP operations continue to use the existing MCP identity/revision/snapshot
and transport owner; do not clone MCP credentials or imply separate publication.
Independent API/plugin tools need their own private definition owner, revision,
validation/publication facts, idempotent command receipts and binding references.
Use existing PostgreSQL infrastructure, BFF sessions, exact grants, revocation,
command audit and development-administrator policy. Private TOOL owner/actions
must be explicitly registered and tested, never mapped to unrelated SKILL grants.
No public CRD, task lifecycle, authentication architecture or persistent service
is changed. If a real frozen contract or cross-plane boundary blocks binding or
execution, document that specific conflict before changing it.

## Import boundary

Follow F3 fields: name, description/purpose, inputSchema, outputSchema,
sideEffect, API source/method/path or plugin id/version/runtime/entrypoint and
permissions. Parse OpenAPI 3.x JSON and t-manufacturing-tool-plugin/v1 manifests;
ZIP has at most 20 files and 100 KB total uncompressed content. No network fetch,
package installation or code execution during import. Check paths, symlinks,
compression expansion and duplicate names. Keep source fingerprint and explicit
unsupported diagnostics. Missing output, request bodies, references, security,
server variables and unsupported schema/parameter semantics cannot silently turn
into a valid executable candidate. YAML and third-party plugin formats require
adapters; don't pretend conversion succeeded. Side effects remain unconfirmed
until explicitly declared and separately validated; GET is not proof of safety.

## Implementation sequence and acceptance

1. Shared import parsing with exact source fingerprint and bounded diagnostics;
   domain model and preview API. No claim of persistence from parsed preview.
2. Persistent draft owner with optimistic concurrency, idempotency, audit and
   exact read/write permission checks; F3 import/edit pages calling real owner.
3. Exact validation/publication and explicit employee/task binding, retaining
   existing references; no execution authority implied by publication.
4. Actual local API/plugin execution adapter under approved scope and budget,
   then original-conversation use and result return. No automatic unknown retry.
5. Actual page/prototype comparison and reviewer acceptance of combined stage.

Tests cover parser loss/ambiguity, source isolation, cross-user/tenant access,
stale writes, repeated command identity, restart persistence, version publication,
fixed binding return, unsupported cases and real authorized local execution.
Use synthetic fixtures honestly. Keep fixtures, isolated real HTTP, installed
readback and business-resolution acceptance separate.

Adjacent correction: legacy MCP administrative history and immediate result must
show dispatch-aware outcomes, not raw FAILED as business failure. Fold technical
identifiers and raw redacted payload; don't infer historical source from selection.

## Frozen-prototype direction review

Automatically extract fields; do not expose every contract field as a mandatory
configuration form. Default views show business name/purpose, inputs/outputs and
impact; raw definitions and technical identifiers are expandable. Credentials
remain references, never user-entered secret material in tool/model parameters.

Diagnostics identify the affected operation and reason. A draft may retain
unresolved items under draft rules; this must not become permission to publish
or execute. Duplicate import must identify the existing logical tool, preserve
its published revision and maintain one current draft. Editing invalidates exact
validation. Publication/upgrade presents combined impact; old tasks retain their
snapshots. MCP references retain the source identity without separate copied
publication. Maintainers manage employee bindings; business users are not asked
to bind tools manually to each task or complete extra approval steps.

The 100 KB / 20-file limit is shown before file selection. The supported subset
is stated plainly and never described as general OpenAPI/plugin compatibility.

## Draft-preview review corrections

Import preview uses operation rows and records an explicit declared effect in the
immutable draft. This declaration is included in command identity; it is not an
execution grant or actual-call validation. Reusing an existing identity never
overwrites its effect or requires a new declaration. All-existing selections
open the saved exact references without an import command; mixed selections
state how many definitions will be created and reused.

Import and draft routes retain the expanded resource navigation, selected Tools
entry and resource/tool breadcrumb. Scope-bound pending command IDs are saved
before submission so refresh recovers by receipt rather than repeating writes.
After a confirmed save, a separate action starts another import without changing
previous definitions.
