CREATE SCHEMA IF NOT EXISTS workflow_definition;
CREATE SCHEMA IF NOT EXISTS runtime_profile;

CREATE TABLE IF NOT EXISTS workflow_definition.schema_migrations (
  version integer PRIMARY KEY, checksum text NOT NULL, adapter text NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS workflow_definition.definitions (
  namespace text NOT NULL, security_domain text NOT NULL,
  workflow_definition_id text NOT NULL, aggregate_version bigint NOT NULL CHECK (aggregate_version > 0),
  record jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, security_domain, workflow_definition_id)
);
CREATE TABLE IF NOT EXISTS workflow_definition.lifecycle_facts (
  namespace text NOT NULL, security_domain text NOT NULL, workflow_definition_id text NOT NULL,
  ordinal bigint NOT NULL CHECK (ordinal > 0), fact_id text NOT NULL, fact jsonb NOT NULL,
  PRIMARY KEY (namespace, security_domain, workflow_definition_id, ordinal), UNIQUE (namespace, security_domain, fact_id),
  FOREIGN KEY (namespace, security_domain, workflow_definition_id) REFERENCES workflow_definition.definitions(namespace, security_domain, workflow_definition_id)
);
CREATE TABLE IF NOT EXISTS runtime_profile.schema_migrations (
  version integer PRIMARY KEY, checksum text NOT NULL, adapter text NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS runtime_profile.profiles (
  namespace text NOT NULL, security_domain text NOT NULL,
  runtime_profile_id text NOT NULL, aggregate_version bigint NOT NULL CHECK (aggregate_version > 0),
  record jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, security_domain, runtime_profile_id)
);
CREATE TABLE IF NOT EXISTS runtime_profile.lifecycle_facts (
  namespace text NOT NULL, security_domain text NOT NULL, runtime_profile_id text NOT NULL,
  ordinal bigint NOT NULL CHECK (ordinal > 0), fact_id text NOT NULL, fact jsonb NOT NULL,
  PRIMARY KEY (namespace, security_domain, runtime_profile_id, ordinal), UNIQUE (namespace, security_domain, fact_id),
  FOREIGN KEY (namespace, security_domain, runtime_profile_id) REFERENCES runtime_profile.profiles(namespace, security_domain, runtime_profile_id)
);
