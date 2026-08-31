-- S5-IMPL-051: additive Agent Definition exact governed bindings.
DO $$
BEGIN
  IF to_regclass('agent_definition.definitions') IS NULL
     OR to_regclass('skill_mcp_resource.resources') IS NULL
     OR to_regclass('knowledge_operation.knowledge') IS NULL
     OR to_regclass('skill_mcp_resource.professional_facts') IS NULL
     OR to_regclass('knowledge_quality.entities') IS NULL THEN
    RAISE EXCEPTION 'MIGRATION_CHAIN_0001_THROUGH_0005_REQUIRED';
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS agent_definition.revision_bindings (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  definition_id text NOT NULL,
  revision_id text NOT NULL,
  binding_kind text NOT NULL CHECK (binding_kind IN ('skill','mcp','knowledge','model','workflow','runtime-profile')),
  binding_ordinal integer NOT NULL CHECK (binding_ordinal >= 0),
  resource_id text NOT NULL,
  resource_revision_id text,
  resource_digest text CHECK (resource_digest IS NULL OR resource_digest ~ '^[0-9a-f]{64}$'),
  tool_name text,
  snapshot_id text,
  binding jsonb NOT NULL,
  PRIMARY KEY(namespace, security_domain, definition_id, revision_id, binding_kind, binding_ordinal),
  FOREIGN KEY(namespace, security_domain, definition_id)
    REFERENCES agent_definition.definitions(namespace, security_domain, definition_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_definition.binding_facts (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  definition_id text NOT NULL,
  ordinal bigint NOT NULL,
  fact_id text NOT NULL,
  fact_type text NOT NULL,
  revision_id text NOT NULL,
  revision_digest text NOT NULL CHECK (revision_digest ~ '^[0-9a-f]{64}$'),
  fact jsonb NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(namespace, security_domain, definition_id, ordinal),
  UNIQUE(namespace, security_domain, fact_id),
  FOREIGN KEY(namespace, security_domain, definition_id)
    REFERENCES agent_definition.definitions(namespace, security_domain, definition_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS agent_revision_bindings_target
  ON agent_definition.revision_bindings(namespace, security_domain, binding_kind, resource_id, resource_revision_id);
