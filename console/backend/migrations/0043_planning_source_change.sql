-- D10: additive immutable request/provenance on the existing planning owner.
CREATE TABLE IF NOT EXISTS workflow_planning.source_changes (
 namespace text NOT NULL, security_domain text NOT NULL,
 request_id text NOT NULL, actor_id text NOT NULL, request_key text NOT NULL,
 payload_digest text NOT NULL, record jsonb NOT NULL,
 proposal_id text NOT NULL, successor_revision integer,
 PRIMARY KEY(namespace,security_domain,request_id),
 UNIQUE(namespace,security_domain,actor_id,request_key),
 FOREIGN KEY(namespace,security_domain,proposal_id,successor_revision)
 REFERENCES workflow_planning.proposals(namespace,security_domain,proposal_id,revision)
);
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='planning_immutable_source_changes') THEN
  CREATE TRIGGER planning_immutable_source_changes BEFORE UPDATE OR DELETE
  ON workflow_planning.source_changes FOR EACH ROW
  EXECUTE FUNCTION workflow_planning.immutable_record();
 END IF;
END $$;
