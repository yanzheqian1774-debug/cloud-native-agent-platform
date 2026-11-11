-- Publication fixes a business definition; it never authorizes execution.
CREATE TABLE IF NOT EXISTS business_process.publications (
 namespace text NOT NULL, security_domain text NOT NULL,
 kind text NOT NULL DEFAULT 'PROCESS' CHECK(kind='PROCESS'),
 object_id text NOT NULL, revision_id text NOT NULL,
 revision_digest text NOT NULL CHECK(revision_digest ~ '^[0-9a-f]{64}$'),
 command_id text NOT NULL, payload_digest text NOT NULL CHECK(payload_digest ~ '^[0-9a-f]{64}$'),
 actor_id text NOT NULL, decision_id text NOT NULL,
 publication_version bigint NOT NULL CHECK(publication_version > 0),
 content_version bigint NOT NULL CHECK(content_version > 0),
 result jsonb NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(namespace,security_domain,command_id),
 UNIQUE(namespace,security_domain,object_id,publication_version),
 UNIQUE(namespace,security_domain,object_id,revision_id),
 FOREIGN KEY(namespace,security_domain,kind,object_id,revision_id)
 REFERENCES business_process.revisions
);
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='immutable_publications'
  AND tgrelid='business_process.publications'::regclass) THEN
  CREATE TRIGGER immutable_publications BEFORE UPDATE OR DELETE ON business_process.publications
   FOR EACH ROW EXECUTE FUNCTION business_process.reject_rewrite();
 END IF;
END $$;
