CREATE SCHEMA IF NOT EXISTS knowledge_attempt;
CREATE TABLE IF NOT EXISTS knowledge_attempt.schema_migrations (
  version integer PRIMARY KEY, checksum text NOT NULL CHECK(length(checksum)=64),
  adapter text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS knowledge_attempt.bindings (
  namespace text NOT NULL, security_domain text NOT NULL, binding_id text NOT NULL,
  attempt_id text NOT NULL, knowledge_id text NOT NULL,
  digest text NOT NULL CHECK(length(digest)=64), record jsonb NOT NULL,
  PRIMARY KEY(namespace,security_domain,binding_id),
  FOREIGN KEY(namespace,security_domain,attempt_id) REFERENCES execution_authority.attempts(namespace,security_domain,attempt_id),
  FOREIGN KEY(namespace,security_domain,knowledge_id) REFERENCES knowledge_operation.knowledge(namespace,security_domain,knowledge_id)
);
CREATE TABLE IF NOT EXISTS knowledge_attempt.retrieval_evidence (
  namespace text NOT NULL, security_domain text NOT NULL, evidence_id text NOT NULL,
  attempt_id text NOT NULL, binding_id text NOT NULL,
  digest text NOT NULL CHECK(length(digest)=64), record jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(namespace,security_domain,evidence_id),
  FOREIGN KEY(namespace,security_domain,attempt_id) REFERENCES execution_authority.attempts(namespace,security_domain,attempt_id),
  FOREIGN KEY(namespace,security_domain,binding_id) REFERENCES knowledge_attempt.bindings(namespace,security_domain,binding_id)
);
