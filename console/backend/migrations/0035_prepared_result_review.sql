-- Accepted ARCH-264 owners; immutable snapshots/results/confirmations/outcomes.
SELECT pg_advisory_xact_lock(3240035);
CREATE SCHEMA success_criteria_evaluation;
CREATE TABLE success_criteria_evaluation.schema_migrations(version integer PRIMARY KEY, checksum text NOT NULL);
CREATE TABLE success_criteria_evaluation.snapshots (
 namespace text NOT NULL, security_domain text NOT NULL, snapshot_id text NOT NULL,
 workflow_run_id text NOT NULL, digest text NOT NULL, record jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,snapshot_id),
 FOREIGN KEY(namespace,security_domain,workflow_run_id) REFERENCES execution_authority.run_preparations
);
CREATE TABLE success_criteria_evaluation.jobs (
 namespace text NOT NULL, security_domain text NOT NULL, job_id text NOT NULL,
 snapshot_id text NOT NULL, evaluator_version text NOT NULL,
 state text NOT NULL CHECK(state IN ('PENDING','RUNNING','FAILED','COMPLETED')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,job_id),
 UNIQUE(namespace,security_domain,snapshot_id,evaluator_version),
 FOREIGN KEY(namespace,security_domain,snapshot_id) REFERENCES success_criteria_evaluation.snapshots
);
CREATE TABLE success_criteria_evaluation.results (
 namespace text NOT NULL, security_domain text NOT NULL, evaluation_id text NOT NULL,
 workflow_run_id text NOT NULL, snapshot_id text NOT NULL, predecessor_id text,
 digest text NOT NULL, record jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,evaluation_id),
 UNIQUE(namespace,security_domain,predecessor_id),
 FOREIGN KEY(namespace,security_domain,workflow_run_id) REFERENCES execution_authority.run_preparations,
 FOREIGN KEY(namespace,security_domain,snapshot_id) REFERENCES success_criteria_evaluation.snapshots,
 FOREIGN KEY(namespace,security_domain,predecessor_id) REFERENCES success_criteria_evaluation.results(namespace,security_domain,evaluation_id)
);
CREATE SCHEMA human_governance;
CREATE TABLE human_governance.confirmations (
 namespace text NOT NULL, security_domain text NOT NULL, confirmation_id text NOT NULL,
 evaluation_id text NOT NULL, snapshot_id text NOT NULL, actor_id text NOT NULL,
 authority_basis text NOT NULL, decision text NOT NULL, reason text NOT NULL,
 digest text NOT NULL, record jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,confirmation_id),
 FOREIGN KEY(namespace,security_domain,evaluation_id) REFERENCES success_criteria_evaluation.results,
 FOREIGN KEY(namespace,security_domain,snapshot_id) REFERENCES success_criteria_evaluation.snapshots
);
CREATE SCHEMA product_outcome;
CREATE TABLE product_outcome.outcomes (
 namespace text NOT NULL, security_domain text NOT NULL, outcome_id text NOT NULL,
 workflow_run_id text NOT NULL, evaluation_id text NOT NULL, confirmation_id text,
 predecessor_id text, resolution text NOT NULL CHECK(resolution IN ('CONFIRMED_SOLVED','NOT_SOLVED','UNDETERMINED')),
 digest text NOT NULL, record jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,outcome_id),
 UNIQUE(namespace,security_domain,predecessor_id),
 FOREIGN KEY(namespace,security_domain,workflow_run_id) REFERENCES execution_authority.run_preparations,
 FOREIGN KEY(namespace,security_domain,evaluation_id) REFERENCES success_criteria_evaluation.results,
 FOREIGN KEY(namespace,security_domain,confirmation_id) REFERENCES human_governance.confirmations,
 FOREIGN KEY(namespace,security_domain,predecessor_id) REFERENCES product_outcome.outcomes(namespace,security_domain,outcome_id)
);
CREATE TABLE product_outcome.heads (
 namespace text NOT NULL, security_domain text NOT NULL, workflow_run_id text NOT NULL,
 version bigint NOT NULL CHECK(version>0), outcome_id text NOT NULL,
 PRIMARY KEY(namespace,security_domain,workflow_run_id),
 FOREIGN KEY(namespace,security_domain,workflow_run_id) REFERENCES execution_authority.run_preparations,
 FOREIGN KEY(namespace,security_domain,outcome_id) REFERENCES product_outcome.outcomes
);
CREATE TABLE product_outcome.commands (
 namespace text NOT NULL, security_domain text NOT NULL, actor_id text NOT NULL,
 command_key text NOT NULL, digest text NOT NULL, outcome_id text NOT NULL,
 PRIMARY KEY(namespace,security_domain,actor_id,command_key),
 FOREIGN KEY(namespace,security_domain,outcome_id) REFERENCES product_outcome.outcomes
);
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['success_criteria_evaluation.snapshots','success_criteria_evaluation.results',
 'human_governance.confirmations','product_outcome.outcomes','product_outcome.commands'] LOOP
 EXECUTE format('CREATE TRIGGER immutable_result_history BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION execution_authority.preparation_immutable()',tab);
 END LOOP;
END $$;
