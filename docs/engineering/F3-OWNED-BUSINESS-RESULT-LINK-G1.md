# G1: retain exact successful result through formal problem linkage

Incident: the installed CREATE path calls DraftAssistanceService.link_problem.
Its successful CAS appends aggregate version +1 and the three problem identity
fields. The immutable business admission correctly retains the original result
version, but the work reader incorrectly requires latest aggregate equality.

Keep the original admission and result history untouched. Permit either the
exact recorded version (existing behavior), or exactly one successor whose
complete stored JSON equals the original except aggregateVersion +1 and the
three formerly-null problem fields. The successor must reference the same
context-bound business problem and its real first revision, matching the formal
creator receipt and original creator in the same tenant/domain. Missing history,
additional version increments, changed output/provider/budget/source/metadata,
foreign linkage and partial linkage fail closed. Current READ, policy, account,
revocation and ancestry checks remain unchanged.

Use one helper for work reads and same-admission replay normalization, so a
successful link neither requires re-modeling nor mutates frozen authorization.
Test the actual service link_problem CAS then actual criteria/activation/planning
owners; include original and mixed body-successor ancestry, idempotent link,
wrong problem/revision/digest, extra changed result field and skipped version.
No real DB/provider/run operations, migration or model configuration changes.
