-- IMPL-284: governed READ_ONLY Skill Attempt invocation authority.
DO $$ BEGIN
  IF to_regclass('resource_use.uses') IS NULL
     OR to_regclass('execution_authority.attempts') IS NULL
     OR to_regclass('skill_mcp_resource.resources') IS NULL
     OR to_regclass('digital_employee_definition.execution_bindings') IS NULL THEN
    RAISE EXCEPTION 'MIGRATION_CHAIN_0001_THROUGH_0015_REQUIRED';
  END IF;
END $$;

CREATE SCHEMA IF NOT EXISTS skill_invocation;
CREATE TABLE IF NOT EXISTS skill_invocation.schema_migrations (
  version integer PRIMARY KEY, checksum text NOT NULL CHECK(length(checksum)=64),
  adapter text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS skill_invocation.invocations (
  namespace text NOT NULL, security_domain text NOT NULL,
  skill_invocation_id text NOT NULL, idempotency_key text NOT NULL,
  payload_digest text NOT NULL CHECK(length(payload_digest)=64),
  input_digest text NOT NULL CHECK(length(input_digest)=64),
  attempt_id text NOT NULL, workflow_run_id text NOT NULL, task_run_id text NOT NULL,
  plan_id text NOT NULL, plan_version bigint NOT NULL CHECK(plan_version>0),
  plan_digest text NOT NULL, approval_id text NOT NULL, assignment_id text NOT NULL,
  digital_employee_definition_id text NOT NULL,
  digital_employee_definition_revision_id text NOT NULL,
  digital_employee_definition_digest text NOT NULL,
  digital_employee_instance_id text NOT NULL,
  agent_instance_id text, runtime_instance_id text,
  skill_id text NOT NULL, skill_revision_id text NOT NULL, skill_digest text NOT NULL,
  operation text NOT NULL, input_schema_digest text NOT NULL,
  output_schema_digest text NOT NULL, binding_id text NOT NULL,
  binding_digest text NOT NULL, executor_id text NOT NULL,
  executor_revision text NOT NULL, executor_configuration_digest text NOT NULL,
  authorization_decision_id text NOT NULL, side_effect_class text NOT NULL
    CHECK(side_effect_class='READ_ONLY'),
  policy_id text NOT NULL, policy_revision text NOT NULL, policy_digest text NOT NULL,
  io_policy_id text NOT NULL, io_policy_revision text NOT NULL, io_policy_digest text NOT NULL,
  resource_use_id text NOT NULL, exact_snapshot jsonb NOT NULL,
  created_at timestamptz NOT NULL,
  PRIMARY KEY(namespace,security_domain,skill_invocation_id),
  UNIQUE(namespace,security_domain,idempotency_key),
  UNIQUE(namespace,security_domain,attempt_id),
  FOREIGN KEY(namespace,security_domain,attempt_id) REFERENCES execution_authority.attempts,
  FOREIGN KEY(namespace,security_domain,workflow_run_id) REFERENCES execution_authority.workflow_runs,
  FOREIGN KEY(namespace,security_domain,task_run_id) REFERENCES execution_authority.task_runs,
  FOREIGN KEY(namespace,security_domain,digital_employee_instance_id)
    REFERENCES execution_authority.digital_employee_instances,
  FOREIGN KEY(namespace,security_domain,resource_use_id) REFERENCES resource_use.uses
);
CREATE TABLE IF NOT EXISTS skill_invocation.facts (
  namespace text NOT NULL, security_domain text NOT NULL, skill_invocation_id text NOT NULL,
  ordinal bigint NOT NULL CHECK(ordinal>0), fact_id text NOT NULL,
  kind text NOT NULL CHECK(kind IN ('INVOCATION_REQUESTED','DISPATCH_RECORDED',
    'INVOCATION_ACCEPTED','INVOCATION_RUNNING','INVOCATION_SUCCEEDED','INVOCATION_FAILED',
    'CANCELLATION_REQUESTED','INVOCATION_CANCELLED','OUTCOME_UNKNOWN')),
  source text NOT NULL, source_observation_id text NOT NULL, source_digest text NOT NULL,
  observed_at timestamptz NOT NULL, record jsonb NOT NULL,
  PRIMARY KEY(namespace,security_domain,skill_invocation_id,ordinal),
  UNIQUE(namespace,security_domain,fact_id),
  UNIQUE(namespace,security_domain,source,source_observation_id),
  FOREIGN KEY(namespace,security_domain,skill_invocation_id)
    REFERENCES skill_invocation.invocations
);
CREATE TABLE IF NOT EXISTS skill_invocation.evidence (
  namespace text NOT NULL, security_domain text NOT NULL, evidence_id text NOT NULL,
  skill_invocation_id text NOT NULL, evidence_digest text NOT NULL,
  redaction_profile text NOT NULL, record jsonb NOT NULL, created_at timestamptz NOT NULL,
  PRIMARY KEY(namespace,security_domain,evidence_id),
  UNIQUE(namespace,security_domain,skill_invocation_id),
  FOREIGN KEY(namespace,security_domain,skill_invocation_id)
    REFERENCES skill_invocation.invocations
);
CREATE TABLE IF NOT EXISTS skill_invocation.projections (
  namespace text NOT NULL, security_domain text NOT NULL, skill_invocation_id text NOT NULL,
  state text NOT NULL, high_water bigint NOT NULL CHECK(high_water>0),
  snapshot_digest text NOT NULL, record jsonb NOT NULL, updated_at timestamptz NOT NULL,
  PRIMARY KEY(namespace,security_domain,skill_invocation_id),
  FOREIGN KEY(namespace,security_domain,skill_invocation_id)
    REFERENCES skill_invocation.invocations
);
CREATE OR REPLACE FUNCTION skill_invocation.reject_rewrite() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'IMMUTABLE_SKILL_INVOCATION_HISTORY'; END $$;
DO $$ DECLARE name text; BEGIN
  FOREACH name IN ARRAY ARRAY['invocations','facts','evidence'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='immutable_skill_invocation_'||name
      AND tgrelid=('skill_invocation.'||name)::regclass) THEN
      EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON skill_invocation.%I FOR EACH ROW EXECUTE FUNCTION skill_invocation.reject_rewrite()', 'immutable_skill_invocation_'||name, name);
    END IF;
  END LOOP;
END $$;
