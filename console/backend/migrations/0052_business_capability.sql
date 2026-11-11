-- Business capability draft definitions. No publication, execution or member mutation.
CREATE SCHEMA IF NOT EXISTS business_capability;
CREATE TABLE IF NOT EXISTS business_capability.schema_migrations (
 version integer PRIMARY KEY, checksum text NOT NULL, adapter text NOT NULL
);
CREATE TABLE IF NOT EXISTS business_capability.definitions (
 namespace text NOT NULL, security_domain text NOT NULL, capability_id text NOT NULL,
 head_revision_id text NOT NULL, aggregate_version bigint NOT NULL CHECK(aggregate_version > 0),
 PRIMARY KEY(namespace,security_domain,capability_id)
);
CREATE TABLE IF NOT EXISTS business_capability.revisions (
 namespace text NOT NULL, security_domain text NOT NULL, capability_id text NOT NULL,
 revision_id text NOT NULL, predecessor_revision_id text,
 digest text NOT NULL CHECK(digest ~ '^[0-9a-f]{64}$'), record jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,capability_id,revision_id),
 UNIQUE(namespace,security_domain,capability_id,predecessor_revision_id),
 FOREIGN KEY(namespace,security_domain,capability_id) REFERENCES business_capability.definitions,
 FOREIGN KEY(namespace,security_domain,capability_id,predecessor_revision_id)
 REFERENCES business_capability.revisions(namespace,security_domain,capability_id,revision_id)
);
CREATE TABLE IF NOT EXISTS business_capability.receipts (
 namespace text NOT NULL, security_domain text NOT NULL, command_id text NOT NULL,
 capability_id text NOT NULL, revision_id text NOT NULL, payload_digest text NOT NULL,
 actor_id text NOT NULL, decision_id text NOT NULL, aggregate_version bigint NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(namespace,security_domain,command_id),
 UNIQUE(namespace,security_domain,capability_id,aggregate_version),
 FOREIGN KEY(namespace,security_domain,capability_id,revision_id) REFERENCES business_capability.revisions
);
CREATE OR REPLACE FUNCTION business_capability.reject_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'CAPABILITY_IMMUTABLE_RECORD'; END $$;
DO $$ DECLARE name text; BEGIN
 FOREACH name IN ARRAY ARRAY['revisions','receipts'] LOOP
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='immutable_'||name
   AND tgrelid=('business_capability.'||name)::regclass) THEN
   EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON business_capability.%I FOR EACH ROW EXECUTE FUNCTION business_capability.reject_rewrite()', 'immutable_'||name, name);
  END IF;
 END LOOP;
END $$;
