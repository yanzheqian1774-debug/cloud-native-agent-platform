CREATE TABLE IF NOT EXISTS business_process.relation_withdrawals (
 namespace text NOT NULL, security_domain text NOT NULL,
 relation_id text NOT NULL, relation_revision_id text NOT NULL,
 command_id text NOT NULL, payload_digest text NOT NULL,
 actor_id text NOT NULL, decision_id text NOT NULL,
 reason text NOT NULL CHECK(length(btrim(reason)) BETWEEN 1 AND 2000),
 result jsonb NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(namespace,security_domain,command_id),
 UNIQUE(namespace,security_domain,relation_id),
 FOREIGN KEY(namespace,security_domain,relation_id,relation_revision_id)
 REFERENCES business_process.capability_relations(namespace,security_domain,relation_id,relation_revision_id)
);
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='immutable_relation_withdrawals'
 AND tgrelid='business_process.relation_withdrawals'::regclass) THEN
 CREATE TRIGGER immutable_relation_withdrawals BEFORE UPDATE OR DELETE
 ON business_process.relation_withdrawals FOR EACH ROW EXECUTE FUNCTION business_process.reject_rewrite();
 END IF;
END $$;
