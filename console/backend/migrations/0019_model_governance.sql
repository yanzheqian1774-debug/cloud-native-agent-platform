-- S5-V023-IMPL-308: authoritative Model Governance continuity.
CREATE SCHEMA IF NOT EXISTS model_governance;

CREATE TABLE IF NOT EXISTS model_governance.schema_migrations (
  version integer PRIMARY KEY,
  checksum text NOT NULL CHECK (checksum ~ '^[0-9a-f]{64}$'),
  adapter text NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_governance.definitions (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  model_id text NOT NULL,
  owner_id text NOT NULL,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL,
  aggregate_version bigint NOT NULL CHECK (aggregate_version > 0),
  current_revision_id text,
  record jsonb NOT NULL,
  PRIMARY KEY (namespace, security_domain, model_id)
);

CREATE TABLE IF NOT EXISTS model_governance.provider_revisions (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  provider_id text NOT NULL,
  revision_id text NOT NULL,
  digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
  adapter_contract_id text NOT NULL,
  adapter_contract_revision_id text NOT NULL,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL,
  record jsonb NOT NULL,
  PRIMARY KEY (namespace, security_domain, provider_id, revision_id),
  UNIQUE (namespace, security_domain, provider_id, revision_id, digest)
);

CREATE TABLE IF NOT EXISTS model_governance.endpoint_revisions (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  endpoint_id text NOT NULL,
  revision_id text NOT NULL,
  digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
  normalized_address_reference text NOT NULL,
  region text NOT NULL,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL,
  record jsonb NOT NULL,
  PRIMARY KEY (namespace, security_domain, endpoint_id, revision_id),
  UNIQUE (namespace, security_domain, endpoint_id, revision_id, digest)
);

CREATE TABLE IF NOT EXISTS model_governance.connection_profile_revisions (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  profile_id text NOT NULL,
  revision_id text NOT NULL,
  digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
  endpoint_id text NOT NULL,
  endpoint_revision_id text NOT NULL,
  endpoint_digest text NOT NULL CHECK (endpoint_digest ~ '^[0-9a-f]{64}$'),
  secret_reference_id text NOT NULL,
  secret_reference_version text NOT NULL,
  connect_timeout_seconds integer NOT NULL CHECK (connect_timeout_seconds > 0),
  request_timeout_seconds integer NOT NULL CHECK (request_timeout_seconds > 0),
  created_by text NOT NULL,
  created_at timestamptz NOT NULL,
  record jsonb NOT NULL,
  PRIMARY KEY (namespace, security_domain, profile_id, revision_id),
  UNIQUE (namespace, security_domain, profile_id, revision_id, digest),
  FOREIGN KEY (
    namespace, security_domain, endpoint_id, endpoint_revision_id, endpoint_digest
  ) REFERENCES model_governance.endpoint_revisions (
    namespace, security_domain, endpoint_id, revision_id, digest
  )
);

CREATE TABLE IF NOT EXISTS model_governance.model_revisions (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  model_id text NOT NULL,
  revision_id text NOT NULL,
  revision bigint NOT NULL CHECK (revision > 0),
  predecessor_revision_id text,
  digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
  provider_id text NOT NULL,
  provider_revision_id text NOT NULL,
  provider_digest text NOT NULL CHECK (provider_digest ~ '^[0-9a-f]{64}$'),
  endpoint_id text NOT NULL,
  endpoint_revision_id text NOT NULL,
  endpoint_digest text NOT NULL CHECK (endpoint_digest ~ '^[0-9a-f]{64}$'),
  profile_id text NOT NULL,
  profile_revision_id text NOT NULL,
  profile_digest text NOT NULL CHECK (profile_digest ~ '^[0-9a-f]{64}$'),
  provider_native_model_id text NOT NULL,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL,
  record jsonb NOT NULL,
  PRIMARY KEY (namespace, security_domain, model_id, revision_id),
  UNIQUE (namespace, security_domain, model_id, revision),
  UNIQUE (namespace, security_domain, model_id, revision_id, digest),
  FOREIGN KEY (namespace, security_domain, model_id)
    REFERENCES model_governance.definitions (namespace, security_domain, model_id),
  FOREIGN KEY (namespace, security_domain, model_id, predecessor_revision_id)
    REFERENCES model_governance.model_revisions (
      namespace, security_domain, model_id, revision_id
    ),
  FOREIGN KEY (
    namespace, security_domain, provider_id, provider_revision_id, provider_digest
  ) REFERENCES model_governance.provider_revisions (
    namespace, security_domain, provider_id, revision_id, digest
  ),
  FOREIGN KEY (
    namespace, security_domain, endpoint_id, endpoint_revision_id, endpoint_digest
  ) REFERENCES model_governance.endpoint_revisions (
    namespace, security_domain, endpoint_id, revision_id, digest
  ),
  FOREIGN KEY (
    namespace, security_domain, profile_id, profile_revision_id, profile_digest
  ) REFERENCES model_governance.connection_profile_revisions (
    namespace, security_domain, profile_id, revision_id, digest
  )
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'definitions_current_revision_fk'
      AND conrelid = 'model_governance.definitions'::regclass
  ) THEN
    ALTER TABLE model_governance.definitions
      ADD CONSTRAINT definitions_current_revision_fk
      FOREIGN KEY (namespace, security_domain, model_id, current_revision_id)
      REFERENCES model_governance.model_revisions (
        namespace, security_domain, model_id, revision_id
      ) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS model_governance.lifecycle_facts (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  model_id text NOT NULL,
  revision_id text NOT NULL,
  model_digest text NOT NULL CHECK (model_digest ~ '^[0-9a-f]{64}$'),
  ordinal bigint NOT NULL CHECK (ordinal > 0),
  fact_id text NOT NULL,
  action text NOT NULL CHECK (action IN (
    'VALIDATED', 'HUMAN_REVIEWED', 'PUBLISHED', 'ENABLED',
    'DISABLED', 'DEPRECATED', 'REVOKED', 'SUCCESSOR_CREATED'
  )),
  actor_id text NOT NULL,
  decision_id text NOT NULL,
  occurred_at timestamptz NOT NULL,
  digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
  record jsonb NOT NULL,
  PRIMARY KEY (namespace, security_domain, model_id, revision_id, ordinal),
  UNIQUE (namespace, security_domain, fact_id),
  FOREIGN KEY (namespace, security_domain, model_id, revision_id, model_digest)
    REFERENCES model_governance.model_revisions (
      namespace, security_domain, model_id, revision_id, digest
    )
);

CREATE INDEX IF NOT EXISTS model_governance_definitions_catalog_idx
  ON model_governance.definitions (namespace, security_domain, model_id);

CREATE OR REPLACE FUNCTION model_governance.reject_immutable_rewrite()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'IMMUTABLE_MODEL_GOVERNANCE_HISTORY';
END $$;

DO $$
DECLARE
  relation_name text;
BEGIN
  FOREACH relation_name IN ARRAY ARRAY[
    'provider_revisions',
    'endpoint_revisions',
    'connection_profile_revisions',
    'model_revisions',
    'lifecycle_facts'
  ] LOOP
    IF NOT EXISTS (
      SELECT 1
      FROM pg_trigger
      WHERE tgname = 'immutable_model_governance_' || relation_name
        AND tgrelid = ('model_governance.' || relation_name)::regclass
    ) THEN
      EXECUTE format(
        'CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON model_governance.%I '
        'FOR EACH ROW EXECUTE FUNCTION model_governance.reject_immutable_rewrite()',
        'immutable_model_governance_' || relation_name,
        relation_name
      );
    END IF;
  END LOOP;
END $$;
