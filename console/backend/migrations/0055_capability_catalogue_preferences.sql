-- Personal catalogue state, never resource or execution authority.
CREATE TABLE IF NOT EXISTS business_capability.catalogue_preferences (
 namespace text NOT NULL, security_domain text NOT NULL, principal_id text NOT NULL,
 version bigint NOT NULL CHECK(version > 0),
 command_id text NOT NULL, payload_digest text NOT NULL CHECK(payload_digest ~ '^[0-9a-f]{64}$'),
 decision_id text NOT NULL, state jsonb NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(namespace,security_domain,principal_id,version),
 UNIQUE(namespace,security_domain,principal_id,command_id)
);
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='immutable_catalogue_preferences'
  AND tgrelid='business_capability.catalogue_preferences'::regclass) THEN
  CREATE TRIGGER immutable_catalogue_preferences BEFORE UPDATE OR DELETE
   ON business_capability.catalogue_preferences FOR EACH ROW
   EXECUTE FUNCTION business_capability.reject_rewrite();
 END IF;
END $$;
