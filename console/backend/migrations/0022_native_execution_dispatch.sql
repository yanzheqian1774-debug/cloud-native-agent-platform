-- S5-V023-IMPL-315: additive Native execution dispatch authority.
-- PostgreSQL owns command, claim, fencing and normalized technical facts.
-- Kubernetes and Runtime remain authoritative for their actual/native state.

DO $$ BEGIN
  IF to_regclass('execution_authority.attempts') IS NULL
     OR to_regclass('execution_authority.placement_requests') IS NULL
     OR to_regclass('execution_authority.placement_decisions') IS NULL
     OR to_regclass('execution_authority.runtime_instances') IS NULL THEN
    RAISE EXCEPTION 'EXECUTION_AUTHORITY_MIGRATION_CHAIN_REQUIRED';
  END IF;
END $$;

CREATE SCHEMA IF NOT EXISTS native_execution_dispatch;
CREATE TABLE IF NOT EXISTS native_execution_dispatch.schema_migrations (
  version integer PRIMARY KEY,
  checksum text NOT NULL CHECK(length(checksum)=64),
  adapter text NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_authority.native_dispatch_commands (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  command_id text NOT NULL CHECK(octet_length(command_id) BETWEEN 1 AND 200),
  command_digest text NOT NULL CHECK(length(command_digest)=64),
  canonical_bytes bytea NOT NULL,
  payload jsonb NOT NULL,
  attempt_id text NOT NULL,
  assignment_id text NOT NULL,
  approved_plan_revision_id text NOT NULL,
  approved_plan_digest text NOT NULL CHECK(length(approved_plan_digest)=64),
  placement_id text NOT NULL,
  placement_digest text NOT NULL CHECK(length(placement_digest)=64),
  runtime_instance_id text NOT NULL,
  runtime_generation bigint NOT NULL CHECK(runtime_generation>0),
  agent_instance_id text NOT NULL,
  principal_id text NOT NULL,
  credential_id text NOT NULL,
  authority_generation bigint NOT NULL CHECK(authority_generation>0),
  recovery_epoch bigint NOT NULL CHECK(recovery_epoch>0),
  authorization_owner text NOT NULL,
  authorization_action text NOT NULL,
  authorization_resource text NOT NULL,
  agent_name text NOT NULL,
  input_text text NOT NULL,
  timeout_seconds integer NOT NULL CHECK(timeout_seconds BETWEEN 1 AND 3600),
  state text NOT NULL CHECK(state IN
    ('QUEUED','CLAIMED','EFFECT_STARTED','SUCCEEDED','FAILED','UNKNOWN','RECOVERY_REQUIRED')),
  claim_generation bigint NOT NULL DEFAULT 0 CHECK(claim_generation>=0),
  fencing_token text,
  worker_id text,
  lease_expires_at timestamptz,
  kubernetes_task_name text,
  kubernetes_task_uid text,
  terminal_observation_digest text CHECK(
    terminal_observation_digest IS NULL OR length(terminal_observation_digest)=64),
  terminal_record jsonb,
  queued_at timestamptz NOT NULL,
  effect_started_at timestamptz,
  terminal_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(namespace,security_domain,command_id),
  UNIQUE(namespace,security_domain,attempt_id),
  UNIQUE(namespace,security_domain,kubernetes_task_name),
  FOREIGN KEY(namespace,security_domain,attempt_id)
    REFERENCES execution_authority.attempts(namespace,security_domain,attempt_id),
  FOREIGN KEY(namespace,security_domain,assignment_id)
    REFERENCES execution_authority.assignments(namespace,security_domain,assignment_id),
  FOREIGN KEY(namespace,security_domain,placement_id)
    REFERENCES execution_authority.placement_decisions(namespace,security_domain,placement_id),
  FOREIGN KEY(namespace,security_domain,runtime_instance_id)
    REFERENCES execution_authority.runtime_instances(namespace,security_domain,runtime_instance_id),
  CHECK ((state='QUEUED' AND claim_generation=0 AND fencing_token IS NULL
          AND worker_id IS NULL AND lease_expires_at IS NULL)
    OR (state='CLAIMED' AND claim_generation>0 AND fencing_token IS NOT NULL
          AND worker_id IS NOT NULL AND lease_expires_at IS NOT NULL)
    OR (state NOT IN ('QUEUED','CLAIMED') AND claim_generation>0
          AND fencing_token IS NOT NULL AND worker_id IS NOT NULL
          AND lease_expires_at IS NULL)),
  CHECK ((state IN ('EFFECT_STARTED','SUCCEEDED','FAILED','UNKNOWN','RECOVERY_REQUIRED'))
          = (effect_started_at IS NOT NULL)),
  CHECK ((state IN ('SUCCEEDED','FAILED','UNKNOWN','RECOVERY_REQUIRED'))
          = (terminal_observation_digest IS NOT NULL AND terminal_record IS NOT NULL
             AND terminal_at IS NOT NULL)),
  CHECK (state IN ('QUEUED','CLAIMED') OR kubernetes_task_name IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS native_dispatch_claim_idx
  ON execution_authority.native_dispatch_commands(state,lease_expires_at,queued_at,command_id);

CREATE TABLE IF NOT EXISTS execution_authority.native_dispatch_facts (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  command_id text NOT NULL,
  ordinal bigint NOT NULL CHECK(ordinal>0),
  kind text NOT NULL CHECK(kind IN
    ('QUEUED','CLAIMED','EFFECT_STARTED','CORRELATED','SUCCEEDED','FAILED','UNKNOWN','RECOVERY_REQUIRED')),
  fact_digest text NOT NULL CHECK(length(fact_digest)=64),
  record jsonb NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(namespace,security_domain,command_id,ordinal),
  UNIQUE(namespace,security_domain,command_id,kind,fact_digest),
  FOREIGN KEY(namespace,security_domain,command_id)
    REFERENCES execution_authority.native_dispatch_commands(namespace,security_domain,command_id)
);
