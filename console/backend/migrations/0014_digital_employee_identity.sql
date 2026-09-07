-- IMPL-276: additive independent employee authority; no historical backfill.
CREATE SCHEMA IF NOT EXISTS digital_employee_definition;
CREATE TABLE IF NOT EXISTS digital_employee_definition.schema_migrations (
  version integer PRIMARY KEY, checksum text NOT NULL, adapter text NOT NULL
);
CREATE TABLE IF NOT EXISTS digital_employee_definition.definitions (
  namespace text NOT NULL, security_domain text NOT NULL, definition_id text NOT NULL,
  aggregate_version bigint NOT NULL CHECK (aggregate_version > 0),
  PRIMARY KEY(namespace,security_domain,definition_id)
);
CREATE TABLE IF NOT EXISTS digital_employee_definition.revisions (
  namespace text NOT NULL, security_domain text NOT NULL, definition_id text NOT NULL,
  revision_id text NOT NULL, predecessor_revision_id text,
  digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'), record jsonb NOT NULL,
  PRIMARY KEY(namespace,security_domain,definition_id,revision_id),
  UNIQUE(namespace,security_domain,definition_id,predecessor_revision_id),
  FOREIGN KEY(namespace,security_domain,definition_id) REFERENCES digital_employee_definition.definitions,
  FOREIGN KEY(namespace,security_domain,definition_id,predecessor_revision_id)
    REFERENCES digital_employee_definition.revisions(namespace,security_domain,definition_id,revision_id)
);
CREATE TABLE IF NOT EXISTS digital_employee_definition.facts (
  namespace text NOT NULL, security_domain text NOT NULL, definition_id text NOT NULL,
  ordinal bigint NOT NULL CHECK(ordinal>0), revision_id text NOT NULL,
  action text NOT NULL CHECK(action IN ('CREATE','VALIDATE','APPROVE','REJECT','PUBLISH','UNPUBLISH','REVOKE_PUBLICATION','GRANT_MATCH','DENY_MATCH','REVOKE_MATCH','DEPRECATE')),
  revision_digest text NOT NULL CHECK(revision_digest ~ '^[0-9a-f]{64}$'),
  decision_id text NOT NULL, command_id text NOT NULL,
  payload_digest text NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(namespace,security_domain,definition_id,ordinal),
  UNIQUE(namespace,security_domain,command_id),
  FOREIGN KEY(namespace,security_domain,definition_id,revision_id) REFERENCES digital_employee_definition.revisions
);
CREATE TABLE IF NOT EXISTS digital_employee_definition.instance_bindings (
  namespace text NOT NULL, security_domain text NOT NULL, digital_employee_instance_id text NOT NULL,
  definition_id text NOT NULL, revision_id text NOT NULL, digest text NOT NULL,
  PRIMARY KEY(namespace,security_domain,digital_employee_instance_id),
  FOREIGN KEY(namespace,security_domain,digital_employee_instance_id) REFERENCES execution_authority.digital_employee_instances,
  FOREIGN KEY(namespace,security_domain,definition_id,revision_id) REFERENCES digital_employee_definition.revisions
);
CREATE TABLE IF NOT EXISTS digital_employee_definition.execution_bindings (
  namespace text NOT NULL, security_domain text NOT NULL, attempt_id text NOT NULL,
  digital_employee_instance_id text NOT NULL, definition_id text NOT NULL,
  revision_id text NOT NULL, digest text NOT NULL, plan_digest text NOT NULL,
  approval_id text NOT NULL, authorization_decision_id text NOT NULL,
  PRIMARY KEY(namespace,security_domain,attempt_id),
  FOREIGN KEY(namespace,security_domain,attempt_id) REFERENCES execution_authority.attempts,
  FOREIGN KEY(namespace,security_domain,digital_employee_instance_id) REFERENCES digital_employee_definition.instance_bindings,
  FOREIGN KEY(namespace,security_domain,definition_id,revision_id) REFERENCES digital_employee_definition.revisions
);
CREATE OR REPLACE FUNCTION digital_employee_definition.reject_rewrite() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'IMMUTABLE_EMPLOYEE_HISTORY'; END $$;
DO $$ DECLARE name text; BEGIN
  FOREACH name IN ARRAY ARRAY['revisions','facts','instance_bindings','execution_bindings'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='immutable_'||name
        AND tgrelid=('digital_employee_definition.'||name)::regclass) THEN
      EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON digital_employee_definition.%I FOR EACH ROW EXECUTE FUNCTION digital_employee_definition.reject_rewrite()', 'immutable_'||name, name);
    END IF;
  END LOOP;
END $$;
