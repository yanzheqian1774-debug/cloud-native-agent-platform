-- Additive atomic Workflow Control command extension. Migrations 0008 and 0009
-- remain immutable. This migration stores relational facts that cannot be
-- represented by the original generic command row without unvalidated JSON.

CREATE TABLE IF NOT EXISTS execution_authority.intervention_reviews (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  review_id text NOT NULL,
  intervention_id text NOT NULL,
  request_transition_ordinal bigint NOT NULL DEFAULT 1 CHECK (request_transition_ordinal = 1),
  actor_id text NOT NULL,
  authority_basis text NOT NULL CHECK (octet_length(authority_basis) BETWEEN 1 AND 128),
  review_digest text NOT NULL CHECK (length(review_digest) = 64),
  reviewed_at timestamptz NOT NULL,
  PRIMARY KEY (namespace, security_domain, review_id),
  UNIQUE (namespace, security_domain, intervention_id),
  FOREIGN KEY (namespace, security_domain, intervention_id, request_transition_ordinal)
    REFERENCES execution_authority.intervention_transitions(namespace, security_domain, intervention_id, ordinal)
);

CREATE TABLE IF NOT EXISTS execution_authority.intervention_decisions (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  decision_id text NOT NULL,
  intervention_id text NOT NULL,
  review_id text NOT NULL,
  decision text NOT NULL CHECK (decision IN ('AUTHORIZE', 'REJECT')),
  actor_id text NOT NULL,
  authority_basis text NOT NULL CHECK (octet_length(authority_basis) BETWEEN 1 AND 128),
  reason_category text NOT NULL,
  decision_digest text NOT NULL CHECK (length(decision_digest) = 64),
  decided_at timestamptz NOT NULL,
  PRIMARY KEY (namespace, security_domain, decision_id),
  UNIQUE (namespace, security_domain, intervention_id),
  FOREIGN KEY (namespace, security_domain, review_id)
    REFERENCES execution_authority.intervention_reviews(namespace, security_domain, review_id),
  FOREIGN KEY (namespace, security_domain, intervention_id)
    REFERENCES execution_authority.interventions(namespace, security_domain, intervention_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS workflow_runs_one_successor_uidx
  ON execution_authority.workflow_runs(namespace, security_domain, predecessor_workflow_run_id)
  WHERE predecessor_workflow_run_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS attempts_one_successor_uidx
  ON execution_authority.attempts(namespace, security_domain, predecessor_attempt_id)
  WHERE predecessor_attempt_id IS NOT NULL;

ALTER TABLE execution_authority.control_commands
  ADD COLUMN IF NOT EXISTS placement_id text,
  ADD COLUMN IF NOT EXISTS successor_attempt_id text,
  ADD COLUMN IF NOT EXISTS result_record jsonb;
ALTER TABLE execution_authority.control_commands
  DROP CONSTRAINT IF EXISTS control_commands_placement_fk;
ALTER TABLE execution_authority.control_commands
  ADD CONSTRAINT control_commands_placement_fk
  FOREIGN KEY(namespace, security_domain, placement_id)
  REFERENCES execution_authority.placement_decisions(namespace, security_domain, placement_id);
ALTER TABLE execution_authority.control_commands
  DROP CONSTRAINT IF EXISTS control_commands_successor_attempt_fk;
ALTER TABLE execution_authority.control_commands
  ADD CONSTRAINT control_commands_successor_attempt_fk
  FOREIGN KEY(namespace, security_domain, successor_attempt_id)
  REFERENCES execution_authority.attempts(namespace, security_domain, attempt_id);

ALTER TABLE execution_authority.idempotency_claims
  ADD COLUMN IF NOT EXISTS result_record jsonb;

CREATE INDEX IF NOT EXISTS intervention_reviews_order_idx
  ON execution_authority.intervention_reviews(namespace, security_domain, intervention_id, reviewed_at, review_id);
CREATE INDEX IF NOT EXISTS intervention_decisions_order_idx
  ON execution_authority.intervention_decisions(namespace, security_domain, intervention_id, decided_at, decision_id);
