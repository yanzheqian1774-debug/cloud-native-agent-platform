-- Additive planning v2 in the existing Workflow Control owner.
CREATE SCHEMA IF NOT EXISTS workflow_planning;
CREATE TABLE IF NOT EXISTS workflow_planning.schema_migrations (
  version integer PRIMARY KEY, checksum text NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_planning.proposals (
  namespace text NOT NULL, security_domain text NOT NULL,
  proposal_id text NOT NULL, revision integer NOT NULL CHECK (revision > 0),
  digest text NOT NULL, record jsonb NOT NULL,
  PRIMARY KEY(namespace, security_domain, proposal_id, revision)
);
CREATE TABLE IF NOT EXISTS workflow_planning.plans (
  namespace text NOT NULL, security_domain text NOT NULL,
  plan_id text NOT NULL, version integer NOT NULL CHECK (version > 0),
  proposal_id text NOT NULL, proposal_revision integer NOT NULL,
  digest text NOT NULL, record jsonb NOT NULL,
  PRIMARY KEY(namespace, security_domain, plan_id, version),
  UNIQUE(namespace, security_domain, proposal_id, proposal_revision),
  FOREIGN KEY(namespace, security_domain, proposal_id, proposal_revision)
    REFERENCES workflow_planning.proposals(namespace, security_domain, proposal_id, revision)
);
CREATE TABLE IF NOT EXISTS workflow_planning.approvals (
  namespace text NOT NULL, security_domain text NOT NULL,
  plan_id text NOT NULL, version integer NOT NULL,
  decision_id text NOT NULL, record jsonb NOT NULL,
  PRIMARY KEY(namespace, security_domain, plan_id, version),
  UNIQUE(namespace, security_domain, decision_id),
  FOREIGN KEY(namespace, security_domain, plan_id, version)
    REFERENCES workflow_planning.plans(namespace, security_domain, plan_id, version)
);
CREATE TABLE IF NOT EXISTS workflow_planning.commands (
  namespace text NOT NULL, security_domain text NOT NULL,
  actor_id text NOT NULL, command_key text NOT NULL,
  payload_digest text NOT NULL, result jsonb NOT NULL,
  PRIMARY KEY(namespace, security_domain, actor_id, command_key)
);
CREATE TABLE IF NOT EXISTS workflow_planning.resource_snapshots (
  namespace text NOT NULL, security_domain text NOT NULL,
  snapshot_id text NOT NULL, proposal_id text NOT NULL, revision integer NOT NULL,
  record jsonb NOT NULL,
  PRIMARY KEY(namespace, security_domain, snapshot_id),
  FOREIGN KEY(namespace, security_domain, proposal_id, revision)
    REFERENCES workflow_planning.proposals(namespace, security_domain, proposal_id, revision)
);
CREATE OR REPLACE FUNCTION workflow_planning.immutable_record()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'PLANNING_IMMUTABLE';
END $$;
DO $$ DECLARE tab text; BEGIN
  FOREACH tab IN ARRAY ARRAY['proposals','plans','approvals','commands','resource_snapshots']
  LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'planning_immutable_' || tab) THEN
      EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON workflow_planning.%I FOR EACH ROW EXECUTE FUNCTION workflow_planning.immutable_record()', 'planning_immutable_' || tab, tab);
    END IF;
  END LOOP;
END $$;
