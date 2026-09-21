-- Append-only, independently signed development revision; original ledgers stay intact.
SELECT pg_advisory_xact_lock(3230028);
CREATE TABLE IF NOT EXISTS authorization_admin.task_development_revisions (
 delegation_id text PRIMARY KEY REFERENCES authorization_admin.task_delegations,
 issuer_id text NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 digest text NOT NULL, record jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS authorization_admin.task_diagnostic_admissions (
 delegation_id text NOT NULL REFERENCES authorization_admin.task_development_revisions,
 request_key text NOT NULL, actor_id text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 digest text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(delegation_id,request_key)
);
CREATE TABLE IF NOT EXISTS authorization_admin.task_development_stops (
 delegation_id text PRIMARY KEY REFERENCES authorization_admin.task_development_revisions,
 actor_id text NOT NULL, reason text NOT NULL CHECK(reason IN ('PAUSED','COMPLETED')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['task_development_revisions','task_diagnostic_admissions','task_development_stops'] LOOP
 IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='immutable_' || tab) THEN
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON authorization_admin.%I FOR EACH ROW EXECUTE FUNCTION authorization_admin.task_delegation_immutable()', 'immutable_' || tab, tab);
 END IF;
 END LOOP;
END $$;
