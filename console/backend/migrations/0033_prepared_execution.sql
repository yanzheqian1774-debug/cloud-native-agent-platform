-- D324: supplemental preparation and artifact records, same Execution owner.
-- No new execution identity, dispatch queue or cost ledger.
SELECT pg_advisory_xact_lock(3240033);
CREATE TABLE IF NOT EXISTS execution_authority.preparation_migrations (
 version integer PRIMARY KEY, checksum text NOT NULL CHECK(length(checksum)=64)
);
CREATE TABLE IF NOT EXISTS execution_authority.run_preparations (
 namespace text NOT NULL, security_domain text NOT NULL, workflow_run_id text NOT NULL,
 digest text NOT NULL CHECK(length(digest)=64), record jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,workflow_run_id),
 UNIQUE(namespace,security_domain,digest),
 FOREIGN KEY(namespace,security_domain,workflow_run_id)
 REFERENCES execution_authority.workflow_runs(namespace,security_domain,workflow_run_id)
);
CREATE TABLE IF NOT EXISTS execution_authority.prepared_run_progress (
 namespace text NOT NULL, security_domain text NOT NULL, workflow_run_id text NOT NULL,
 version bigint NOT NULL CHECK(version>0), record jsonb NOT NULL,
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,workflow_run_id),
 FOREIGN KEY(namespace,security_domain,workflow_run_id)
 REFERENCES execution_authority.run_preparations(namespace,security_domain,workflow_run_id)
);
CREATE TABLE IF NOT EXISTS execution_authority.prepared_run_events (
 namespace text NOT NULL, security_domain text NOT NULL, workflow_run_id text NOT NULL,
 event_id text NOT NULL, version bigint NOT NULL CHECK(version>1),
 digest text NOT NULL CHECK(length(digest)=64), record jsonb NOT NULL,
 result jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,workflow_run_id,event_id),
 UNIQUE(namespace,security_domain,workflow_run_id,version),
 FOREIGN KEY(namespace,security_domain,workflow_run_id)
 REFERENCES execution_authority.run_preparations(namespace,security_domain,workflow_run_id)
);
CREATE TABLE IF NOT EXISTS execution_authority.run_artifacts (
 namespace text NOT NULL, security_domain text NOT NULL, workflow_run_id text NOT NULL,
 artifact_id text NOT NULL, task_id text NOT NULL, attempt_id text NOT NULL,
 digest text NOT NULL CHECK(length(digest)=64),
 content text NOT NULL, record jsonb NOT NULL,
 byte_size integer GENERATED ALWAYS AS (octet_length(content)) STORED,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,workflow_run_id,artifact_id),
 CHECK(octet_length(content)<=262144),
 CHECK((record->>'artifact_id') IS NOT DISTINCT FROM artifact_id),
 CHECK((record->>'task_id') IS NOT DISTINCT FROM task_id),
 CHECK((record->>'attempt_id') IS NOT DISTINCT FROM attempt_id),
 CHECK((record->>'digest') IS NOT DISTINCT FROM digest),
 CHECK((record->>'content') IS NOT DISTINCT FROM content),
 CHECK(encode(sha256(convert_to(content,'UTF8')),'hex')=digest),
 FOREIGN KEY(namespace,security_domain,workflow_run_id)
 REFERENCES execution_authority.run_preparations(namespace,security_domain,workflow_run_id),
 FOREIGN KEY(namespace,security_domain,attempt_id)
 REFERENCES execution_authority.attempts(namespace,security_domain,attempt_id)
);
CREATE OR REPLACE FUNCTION execution_authority.preparation_immutable()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 RAISE EXCEPTION 'PREPARED_EXECUTION_HISTORY_IMMUTABLE';
END $$;
CREATE OR REPLACE FUNCTION execution_authority.artifact_capacity()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE task_count bigint; run_bytes bigint;
BEGIN
 -- Serialize ALL writers, including different Tasks and retry Attempts.
 PERFORM 1 FROM execution_authority.prepared_run_progress
 WHERE namespace=NEW.namespace AND security_domain=NEW.security_domain
 AND workflow_run_id=NEW.workflow_run_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'ARTIFACT_RUN_NOT_FOUND'; END IF;
 SELECT count(*) FILTER (WHERE task_id=NEW.task_id),coalesce(sum(byte_size),0)
 INTO task_count,run_bytes FROM execution_authority.run_artifacts
 WHERE namespace=NEW.namespace AND security_domain=NEW.security_domain
 AND workflow_run_id=NEW.workflow_run_id;
 IF task_count>=16 OR run_bytes+octet_length(NEW.content)>4194304 THEN
  RAISE EXCEPTION 'ARTIFACT_HISTORY_CAPACITY_EXCEEDED';
 END IF;
 RETURN NEW;
END $$;
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['run_preparations','prepared_run_events','run_artifacts'] LOOP
 IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid=('execution_authority.'||tab)::regclass AND tgname='prepared_history_immutable') THEN
 EXECUTE format('CREATE TRIGGER prepared_history_immutable BEFORE UPDATE OR DELETE ON execution_authority.%I FOR EACH ROW EXECUTE FUNCTION execution_authority.preparation_immutable()',tab);
 END IF;
 END LOOP;
 IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='execution_authority.run_artifacts'::regclass AND tgname='artifact_atomic_capacity') THEN
 CREATE TRIGGER artifact_atomic_capacity BEFORE INSERT ON execution_authority.run_artifacts
 FOR EACH ROW EXECUTE FUNCTION execution_authority.artifact_capacity();
 END IF;
END $$;
