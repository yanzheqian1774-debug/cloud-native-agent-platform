# Package03 prerequisite exact-resource review G1 implementation plan

Authority: user's instruction to advance the three stages and bring forward
package04 prerequisites. Registry IMPL324 remains active; no closed session reused.

Implement bounded exact-resource batch readiness using existing authorized
prepared-resource GET/review-publish APIs. No new owner, discovery scope, lifecycle,
persistence or grant semantics. Discovery/instance binding remain separate work.

Current panel trusts response identity, permits old resource cards after failed
refresh, and can continue a multi-resource publish after inputs become blocked.
Fix these prerequisite gaps before using its published facts in execution prep.
Bind each read to requested kind/id/revision, validate digest and version, reject
invalid/duplicate target batches, require successful full fresh batch before any
publish. Changing target/context or becoming blocked stops subsequent writes;
never auto-resume. In-flight command facts are preserved; GET-only refresh follows
partial publication, failed refresh clears actionable data. Refresh never writes.

Tests: wrong kind/id/revision, invalid digest/version, failed refresh disables
publication, delayed context/input change stops remaining commands, partial
publication and reload preserve facts without replay. Run focused browser tests,
frontend lint/build and repository baseline checks. Screenshots are mock-interface
engineering evidence, not whole-page or original-case acceptance.

## G1 generated-proposal planning scope checkpoint

A real validated AI proposal and confirmed Plan exposed a prerequisite gap:
the existing execution successor requires exact canonical PLANNING_ONLY and
READ_ONLY_PLANNING owner boundary markers, whereas the provider emits ordinary
business prose. Keep that existing gate and every old Plan unchanged.

For newly generated modern proposals only, append those two canonical restrictive
markers as platform-owned policy before creating the proposal/its digest and
before confirmation. Preserve every model task, dependency, criterion, policy,
resource reference and business fact; reject duplicate markers, declared execution
scope, or overflow rather than dropping content. Record provider output digest
separately from policy-bounded proposal digest. No grant, approval, Assignment,
Run, new endpoint or lifecycle change. Legacy planning.v2 retains old behavior.
Tests cover absence/presence/duplicates, graph/data preservation, read-only scope,
existing execution-successor gate and real-service composition. A fresh formally
admitted call may create a new candidate; never rewrite the already confirmed Plan.

## G1 read-only delivery artifact presentation

The real Native run produced three durable artifacts and six satisfied original
criteria. Present authorized synthetic-delivery report content as supplier ranking,
unit-separated remaining quantities, anomalies and explicit source/limitations.
Use only existing authorized artifact bytes; no new fetch, aggregate, mutation,
evaluation or business-resolution inference. Retain exact raw bytes in a details
view. Unsupported/invalid payloads keep the existing raw display. Test this exact
captured synthetic artifact and ordinary text fallback with GET-only reload;
verify responsive overflow and bind actual page screenshots to source/deployment.

Stage03 read recovery also withdraws stale execution actions after a failed GET
and binds every displayed response to exact session/problem/digest. Wrong digest,
problem switch and failed post-command readback must leave only explicit GET
recovery; no command is replayed. This uses existing endpoints and immutable facts.

Actual page review exposed stale stage framing: a succeeded Run still highlighted
execution instead of result review, and deterministic criteria displayed repeated
machine enums. Derive the page title/step only from accepted exact execution GET
state, withdraw it on failed read, and render criterion descriptions from the
existing applicability.description (Human rubric remains first choice). No new
facts or acceptances are inferred. Evaluation names use the owner-supplied check;
unknown checks retain numbered standards and exact details.

Result-page composition follows P06.3/P06.4: show persisted report/KPIs in the main
column, collapse completed execution detail, and use the side summary for exact
run/criteria/decision status with original problem context still expandable.
Every displayed count comes from the accepted execution GET or authorized report;
failed reads withdraw the projection. No new commands, stores or inferred success.
