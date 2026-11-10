# F3 historical execution read repair

Bounded bug repair discovered during task-directory completeness audit. Live read-only requests found three saved runs whose GET fails with EmployeeDefinitionError(BOUND_RESOURCE_INELIGIBLE) inside the current admission preview. Existing admission preview already reports known authority/execution validation failures as NOT_ADMITTED while returning authorized historical state. Extend that boundary to the exact employee-definition domain exception; do not catch arbitrary errors, change START/RETRY, suppress read authorization, mutate resources or replay tasks.

Evidence: work/evidence/f3-task-directory-query-review-20261110/api-readback.json and main log stack at 2026-11-10 09:56 UTC. Thirty-one runs read successfully and original twenty-five are preserved; three fail due to current member eligibility. These are faults, not denied-permission exclusions. Directory implementation must not silently omit them.

Checks: direct read preserves saved state, events, permitted artifact content, and NOT_ADMITTED reason; restricted artifact remains unreadable; unexpected storage/runtime exceptions still propagate. Normal backend checks. Candidate is not installed; real repaired HTTP readback remains required after authorized deployment/isolated integration validation. Existing successful read, execute authorization and model budget rules remain intact.
