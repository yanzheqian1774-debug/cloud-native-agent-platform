# Exact Native progress read for ordinary users

G1 bounded observation correction. native-progress is registered with exact
EXECUTION READ, but native_interaction.records also required a development
administrator role, rejecting ordinary authorized execution readers.

Require exact execution READ inside records before any journal query, retain
per-participant resource_read_grants, and scope the journal to the exact Run.
The existing resource helper includes pinned ontology USE for rule-bound work;
this package retains that requirement. No CONTEXT/CALL registration is used.
Remove the administrator role gate from both routes. Answer remains limited to
the original question subject and owned original conversation/root, after exact
START/root/participant/resource checks, question digest/expiry and RUNNING state.
This enables the already-authorized ordinary original-conversation workflow;
it grants no cross-account or cross-conversation answer authority. Both routes
are reviewed.

Tests cover ordinary exact readers, wrong execution/subject/scope, revoked root
and resource permission before data reads, repeat reads without writes, and the
exact START and original-subject answer gates. Real isolated PostgreSQL journal tests remain separate
from live platform acceptance; no actual model/worker/DB operation is allowed.

Answer origin is additionally pinned to the existing BUSINESS_PROBLEM context
object's original subject/conversation when present. A second conversation with
the same problem is not sufficient. Missing half of the context schema or
ambiguous origins fail closed. Legacy work with no context object must have one
unique owned conversation/root link. Existing same-answer idempotency remains;
revoked permission is checked before replay, no answer journal is fabricated.

Scope evidence propagation is not changed here. The optional pre-existing
native_confirmed_scope PG suite requires port 64335; that port was occupied, so
this task did not attach to it or relax its test guard. The new progress/answer
suite uses its own disposable PostgreSQL and controlled grant/origin fixtures.
