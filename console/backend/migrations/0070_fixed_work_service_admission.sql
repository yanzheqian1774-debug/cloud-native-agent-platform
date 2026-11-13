-- Append-only call preparations. No browser accounts, grants, or budget resets.
CREATE SCHEMA fixed_work_service;
CREATE TABLE fixed_work_service.schema_migrations (
 version integer PRIMARY KEY, checksum text NOT NULL, adapter text NOT NULL
);
CREATE TABLE fixed_work_service.planning_preparations (
 namespace text NOT NULL, security_domain text NOT NULL,
 subject_id text NOT NULL, credential_id text NOT NULL,
 work_id text NOT NULL, revision_id text NOT NULL, event_id text NOT NULL,
 invocation_id text NOT NULL, request_digest text NOT NULL,
 record_digest text NOT NULL, policy_digest text NOT NULL,
 expires_at timestamptz NOT NULL, record jsonb NOT NULL, context jsonb NOT NULL,
 policy jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,subject_id,work_id,event_id),
 UNIQUE(namespace,security_domain,invocation_id),
 UNIQUE(namespace,security_domain,work_id,event_id),
 FOREIGN KEY(namespace,security_domain,work_id,revision_id)
  REFERENCES fixed_work_authoring.revisions(namespace,security_domain,work_id,revision_id)
);
CREATE FUNCTION fixed_work_service.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'service call preparations are immutable'; END;
$$;
CREATE TRIGGER immutable_planning_preparations BEFORE UPDATE OR DELETE
ON fixed_work_service.planning_preparations FOR EACH ROW
EXECUTE FUNCTION fixed_work_service.reject_mutation();
