-- Explicit case enrollment extends, never replaces, the original task ledger.
SELECT pg_advisory_xact_lock(3230028);
CREATE TABLE IF NOT EXISTS authorization_admin.task_cases (
 delegation_id text NOT NULL REFERENCES authorization_admin.task_development_revisions,
 context_id text NOT NULL, issuer_id text NOT NULL,
 idempotency_key text NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 digest text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(delegation_id,context_id), UNIQUE(delegation_id,idempotency_key)
);
CREATE TABLE IF NOT EXISTS authorization_admin.task_case_problems (
 delegation_id text NOT NULL, context_id text NOT NULL, problem_id text NOT NULL,
 invocation_id text NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(delegation_id,context_id), UNIQUE(delegation_id,problem_id),
 FOREIGN KEY(delegation_id,context_id) REFERENCES authorization_admin.task_cases
);
DROP INDEX IF EXISTS authorization_admin.task_delegation_one_problem;
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['task_cases','task_case_problems'] LOOP
 IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='immutable_' || tab) THEN
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON authorization_admin.%I FOR EACH ROW EXECUTE FUNCTION authorization_admin.task_delegation_immutable()', 'immutable_' || tab, tab);
 END IF;
 END LOOP;
END $$;
