-- Immutable single-variable planning timeout revisions on original task ledgers.
SELECT pg_advisory_xact_lock(3230028);
CREATE TABLE IF NOT EXISTS authorization_admin.task_timeout_revisions (
 delegation_id text PRIMARY KEY REFERENCES authorization_admin.task_development_revisions,
 problem_id text NOT NULL, issuer_id text NOT NULL,
 digest text NOT NULL, record jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER immutable_task_timeout_revisions BEFORE UPDATE OR DELETE
 ON authorization_admin.task_timeout_revisions FOR EACH ROW
 EXECUTE FUNCTION authorization_admin.task_delegation_immutable();
