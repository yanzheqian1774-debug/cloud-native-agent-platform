# Employee version cards using existing owner reads

G1. Replace default collection's revision-first rows with one employee card
showing independently verified current publication and draft, plus preserved
exact historical selection. Keep professional collection unchanged. Retain
search, filters, pagination, exact links and scroll return. Do not create a new
team or navigation layer.

Reuse GET authoring on a currently listed exact parent, which already checks
each target READ. Share its response verifier with detail. Read at most three
employees concurrently, only while the collection is visible and once per loaded batch, with a session check before and
after the batch. Unknown, denied, withdrawn and partial states never imply no
history or current publication. Never infer latest from list or UUID order.
Do not execute, save, publish or allocate a model budget. No backend/API change.

Also prefer fresh verified publication/draft lifecycle over stale selected
metadata when the same immutable revision has just been published/validated.
No automatic selected-revision switch.

Validate current/draft/historical separation, wrong parent/digest, withdrawn,
unreadable and identity changes, nonzero scroll return and exact historical
links, plus existing employee/resource regressions and real read-only pages.
The collection remains a supporting F3 adaptation, not an invented frozen page.

Historical edit return preserves its exact original revision and detail tab, including after reload. Switching detail revisions must not overwrite saved collection scroll with a hidden list position.
