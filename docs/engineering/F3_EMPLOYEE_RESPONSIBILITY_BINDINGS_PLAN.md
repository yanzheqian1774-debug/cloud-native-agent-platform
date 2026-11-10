# F3 employee responsibility/resource associations (G1)

User-authorized F3 digital employee delivery, continuing the prototype review dated
2026-11-11. Current definitions persist responsibilities and composition members
independently. The duties tab consequently cannot show verified associations.

Add optional explicit associations owned by the existing immutable employee
revision, through existing create/read commands and the same repository, grants,
validation and publication. Each association binds one exact responsibility text
to one exact SKILL, MCP or KNOWLEDGE composition member (kind, resource, revision,
digest). No text/name inference, additional execution permission or model call.
Duplicate responsibility text is ambiguous for association and must be rejected.
Missing, duplicate, changed or nonmember bindings fail validation. A resource
replacement or duty edit requires the user to review its association again.

Unassociated historical definitions preserve their v1 record and digest exactly.
Definitions with associations use explicit internal composition v2; parsing must
reject unsupported schemas and v1 records carrying v2 data. No SQL migration,
new persistence infrastructure, public CRD, frozen contract, lifecycle or control
plane ownership change. Existing consumers reconstruct the full revision and
must preserve its digest. New fields are optional on internal product commands.

The F3 duties tab renders saved associations inline with exact resource cards.
The existing successor editor provides per-duty resource selection, clear removal
of stale associations and a saved association summary. All changes create a new
draft requiring the existing validation/publication flow. Old task references
and current publication remain unchanged. Preserve associations when editing
other content; do not silently erase mappings through an older authoring path.

Validate canonical v1 compatibility, v2 roundtrip/tamper detection, duplicate and
cross-member rejection, authorized durable create/read and successor lifecycle,
old consumers, UI selection/readback/reload and stale-binding repair. Then
install with paired runtime source verification and show actual same-state F3
comparison. Prototype review remains required; unit tests are not delivery.

Implementation checkpoint: the internal command distinguishes an omitted mapping
field from an explicit empty list. Both existing repository create paths reject
an omitted/implicit clearing of a predecessor's saved associations. This guard
runs under the existing definition transaction lock; it does not create a new
owner or bypass authorization. An explicit empty selection creates a successor
without associations and preserves the prior immutable record. Saved-review tab
navigation now leaves review mode for the selected tab without changing revision.

Validation evidence is recorded separately under the delivery workspace's
`f3-responsibility-bindings-20261111` directory. Do not interpret the isolated
PostgreSQL or browser fixture checks as installed service or prototype acceptance.
