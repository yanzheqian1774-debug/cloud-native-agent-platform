CREATE SCHEMA IF NOT EXISTS governed_execution;
CREATE TABLE IF NOT EXISTS governed_execution.schema_migrations (
  version integer PRIMARY KEY,
  checksum text NOT NULL CHECK(length(checksum)=64),
  adapter text NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_authority.governed_execution_claims (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  principal_id text NOT NULL,
  idempotency_key text NOT NULL,
  request_digest text NOT NULL CHECK(length(request_digest)=64),
  workflow_run_id text NOT NULL,
  task_run_id text NOT NULL,
  attempt_id text NOT NULL,
  state text NOT NULL CHECK(state IN ('EXECUTION_CREATED')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(namespace,security_domain,principal_id,idempotency_key),
  FOREIGN KEY(namespace,security_domain,workflow_run_id)
    REFERENCES execution_authority.workflow_runs(namespace,security_domain,workflow_run_id),
  FOREIGN KEY(namespace,security_domain,task_run_id)
    REFERENCES execution_authority.task_runs(namespace,security_domain,task_run_id),
  FOREIGN KEY(namespace,security_domain,attempt_id)
    REFERENCES execution_authority.attempts(namespace,security_domain,attempt_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS governed_execution_claim_attempt_idx
  ON execution_authority.governed_execution_claims(namespace,security_domain,attempt_id);
