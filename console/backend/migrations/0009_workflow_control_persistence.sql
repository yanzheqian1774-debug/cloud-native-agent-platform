-- Additive Workflow Control persistence. Migration 0008 remains immutable.
-- Rollback is forward-repair only after authoritative facts exist; operators must
-- stop writers and capture a verified backup/high-water before code rollback.

ALTER TABLE execution_authority.workflow_runs
  ADD COLUMN IF NOT EXISTS aggregate_version bigint NOT NULL DEFAULT 1 CHECK (aggregate_version > 0),
  ADD COLUMN IF NOT EXISTS control_state text NOT NULL DEFAULT 'LEGACY_UNBOUND',
  ADD COLUMN IF NOT EXISTS plan_id text,
  ADD COLUMN IF NOT EXISTS plan_version bigint,
  ADD COLUMN IF NOT EXISTS approved_plan_digest text;
ALTER TABLE execution_authority.workflow_runs
  DROP CONSTRAINT IF EXISTS workflow_runs_control_state_check;
ALTER TABLE execution_authority.workflow_runs ADD CONSTRAINT workflow_runs_control_state_check CHECK
  (control_state IN ('LEGACY_UNBOUND','PENDING','RUNNING','PAUSE_REQUESTED','PAUSE_PENDING','PAUSED','RESUME_REQUESTED','CANCELLATION_PENDING','SUCCEEDED','FAILED','CANCELLED','RECOVERY_REQUIRED'));
ALTER TABLE execution_authority.workflow_runs
  DROP CONSTRAINT IF EXISTS workflow_runs_plan_binding_check;
ALTER TABLE execution_authority.workflow_runs ADD CONSTRAINT workflow_runs_plan_binding_check CHECK
  ((control_state='LEGACY_UNBOUND' AND plan_id IS NULL AND plan_version IS NULL AND approved_plan_digest IS NULL)
   OR (control_state<>'LEGACY_UNBOUND' AND plan_id IS NOT NULL AND plan_version > 0 AND length(approved_plan_digest)=64));

ALTER TABLE execution_authority.task_runs
  ADD COLUMN IF NOT EXISTS aggregate_version bigint NOT NULL DEFAULT 1 CHECK (aggregate_version > 0),
  ADD COLUMN IF NOT EXISTS control_state text NOT NULL DEFAULT 'LEGACY_IMPORTED',
  ADD COLUMN IF NOT EXISTS workflow_node_id text;
ALTER TABLE execution_authority.task_runs DROP CONSTRAINT IF EXISTS task_runs_control_state_check;
ALTER TABLE execution_authority.task_runs ADD CONSTRAINT task_runs_control_state_check CHECK
  (control_state IN ('LEGACY_IMPORTED','PENDING','READY','RUNNING','BLOCKED','CANCELLATION_PENDING','SUCCEEDED','FAILED','SKIPPED','CANCELLED'));

ALTER TABLE execution_authority.attempts
  ADD COLUMN IF NOT EXISTS aggregate_version bigint NOT NULL DEFAULT 1 CHECK (aggregate_version > 0),
  ADD COLUMN IF NOT EXISTS control_state text NOT NULL DEFAULT 'RECOVERY_REQUIRED',
  ADD COLUMN IF NOT EXISTS attempt_ordinal bigint;
ALTER TABLE execution_authority.attempts DROP CONSTRAINT IF EXISTS attempts_control_state_check;
ALTER TABLE execution_authority.attempts ADD CONSTRAINT attempts_control_state_check CHECK
  (control_state IN ('PENDING','PLACED','RUNNING','CANCELLATION_PENDING','SUCCEEDED','FAILED','CANCELLED','UNKNOWN','RECOVERY_REQUIRED'));
CREATE UNIQUE INDEX IF NOT EXISTS attempts_task_ordinal_uidx
  ON execution_authority.attempts(namespace,security_domain,task_run_id,attempt_ordinal)
  WHERE attempt_ordinal IS NOT NULL;

CREATE TABLE IF NOT EXISTS execution_authority.plans (
  namespace text NOT NULL, security_domain text NOT NULL,
  plan_id text NOT NULL CHECK (octet_length(plan_id) BETWEEN 1 AND 200),
  plan_version bigint NOT NULL CHECK (plan_version > 0),
  predecessor_plan_id text, predecessor_plan_version bigint,
  workflow_definition_id text NOT NULL, workflow_definition_revision_id text NOT NULL,
  workflow_definition_digest text NOT NULL CHECK (length(workflow_definition_digest)=64),
  status text NOT NULL CHECK (status IN ('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED','CANCELLED','INVALIDATED','SUPERSEDED')),
  aggregate_version bigint NOT NULL DEFAULT 1 CHECK (aggregate_version > 0),
  plan_digest text NOT NULL CHECK (length(plan_digest)=64), canonical_bytes bytea NOT NULL,
  created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
  PRIMARY KEY(namespace,security_domain,plan_id,plan_version),
  UNIQUE(namespace,security_domain,predecessor_plan_id,predecessor_plan_version),
  CHECK ((predecessor_plan_id IS NULL)=(predecessor_plan_version IS NULL)),
  FOREIGN KEY(namespace,security_domain,predecessor_plan_id,predecessor_plan_version)
    REFERENCES execution_authority.plans(namespace,security_domain,plan_id,plan_version),
  FOREIGN KEY(namespace,security_domain,workflow_definition_id)
    REFERENCES workflow_definition.definitions(namespace,security_domain,workflow_definition_id)
);
CREATE INDEX IF NOT EXISTS plans_status_digest_idx ON execution_authority.plans(namespace,security_domain,status,plan_digest);

ALTER TABLE execution_authority.workflow_runs DROP CONSTRAINT IF EXISTS workflow_runs_plan_fk;
ALTER TABLE execution_authority.workflow_runs ADD CONSTRAINT workflow_runs_plan_fk
  FOREIGN KEY(namespace,security_domain,plan_id,plan_version)
  REFERENCES execution_authority.plans(namespace,security_domain,plan_id,plan_version);

CREATE TABLE IF NOT EXISTS execution_authority.plan_approval_decisions (
  namespace text NOT NULL, security_domain text NOT NULL, approval_decision_id text NOT NULL,
  plan_id text NOT NULL, plan_version bigint NOT NULL, plan_digest text NOT NULL CHECK(length(plan_digest)=64),
  ordinal bigint NOT NULL CHECK(ordinal>0), decision text NOT NULL CHECK(decision IN ('APPROVE','REJECT')),
  actor_id text NOT NULL, authority_basis text NOT NULL CHECK(octet_length(authority_basis) BETWEEN 1 AND 128),
  reason_category text NOT NULL CHECK(reason_category IN ('BUSINESS_APPROVAL','BUSINESS_REJECTION','POLICY_APPROVAL','POLICY_REJECTION')),
  decision_digest text NOT NULL CHECK(length(decision_digest)=64), decided_at timestamptz NOT NULL,
  PRIMARY KEY(namespace,security_domain,approval_decision_id),
  UNIQUE(namespace,security_domain,plan_id,plan_version,ordinal),
  FOREIGN KEY(namespace,security_domain,plan_id,plan_version)
    REFERENCES execution_authority.plans(namespace,security_domain,plan_id,plan_version)
);
CREATE UNIQUE INDEX IF NOT EXISTS plan_approval_effective_uidx ON execution_authority.plan_approval_decisions(namespace,security_domain,plan_id,plan_version);
CREATE INDEX IF NOT EXISTS plan_approval_order_idx ON execution_authority.plan_approval_decisions(namespace,security_domain,plan_id,plan_version,ordinal);

ALTER TABLE execution_authority.interventions
  ADD COLUMN IF NOT EXISTS workflow_run_id text,
  ADD COLUMN IF NOT EXISTS task_run_id text,
  ADD COLUMN IF NOT EXISTS attempt_id text,
  ADD COLUMN IF NOT EXISTS action_type text,
  ADD COLUMN IF NOT EXISTS reason_category text,
  ADD COLUMN IF NOT EXISTS actor_id text,
  ADD COLUMN IF NOT EXISTS authority_basis text,
  ADD COLUMN IF NOT EXISTS expected_target_version bigint,
  ADD COLUMN IF NOT EXISTS current_state text NOT NULL DEFAULT 'LEGACY_CONTEXT_ONLY',
  ADD COLUMN IF NOT EXISTS aggregate_version bigint NOT NULL DEFAULT 1 CHECK(aggregate_version>0),
  ADD COLUMN IF NOT EXISTS requested_at timestamptz;
ALTER TABLE execution_authority.interventions DROP CONSTRAINT IF EXISTS interventions_check;
ALTER TABLE execution_authority.interventions DROP CONSTRAINT IF EXISTS interventions_complete_model_check;
ALTER TABLE execution_authority.interventions ADD CONSTRAINT interventions_complete_model_check CHECK
  (current_state='LEGACY_CONTEXT_ONLY' OR (
    num_nonnulls(workflow_run_id,task_run_id,attempt_id)=1 AND
    action_type IN ('PAUSE','APPROVE_AND_CONTINUE','PROVIDE_HUMAN_INPUT','CORRECT_BUSINESS_INTENT','RESUME','RETRY_ATTEMPT','RERUN_APPROVED_PLAN','CANCEL','STOP','REQUEST_RUNTIME_REPLACEMENT') AND
    reason_category IN ('BUSINESS_REQUEST','BUSINESS_CORRECTION','HUMAN_APPROVAL','HUMAN_INPUT','OPERATIONAL_RECOVERY','POLICY','SAFETY','RUNTIME_HEALTH') AND
    actor_id IS NOT NULL AND authority_basis IS NOT NULL AND expected_target_version>0 AND requested_at IS NOT NULL AND
    current_state IN ('REQUESTED','AUTHORIZED','APPLICATION_PENDING','APPLIED','OBSERVED','REJECTED','EXPIRED','CANCELLED','FAILED')));
ALTER TABLE execution_authority.interventions DROP CONSTRAINT IF EXISTS interventions_workflow_target_fk;
ALTER TABLE execution_authority.interventions ADD CONSTRAINT interventions_workflow_target_fk FOREIGN KEY(namespace,security_domain,workflow_run_id) REFERENCES execution_authority.workflow_runs(namespace,security_domain,workflow_run_id);
ALTER TABLE execution_authority.interventions DROP CONSTRAINT IF EXISTS interventions_task_target_fk;
ALTER TABLE execution_authority.interventions ADD CONSTRAINT interventions_task_target_fk FOREIGN KEY(namespace,security_domain,task_run_id) REFERENCES execution_authority.task_runs(namespace,security_domain,task_run_id);
ALTER TABLE execution_authority.interventions DROP CONSTRAINT IF EXISTS interventions_attempt_target_fk;
ALTER TABLE execution_authority.interventions ADD CONSTRAINT interventions_attempt_target_fk FOREIGN KEY(namespace,security_domain,attempt_id) REFERENCES execution_authority.attempts(namespace,security_domain,attempt_id);

CREATE TABLE IF NOT EXISTS execution_authority.intervention_transitions (
  namespace text NOT NULL, security_domain text NOT NULL, intervention_id text NOT NULL,
  ordinal bigint NOT NULL CHECK(ordinal>0), transition_id text NOT NULL,
  from_state text, to_state text NOT NULL,
  actor_id text NOT NULL, authority_basis text NOT NULL,
  reason_category text NOT NULL, transition_digest text NOT NULL CHECK(length(transition_digest)=64),
  transitioned_at timestamptz NOT NULL,
  PRIMARY KEY(namespace,security_domain,intervention_id,ordinal),
  UNIQUE(namespace,security_domain,transition_id),
  CHECK ((ordinal=1 AND from_state IS NULL AND to_state='REQUESTED') OR ordinal>1),
  CHECK (to_state IN ('REQUESTED','AUTHORIZED','APPLICATION_PENDING','APPLIED','OBSERVED','REJECTED','EXPIRED','CANCELLED','FAILED')),
  FOREIGN KEY(namespace,security_domain,intervention_id) REFERENCES execution_authority.interventions(namespace,security_domain,intervention_id)
);
CREATE INDEX IF NOT EXISTS intervention_transition_order_idx ON execution_authority.intervention_transitions(namespace,security_domain,intervention_id,ordinal);

CREATE TABLE IF NOT EXISTS execution_authority.idempotency_claims (
  namespace text NOT NULL, security_domain text NOT NULL, actor_id text NOT NULL,
  command_type text NOT NULL, idempotency_key text NOT NULL,
  payload_digest text NOT NULL CHECK(length(payload_digest)=64),
  state text NOT NULL CHECK(state IN ('IN_PROGRESS','COMPLETED')),
  intervention_id text, control_command_id text, result_identity text,
  claimed_at timestamptz NOT NULL, completed_at timestamptz, retain_until timestamptz NOT NULL,
  PRIMARY KEY(namespace,security_domain,actor_id,command_type,idempotency_key),
  CHECK ((state='IN_PROGRESS' AND completed_at IS NULL) OR (state='COMPLETED' AND completed_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idempotency_retention_idx ON execution_authority.idempotency_claims(retain_until,state);

CREATE TABLE IF NOT EXISTS execution_authority.control_commands (
  namespace text NOT NULL, security_domain text NOT NULL, control_command_id text NOT NULL,
  command_type text NOT NULL, intervention_id text NOT NULL, transition_ordinal bigint NOT NULL,
  workflow_run_id text, task_run_id text, attempt_id text, expected_target_version bigint NOT NULL CHECK(expected_target_version>0),
  successor_plan_id text, successor_plan_version bigint, successor_workflow_run_id text, affected_attempt_id text,
  runtime_command_id text, command_digest text NOT NULL CHECK(length(command_digest)=64), canonical_record jsonb NOT NULL,
  requested_at timestamptz NOT NULL,
  PRIMARY KEY(namespace,security_domain,control_command_id),
  UNIQUE(namespace,security_domain,intervention_id,transition_ordinal),
  CHECK(num_nonnulls(workflow_run_id,task_run_id,attempt_id)=1),
  CHECK((successor_plan_id IS NULL)=(successor_plan_version IS NULL)),
  FOREIGN KEY(namespace,security_domain,intervention_id,transition_ordinal) REFERENCES execution_authority.intervention_transitions(namespace,security_domain,intervention_id,ordinal),
  FOREIGN KEY(namespace,security_domain,workflow_run_id) REFERENCES execution_authority.workflow_runs(namespace,security_domain,workflow_run_id),
  FOREIGN KEY(namespace,security_domain,task_run_id) REFERENCES execution_authority.task_runs(namespace,security_domain,task_run_id),
  FOREIGN KEY(namespace,security_domain,attempt_id) REFERENCES execution_authority.attempts(namespace,security_domain,attempt_id),
  FOREIGN KEY(namespace,security_domain,successor_plan_id,successor_plan_version) REFERENCES execution_authority.plans(namespace,security_domain,plan_id,plan_version),
  FOREIGN KEY(namespace,security_domain,successor_workflow_run_id) REFERENCES execution_authority.workflow_runs(namespace,security_domain,workflow_run_id),
  FOREIGN KEY(namespace,security_domain,affected_attempt_id) REFERENCES execution_authority.attempts(namespace,security_domain,attempt_id),
  FOREIGN KEY(namespace,security_domain,runtime_command_id) REFERENCES execution_authority.desired_commands(namespace,security_domain,command_id)
);
CREATE INDEX IF NOT EXISTS control_commands_pending_idx ON execution_authority.control_commands(namespace,security_domain,requested_at,control_command_id);

CREATE UNIQUE INDEX IF NOT EXISTS execution_evidence_scoped_uidx ON execution_authority.execution_evidence(namespace,security_domain,evidence_record_id);
CREATE TABLE IF NOT EXISTS execution_authority.intervention_evidence_links (
  namespace text NOT NULL, security_domain text NOT NULL, intervention_id text NOT NULL,
  transition_ordinal bigint NOT NULL, ordinal bigint NOT NULL CHECK(ordinal>0), evidence_record_id text NOT NULL,
  PRIMARY KEY(namespace,security_domain,intervention_id,transition_ordinal,ordinal),
  FOREIGN KEY(namespace,security_domain,intervention_id,transition_ordinal) REFERENCES execution_authority.intervention_transitions(namespace,security_domain,intervention_id,ordinal),
  FOREIGN KEY(namespace,security_domain,evidence_record_id) REFERENCES execution_authority.execution_evidence(namespace,security_domain,evidence_record_id)
);
CREATE INDEX IF NOT EXISTS intervention_evidence_traversal_idx ON execution_authority.intervention_evidence_links(namespace,security_domain,intervention_id,transition_ordinal,ordinal);
CREATE TABLE IF NOT EXISTS execution_authority.intervention_outcome_links (
  namespace text NOT NULL, security_domain text NOT NULL, intervention_id text NOT NULL,
  transition_ordinal bigint NOT NULL, ordinal bigint NOT NULL CHECK(ordinal>0), outcome_id text NOT NULL,
  PRIMARY KEY(namespace,security_domain,intervention_id,transition_ordinal,ordinal),
  FOREIGN KEY(namespace,security_domain,intervention_id,transition_ordinal) REFERENCES execution_authority.intervention_transitions(namespace,security_domain,intervention_id,ordinal),
  FOREIGN KEY(namespace,security_domain,outcome_id) REFERENCES execution_authority.outcomes(namespace,security_domain,outcome_id)
);
CREATE INDEX IF NOT EXISTS intervention_outcome_traversal_idx ON execution_authority.intervention_outcome_links(namespace,security_domain,intervention_id,transition_ordinal,ordinal);
