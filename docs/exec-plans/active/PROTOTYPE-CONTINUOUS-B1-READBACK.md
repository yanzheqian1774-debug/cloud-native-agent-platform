# B1 autonomous readback and truthful Plan execution state

User-authorized 2026-11-04 continuation after B0, per the shared continuous delivery
plan and J01/J02/J05/J11. D11 policy publication/provenance decision remains
separate; do not implement its frozen changes until approved.

G1 bounded changes: add a reusable visibility-aware GET-only polling hook for
active execution/awaited original records; no command replay, implicit retry,
model call, approval or execution start. Bind every response to current principal/
problem/digest/request locator, serialize with manual operations, stop at terminal
facts or definitive authorization failure, back off transient failures and pause
hidden/unmounted pages. Keep explicit read as fallback, not normal required work.

Paired actual P10 review found legacy Plan history's hardcoded NOT_STARTED label
can describe an already completed Plan. Add a read-only optional execution_summary
from existing prepared execution owner records, gated by each exact EXECUTION READ.
Unknown/unreadable state stays unknown; do not disclose hidden IDs/counts. Preserve
legacy stored Plan/approval/serialization. Console uses the actual summary when
provided; old fixture/legacy response compatibility stays. No new state authority,
migration, grant kind, frozen Contract, provider or service restart in this batch.

Verify completed/running/absent/unreadable states; automatic GET transitions with
zero POST, hidden-page pause, identity/target switch rejection and terminal stop.
Affected frontend lint/build/browser and owner PG tests are separate from B0's
fixed candidate. B0 original supplier/sales results and UNKNOWN remain untouched.
Do not count this readback slice as default resource POLICY decisions or J03/J04/J06
whole-journey completion. Record actual versions/evidence in the J table.

Implementation checkpoint 2026-11-04: existing exact execution owner PG pipeline
covers absent/current/running/succeeded and denied reads in three synthetic
families; no new state store. Browser tests exercise active-to-terminal GET,
terminal/authorization stop, hidden-page pause and original source request GET
recovery with newer input retained and exactly one save. Completed-run read
fallback remains visible (a wrapper regression was caught and corrected).
Technical source/mapping IDs moved to a disclosure; business boundaries remain.
First full browser attempt exposed a manual-recovery expectation racing an
already-successful GET; source recovery now explicitly uses the automatic read
hook, and the test requires automatic readback rather than a manual click.
A later CSS wrapper error hid the completed-run fallback; corrected before install.
These are B1 readback/clarity changes, not J03/J04/J06 acceptance. D11 remains
PROPOSED; no fake policy identity or default automated publication is active.

Authenticated readback on installed 551d628 found the old resource snapshot could
still add “resources pending” beside an execution-owner SUCCEEDED fact. Follow-up
keeps the historical snapshot visible as planning-time evidence and removes it
from current execution blockers; completed/current execution facts take priority.
A focused browser regression covers this case without issuing any POST.
