CREATE SCHEMA fixed_work_successions;
CREATE TABLE fixed_work_successions.schema_migrations (
 version integer PRIMARY KEY, checksum text NOT NULL, adapter text NOT NULL
);
CREATE TABLE fixed_work_successions.transitions (
 namespace text NOT NULL, security_domain text NOT NULL,
 logical_work_id text NOT NULL, ordinal bigint NOT NULL CHECK (ordinal > 0),
 subject_id text NOT NULL, conversation_id text NOT NULL,
 predecessor_work_id text NOT NULL, predecessor_revision_id text NOT NULL,
 work_id text NOT NULL, revision_id text NOT NULL,
 command_id text NOT NULL, payload_digest text NOT NULL,
 digest text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,logical_work_id,ordinal),
 UNIQUE(namespace,security_domain,subject_id,command_id),
 UNIQUE(namespace,security_domain,predecessor_work_id,predecessor_revision_id),
 UNIQUE(namespace,security_domain,work_id,revision_id),
 UNIQUE(namespace,security_domain,conversation_id,ordinal),
 FOREIGN KEY(namespace,security_domain,predecessor_work_id,predecessor_revision_id)
  REFERENCES fixed_work_authoring.revisions(namespace,security_domain,work_id,revision_id),
 FOREIGN KEY(namespace,security_domain,work_id,revision_id)
  REFERENCES fixed_work_authoring.revisions(namespace,security_domain,work_id,revision_id)
);
CREATE TABLE fixed_work_successions.bindings (
 namespace text NOT NULL, security_domain text NOT NULL,
 work_id text NOT NULL, revision_id text NOT NULL,
 subject_id text NOT NULL, conversation_id text NOT NULL,
 command_id text NOT NULL, digest text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,work_id,revision_id),
 UNIQUE(namespace,security_domain,subject_id,command_id),
 FOREIGN KEY(namespace,security_domain,work_id,revision_id)
  REFERENCES fixed_work_successions.transitions(namespace,security_domain,work_id,revision_id)
);
CREATE TRIGGER immutable_fixed_work_successions BEFORE UPDATE OR DELETE ON fixed_work_successions.transitions
 FOR EACH ROW EXECUTE FUNCTION fixed_work_authoring.reject_mutation();
CREATE TRIGGER immutable_fixed_work_successor_bindings BEFORE UPDATE OR DELETE ON fixed_work_successions.bindings
 FOR EACH ROW EXECUTE FUNCTION fixed_work_authoring.reject_mutation();
