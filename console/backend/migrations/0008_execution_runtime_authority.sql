CREATE SCHEMA IF NOT EXISTS execution_authority;

CREATE TABLE IF NOT EXISTS execution_authority.schema_migrations (
  version integer PRIMARY KEY,
  checksum text NOT NULL CHECK (length(checksum) = 64),
  adapter text NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_authority.digital_employee_instances (
  namespace text NOT NULL CHECK (octet_length(namespace) BETWEEN 1 AND 128),
  security_domain text NOT NULL CHECK (octet_length(security_domain) BETWEEN 1 AND 128),
  digital_employee_instance_id text NOT NULL CHECK (octet_length(digital_employee_instance_id) BETWEEN 1 AND 200),
  definition_revision_id text NOT NULL,
  aggregate_version bigint NOT NULL CHECK (aggregate_version > 0),
  record jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, security_domain, digital_employee_instance_id)
);

CREATE TABLE IF NOT EXISTS execution_authority.agent_instances (
  namespace text NOT NULL, security_domain text NOT NULL,
  agent_instance_id text NOT NULL CHECK (octet_length(agent_instance_id) BETWEEN 1 AND 200),
  agent_revision_id text NOT NULL, runtime_instance_id text,
  aggregate_version bigint NOT NULL CHECK (aggregate_version > 0), record jsonb NOT NULL,
  PRIMARY KEY (namespace, security_domain, agent_instance_id)
);
CREATE TABLE IF NOT EXISTS execution_authority.runtime_instances (
  namespace text NOT NULL, security_domain text NOT NULL,
  runtime_instance_id text NOT NULL CHECK (octet_length(runtime_instance_id) BETWEEN 1 AND 200),
  current_generation bigint NOT NULL CHECK (current_generation > 0),
  aggregate_version bigint NOT NULL CHECK (aggregate_version > 0), record jsonb NOT NULL,
  PRIMARY KEY (namespace, security_domain, runtime_instance_id)
);
ALTER TABLE execution_authority.agent_instances DROP CONSTRAINT IF EXISTS agent_instances_runtime_fk;
ALTER TABLE execution_authority.agent_instances ADD CONSTRAINT agent_instances_runtime_fk
  FOREIGN KEY (namespace, security_domain, runtime_instance_id)
  REFERENCES execution_authority.runtime_instances(namespace, security_domain, runtime_instance_id);

CREATE TABLE IF NOT EXISTS execution_authority.assignments (
  namespace text NOT NULL, security_domain text NOT NULL, assignment_id text NOT NULL,
  digital_employee_instance_id text NOT NULL, approved_input_digest text NOT NULL CHECK (length(approved_input_digest)=64),
  record jsonb NOT NULL, PRIMARY KEY (namespace, security_domain, assignment_id),
  FOREIGN KEY (namespace, security_domain, digital_employee_instance_id)
    REFERENCES execution_authority.digital_employee_instances(namespace, security_domain, digital_employee_instance_id)
);
CREATE TABLE IF NOT EXISTS execution_authority.workflow_runs (
  namespace text NOT NULL, security_domain text NOT NULL, workflow_run_id text NOT NULL,
  assignment_id text NOT NULL, approved_plan_revision_id text NOT NULL,
  predecessor_workflow_run_id text, correction_of_workflow_run_id text, record jsonb NOT NULL,
  PRIMARY KEY (namespace, security_domain, workflow_run_id),
  FOREIGN KEY (namespace, security_domain, assignment_id) REFERENCES execution_authority.assignments(namespace, security_domain, assignment_id),
  FOREIGN KEY (namespace, security_domain, predecessor_workflow_run_id) REFERENCES execution_authority.workflow_runs(namespace, security_domain, workflow_run_id)
);
CREATE TABLE IF NOT EXISTS execution_authority.task_runs (
  namespace text NOT NULL, security_domain text NOT NULL, task_run_id text NOT NULL,
  workflow_run_id text NOT NULL, record jsonb NOT NULL,
  PRIMARY KEY (namespace, security_domain, task_run_id),
  FOREIGN KEY (namespace, security_domain, workflow_run_id) REFERENCES execution_authority.workflow_runs(namespace, security_domain, workflow_run_id)
);
CREATE TABLE IF NOT EXISTS execution_authority.attempts (
  namespace text NOT NULL, security_domain text NOT NULL, attempt_id text NOT NULL,
  task_run_id text NOT NULL, predecessor_attempt_id text, record jsonb NOT NULL,
  PRIMARY KEY (namespace, security_domain, attempt_id),
  FOREIGN KEY (namespace, security_domain, task_run_id) REFERENCES execution_authority.task_runs(namespace, security_domain, task_run_id),
  FOREIGN KEY (namespace, security_domain, predecessor_attempt_id) REFERENCES execution_authority.attempts(namespace, security_domain, attempt_id)
);

CREATE TABLE IF NOT EXISTS execution_authority.placement_requests (
  namespace text NOT NULL, security_domain text NOT NULL, request_id text NOT NULL,
  request_digest text NOT NULL CHECK (length(request_digest)=64), canonical_bytes bytea NOT NULL,
  attempt_id text NOT NULL, agent_instance_id text NOT NULL, requested_at timestamptz NOT NULL,
  PRIMARY KEY (namespace, security_domain, request_id),
  FOREIGN KEY (namespace, security_domain, attempt_id) REFERENCES execution_authority.attempts(namespace, security_domain, attempt_id),
  FOREIGN KEY (namespace, security_domain, agent_instance_id) REFERENCES execution_authority.agent_instances(namespace, security_domain, agent_instance_id)
);
CREATE TABLE IF NOT EXISTS execution_authority.placement_decisions (
  namespace text NOT NULL, security_domain text NOT NULL, placement_id text NOT NULL,
  request_id text NOT NULL, decision text NOT NULL CHECK (decision IN ('PLACED','REJECTED')),
  runtime_instance_id text, digest text NOT NULL CHECK (length(digest)=64), canonical_record jsonb NOT NULL,
  decided_at timestamptz NOT NULL, PRIMARY KEY (namespace, security_domain, placement_id),
  UNIQUE (namespace, security_domain, request_id),
  CHECK ((decision='PLACED' AND runtime_instance_id IS NOT NULL) OR (decision='REJECTED' AND runtime_instance_id IS NULL)),
  FOREIGN KEY (namespace, security_domain, request_id) REFERENCES execution_authority.placement_requests(namespace, security_domain, request_id),
  FOREIGN KEY (namespace, security_domain, runtime_instance_id) REFERENCES execution_authority.runtime_instances(namespace, security_domain, runtime_instance_id)
);

CREATE TABLE IF NOT EXISTS execution_authority.desired_commands (
  namespace text NOT NULL, security_domain text NOT NULL, command_id text NOT NULL,
  runtime_instance_id text NOT NULL, generation bigint NOT NULL CHECK (generation > 0),
  command_digest text NOT NULL CHECK (length(command_digest)=64), record jsonb NOT NULL,
  requested_at timestamptz NOT NULL, PRIMARY KEY (namespace, security_domain, command_id),
  UNIQUE (namespace, security_domain, runtime_instance_id, generation),
  FOREIGN KEY (namespace, security_domain, runtime_instance_id) REFERENCES execution_authority.runtime_instances(namespace, security_domain, runtime_instance_id)
);
CREATE TABLE IF NOT EXISTS execution_authority.command_results (
  namespace text NOT NULL, security_domain text NOT NULL, command_id text NOT NULL,
  ordinal bigint NOT NULL CHECK (ordinal > 0), result text NOT NULL CHECK (result IN ('REQUESTED','APPLIED','OBSERVED','REJECTED','UNKNOWN','STALE','RECOVERY_REQUIRED')),
  fact_digest text NOT NULL CHECK (length(fact_digest)=64), fact jsonb NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, security_domain, command_id, ordinal),
  FOREIGN KEY (namespace, security_domain, command_id) REFERENCES execution_authority.desired_commands(namespace, security_domain, command_id)
);
CREATE TABLE IF NOT EXISTS execution_authority.runtime_observations (
  storage_sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  namespace text NOT NULL, security_domain text NOT NULL, observation_id text NOT NULL,
  runtime_instance_id text NOT NULL, generation bigint NOT NULL CHECK (generation > 0),
  observation_digest text NOT NULL CHECK (length(observation_digest)=64), record jsonb NOT NULL,
  observed_at timestamptz NOT NULL, UNIQUE (namespace, security_domain, observation_id),
  FOREIGN KEY (namespace, security_domain, runtime_instance_id) REFERENCES execution_authority.runtime_instances(namespace, security_domain, runtime_instance_id)
);

CREATE TABLE IF NOT EXISTS execution_authority.execution_evidence (
  storage_sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  evidence_record_id text NOT NULL UNIQUE, schema_version integer NOT NULL CHECK (schema_version=1),
  namespace text NOT NULL, security_domain text NOT NULL, platform_execution_identity text NOT NULL,
  workflow_identity text NOT NULL, task_identity text NOT NULL, attempt_ordinal bigint NOT NULL CHECK (attempt_ordinal>0),
  event_ordinal bigint NOT NULL CHECK (event_ordinal>0), event_type text NOT NULL,
  occurred_at timestamptz NOT NULL, recorded_at timestamptz NOT NULL,
  payload_digest text NOT NULL CHECK (length(payload_digest)=64), canonical_bytes bytea NOT NULL,
  record jsonb NOT NULL, supersedes_record_id text REFERENCES execution_authority.execution_evidence(evidence_record_id)
);
CREATE INDEX IF NOT EXISTS execution_evidence_execution_idx ON execution_authority.execution_evidence(namespace,security_domain,platform_execution_identity,storage_sequence);
CREATE INDEX IF NOT EXISTS execution_evidence_subject_idx ON execution_authority.execution_evidence(namespace,security_domain,workflow_identity,task_identity,storage_sequence);

CREATE TABLE IF NOT EXISTS execution_authority.outcomes (
  namespace text NOT NULL, security_domain text NOT NULL, outcome_id text NOT NULL,
  workflow_run_id text NOT NULL, digest text NOT NULL CHECK (length(digest)=64), record jsonb NOT NULL,
  PRIMARY KEY (namespace, security_domain, outcome_id),
  FOREIGN KEY (namespace, security_domain, workflow_run_id) REFERENCES execution_authority.workflow_runs(namespace, security_domain, workflow_run_id)
);
CREATE TABLE IF NOT EXISTS execution_authority.interventions (
  storage_sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  namespace text NOT NULL, security_domain text NOT NULL, intervention_id text NOT NULL,
  runtime_instance_id text, assignment_id text, fact_digest text NOT NULL CHECK (length(fact_digest)=64), fact jsonb NOT NULL,
  UNIQUE (namespace, security_domain, intervention_id)
);

CREATE TABLE IF NOT EXISTS execution_authority.evidence_cutover (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  state text NOT NULL CHECK (state IN ('SQLITE_ACTIVE','IMPORTING','POSTGRES_ACTIVE','RECOVERY_REQUIRED','ROLLBACK_REQUIRED')),
  authoritative_writer text NOT NULL CHECK (authoritative_writer IN ('SQLITE','NONE','POSTGRES')),
  source_backup_identity text, source_backup_digest text CHECK (source_backup_digest IS NULL OR length(source_backup_digest)=64),
  last_storage_sequence bigint NOT NULL DEFAULT 0 CHECK (last_storage_sequence >= 0),
  last_record_id text, target_high_water bigint NOT NULL DEFAULT 0 CHECK (target_high_water >= 0),
  importer_version text NOT NULL, verification_status text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (NOT (state='POSTGRES_ACTIVE' AND authoritative_writer<>'POSTGRES'))
);
INSERT INTO execution_authority.evidence_cutover(singleton,state,authoritative_writer,importer_version,verification_status)
VALUES (true,'SQLITE_ACTIVE','SQLITE','v1','NOT_STARTED') ON CONFLICT (singleton) DO NOTHING;
