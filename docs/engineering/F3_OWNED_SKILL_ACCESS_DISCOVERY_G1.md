# G1: discover existing owned Skill access recovery

Base bb92728. Bounded additive management-directory read hint plus links in the
existing Skill card/detail styles. No frozen contract, lifecycle, grant, CRD,
route, storage or authorization-system change. The existing explicit access POST
remains the sole recovery writer and existing current policy/creator ownership
remain authoritative. GET never authorizes or creates revisions.

Directory may return only kind/identity/revisionId/digest for creator-owned current
Skill tuples having current exact READ_RESOURCE. A missing MANAGE grant must not
expose the full aggregate, tests or secrets. Non-owner and unreadable tuples have
no hint. Current management full items retain existing MANAGE behavior.

Cards display a qualification-check link only with the exact owned readable hint;
existing authorized Edit is unchanged. Exact detail checks session/scope and uses
the same hint, explicitly navigating current definition while retaining historical
references. Existing recovery view/intents handle POST without expectedVersion,
current record readback and UNKNOWN recovery. Do not synthesize new drafts.

Validate owner/expired MANAGE, non-owner/no READ, same-scope/identity changes,
GET-only discovery, explicit single access with omitted version and zero replay
of an unresolved command. Only isolated synthetic tests, separate unused frontend
port. No real DB, actual POST, full/commit/install; previous seven-file basis
package and current frozen candidate stay unchanged.
