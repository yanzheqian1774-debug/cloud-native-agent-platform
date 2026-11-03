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
