CREATE SCHEMA fixed_work_sources;
CREATE TABLE fixed_work_sources.schema_migrations(version integer PRIMARY KEY, checksum text NOT NULL, adapter text NOT NULL);
CREATE TABLE fixed_work_sources.handoffs (
 namespace text NOT NULL, security_domain text NOT NULL, work_id text NOT NULL,
 revision_id text NOT NULL, subject_id text NOT NULL, conversation_id text NOT NULL,
 command_id text NOT NULL, digest text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,work_id,revision_id),
 UNIQUE(namespace,security_domain,subject_id,command_id),
 UNIQUE(namespace,security_domain,conversation_id),
 FOREIGN KEY(namespace,security_domain,work_id,revision_id) REFERENCES fixed_work_authoring.revisions(namespace,security_domain,work_id,revision_id)
);
CREATE TABLE fixed_work_sources.bindings (
 namespace text NOT NULL, security_domain text NOT NULL, work_id text NOT NULL,
 revision_id text NOT NULL, subject_id text NOT NULL, conversation_id text NOT NULL,
 command_id text NOT NULL, digest text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,work_id,revision_id),
 UNIQUE(namespace,security_domain,subject_id,command_id),
 FOREIGN KEY(namespace,security_domain,work_id,revision_id) REFERENCES fixed_work_sources.handoffs(namespace,security_domain,work_id,revision_id)
);
CREATE TRIGGER immutable_fixed_work_handoffs BEFORE UPDATE OR DELETE ON fixed_work_sources.handoffs FOR EACH ROW EXECUTE FUNCTION fixed_work_authoring.reject_mutation();
CREATE TRIGGER immutable_fixed_work_bindings BEFORE UPDATE OR DELETE ON fixed_work_sources.bindings FOR EACH ROW EXECUTE FUNCTION fixed_work_authoring.reject_mutation();
