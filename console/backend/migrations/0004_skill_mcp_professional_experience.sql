CREATE SCHEMA IF NOT EXISTS skill_mcp_resource;
CREATE TABLE IF NOT EXISTS skill_mcp_resource.professional_facts (
  namespace text NOT NULL, security_domain text NOT NULL, kind text NOT NULL CHECK (kind IN ('skill','mcp')),
  resource_id text NOT NULL, ordinal integer NOT NULL, fact_id text NOT NULL, fact_type text NOT NULL,
  safe_fact jsonb NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, security_domain, kind, resource_id, ordinal),
  UNIQUE (namespace, security_domain, fact_id),
  FOREIGN KEY (namespace, security_domain, kind, resource_id)
    REFERENCES skill_mcp_resource.resources(namespace, security_domain, kind, resource_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS skill_mcp_professional_facts_type
  ON skill_mcp_resource.professional_facts(namespace, security_domain, kind, resource_id, fact_type);
