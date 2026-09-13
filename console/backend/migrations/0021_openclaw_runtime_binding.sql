CREATE TABLE IF NOT EXISTS execution_authority.openclaw_binding_migrations (
  version integer PRIMARY KEY,
  checksum text NOT NULL CHECK (length(checksum) = 64),
  adapter text NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_authority.openclaw_runtime_bindings (
  namespace text NOT NULL CHECK (octet_length(namespace) BETWEEN 1 AND 128),
  security_domain text NOT NULL CHECK (octet_length(security_domain) BETWEEN 1 AND 128),
  runtime_instance_id text NOT NULL CHECK (octet_length(runtime_instance_id) BETWEEN 1 AND 200),
  placement_id text NOT NULL CHECK (octet_length(placement_id) BETWEEN 1 AND 200),
  gateway_digest text NOT NULL CHECK (length(gateway_digest) = 64),
  agent_id text NOT NULL CHECK (octet_length(agent_id) BETWEEN 1 AND 512),
  canonical_workspace text NOT NULL CHECK (octet_length(canonical_workspace) BETWEEN 1 AND 512),
  workspace_host text NOT NULL CHECK (octet_length(workspace_host) BETWEEN 1 AND 512),
  workspace_storage_domain text NOT NULL CHECK (octet_length(workspace_storage_domain) BETWEEN 1 AND 512),
  source_version text NOT NULL CHECK (source_version = '2026.7.1-2'),
  authorization_decision_id text NOT NULL CHECK (octet_length(authorization_decision_id) BETWEEN 1 AND 512),
  binding_digest text NOT NULL CHECK (length(binding_digest) = 64),
  record jsonb NOT NULL,
  recorded_at timestamptz NOT NULL,
  PRIMARY KEY (namespace, security_domain, runtime_instance_id),
  UNIQUE (gateway_digest, agent_id),
  UNIQUE (workspace_host, workspace_storage_domain, canonical_workspace),
  FOREIGN KEY (namespace, security_domain, runtime_instance_id)
    REFERENCES execution_authority.runtime_instances(namespace, security_domain, runtime_instance_id),
  FOREIGN KEY (namespace, security_domain, placement_id)
    REFERENCES execution_authority.placement_decisions(namespace, security_domain, placement_id)
);

CREATE TABLE IF NOT EXISTS execution_authority.openclaw_generation_bindings (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  runtime_instance_id text NOT NULL,
  generation bigint NOT NULL CHECK (generation > 0),
  gateway_digest text NOT NULL CHECK (length(gateway_digest) = 64),
  session_key text NOT NULL CHECK (octet_length(session_key) BETWEEN 1 AND 512),
  session_id text NOT NULL CHECK (octet_length(session_id) BETWEEN 1 AND 512),
  command_id text NOT NULL CHECK (octet_length(command_id) BETWEEN 1 AND 200),
  idempotency_key text NOT NULL CHECK (octet_length(idempotency_key) BETWEEN 1 AND 512),
  command_payload_digest text NOT NULL CHECK (length(command_payload_digest) = 64),
  association_status text NOT NULL CHECK (association_status IN ('UNVERIFIED','MATCHED','MISMATCHED','RECOVERY_REQUIRED')),
  observation_high_water bigint NOT NULL DEFAULT 0 CHECK (observation_high_water >= 0),
  generation_digest text NOT NULL CHECK (length(generation_digest) = 64),
  record jsonb NOT NULL,
  recorded_at timestamptz NOT NULL,
  PRIMARY KEY (namespace, security_domain, runtime_instance_id, generation),
  UNIQUE (gateway_digest, session_key),
  UNIQUE (gateway_digest, session_id),
  UNIQUE (namespace, security_domain, idempotency_key),
  FOREIGN KEY (namespace, security_domain, runtime_instance_id)
    REFERENCES execution_authority.openclaw_runtime_bindings(namespace, security_domain, runtime_instance_id),
  FOREIGN KEY (namespace, security_domain, command_id)
    REFERENCES execution_authority.desired_commands(namespace, security_domain, command_id)
);

CREATE TABLE IF NOT EXISTS execution_authority.openclaw_binding_observations (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  runtime_instance_id text NOT NULL,
  generation bigint NOT NULL CHECK (generation > 0),
  high_water bigint NOT NULL CHECK (high_water > 0),
  association_status text NOT NULL CHECK (association_status IN ('UNVERIFIED','MATCHED','MISMATCHED','RECOVERY_REQUIRED')),
  source_version text NOT NULL CHECK (source_version = '2026.7.1-2'),
  observation_digest text NOT NULL CHECK (length(observation_digest) = 64),
  record jsonb NOT NULL,
  observed_at timestamptz NOT NULL,
  freshness_deadline timestamptz NOT NULL CHECK (freshness_deadline > observed_at),
  PRIMARY KEY (namespace, security_domain, runtime_instance_id, generation, high_water),
  FOREIGN KEY (namespace, security_domain, runtime_instance_id, generation)
    REFERENCES execution_authority.openclaw_generation_bindings(namespace, security_domain, runtime_instance_id, generation)
);
