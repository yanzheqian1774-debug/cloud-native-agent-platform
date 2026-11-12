-- Independent imported tool drafts; no execution or publication authority.
CREATE SCHEMA IF NOT EXISTS tool_definition;
CREATE TABLE IF NOT EXISTS tool_definition.schema_migrations (
 version integer PRIMARY KEY, checksum text NOT NULL, adapter text NOT NULL
);
CREATE TABLE IF NOT EXISTS tool_definition.sources (
 namespace text NOT NULL, security_domain text NOT NULL,
 source_digest text NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),
 source_kind text NOT NULL CHECK(source_kind IN ('API','PLUGIN','PLUGIN_ZIP')),
 payload bytea NOT NULL CHECK(octet_length(payload) <= 100000),
 PRIMARY KEY(namespace,security_domain,source_digest)
);
CREATE TABLE IF NOT EXISTS tool_definition.definitions (
 namespace text NOT NULL, security_domain text NOT NULL, tool_id text NOT NULL,
 logical_digest text NOT NULL CHECK(logical_digest ~ '^[0-9a-f]{64}$'),
 draft_revision_id text, published_revision_id text,
 aggregate_version bigint NOT NULL CHECK(aggregate_version > 0),
 PRIMARY KEY(namespace,security_domain,tool_id),
 UNIQUE(namespace,security_domain,logical_digest)
);
CREATE TABLE IF NOT EXISTS tool_definition.revisions (
 namespace text NOT NULL, security_domain text NOT NULL, tool_id text NOT NULL,
 revision_id text NOT NULL, predecessor_revision_id text,
 source_digest text NOT NULL, digest text NOT NULL CHECK(digest ~ '^[0-9a-f]{64}$'),
 record jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,tool_id,revision_id),
 FOREIGN KEY(namespace,security_domain,tool_id) REFERENCES tool_definition.definitions,
 FOREIGN KEY(namespace,security_domain,source_digest) REFERENCES tool_definition.sources,
 FOREIGN KEY(namespace,security_domain,tool_id,predecessor_revision_id)
 REFERENCES tool_definition.revisions(namespace,security_domain,tool_id,revision_id)
);
CREATE TABLE IF NOT EXISTS tool_definition.receipts (
 namespace text NOT NULL, security_domain text NOT NULL, command_id text NOT NULL,
 actor_id text NOT NULL, decision_id text NOT NULL,
 payload_digest text NOT NULL CHECK(payload_digest ~ '^[0-9a-f]{64}$'),
 result jsonb NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(namespace,security_domain,command_id)
);
CREATE OR REPLACE FUNCTION tool_definition.reject_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'TOOL_IMMUTABLE_RECORD'; END $$;
DO $$ DECLARE name text; BEGIN
 FOREACH name IN ARRAY ARRAY['sources','revisions','receipts'] LOOP
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='immutable_'||name
   AND tgrelid=('tool_definition.'||name)::regclass) THEN
   EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON tool_definition.%I FOR EACH ROW EXECUTE FUNCTION tool_definition.reject_rewrite()', 'immutable_'||name, name);
  END IF;
 END LOOP;
END $$;
