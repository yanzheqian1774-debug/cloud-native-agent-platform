CREATE SCHEMA IF NOT EXISTS fixed_work_authoring;
CREATE TABLE IF NOT EXISTS fixed_work_authoring.schema_migrations (
 version integer PRIMARY KEY, checksum text NOT NULL, adapter text NOT NULL
);
CREATE TABLE IF NOT EXISTS fixed_work_authoring.heads (
 namespace text NOT NULL, security_domain text NOT NULL, work_id text NOT NULL,
 team_id text NOT NULL, team_revision_id text NOT NULL, team_digest text NOT NULL,
 head_revision_id text NOT NULL, aggregate_version bigint NOT NULL CHECK (aggregate_version > 0),
 PRIMARY KEY(namespace,security_domain,work_id)
);
CREATE TABLE IF NOT EXISTS fixed_work_authoring.revisions (
 namespace text NOT NULL, security_domain text NOT NULL, work_id text NOT NULL,
 revision_id text NOT NULL, predecessor_revision_id text,
 digest text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,work_id,revision_id),
 UNIQUE(namespace,security_domain,work_id,predecessor_revision_id),
 FOREIGN KEY(namespace,security_domain,work_id) REFERENCES fixed_work_authoring.heads(namespace,security_domain,work_id),
 FOREIGN KEY(namespace,security_domain,work_id,predecessor_revision_id) REFERENCES fixed_work_authoring.revisions(namespace,security_domain,work_id,revision_id)
);
CREATE TABLE IF NOT EXISTS fixed_work_authoring.receipts (
 namespace text NOT NULL, security_domain text NOT NULL, actor_id text NOT NULL,
 command_id text NOT NULL, payload_digest text NOT NULL, work_id text NOT NULL,
 revision_id text NOT NULL, aggregate_version bigint NOT NULL,
 decision_id text NOT NULL, policy_digest text NOT NULL, recorded_at timestamptz NOT NULL,
 PRIMARY KEY(namespace,security_domain,actor_id,command_id),
 UNIQUE(namespace,security_domain,work_id,aggregate_version),
 FOREIGN KEY(namespace,security_domain,work_id,revision_id) REFERENCES fixed_work_authoring.revisions(namespace,security_domain,work_id,revision_id)
);
CREATE OR REPLACE FUNCTION fixed_work_authoring.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'fixed work authoring records are immutable'; END;
$$;
DROP TRIGGER IF EXISTS immutable_revisions ON fixed_work_authoring.revisions;
CREATE TRIGGER immutable_revisions BEFORE UPDATE OR DELETE ON fixed_work_authoring.revisions FOR EACH ROW EXECUTE FUNCTION fixed_work_authoring.reject_mutation();
DROP TRIGGER IF EXISTS immutable_receipts ON fixed_work_authoring.receipts;
CREATE TRIGGER immutable_receipts BEFORE UPDATE OR DELETE ON fixed_work_authoring.receipts FOR EACH ROW EXECUTE FUNCTION fixed_work_authoring.reject_mutation();
