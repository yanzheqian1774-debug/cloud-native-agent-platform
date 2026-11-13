-- Explicit one-use adapter receipts, never a timer or independent execution owner.
CREATE SCHEMA fixed_work_triggers;
CREATE TABLE fixed_work_triggers.schema_migrations (
    version integer PRIMARY KEY, checksum text NOT NULL, adapter text NOT NULL
);
CREATE TABLE fixed_work_triggers.receipts (
    namespace text NOT NULL,
    security_domain text NOT NULL,
    actor_id text NOT NULL,
    event_id text NOT NULL,
    work_id text NOT NULL,
    revision_id text NOT NULL,
    work_digest text NOT NULL,
    preparation_digest text NOT NULL,
    payload_digest text NOT NULL,
    policy_digest text NOT NULL,
    workflow_run_id text NOT NULL,
    start_command_key text NOT NULL,
    recorded_at timestamptz NOT NULL,
    PRIMARY KEY(namespace, security_domain, actor_id, event_id),
    UNIQUE(namespace, security_domain, preparation_digest),
    FOREIGN KEY(namespace,security_domain,work_id,revision_id)
        REFERENCES fixed_work_authoring.revisions(namespace,security_domain,work_id,revision_id),
    FOREIGN KEY(namespace,security_domain,workflow_run_id)
        REFERENCES execution_authority.workflow_runs(namespace,security_domain,workflow_run_id)
);
CREATE FUNCTION fixed_work_triggers.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'fixed work trigger receipts are immutable'; END;
$$;
CREATE TRIGGER immutable_receipts BEFORE UPDATE OR DELETE ON fixed_work_triggers.receipts
FOR EACH ROW EXECUTE FUNCTION fixed_work_triggers.reject_mutation();
