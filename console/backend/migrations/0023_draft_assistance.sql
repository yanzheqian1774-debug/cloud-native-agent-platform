CREATE SCHEMA IF NOT EXISTS draft_assistance;
CREATE SCHEMA IF NOT EXISTS contextual_resource_use;
CREATE SCHEMA IF NOT EXISTS model_evidence;

CREATE TABLE IF NOT EXISTS draft_assistance.schema_migrations (
  version integer PRIMARY KEY,
  checksum text NOT NULL,
  adapter text NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS draft_assistance.contexts (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  context_id text NOT NULL,
  initiating_principal_id text NOT NULL,
  created_at timestamptz NOT NULL,
  PRIMARY KEY (namespace, security_domain, context_id)
);

CREATE TABLE IF NOT EXISTS draft_assistance.turns (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  context_id text NOT NULL,
  turn_id text NOT NULL,
  ordinal bigint NOT NULL CHECK (ordinal > 0),
  version bigint NOT NULL CHECK (version > 0),
  parent_turn_id text,
  created_at timestamptz NOT NULL,
  PRIMARY KEY (namespace, security_domain, turn_id),
  UNIQUE (namespace, security_domain, context_id, ordinal),
  FOREIGN KEY (namespace, security_domain, context_id)
    REFERENCES draft_assistance.contexts(namespace, security_domain, context_id)
);

CREATE TABLE IF NOT EXISTS draft_assistance.invocations (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  invocation_id text NOT NULL,
  context_id text NOT NULL,
  turn_id text NOT NULL,
  initiating_principal_id text NOT NULL,
  created_at timestamptz NOT NULL,
  PRIMARY KEY (namespace, security_domain, invocation_id),
  FOREIGN KEY (namespace, security_domain, context_id)
    REFERENCES draft_assistance.contexts(namespace, security_domain, context_id),
  FOREIGN KEY (namespace, security_domain, turn_id)
    REFERENCES draft_assistance.turns(namespace, security_domain, turn_id)
);

CREATE TABLE IF NOT EXISTS draft_assistance.idempotency_claims (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  initiating_principal_id text NOT NULL,
  action text NOT NULL CHECK (action = 'REQUEST_DRAFT_ASSISTANCE'),
  scoped_idempotency_key text NOT NULL,
  invocation_id text NOT NULL,
  commitment text NOT NULL CHECK (commitment ~ '^[0-9a-f]{64}$'),
  commitment_algorithm text NOT NULL CHECK (commitment_algorithm = 'HMAC-SHA-256'),
  canonicalization_version text NOT NULL,
  pepper_reference text NOT NULL,
  pepper_version text NOT NULL,
  created_at timestamptz NOT NULL,
  replay_not_after timestamptz NOT NULL,
  PRIMARY KEY (
    namespace, security_domain, initiating_principal_id, action,
    scoped_idempotency_key
  ),
  UNIQUE (namespace, security_domain, invocation_id),
  FOREIGN KEY (namespace, security_domain, invocation_id)
    REFERENCES draft_assistance.invocations(namespace, security_domain, invocation_id)
    DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS draft_assistance.invocation_versions (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  invocation_id text NOT NULL,
  aggregate_version bigint NOT NULL CHECK (aggregate_version > 0),
  state text NOT NULL,
  record jsonb NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, security_domain, invocation_id, aggregate_version),
  FOREIGN KEY (namespace, security_domain, invocation_id)
    REFERENCES draft_assistance.invocations(namespace, security_domain, invocation_id)
);

CREATE TABLE IF NOT EXISTS contextual_resource_use.operations (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  operation_id text NOT NULL,
  payload_digest text NOT NULL CHECK (payload_digest ~ '^[0-9a-f]{64}$'),
  resource_use_id text NOT NULL,
  record jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, security_domain, operation_id)
);

CREATE TABLE IF NOT EXISTS contextual_resource_use.uses (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  resource_use_id text NOT NULL,
  context_kind text NOT NULL CHECK (context_kind = 'DRAFT_ASSISTANCE_INVOCATION'),
  context_id text NOT NULL,
  resource_kind text NOT NULL CHECK (resource_kind = 'MODEL'),
  binding_snapshot_id text NOT NULL,
  record jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, security_domain, resource_use_id)
);

CREATE TABLE IF NOT EXISTS contextual_resource_use.facts (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  resource_use_id text NOT NULL,
  operation_id text NOT NULL,
  fact_kind text NOT NULL,
  record jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, security_domain, resource_use_id, operation_id),
  FOREIGN KEY (namespace, security_domain, resource_use_id)
    REFERENCES contextual_resource_use.uses(namespace, security_domain, resource_use_id)
);

CREATE TABLE IF NOT EXISTS model_evidence.records (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  evidence_id text NOT NULL,
  schema_version text NOT NULL CHECK (
    schema_version = 'model-draft-assistance-invocation-evidence.v1'
  ),
  operation_id text NOT NULL,
  payload_digest text NOT NULL CHECK (payload_digest ~ '^[0-9a-f]{64}$'),
  record jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, security_domain, evidence_id),
  UNIQUE (namespace, security_domain, operation_id)
);

CREATE OR REPLACE FUNCTION draft_assistance.reject_immutable_rewrite()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'IMMUTABLE_DRAFT_ASSISTANCE_HISTORY';
END $$;

CREATE OR REPLACE FUNCTION contextual_resource_use.reject_immutable_rewrite()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'IMMUTABLE_CONTEXTUAL_RESOURCE_USE_HISTORY';
END $$;

CREATE OR REPLACE FUNCTION model_evidence.reject_immutable_rewrite()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'IMMUTABLE_MODEL_EVIDENCE_HISTORY';
END $$;

DO $$
DECLARE
  relation_name text;
BEGIN
  FOREACH relation_name IN ARRAY ARRAY['operations', 'uses', 'facts'] LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_trigger
      WHERE tgname = 'immutable_contextual_resource_use_' || relation_name
        AND tgrelid = ('contextual_resource_use.' || relation_name)::regclass
    ) THEN
      EXECUTE format(
        'CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON contextual_resource_use.%I '
        'FOR EACH ROW EXECUTE FUNCTION contextual_resource_use.reject_immutable_rewrite()',
        'immutable_contextual_resource_use_' || relation_name,
        relation_name
      );
    END IF;
  END LOOP;
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'immutable_model_evidence_records'
      AND tgrelid = 'model_evidence.records'::regclass
  ) THEN
    CREATE TRIGGER immutable_model_evidence_records
      BEFORE UPDATE OR DELETE ON model_evidence.records
      FOR EACH ROW EXECUTE FUNCTION model_evidence.reject_immutable_rewrite();
  END IF;
END $$;

DO $$
DECLARE
  relation_name text;
BEGIN
  FOREACH relation_name IN ARRAY ARRAY[
    'contexts', 'turns', 'invocations', 'idempotency_claims',
    'invocation_versions'
  ] LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_trigger
      WHERE tgname = 'immutable_draft_assistance_' || relation_name
        AND tgrelid = ('draft_assistance.' || relation_name)::regclass
    ) THEN
      EXECUTE format(
        'CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON draft_assistance.%I '
        'FOR EACH ROW EXECUTE FUNCTION draft_assistance.reject_immutable_rewrite()',
        'immutable_draft_assistance_' || relation_name,
        relation_name
      );
    END IF;
  END LOOP;
END $$;
