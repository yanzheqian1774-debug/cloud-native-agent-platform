-- Append-only declaration publication. No execution or reference upgrade.
CREATE TABLE IF NOT EXISTS business_capability.publications (
 namespace text NOT NULL, security_domain text NOT NULL, capability_id text NOT NULL,
 revision_id text NOT NULL, revision_digest text NOT NULL CHECK(revision_digest ~ '^[0-9a-f]{64}$'),
 command_id text NOT NULL, payload_digest text NOT NULL CHECK(payload_digest ~ '^[0-9a-f]{64}$'),
 actor_id text NOT NULL, decision_id text NOT NULL,
 authority_basis text NOT NULL CHECK(authority_basis IN ('HUMAN_EXACT_REVIEW','DEVELOPMENT_ADMINISTRATOR')),
 impact_digest text NOT NULL CHECK(impact_digest ~ '^[0-9a-f]{64}$'),
 record jsonb NOT NULL, aggregate_version bigint NOT NULL CHECK(aggregate_version > 0),
 recorded_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(namespace,security_domain,command_id),
 UNIQUE(namespace,security_domain,capability_id,aggregate_version),
 UNIQUE(namespace,security_domain,capability_id,revision_id),
 FOREIGN KEY(namespace,security_domain,capability_id,revision_id) REFERENCES business_capability.revisions
);
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='immutable_publications'
  AND tgrelid='business_capability.publications'::regclass) THEN
  CREATE TRIGGER immutable_publications BEFORE UPDATE OR DELETE ON business_capability.publications
   FOR EACH ROW EXECUTE FUNCTION business_capability.reject_rewrite();
 END IF;
END $$;
