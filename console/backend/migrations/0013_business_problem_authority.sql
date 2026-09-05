CREATE SCHEMA IF NOT EXISTS business_problem_authority;
CREATE TABLE business_problem_authority.schema_migrations (
  version integer PRIMARY KEY, checksum text NOT NULL CHECK(length(checksum)=64),
  adapter text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE business_problem_authority.problems (
  namespace text NOT NULL, security_domain text NOT NULL, business_problem_id text NOT NULL,
  owner_id text NOT NULL, current_state text NOT NULL CHECK(current_state IN ('DRAFT','ACTIVE','IN_PROGRESS','RESOLVED','CLOSED')),
  aggregate_version bigint NOT NULL CHECK(aggregate_version > 0), current_revision_id text NOT NULL,
  created_by text NOT NULL, created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
  PRIMARY KEY(namespace,security_domain,business_problem_id)
);
CREATE TABLE business_problem_authority.problem_revisions (
  namespace text NOT NULL, security_domain text NOT NULL, business_problem_id text NOT NULL,
  revision_id text NOT NULL, revision bigint NOT NULL CHECK(revision > 0), predecessor_revision_id text,
  digest text NOT NULL CHECK(length(digest)=64), canonical_bytes bytea NOT NULL,
  title text NOT NULL, description text NOT NULL, owner_id text NOT NULL, created_by text NOT NULL, created_at timestamptz NOT NULL,
  PRIMARY KEY(namespace,security_domain,revision_id),
  UNIQUE(namespace,security_domain,business_problem_id,revision),
  UNIQUE(namespace,security_domain,business_problem_id,digest),
  FOREIGN KEY(namespace,security_domain,business_problem_id) REFERENCES business_problem_authority.problems(namespace,security_domain,business_problem_id),
  FOREIGN KEY(namespace,security_domain,predecessor_revision_id) REFERENCES business_problem_authority.problem_revisions(namespace,security_domain,revision_id)
);
ALTER TABLE business_problem_authority.problems ADD CONSTRAINT problems_current_revision_fk
  FOREIGN KEY(namespace,security_domain,current_revision_id) REFERENCES business_problem_authority.problem_revisions(namespace,security_domain,revision_id)
  DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE business_problem_authority.lifecycle_events (
  namespace text NOT NULL, security_domain text NOT NULL, event_id text NOT NULL, business_problem_id text NOT NULL,
  ordinal bigint NOT NULL CHECK(ordinal > 0), event_type text NOT NULL CHECK(event_type IN ('INITIAL','TRANSITION','REOPENED')), from_state text, to_state text NOT NULL,
  actor_id text NOT NULL, event_digest text NOT NULL CHECK(length(event_digest)=64), occurred_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(namespace,security_domain,event_id), UNIQUE(namespace,security_domain,business_problem_id,ordinal),
  FOREIGN KEY(namespace,security_domain,business_problem_id) REFERENCES business_problem_authority.problems(namespace,security_domain,business_problem_id)
);
CREATE TABLE business_problem_authority.criteria (
  namespace text NOT NULL, security_domain text NOT NULL, success_criterion_id text NOT NULL,
  aggregate_version bigint NOT NULL CHECK(aggregate_version > 0), current_revision_id text NOT NULL,
  PRIMARY KEY(namespace,security_domain,success_criterion_id)
);
CREATE TABLE business_problem_authority.criterion_revisions (
  namespace text NOT NULL, security_domain text NOT NULL, success_criterion_id text NOT NULL,
  revision_id text NOT NULL, revision bigint NOT NULL CHECK(revision > 0), predecessor_revision_id text,
  criterion_type text NOT NULL CHECK(criterion_type IN ('DETERMINISTIC_BOOLEAN','NUMERIC_THRESHOLD','CATEGORICAL_RESULT','EVIDENCE_PRESENCE','HUMAN_EVALUATED','NOT_MEASURABLE')),
  measurement jsonb NOT NULL, required_evidence_kinds jsonb NOT NULL, evaluator_type text NOT NULL, evaluator_version text NOT NULL,
  applicability jsonb NOT NULL, digest text NOT NULL CHECK(length(digest)=64), canonical_bytes bytea NOT NULL,
  created_by text NOT NULL, created_at timestamptz NOT NULL,
  PRIMARY KEY(namespace,security_domain,revision_id), UNIQUE(namespace,security_domain,success_criterion_id,revision),
  FOREIGN KEY(namespace,security_domain,success_criterion_id) REFERENCES business_problem_authority.criteria(namespace,security_domain,success_criterion_id),
  FOREIGN KEY(namespace,security_domain,predecessor_revision_id) REFERENCES business_problem_authority.criterion_revisions(namespace,security_domain,revision_id)
);
ALTER TABLE business_problem_authority.criteria ADD CONSTRAINT criteria_current_revision_fk
  FOREIGN KEY(namespace,security_domain,current_revision_id) REFERENCES business_problem_authority.criterion_revisions(namespace,security_domain,revision_id)
  DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE business_problem_authority.criteria_sets (
  namespace text NOT NULL, security_domain text NOT NULL, set_revision_id text NOT NULL,
  business_problem_id text NOT NULL, problem_revision_id text NOT NULL, revision bigint NOT NULL CHECK(revision > 0), predecessor_set_revision_id text,
  digest text NOT NULL CHECK(length(digest)=64), canonical_bytes bytea NOT NULL, created_by text NOT NULL, created_at timestamptz NOT NULL,
  PRIMARY KEY(namespace,security_domain,set_revision_id), UNIQUE(namespace,security_domain,business_problem_id,revision),
  UNIQUE(namespace,security_domain,business_problem_id,set_revision_id),
  FOREIGN KEY(namespace,security_domain,business_problem_id) REFERENCES business_problem_authority.problems(namespace,security_domain,business_problem_id),
  FOREIGN KEY(namespace,security_domain,problem_revision_id) REFERENCES business_problem_authority.problem_revisions(namespace,security_domain,revision_id),
  FOREIGN KEY(namespace,security_domain,business_problem_id,predecessor_set_revision_id) REFERENCES business_problem_authority.criteria_sets(namespace,security_domain,business_problem_id,set_revision_id)
);
CREATE TABLE business_problem_authority.criteria_set_members (
  namespace text NOT NULL, security_domain text NOT NULL, set_revision_id text NOT NULL, ordinal bigint NOT NULL CHECK(ordinal > 0), criterion_revision_id text NOT NULL,
  PRIMARY KEY(namespace,security_domain,set_revision_id,ordinal), UNIQUE(namespace,security_domain,set_revision_id,criterion_revision_id),
  FOREIGN KEY(namespace,security_domain,set_revision_id) REFERENCES business_problem_authority.criteria_sets(namespace,security_domain,set_revision_id),
  FOREIGN KEY(namespace,security_domain,criterion_revision_id) REFERENCES business_problem_authority.criterion_revisions(namespace,security_domain,revision_id)
);
CREATE TABLE business_problem_authority.plan_bindings (
  namespace text NOT NULL, security_domain text NOT NULL, binding_id text NOT NULL,
  plan_id text NOT NULL, plan_version bigint NOT NULL, plan_digest text NOT NULL CHECK(length(plan_digest)=64),
  business_problem_id text NOT NULL, problem_revision_id text NOT NULL, problem_revision_digest text NOT NULL CHECK(length(problem_revision_digest)=64),
  criteria_set_revision_id text NOT NULL, criteria_set_digest text NOT NULL CHECK(length(criteria_set_digest)=64),
  actor_id text NOT NULL, digest text NOT NULL CHECK(length(digest)=64), canonical_bytes bytea NOT NULL, created_at timestamptz NOT NULL,
  PRIMARY KEY(namespace,security_domain,binding_id), UNIQUE(namespace,security_domain,plan_id,plan_version),
  FOREIGN KEY(namespace,security_domain,plan_id,plan_version) REFERENCES execution_authority.plans(namespace,security_domain,plan_id,plan_version),
  FOREIGN KEY(namespace,security_domain,business_problem_id) REFERENCES business_problem_authority.problems(namespace,security_domain,business_problem_id),
  FOREIGN KEY(namespace,security_domain,problem_revision_id) REFERENCES business_problem_authority.problem_revisions(namespace,security_domain,revision_id),
  FOREIGN KEY(namespace,security_domain,business_problem_id,criteria_set_revision_id) REFERENCES business_problem_authority.criteria_sets(namespace,security_domain,business_problem_id,set_revision_id)
);
CREATE TABLE business_problem_authority.idempotency_claims (
  namespace text NOT NULL, security_domain text NOT NULL, actor_id text NOT NULL, command_type text NOT NULL, idempotency_key text NOT NULL,
  payload_digest text NOT NULL CHECK(length(payload_digest)=64), result_kind text NOT NULL, result_id text NOT NULL, result_record jsonb NOT NULL,
  completed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(namespace,security_domain,actor_id,command_type,idempotency_key)
);
CREATE INDEX problems_visible_idx ON business_problem_authority.problems(namespace,security_domain,updated_at,business_problem_id);
