-- Optional operator maintenance, not an automatic schema-version migration.
-- Execute outside a transaction with bounded lock_timeout/statement_timeout.
-- Inspect an existing/invalid index instead of silently skipping or replacing it.
-- Preserve exact grant predicates and the existing ordered row locks.
CREATE INDEX CONCURRENTLY grants_exact_lookup_idx
    ON authorization_admin.grants
    (subject_principal_id, tenant_id, security_domain, owner, action, exact_resource);
