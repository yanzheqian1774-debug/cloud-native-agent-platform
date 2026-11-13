# G1: Task-directory question projection alignment

Scope: original F3 P2 task/record directory, based on 95129be. Ordinary users
can read Native progress under current exact READ permissions, but the directory
still imposes a development-administrator-only check and uses ontology USE.

Change only the directory projection to reuse `projection_read_grants` for every
identity. Keep collection LIST plus per-run EXECUTION READ and BUSINESS_PROBLEM
READ preselection, current scope, exact version checks, counts, filters and
pagination. A denied required resource leaves all question fields null. Authority
unavailability continues to fail the read instead of manufacturing zeros.
Execution, answer submission, START/USE, model calls and persistent records are
unchanged. No endpoint, schema, migration, grant or new infrastructure.

Validation: controlled projection regressions for complete/missing permissions,
terminal answers, malformed answer bindings and foreign origins; isolated PG/BFF
with real ordinary identity and exact grant owner, ontology USE expired but READ
valid, exact READ revocation, wrong version, cross-domain denial, and zero model
or execution effects. Fixture candidate/Native rows are controlled and are not
claims of an actual Native run. Root performs integration and live acceptance.
