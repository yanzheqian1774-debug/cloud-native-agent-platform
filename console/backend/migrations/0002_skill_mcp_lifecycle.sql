CREATE SCHEMA IF NOT EXISTS skill_mcp_resource;
CREATE TABLE IF NOT EXISTS skill_mcp_resource.schema_migrations (
  version integer PRIMARY KEY, checksum text NOT NULL, adapter text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS skill_mcp_resource.resources (
  namespace text NOT NULL, security_domain text NOT NULL, kind text NOT NULL CHECK (kind IN ('skill','mcp')),
  resource_id text NOT NULL, aggregate_version integer NOT NULL CHECK (aggregate_version > 0), record jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, security_domain, kind, resource_id)
);
CREATE TABLE IF NOT EXISTS skill_mcp_resource.lifecycle_facts (
  namespace text NOT NULL, security_domain text NOT NULL, kind text NOT NULL, resource_id text NOT NULL,
  ordinal integer NOT NULL, fact_id text NOT NULL, fact jsonb NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, security_domain, kind, resource_id, ordinal), UNIQUE (namespace, security_domain, fact_id),
  FOREIGN KEY (namespace, security_domain, kind, resource_id) REFERENCES skill_mcp_resource.resources(namespace, security_domain, kind, resource_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS skill_mcp_resource.tombstones (
  namespace text NOT NULL, security_domain text NOT NULL, kind text NOT NULL, resource_id text NOT NULL, tombstone jsonb NOT NULL,
  deleted_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (namespace, security_domain, kind, resource_id)
);
CREATE INDEX IF NOT EXISTS skill_mcp_resources_scope_state ON skill_mcp_resource.resources(namespace, security_domain, kind, (record->>'lifecycleState'));
