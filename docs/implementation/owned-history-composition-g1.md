# Retained policy composition correction (G1)

Observed r7 API boots but Native manager fails: two production composition paths omitted the already supported retained_history_paths parameter. This is a wiring correction, not a relaxation of v2 policy validation. Both use the existing configured_paths parser on OWNED_BUSINESS_RETAINED_HISTORY_POLICIES. Missing/malformed/incomplete history configuration still fails closed.

All four production OwnedBusinessWorkReader constructor sites audited:
1. owned_business_admission.py: delegates its explicit retained_history_paths; workbench_bootstrap already parses the environment with configured_paths and passes it to this owner.
2. owned_business_retained_history.py: deliberately constructs old exact reader with _retained_read_only=True and no recursive history paths. This is correct: original admission digest already selects that reader, which denies nonhistory work/planning. Do not expand recursive environment here.
3. native_dispatch_reconciler.py: corrected manager construction to pass parsed environment.
4. native_wait_answer.py: corrected original answer bridge construction to pass parsed environment. Answer remains current work authorization (history=False), not history permission.

Regression directly enters production build_native_dispatch_from_environment and accept_if_waiting, delegates their constructor call to the real v2 policy loader/retained reader graph, and stops with a controlled sentinel after construction. Database/process/provider surroundings are test doubles and no execution or answer is fabricated. Each entry has valid-pins and missing-environment cases; original strict reader and interaction cases also run. This proves actual call-site wiring, not successful real host boot/claim/answer. Prior slice four real owner PG cases prove unchanged history-only/revocation/derive_work gates; they are not re-labelled as this slice live acceptance. Root must perform actual composition startup after installation.
