-- IMPL-282: additive Attempt Resource Use and measurement authority.
CREATE SCHEMA IF NOT EXISTS resource_use;
CREATE TABLE IF NOT EXISTS resource_use.schema_migrations (
  version integer PRIMARY KEY, checksum text NOT NULL CHECK(length(checksum)=64),
  adapter text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS resource_use.uses (
  namespace text NOT NULL, security_domain text NOT NULL,
  resource_use_id text NOT NULL, attempt_id text NOT NULL,
  resource_kind text NOT NULL CHECK(resource_kind IN ('SKILL','MCP','KNOWLEDGE','WORKFLOW','RUNTIME','DIGITAL_EMPLOYEE')),
  slot_key text NOT NULL, occurrence_ordinal integer NOT NULL CHECK(occurrence_ordinal=1),
  resource_id text NOT NULL, resource_revision_id text NOT NULL, resource_digest text NOT NULL,
  binding_id text NOT NULL, binding_digest text NOT NULL,
  plan_id text NOT NULL, plan_version bigint NOT NULL CHECK(plan_version>0), plan_digest text NOT NULL,
  workflow_run_id text NOT NULL, task_run_id text NOT NULL,
  digital_employee_definition_id text NOT NULL,
  digital_employee_definition_revision_id text NOT NULL,
  digital_employee_definition_digest text NOT NULL,
  digital_employee_instance_id text NOT NULL,
  agent_instance_id text, runtime_instance_id text,
  executor_id text, executor_revision text, provider_id text, provider_revision text,
  authorization_decision_id text NOT NULL,
  predecessor_attempt_id text, predecessor_workflow_run_id text,
  payload_digest text NOT NULL CHECK(length(payload_digest)=64), record jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(namespace,security_domain,resource_use_id),
  UNIQUE(namespace,security_domain,attempt_id,resource_kind,slot_key,occurrence_ordinal),
  FOREIGN KEY(namespace,security_domain,attempt_id) REFERENCES execution_authority.attempts,
  FOREIGN KEY(namespace,security_domain,workflow_run_id) REFERENCES execution_authority.workflow_runs,
  FOREIGN KEY(namespace,security_domain,task_run_id) REFERENCES execution_authority.task_runs,
  FOREIGN KEY(namespace,security_domain,digital_employee_instance_id)
    REFERENCES execution_authority.digital_employee_instances,
  FOREIGN KEY(namespace,security_domain,plan_id,plan_version)
    REFERENCES execution_authority.plans,
  FOREIGN KEY(namespace,security_domain,attempt_id)
    REFERENCES digital_employee_definition.execution_bindings,
  FOREIGN KEY(namespace,security_domain,agent_instance_id)
    REFERENCES execution_authority.agent_instances,
  FOREIGN KEY(namespace,security_domain,runtime_instance_id)
    REFERENCES execution_authority.runtime_instances
);
CREATE TABLE IF NOT EXISTS resource_use.facts (
  namespace text NOT NULL, security_domain text NOT NULL,
  resource_use_id text NOT NULL, ordinal bigint NOT NULL CHECK(ordinal>0), fact_id text NOT NULL,
  kind text NOT NULL, source_owner text NOT NULL, source_observation_id text NOT NULL,
  source_digest text NOT NULL, observed_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL, supersedes_fact_id text,
  record jsonb NOT NULL,
  PRIMARY KEY(namespace,security_domain,resource_use_id,ordinal),
  UNIQUE(namespace,security_domain,fact_id),
  UNIQUE(namespace,security_domain,source_owner,source_observation_id),
  FOREIGN KEY(namespace,security_domain,resource_use_id) REFERENCES resource_use.uses
);
CREATE TABLE IF NOT EXISTS resource_use.measurements (
  namespace text NOT NULL, security_domain text NOT NULL,
  resource_use_id text NOT NULL, measurement_id text NOT NULL,
  metric text NOT NULL, value double precision, unit text NOT NULL,
  availability text NOT NULL CHECK(availability IN ('MEASURED','NOT_COLLECTED','NOT_MEASURABLE','ESTIMATED','STALE','CONFLICTED')),
  source_identity text NOT NULL, source_digest text NOT NULL,
  window_started_at timestamptz NOT NULL, window_ended_at timestamptz NOT NULL,
  observed_at timestamptz NOT NULL, record jsonb NOT NULL,
  PRIMARY KEY(namespace,security_domain,measurement_id),
  FOREIGN KEY(namespace,security_domain,resource_use_id) REFERENCES resource_use.uses,
  CHECK((availability='MEASURED' AND value IS NOT NULL AND value>=0) OR
        (availability<>'MEASURED' AND value IS NULL)),
  CHECK(window_started_at<=window_ended_at)
);
CREATE TABLE IF NOT EXISTS resource_use.evidence_references (
  namespace text NOT NULL, security_domain text NOT NULL,
  resource_use_id text NOT NULL, evidence_id text NOT NULL, evidence_digest text NOT NULL,
  evidence_kind text NOT NULL, record jsonb NOT NULL,
  PRIMARY KEY(namespace,security_domain,resource_use_id,evidence_id),
  FOREIGN KEY(namespace,security_domain,resource_use_id) REFERENCES resource_use.uses
);
CREATE TABLE IF NOT EXISTS resource_use.claims (
  namespace text NOT NULL, security_domain text NOT NULL,
  resource_use_id text NOT NULL, claim_id text NOT NULL, claim_digest text NOT NULL,
  record jsonb NOT NULL,
  PRIMARY KEY(namespace,security_domain,resource_use_id,claim_id),
  FOREIGN KEY(namespace,security_domain,resource_use_id) REFERENCES resource_use.uses
);
CREATE TABLE IF NOT EXISTS resource_use.high_waters (
  namespace text NOT NULL, security_domain text NOT NULL,
  resource_use_id text NOT NULL, high_water bigint NOT NULL CHECK(high_water>0), version bigint NOT NULL CHECK(version>0),
  PRIMARY KEY(namespace,security_domain,resource_use_id),
  FOREIGN KEY(namespace,security_domain,resource_use_id) REFERENCES resource_use.uses
);
CREATE TABLE IF NOT EXISTS resource_use.snapshots (
  namespace text NOT NULL, security_domain text NOT NULL,
  resource_use_id text NOT NULL, snapshot_id text NOT NULL, digest text NOT NULL,
  high_water bigint NOT NULL, reducer_version text NOT NULL, record jsonb NOT NULL,
  created_at timestamptz NOT NULL,
  PRIMARY KEY(namespace,security_domain,snapshot_id),
  UNIQUE(namespace,security_domain,resource_use_id,high_water),
  FOREIGN KEY(namespace,security_domain,resource_use_id) REFERENCES resource_use.uses
);
CREATE TABLE IF NOT EXISTS resource_use.idempotency (
  namespace text NOT NULL, security_domain text NOT NULL,
  idempotency_key text NOT NULL, payload_digest text NOT NULL,
  resource_use_id text NOT NULL, snapshot_id text NOT NULL,
  PRIMARY KEY(namespace,security_domain,idempotency_key),
  FOREIGN KEY(namespace,security_domain,resource_use_id) REFERENCES resource_use.uses
);
CREATE OR REPLACE FUNCTION resource_use.reject_rewrite() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'IMMUTABLE_RESOURCE_USE_HISTORY'; END $$;
DO $$ DECLARE name text; BEGIN
  FOREACH name IN ARRAY ARRAY['uses','facts','measurements','evidence_references','claims','snapshots','idempotency'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='immutable_resource_use_'||name
        AND tgrelid=('resource_use.'||name)::regclass) THEN
      EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON resource_use.%I FOR EACH ROW EXECUTE FUNCTION resource_use.reject_rewrite()', 'immutable_resource_use_'||name, name);
    END IF;
  END LOOP;
END $$;
