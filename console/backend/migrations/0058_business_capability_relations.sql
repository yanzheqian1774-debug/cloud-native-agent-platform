-- Immutable association facts, not executable workflow bindings.
CREATE TABLE IF NOT EXISTS business_process.capability_relations (
 namespace text NOT NULL, security_domain text NOT NULL,
 relation_id text NOT NULL, relation_revision_id text NOT NULL,
 relation_version bigint NOT NULL CHECK(relation_version>0),
 relation_type text NOT NULL CHECK(relation_type IN ('SUPPORTS_ACTIVITY','DERIVED_FROM_PROCESS')),
 process_kind text NOT NULL DEFAULT 'PROCESS' CHECK(process_kind='PROCESS'),
 process_id text NOT NULL, process_revision_id text NOT NULL,
 capability_id text NOT NULL, capability_revision_id text NOT NULL,
 digest text NOT NULL CHECK(digest ~ '^[0-9a-f]{64}$'),
 record jsonb NOT NULL,
 command_id text NOT NULL, payload_digest text NOT NULL CHECK(payload_digest ~ '^[0-9a-f]{64}$'),
 actor_id text NOT NULL, decision_id text NOT NULL,
 result jsonb NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(namespace,security_domain,command_id),
 UNIQUE(namespace,security_domain,relation_id,relation_version),
 UNIQUE(namespace,security_domain,relation_id,relation_revision_id),
 FOREIGN KEY(namespace,security_domain,process_kind,process_id,process_revision_id)
 REFERENCES business_process.revisions
);
CREATE INDEX IF NOT EXISTS capability_relations_process
 ON business_process.capability_relations(namespace,security_domain,process_id,process_revision_id,relation_id,relation_version);
CREATE INDEX IF NOT EXISTS capability_relations_capability
 ON business_process.capability_relations(namespace,security_domain,capability_id,capability_revision_id,relation_id,relation_version);
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='immutable_capability_relations'
  AND tgrelid='business_process.capability_relations'::regclass) THEN
  CREATE TRIGGER immutable_capability_relations BEFORE UPDATE OR DELETE
   ON business_process.capability_relations FOR EACH ROW
   EXECUTE FUNCTION business_process.reject_rewrite();
 END IF;
END $$;
