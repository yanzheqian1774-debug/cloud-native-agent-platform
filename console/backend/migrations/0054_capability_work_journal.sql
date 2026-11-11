-- UI continuation only; domain owners remain authoritative.
CREATE TABLE IF NOT EXISTS private_conversation.schema_migrations (
 version integer PRIMARY KEY, checksum text NOT NULL,
 applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS private_conversation.capability_work_journal (
 tenant_id text NOT NULL, security_domain text NOT NULL, conversation_id text NOT NULL,
 source_message_id text NOT NULL, version bigint NOT NULL CHECK(version > 0),
 contract_digest text NOT NULL CHECK(contract_digest ~ '^[0-9a-f]{64}$'),
 state jsonb NOT NULL CHECK(jsonb_typeof(state) = 'object'),
 command_id text NOT NULL, payload_digest text NOT NULL CHECK(payload_digest ~ '^[0-9a-f]{64}$'),
 actor_id text NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,security_domain,conversation_id,source_message_id,version),
 UNIQUE(tenant_id,security_domain,conversation_id,source_message_id,command_id),
 FOREIGN KEY(tenant_id,security_domain,conversation_id,source_message_id)
 REFERENCES private_conversation.messages(tenant_id,security_domain,conversation_id,message_id)
);
CREATE OR REPLACE FUNCTION private_conversation.reject_journal_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'CAPABILITY_JOURNAL_IMMUTABLE'; END $$;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='immutable_capability_work_journal'
  AND tgrelid='private_conversation.capability_work_journal'::regclass) THEN
  CREATE TRIGGER immutable_capability_work_journal BEFORE UPDATE OR DELETE
   ON private_conversation.capability_work_journal FOR EACH ROW
   EXECUTE FUNCTION private_conversation.reject_journal_rewrite();
 END IF;
END $$;
