-- Same-database batch receipts. Object owners retain their own lifecycle records.
CREATE SCHEMA IF NOT EXISTS resource_upgrade;
CREATE TABLE IF NOT EXISTS resource_upgrade.schema_migrations (
 version integer PRIMARY KEY, checksum text NOT NULL, adapter text NOT NULL
);
CREATE TABLE IF NOT EXISTS resource_upgrade.receipts (
 namespace text NOT NULL, security_domain text NOT NULL,
 actor_id text NOT NULL, command_id text NOT NULL,
 request_digest text NOT NULL CHECK(request_digest ~ '^[0-9a-f]{64}$'),
 preview_digest text NOT NULL CHECK(preview_digest ~ '^[0-9a-f]{64}$'),
 record_digest text NOT NULL CHECK(record_digest ~ '^[0-9a-f]{64}$'),
 record jsonb NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(namespace,security_domain,actor_id,command_id)
);
CREATE OR REPLACE FUNCTION resource_upgrade.reject_rewrite() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
 RAISE EXCEPTION 'RESOURCE_UPGRADE_RECEIPT_IMMUTABLE';
END $$;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='immutable_upgrade_receipts'
  AND tgrelid='resource_upgrade.receipts'::regclass) THEN
  CREATE TRIGGER immutable_upgrade_receipts BEFORE UPDATE OR DELETE ON resource_upgrade.receipts
   FOR EACH ROW EXECUTE FUNCTION resource_upgrade.reject_rewrite();
 END IF;
END $$;
