-- Complete the Workflow Control application persistence contract without
-- rewriting migrations 0008-0010 or any pre-existing immutable fact.

ALTER TABLE execution_authority.plans
  ADD COLUMN IF NOT EXISTS source_plan_revision bigint,
  ADD COLUMN IF NOT EXISTS source_plan_digest text,
  ADD COLUMN IF NOT EXISTS actor_id text,
  ADD COLUMN IF NOT EXISTS authority_classification text,
  ADD COLUMN IF NOT EXISTS correction_reason_category text;
ALTER TABLE execution_authority.plans
  DROP CONSTRAINT IF EXISTS plans_successor_metadata_check;
ALTER TABLE execution_authority.plans
  ADD CONSTRAINT plans_successor_metadata_check CHECK (
    predecessor_plan_id IS NULL OR (
      source_plan_revision IS NOT NULL AND source_plan_revision > 0 AND
      source_plan_digest IS NOT NULL AND length(source_plan_digest) = 64 AND
      actor_id IS NOT NULL AND octet_length(actor_id) BETWEEN 1 AND 128 AND
      authority_classification IN ('BUSINESS_OWNER','AUTHORIZED_OPERATOR','POLICY_AUTHORITY') AND
      correction_reason_category IN ('BUSINESS_CORRECTION','DEPENDENCY_CORRECTION','POLICY_CORRECTION','SAFETY_CORRECTION')
    )
  );

CREATE TABLE IF NOT EXISTS execution_authority.plan_corrections (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  correction_id text NOT NULL,
  predecessor_plan_id text NOT NULL,
  predecessor_plan_version bigint NOT NULL,
  successor_plan_id text NOT NULL,
  successor_plan_version bigint NOT NULL,
  actor_id text NOT NULL,
  authority_classification text NOT NULL CHECK (authority_classification IN ('BUSINESS_OWNER','AUTHORIZED_OPERATOR','POLICY_AUTHORITY')),
  reason_category text NOT NULL CHECK (reason_category IN ('BUSINESS_CORRECTION','DEPENDENCY_CORRECTION','POLICY_CORRECTION','SAFETY_CORRECTION')),
  correction_digest text NOT NULL CHECK (length(correction_digest) = 64),
  normalized_correction jsonb NOT NULL,
  corrected_at timestamptz NOT NULL,
  PRIMARY KEY (namespace, security_domain, correction_id),
  UNIQUE (namespace, security_domain, predecessor_plan_id, predecessor_plan_version),
  UNIQUE (namespace, security_domain, successor_plan_id, successor_plan_version),
  FOREIGN KEY (namespace, security_domain, predecessor_plan_id, predecessor_plan_version)
    REFERENCES execution_authority.plans(namespace, security_domain, plan_id, plan_version),
  FOREIGN KEY (namespace, security_domain, successor_plan_id, successor_plan_version)
    REFERENCES execution_authority.plans(namespace, security_domain, plan_id, plan_version)
);

ALTER TABLE execution_authority.control_commands
  DROP CONSTRAINT IF EXISTS control_commands_namespace_security_domain_intervention_id_trans_key,
  DROP CONSTRAINT IF EXISTS control_commands_namespace_security_domain_intervention_id__key;
CREATE INDEX IF NOT EXISTS control_commands_transition_idx
  ON execution_authority.control_commands(namespace, security_domain, intervention_id, transition_ordinal, requested_at, control_command_id);

ALTER TABLE execution_authority.intervention_evidence_links
  ADD COLUMN IF NOT EXISTS control_command_id text;
UPDATE execution_authority.intervention_evidence_links l
SET control_command_id = c.control_command_id
FROM execution_authority.control_commands c
WHERE l.control_command_id IS NULL
  AND c.namespace=l.namespace AND c.security_domain=l.security_domain
  AND c.intervention_id=l.intervention_id AND c.transition_ordinal=l.transition_ordinal;
ALTER TABLE execution_authority.intervention_evidence_links
  ALTER COLUMN control_command_id SET NOT NULL,
  DROP CONSTRAINT IF EXISTS intervention_evidence_links_pkey,
  DROP CONSTRAINT IF EXISTS intervention_evidence_links_command_fk;
ALTER TABLE execution_authority.intervention_evidence_links
  ADD CONSTRAINT intervention_evidence_links_pkey PRIMARY KEY(namespace,security_domain,control_command_id,ordinal),
  ADD CONSTRAINT intervention_evidence_links_command_fk FOREIGN KEY(namespace,security_domain,control_command_id)
    REFERENCES execution_authority.control_commands(namespace,security_domain,control_command_id);

ALTER TABLE execution_authority.intervention_outcome_links
  ADD COLUMN IF NOT EXISTS control_command_id text;
UPDATE execution_authority.intervention_outcome_links l
SET control_command_id = c.control_command_id
FROM execution_authority.control_commands c
WHERE l.control_command_id IS NULL
  AND c.namespace=l.namespace AND c.security_domain=l.security_domain
  AND c.intervention_id=l.intervention_id AND c.transition_ordinal=l.transition_ordinal;
ALTER TABLE execution_authority.intervention_outcome_links
  ALTER COLUMN control_command_id SET NOT NULL,
  DROP CONSTRAINT IF EXISTS intervention_outcome_links_pkey,
  DROP CONSTRAINT IF EXISTS intervention_outcome_links_command_fk;
ALTER TABLE execution_authority.intervention_outcome_links
  ADD CONSTRAINT intervention_outcome_links_pkey PRIMARY KEY(namespace,security_domain,control_command_id,ordinal),
  ADD CONSTRAINT intervention_outcome_links_command_fk FOREIGN KEY(namespace,security_domain,control_command_id)
    REFERENCES execution_authority.control_commands(namespace,security_domain,control_command_id);

ALTER TABLE execution_authority.outcomes
  ADD COLUMN IF NOT EXISTS task_run_id text,
  ADD COLUMN IF NOT EXISTS attempt_id text,
  ADD COLUMN IF NOT EXISTS terminal_target_kind text,
  ADD COLUMN IF NOT EXISTS terminal_target_id text,
  ADD COLUMN IF NOT EXISTS terminal_state text;
ALTER TABLE execution_authority.outcomes
  DROP CONSTRAINT IF EXISTS outcomes_terminal_binding_check,
  DROP CONSTRAINT IF EXISTS outcomes_task_run_fk,
  DROP CONSTRAINT IF EXISTS outcomes_attempt_fk;
ALTER TABLE execution_authority.outcomes
  ADD CONSTRAINT outcomes_terminal_binding_check CHECK (
    terminal_target_kind IS NULL OR (
      terminal_target_kind IN ('RUN','TASK_RUN','ATTEMPT') AND
      terminal_target_id IS NOT NULL AND
      terminal_state IN ('SUCCEEDED','FAILED','SKIPPED','CANCELLED') AND
      ((terminal_target_kind='RUN' AND terminal_target_id=workflow_run_id AND task_run_id IS NULL AND attempt_id IS NULL) OR
       (terminal_target_kind='TASK_RUN' AND terminal_target_id=task_run_id AND task_run_id IS NOT NULL AND attempt_id IS NULL) OR
       (terminal_target_kind='ATTEMPT' AND terminal_target_id=attempt_id AND attempt_id IS NOT NULL))
    )
  );
ALTER TABLE execution_authority.outcomes
  ADD CONSTRAINT outcomes_task_run_fk FOREIGN KEY(namespace, security_domain, task_run_id)
    REFERENCES execution_authority.task_runs(namespace, security_domain, task_run_id),
  ADD CONSTRAINT outcomes_attempt_fk FOREIGN KEY(namespace, security_domain, attempt_id)
    REFERENCES execution_authority.attempts(namespace, security_domain, attempt_id);

CREATE INDEX IF NOT EXISTS outcomes_terminal_target_idx
  ON execution_authority.outcomes(namespace, security_domain, terminal_target_kind, terminal_target_id);
