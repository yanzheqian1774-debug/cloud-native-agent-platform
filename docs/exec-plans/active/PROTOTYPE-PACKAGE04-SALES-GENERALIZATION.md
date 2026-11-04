# Package03 visual closeout and Package04 sales diagnostic generalization

Authority: user's 2026-11-04 instruction to close the main journey's visuals and
interactions, build reusable ingestion/assembly/evaluation with sales diagnostics,
and regress supplier delivery. Routine dev/test accounts and approvals continue.
Preserve the existing externally authored package02/package03/core plan changes.

G1 bounded engineering: add deterministic CSV snapshot ingestion with explicit
column mapping, source commitments and strict parse errors; a sales read-only
Skill implementing the existing SkillExecutor protocol; independent evaluator
checks and exact resource-manifest checks behind current interfaces. No arbitrary
network URL, SQL, CRM write, new datastore, CRD or infrastructure. Synthetic two-
period case declares recognized net sales excluding tax and separated currencies;
returns are signed, cancellations excluded, zero denominators not reported as0%.
Observations do not assert causality or improved future sales. Use the existing
executor registry rather than another task/planning/runtime framework.

Visual scope: P03/P04/P08/P10/P12/P13 and P06.2/P06.3/P06.4 required page/state
mapping. Close export/source/drilldown and result-conversation semantics with
existing immutable outputs; fix shared tokens/icons and page structure against
V2.59. Each accepted page/state needs original/current/side-by-side plus five
categories. Unsupported states stay open and independently reported.

Before installing generic authorization or adding a new cross-case authority
source, make exact D9 contract/compatibility/owner/budget decision reviewable.
Current D8 is explicitly supplier-root/predecessor bounded and cannot be reused
as sales authority by changing a URL or its recorded purpose. G2 changes remain
unimplemented until specifically decided; ingestion/Skill/evaluator/UI work can
proceed without them. User approval of a new case never accepts fabricated data
or modifies old UNKNOWN/reservations.

Checks: CSV encoding/header/mapping/dedup/row bounds, numeric precision and invalid
rows; known sales totals, returns, currencies, grouping reconciliation, zero base,
tampered source/report, no-causal-claim boundary; exact resource versions and
cross-scenario rejection. Regress original delivery executor/evaluator and then
actual supplier case via GET without new calls. Real sales planning/Native run
requires installed formal ownership/authorization and persisted evidence, not
these offline checks. Frontend lint/build, relevant browser scenarios, repository
baseline and visual comparisons are separate gates.

## User-directed reading refinement, 2026-11-04

The user explicitly endorsed the supplied screenshot's inline supplier ranking,
per-unit quantities, expandable order/source rows and visible anomalies. Retain
this practical data view directly within the delivery conversation, after the
concise summary; do not require opening a file dialog to read key data. The same
pattern applies to sales currency totals and dimension contributions. Detailed
files, exports and exact provenance remain supplementary. This is an authorized
presentation refinement to P06.3; preserve the full header, right-rail grouping,
result/file/review hierarchy and read-only behavior. Record the departure from
the original file-only first screen instead of claiming pixel identity.

## D9 evidence-based recovery implementation

The approved D9 explicitly requires preservation of UNKNOWN reservations and
evidence-based recovery through independent fresh-call signing. The first sales
call is now UNKNOWN: WAIT_HEADERS/TIMEOUT, worker reaped, no usage measurement.
It is not replayable. Implement D9's recovery precondition behind the existing
owners, observation store and exact configured sales-root allowlist: optional
observation references on a new signed case revision; legacy serialization stays
byte-compatible when absent. No new datastore, migration, lifecycle, provider,
price, timeout or budget policy is introduced; original D8 roots/records remain.

Every unresolved invocation of this sales root must have its own immutable
LOCAL_ONLY observation, committed to that invocation's actual durable receipt.
The receipt must establish local worker reaping, not supplier outcome or usage.
The observation must match root/revision, subject, invocation and the original
ledger's D9 call lineage. Supplier observations cannot qualify. Missing receipts,
partial coverage, mismatched commitments, duplicate IDs, unreaped workers or
unreserved/unlinked calls fail closed. One independently signed new task still
admits one new invocation and counts all historical reservations under100/USD50.
No old result, receipt, reservation or settlement is updated or released.

Before installation test these failures, legacy record identities and old D8
compatibility on an exclusive disposable database, then preserve a fresh backup,
stop the old writer and install the checked source. A subsequent fresh diagnostic
attempt will bound graph size to at most four tasks to reduce nonstreaming
response volume while retaining all five original criteria and FREE policy.
Any further unknown is retained and investigated; the call cap is not an automatic
retry queue. Visual/read-only resource and independent evaluator work continues.
