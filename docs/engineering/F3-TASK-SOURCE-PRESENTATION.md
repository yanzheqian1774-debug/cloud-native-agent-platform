# F3 task source and status presentation

Scope: user-authorized frozen F3 `tasks` alignment, G1 bounded internal projection change.

Use the existing authorized current-work projection. Add an optional source filter
(`all` by default, `conversation` only for verified conversation origins) before
counts and pagination. Bind the filter to cursors without changing default cursor
identity. No grants, lifecycle transitions, model calls or new persistence.

Present All / Conversation / Fixed work / Completed tabs. Fixed work is explicitly
not connected, never a fabricated empty result. Retain waiting as a secondary
status filter and preserve existing waiting links. Execution completion is not
business resolution. Missing participant or question facts remain unknown; pending
work must not be described as ended. Preserve search, permission scope, pagination
and return position.

Files: current-work query/page projection, frontend API and Native directory;
targeted query/page and browser tests. Test verified versus merely associated
origins, counts/pagination/cursor isolation, pending/unknown/failed states and
routine unavailable display. Run lint/build and relevant regressions. Actual
ordinary-account populated-list acceptance remains required and separate from
fixture tests. Initiator provenance correction is a separate audited follow-up;
do not guess original user from start actor or presentation strings.

Implemented source filtering runs after exact authorization and origin projection,
before counts and pagination; a merely associated conversation is not admitted.
Default source=all retains the old cursor route, source=conversation binds a distinct
route. Frontend rejects a server response with unverified conversation provenance.
Fixed work renders an explicit unsupported state without a directory request or
zero-result claim. The waiting deep link remains a secondary status filter.

Known scope limits retained: initiated still means existing start-command actor;
correct requester projection needs exact source receipts across historic owners and
is not inferred here. Conversation verification still follows saved journey/link
facts; no new immutable origin receipt is manufactured. Model/policy/permissions
and task execution actions are untouched. Actual populated ordinary-user acceptance
and prototype visual acceptance remain mainline checks, not fixture-test claims.
