-- Business architecture and process drafts, separate from executable workflows.
CREATE SCHEMA IF NOT EXISTS business_process;
CREATE TABLE IF NOT EXISTS business_process.schema_migrations (
 version integer PRIMARY KEY, checksum text NOT NULL, adapter text NOT NULL
);
CREATE TABLE IF NOT EXISTS business_process.definitions (
 namespace text NOT NULL, security_domain text NOT NULL,
 kind text NOT NULL CHECK(kind IN ('ARCHITECTURE','PROCESS')),
 object_id text NOT NULL, head_revision_id text NOT NULL,
 aggregate_version bigint NOT NULL CHECK(aggregate_version > 0),
 PRIMARY KEY(namespace,security_domain,kind,object_id)
);
CREATE TABLE IF NOT EXISTS business_process.revisions (
 namespace text NOT NULL, security_domain text NOT NULL, kind text NOT NULL,
 object_id text NOT NULL, revision_id text NOT NULL, predecessor_revision_id text,
 digest text NOT NULL CHECK(digest ~ '^[0-9a-f]{64}$'), record jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,kind,object_id,revision_id),
 UNIQUE(namespace,security_domain,kind,object_id,predecessor_revision_id),
 FOREIGN KEY(namespace,security_domain,kind,object_id) REFERENCES business_process.definitions,
 FOREIGN KEY(namespace,security_domain,kind,object_id,predecessor_revision_id)
 REFERENCES business_process.revisions(namespace,security_domain,kind,object_id,revision_id)
);
CREATE TABLE IF NOT EXISTS business_process.receipts (
 namespace text NOT NULL, security_domain text NOT NULL, command_id text NOT NULL,
 kind text NOT NULL, object_id text NOT NULL, revision_id text NOT NULL,
 actor_id text NOT NULL, decision_id text NOT NULL, payload_digest text NOT NULL,
 aggregate_version bigint NOT NULL, result jsonb NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(namespace,security_domain,command_id),
 UNIQUE(namespace,security_domain,kind,object_id,aggregate_version),
 FOREIGN KEY(namespace,security_domain,kind,object_id,revision_id)
 REFERENCES business_process.revisions
);
CREATE OR REPLACE FUNCTION business_process.reject_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'BUSINESS_PROCESS_IMMUTABLE_RECORD'; END $$;
DO $$ DECLARE name text; BEGIN
 FOREACH name IN ARRAY ARRAY['revisions','receipts'] LOOP
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='immutable_'||name
   AND tgrelid=('business_process.'||name)::regclass) THEN
   EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON business_process.%I FOR EACH ROW EXECUTE FUNCTION business_process.reject_rewrite()', 'immutable_'||name, name);
  END IF;
 END LOOP;
END $$;
