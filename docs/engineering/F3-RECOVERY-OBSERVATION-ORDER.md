# Recovery observation order

G1 presentation-only race repair. Each GET observation has a generation; a newer
observation, explicit continue or unmount invalidates older reads. A delayed GET
cannot replace current continuation progress with stale waiting/authorized state.
No backend, authorization, invocation, budget, polling frequency or POST change.
Verify delayed polling GET, manual GET returning authorization, explicit continue,
and late polling response; continuation UI must remain current and POST count one.

Validation: eight browser cases passed, including delayed success/failure after
continue; final two race cases rerun passed. Frontend lint and build passed.
An in-flight old read is ignored, not cancelled or replayed; one explicit continue
POST remains one POST and no automatic model invocation is introduced.
